"""
bot_sheets.py — Bot da Planilha

Funções: Conectar com API do Google Sheets, ler as vagas coletadas, 
comparar com a planilha e registrar apenas as vagas inéditas.
"""

import json
import os
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

# ──────────────────────────────────────────────
# CONFIGURAÇÕES INICIAIS
# ──────────────────────────────────────────────

load_dotenv()

# Caminhos e constantes
SPREADSHEET_ID   = os.getenv("SPREADSHEET_ID")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_FILE = os.path.join(BASE_DIR, "credentials.json")
INPUT_FILE       = os.path.join(BASE_DIR, "vagas_temp.json")
NOME_ABA         = "vagas"

# Escopos de acesso da planilha
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Colunas da planilha
COLUNAS = [
    "titulo",
    "empresa",
    "localizacao",
    "categoria",
    "modalidade",
    "salario",
    "data_publicacao",
    "link",
    "data_registrado",
    "notificado",
]


# ──────────────────────────────────────────────
# FUNÇÕES
# ──────────────────────────────────────────────

def conectar_sheets():
    # Verifica as crendenciais e conecta com a planilha online.

    credenciais = Credentials.from_service_account_file(
        CREDENTIALS_FILE,
        scopes=SCOPES
    )
    cliente = gspread.authorize(credenciais)
    planilha = cliente.open_by_key(SPREADSHEET_ID)
    aba = planilha.worksheet(NOME_ABA)
    print(f"[OK] Conectado à planilha '{NOME_ABA}' com sucesso.")
    return aba


def carregar_vagas_temp():
    # Lê o arquivo .json de vagas e retorna a lista de vagas e a categoria.

    if not os.path.exists(INPUT_FILE):
        print(f"[ERRO] Arquivo '{INPUT_FILE}' não encontrado.")
        print("       Execute bot_scraper.py antes de rodar este bot.")
        exit(1)

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        dados = json.load(f)

    vagas    = dados.get("vagas", [])
    categoria = dados.get("categoria", "")
    coletado = dados.get("coletado_em", "")

    print(f"[INFO] {len(vagas)} vaga(s) carregada(s) de '{INPUT_FILE}'")
    print(f"[INFO] Categoria: {categoria} | Coletado em: {coletado}")
    return vagas, categoria


def obter_links_registrados(aba):
    # Verifica todos os links registrados na planilha.

    indice_link = COLUNAS.index("link") + 1
    valores = aba.col_values(indice_link)
    links_registrados = set(valores[1:])

    print(f"[INFO] {len(links_registrados)} vaga(s) já registrada(s) na planilha.")
    return links_registrados


def filtrar_vagas_novas(vagas, links_registrados):
    # Compara as vagas coletadas com os links já na planilha e retorna apenas as vagas inéditas.

    novas = [v for v in vagas if v.get("link") not in links_registrados]
    print(f"[INFO] {len(novas)} vaga(s) nova(s) identificada(s) para inserção.")
    return novas


def montar_linha(vaga):
    # Monta uma linha no formato esperado pela planilha.
  
    agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    return [
        vaga.get("titulo",          ""),
        vaga.get("empresa",         ""),
        vaga.get("localizacao",     ""),
        vaga.get("categoria",       ""),
        vaga.get("modalidade",      ""),
        vaga.get("salario",         ""),
        vaga.get("data_publicacao", ""),
        vaga.get("link",            ""),
        agora,    # data_registrado
        "NÃO",    # notificado
    ]


def inserir_vagas_novas(aba, vagas_novas):
    # Insere as vagas novas na planilha e exibe progresso no terminal.

    if not vagas_novas:
        print("[INFO] Nenhuma vaga nova para inserir. Planilha já está atualizada.")
        return

    print(f"\n[INFO] Inserindo {len(vagas_novas)} vaga(s) na planilha...")

    for i, vaga in enumerate(vagas_novas, start=1):
        linha = montar_linha(vaga)
        aba.append_row(linha, value_input_option="USER_ENTERED")
        print(f"  [{i}/{len(vagas_novas)}] ✓ {vaga.get('titulo', 'Sem título')} — {vaga.get('empresa', '')}")

    print(f"\n[OK] {len(vagas_novas)} vaga(s) inserida(s) com sucesso.")


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────

def main():
    print("=" * 50)
    print("  Estágio Monitor — Bot Sheets")
    print("=" * 50)

    # Valida a crendencial da planilha
    if not SPREADSHEET_ID:
        print("[ERRO] Variável SPREADSHEET_ID não encontrada no .env")
        exit(1)

    # Carrega as vagas coletadas
    vagas, categoria = carregar_vagas_temp()

    # Conecta a planilha
    aba = conectar_sheets()

    # Obtém os links já registrados para comparação
    links_registrados = obter_links_registrados(aba)

    # Filtra apenas as vagas inéditas
    vagas_novas = filtrar_vagas_novas(vagas, links_registrados)

    # Insere as vagas novas na planilha
    inserir_vagas_novas(aba, vagas_novas)

    print("\n[CONCLUÍDO] bot_sheets.py finalizado com sucesso.")
    print("=" * 50)


if __name__ == "__main__":
    main()