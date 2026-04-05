"""
bot_telegram.py — Bot Comunicador
Funções:

  Parte 1. Modo Configuração:
     Fica esperando o usuário enviar /start e exibe uma enquete com as categorias.
     Ao receber a resposta, salva a preferência num .json.

  Parte 2. Modo Notificação:
     Lê a planilha online, busca vagas não notificadas,
     envia mensagem formatada no Telegram e marca como a vaga como notificada.

Como usar:
  python bot_telegram.py                # Modo Configuração
  python bot_telegram.py --notificar    # Modo Notificação (via Cron)
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timedelta

import gspread
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from telegram import Bot, Poll, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    PollAnswerHandler,
)

# ──────────────────────────────────────────────
# CONFIGURAÇÕES INICIAIS
# ──────────────────────────────────────────────

load_dotenv()

# Caminhos e constantes
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
SPREADSHEET_ID   = os.getenv("SPREADSHEET_ID")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_FILE = os.path.join(BASE_DIR, "credentials.json")
PREFS_FILE       = os.path.join(BASE_DIR, "user_prefs.json")
NOME_ABA         = "vagas"

# Escopos de acesso da planilha
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Limite máximo de vagas enviadas
LIMITE_VAGAS_POR_ENVIO = 5

# Horários de execução e margem de tempo do cron
HORAS_CRON = [0, 6, 12, 18]
MARGEM_CRON_MINUTOS = 10

# Categorias disponíveis
CATEGORIAS = [
    "💻 Tecnologia",
    "🏥 Saúde",
    "📊 Administração",
    "📣 Comunicação",
    "🏗️ Engenharia",
    "🔧 Técnico",
    "🎓 Educação",
    "⚖️ Direito/Outros",
]

# Mapeamento das categorias
CATEGORIAS_MAPA = {
    "💻 Tecnologia":    "Tecnologia",
    "🏥 Saúde":         "Saúde",
    "📊 Administração": "Administração",
    "📣 Comunicação":   "Comunicação",
    "🏗️ Engenharia":    "Engenharia",
    "🔧 Técnico":       "Técnico",
    "🎓 Educação":      "Educação",
    "⚖️ Direito/Outros":"Direito/Outros",
}

# Configura o logging do terminal
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Armazena a resposta da enquete
poll_id_ativo = {}


# ──────────────────────────────────────────────
# MODO CONFIGURAÇÃO
# ──────────────────────────────────────────────

async def comando_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Envia uma mensagem de boas-vindas e uma enquete com as categorias.

    chat_id = update.effective_chat.id

    await update.message.reply_text(
        "👋 Olá! Bem-vindo ao *Estágio Monitor*!\n\n"
        "Vou te notificar sobre novas vagas de estágio no portal IEL Amazonas "
        "de acordo com a sua área de interesse.\n\n"
        "📋 Selecione sua categoria na enquete abaixo:",
        parse_mode="Markdown"
    )

    # Envia a enquete com as categorias disponíveis
    mensagem_poll = await context.bot.send_poll(
        chat_id=chat_id,
        question="🎯 Qual é a sua área de interesse?",
        options=CATEGORIAS,
        is_anonymous=False,   
        allows_multiple_answers=False,
    )

    # Salva o poll_id para identificar a resposta
    poll_id_ativo[mensagem_poll.poll.id] = chat_id
    logger.info(f"Enquete enviada para chat_id={chat_id} | poll_id={mensagem_poll.poll.id}")


async def receber_resposta_enquete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Salva a categoria escolhida em .json e confirma ao usuário.

    resposta = update.poll_answer

    # Verifica se esta enquete foi registrada por este bot
    if resposta.poll_id not in poll_id_ativo:
        return

    chat_id = poll_id_ativo[resposta.poll_id]

    # Obtém o índice da opção escolhida e mapeia a categoria
    indice_escolhido = resposta.option_ids[0]
    categoria_com_emoji = CATEGORIAS[indice_escolhido]
    categoria_salva = CATEGORIAS_MAPA[categoria_com_emoji]

    # Salva a preferência do usuário
    prefs = {
        "chat_id":   str(chat_id),
        "categoria": categoria_salva,
        "atualizado_em": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
    }

    with open(PREFS_FILE, "w", encoding="utf-8") as f:
        json.dump(prefs, f, ensure_ascii=False, indent=2)

    logger.info(f"Preferência salva: chat_id={chat_id} | categoria={categoria_salva}")

    # Verifica quanto tempo falta para o próximo ciclo do cron
    minutos_faltando, proximo_cron = minutos_para_proximo_cron()
    hora_formatada = proximo_cron.strftime("%H:%M")

    if minutos_faltando <= MARGEM_CRON_MINUTOS:
        # Próximo ciclo está muito perto — avisa o usuário para aguardar
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                f"✅ Preferência salva com sucesso!\n\n"
                f"📂 Sua categoria: *{categoria_com_emoji}*\n\n"
                f"⏰ O próximo ciclo automático começa em *{minutos_faltando} minuto(s)* "
                f"(às *{hora_formatada}*). Suas vagas chegarão em breve!\n\n"
                f"💡 Para trocar de categoria, envie /start novamente."
            ),
            parse_mode="Markdown"
        )
    else:
        # Ciclo ainda está longe — dispara imediatamente
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                f"✅ Preferência salva com sucesso!\n\n"
                f"📂 Sua categoria: *{categoria_com_emoji}*\n\n"
                f"🔍 Buscando vagas para você agora... Aguarde alguns instantes!"
            ),
            parse_mode="Markdown"
        )

        # Dispara o ciclo completo
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, disparar_ciclo_inicial)

    del poll_id_ativo[resposta.poll_id]


# ──────────────────────────────────────────────
# CICLO INICIAL
# ──────────────────────────────────────────────

def minutos_para_proximo_cron():
    # Calcula quantos minutos faltam para o próximo ciclo do cron.

    agora = datetime.now()
    proximos = []

    for hora in HORAS_CRON:
        candidato = agora.replace(hour=hora, minute=0, second=0, microsecond=0)
        if candidato <= agora:
            candidato += timedelta(days=1)
        proximos.append(candidato)

    proximo = min(proximos)
    diferenca = (proximo - agora).total_seconds() / 60
    return int(diferenca), proximo


def disparar_ciclo_inicial():
    # Executa os 3 bots em sequência como o cron faria.

    python = sys.executable
    base   = os.path.dirname(os.path.abspath(__file__))

    logger.info("Disparando ciclo inicial...")
    subprocess.run([python, os.path.join(base, "bot_scraper.py")])
    subprocess.run([python, os.path.join(base, "bot_sheets.py")])
    subprocess.run([python, os.path.join(base, "bot_telegram.py"), "--notificar"])
    logger.info("Ciclo inicial concluído.")


# ──────────────────────────────────────────────
# MODO NOTIFICAÇÃO
# ──────────────────────────────────────────────

def conectar_sheets():
    # Verifica as crendenciais e conecta com a planilha online.

    credenciais = Credentials.from_service_account_file(
        CREDENTIALS_FILE,
        scopes=SCOPES
    )
    cliente = gspread.authorize(credenciais)
    planilha = cliente.open_by_key(SPREADSHEET_ID)
    return planilha.worksheet(NOME_ABA)


def buscar_vagas_nao_notificadas(aba):
    # Lê todas as linhas da planilha e retorna as vagas não notificadas.

    todos_registros = aba.get_all_records()
    vagas_pendentes = []

    for i, registro in enumerate(todos_registros, start=2):  
        if registro.get("notificado", "").strip().upper() == "NÃO":
            vagas_pendentes.append({
                "linha_planilha": i,
                "dados": registro,
            })

    logger.info(f"{len(vagas_pendentes)} vaga(s) pendente(s) de notificação.")
    return vagas_pendentes


def formatar_mensagem(vaga):
    # Formata os dados de uma vaga em uma mensagem para o Telegram.

    dados = vaga["dados"]

    titulo      = dados.get("titulo",          "Não informado")
    empresa     = dados.get("empresa",         "Não informado")
    localizacao = dados.get("localizacao",     "Não informado")
    modalidade  = dados.get("modalidade",      "Não informado")
    salario     = dados.get("salario",         "Não informado")
    data_pub    = dados.get("data_publicacao", "Não informado")
    link        = dados.get("link",            "")

    return (
        f"🎓 *Nova vaga de estágio!*\n\n"
        f"💼 *Cargo:* {titulo}\n"
        f"🏢 *Empresa:* {empresa}\n"
        f"📍 *Local:* {localizacao}\n"
        f"📂 *Modalidade:* {modalidade}\n"
        f"💰 *Salário:* {salario}\n"
        f"📅 *Publicado em:* {data_pub}\n\n"
        f"🔗 [Ver vaga]({link})"
    )


def marcar_como_notificado(aba, linha):
    # Atualiza a coluna 'notificado' de uma linha específica para 'SIM'.

    col_notificado = 10
    aba.update_cell(linha, col_notificado, "SIM")


# ──────────────────────────────────────────────
# ORGANIZADOR DA MENSAGEM ("MAIN" DO MODO NOTIF.)
# ──────────────────────────────────────────────

async def enviar_notificacoes():
    # Função importante: Lê vagas não notificadas, envia mensagens no Telegram e atualiza a planilha.
  
    print("=" * 50)
    print("  Estágio Monitor — Bot Telegram (Modo Notificação)")
    print("=" * 50)

    # Valida variáveis de ambiente
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID or not SPREADSHEET_ID:
        print("[ERRO] Variáveis de ambiente incompletas. Verifique o .env")
        sys.exit(1)

    # Carrega preferências do usuário
    if not os.path.exists(PREFS_FILE):
        print("[ERRO] user_prefs.json não encontrado. Execute /start no Telegram primeiro.")
        sys.exit(1)

    with open(PREFS_FILE, "r", encoding="utf-8") as f:
        prefs = json.load(f)

    chat_id = prefs.get("chat_id", TELEGRAM_CHAT_ID)

    # Conecta à planilha
    print("[INFO] Conectando ao Google Sheets...")
    aba = conectar_sheets()

    # Busca vagas não notificadas
    vagas_pendentes = buscar_vagas_nao_notificadas(aba)

    if not vagas_pendentes:
        print("[INFO] Nenhuma vaga nova para notificar.")
        print("[CONCLUÍDO] bot_telegram.py (notificação) finalizado.")
        return

    # Inicia o bot do Telegram para envio
    bot = Bot(token=TELEGRAM_TOKEN)

    total_pendentes = len(vagas_pendentes)
    vagas_para_enviar = vagas_pendentes[:LIMITE_VAGAS_POR_ENVIO]
    restantes = total_pendentes - len(vagas_para_enviar)

    print(f"[INFO] {total_pendentes} vaga(s) pendente(s). Enviando {len(vagas_para_enviar)} agora...")

    for i, vaga in enumerate(vagas_para_enviar, start=1):
        try:
            mensagem = formatar_mensagem(vaga)

            await bot.send_message(
                chat_id=chat_id,
                text=mensagem,
                parse_mode="Markdown",
                disable_web_page_preview=False,
            )

            # Marca como notificado na planilha
            marcar_como_notificado(aba, vaga["linha_planilha"])

            print(f"  [{i}/{len(vagas_para_enviar)}] ✓ Enviado: {vaga['dados'].get('titulo', '')}")

            await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"Erro ao enviar vaga {i}: {e}")
            continue

    # Avisa o usuário se ainda houver vagas na fila
    if restantes > 0:
        await bot.send_message(
            chat_id=chat_id,
            text=(
                f"📋 Há mais *{restantes} vaga(s)* disponíveis na sua fila.\n"
                f"Você receberá as próximas na próxima execução automática. 😊"
            ),
            parse_mode="Markdown",
        )
        print(f"[INFO] {restantes} vaga(s) restante(s) aguardando próxima execução.")

    print(f"\n[OK] {len(vagas_para_enviar)} notificação(ões) enviada(s) com sucesso.")
    print("[CONCLUÍDO] bot_telegram.py (notificação) finalizado.")
    print("=" * 50)


# ──────────────────────────────────────────────
# INICIALIZAÇÃO DO BOT ("MAIN" DO MODO CONFIG.)
# ──────────────────────────────────────────────

def iniciar_modo_configuracao():

    # Inicia o bot, aguarda comando /start e respostas de enquete do usuário.

    print("=" * 50)
    print("  Estágio Monitor — Bot Telegram (Modo Configuração)")
    print("=" * 50)

    if not TELEGRAM_TOKEN:
        print("[ERRO] TELEGRAM_TOKEN não encontrado no .env")
        sys.exit(1)

    print("[INFO] Bot iniciado. Aguardando /start no Telegram...")
    print("[INFO] Pressione Ctrl+C para encerrar.\n")

    # Cria e configura a aplicação do bot
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", comando_start))
    app.add_handler(PollAnswerHandler(receber_resposta_enquete))

    # Inicia a escuta de mensagens
    app.run_polling()


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────

if __name__ == "__main__":
    # Verifica o argumento passado na linha de comando
    if "--notificar" in sys.argv:
        # Modo Notificação
        asyncio.run(enviar_notificacoes())
    else:
        # Modo Configuração
        iniciar_modo_configuracao()