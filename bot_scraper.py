"""
bot_scraper.py — Bot Raspador

Funções: Ler a categoria escolhida do usuário, coletar as vagas correspondentes no portal IEL/AM
realizar uma curadoria das vagas e salvar os resultados em vagas_temp.json.
"""

import json
import os
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# ──────────────────────────────────────────────
# CONFIGURAÇÕES INICIAIS
# ──────────────────────────────────────────────

# Categorias e suas palavras-chave
CATEGORIAS = {
    "Tecnologia":     ["sistemas", "desenvolvimento", "computação", "informática"],
    "Saúde":          ["enfermagem", "nutrição", "farmácia", "biomedicina"],
    "Administração":  ["administração", "gestão", "recursos humanos", "contabilidade", "economia"],
    "Comunicação":    ["marketing", "publicidade", "design", "jornalismo", "comunicação"],
    "Engenharia":     ["engenharia", "civil", "elétrica", "produção"],
    "Técnico":        ["técnico", "segurança", "análises", "eletrotécnica", "edificações"],
    "Educação":       ["pedagogia", "matemática", "física", "química", "educação física"],
    "Direito/Outros": ["direito", "turismo", "serviço social"],
}

# Endereço do site
BASE_URL = "https://carreiras.iel.org.br/AM"

# Caminhos dos arquivos
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PREFS_FILE  = os.path.join(BASE_DIR, "user_prefs.json")
OUTPUT_FILE = os.path.join(BASE_DIR, "vagas_temp.json")

# Limite máximo de páginas
LIMITE_PAGINAS = 2

# Período de validade da vagas
VALIDADE_DIAS = 60


# ──────────────────────────────────────────────
# FUNÇÕES
# ──────────────────────────────────────────────

def carregar_preferencias():
    # Lê o arquivo .json e retorna a categoria escolhida pelo usuário.

    if not os.path.exists(PREFS_FILE):
        print("[ERRO] Arquivo user_prefs.json não encontrado.")
        print("       Inicie o bot do Telegram com /start para definir sua categoria.")
        exit(1)

    with open(PREFS_FILE, "r", encoding="utf-8") as f:
        prefs = json.load(f)

    categoria = prefs.get("categoria")
    if not categoria or categoria not in CATEGORIAS:
        print(f"[ERRO] Categoria '{categoria}' inválida ou não encontrada.")
        exit(1)

    print(f"[INFO] Categoria do usuário: {categoria}")
    return categoria


def extrair_vagas_da_pagina(page):
    # Extrai todas as vaga visíveis na página atual e retorna uma lista de dicionários com os dados de cada vaga.

    vagas = []
    cards = page.query_selector_all("a[href*='/vaga/']")

    for card in cards:
        try:
            # Link da vaga
            link = card.get_attribute("href")
            if not link:
                continue
            if link.startswith("/"):
                link = f"https://carreiras.iel.org.br{link}"
            if "/jovem-aprendiz/" in link:
                continue

            # Tipo da vaga
            tipo_el = card.query_selector("h1.text-customColorDarkGreen")
            tipo = tipo_el.inner_text().strip() if tipo_el else ""
            if "stágio" not in tipo:
                continue

            # Data de publicação
            data_el = card.query_selector("h1.text-customColorMediumGray")
            data_publicacao = data_el.inner_text().strip() if data_el else ""

            # Título da vaga
            titulo_el = card.query_selector("span.font-bold")
            titulo = titulo_el.inner_text().strip() if titulo_el else ""

            # Empresa
            empresa_el = card.query_selector("span.text-customColorMediumGray")
            empresa = empresa_el.inner_text().strip() if empresa_el else ""

            # Localização, Modalidade e Salário
            info_els = card.query_selector_all("div.text-customColorVacancyGray")
            localizacao = info_els[0].inner_text().strip() if len(info_els) > 0 else ""
            modalidade  = info_els[1].inner_text().strip() if len(info_els) > 1 else ""
            salario     = info_els[2].inner_text().strip() if len(info_els) > 2 else ""
            
            if not titulo:
                continue

            vagas.append({
                "titulo":          titulo,
                "empresa":         empresa,
                "localizacao":     localizacao,
                "modalidade":      modalidade,
                "salario":         salario,
                "data_publicacao": data_publicacao,
                "link":            link,
            })

        except Exception as e:
            print(f"[AVISO] Erro ao extrair card: {e}")
            continue

    return vagas


def aguardar_cards(page):
    # Espera os cards de vaga carregarem e aparecerem na página.

    try:
        page.wait_for_selector("a[href*='/vaga/']", timeout=8000)
    except PlaywrightTimeoutError:
        pass


def proxima_pagina_disponivel(page):
    # Verifica se o botão de próxima página está disponível e clicável.

    try:
        botao = page.locator("li.next > a[aria-label='Next page']").first

        # Verifica se o botão existe
        if botao.count() == 0:
            return False

        # Verifica se está desabilitado
        aria_disabled = botao.get_attribute("aria-disabled") or "false"
        if aria_disabled == "true":
            return False

        botao.click()
        page.wait_for_timeout(1500)
        aguardar_cards(page)

        return True

    except Exception:
        return False


def buscar_vagas_por_palavra(page, palavra_chave):
    # Acessa o portal, pesquisa pela palavra-chave, percorre todas as páginas e retorna as vagas encontradas.


    print(f"  → Buscando por: '{palavra_chave}'")
    vagas_encontradas = []

    # Navega até o portal
    page.goto(BASE_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(2000) 

    # Localiza o campo de busca e digita as palavras chaves
    campo_busca = page.locator("#search-vacancy").first
    campo_busca.fill("")
    campo_busca.type(palavra_chave, delay=80)

    # Aguarda o resultado das buscas
    page.wait_for_timeout(1500)
    aguardar_cards(page)

    pagina_atual = 1

    while True:
        print(f"     Página {pagina_atual}...")

        # Extrai as vagas da página atual
        vagas_pagina = extrair_vagas_da_pagina(page)
        vagas_encontradas.extend(vagas_pagina)
        print(f"     {len(vagas_pagina)} vaga(s) nesta página")

        # Respeita o limite máximo de páginas
        if pagina_atual >= LIMITE_PAGINAS:
            print(f"     Limite de {LIMITE_PAGINAS} página(s) atingido.")
            break

        # Tenta avançar para a próxima página
        if not proxima_pagina_disponivel(page):
            break 

        pagina_atual += 1

    print(f"     Total para '{palavra_chave}': {len(vagas_encontradas)} vaga(s)")
    return vagas_encontradas


def vaga_valida(data_publicacao):
    # Verifica se a vaga está dentro do prazo de validade.

    if not data_publicacao:
        return True 

    try:
        data = datetime.strptime(data_publicacao, "%d/%m/%Y")
        limite = datetime.now() - timedelta(days=VALIDADE_DIAS)
        return data >= limite
    except ValueError:
        return True
    

def complementar_dados_vaga(page, vaga):
    # Acessa a página individual da vaga para buscar título e empresa completos

    titulo_truncado  = "..." in vaga.get("titulo", "")
    empresa_truncada = "..." in vaga.get("empresa", "")

    if not titulo_truncado and not empresa_truncada:
        return vaga

    try:
        page.goto(vaga["link"], wait_until="domcontentloaded")
        page.wait_for_timeout(1500)

        # Título completo
        if titulo_truncado:
            titulo_el = page.query_selector("h1")
            if titulo_el:
                vaga["titulo"] = titulo_el.inner_text().strip()

        # Empresa completa
        if empresa_truncada:
            empresa_el = page.query_selector("div.text-customColorVacancyGray > div")
            if empresa_el:
                vaga["empresa"] = empresa_el.inner_text().strip()

        print(f"     ✓ Dados complementados: {vaga['titulo'][:50]}")

    except Exception as e:
        print(f"[AVISO] Não foi possível complementar dados de '{vaga['link']}': {e}")

    return vaga


def deduplicar(vagas):
    # Remove vagas duplicadas com base no link.

    vistas = set()
    unicas = []
    for vaga in vagas:
        if vaga["link"] not in vistas:
            vistas.add(vaga["link"])
            unicas.append(vaga)
    return unicas


def salvar_resultado(vagas, categoria):
    # Salva as vagas coletadas em vagas_temp.json.

    payload = {
        "categoria":   categoria,
        "coletado_em": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "total":       len(vagas),
        "vagas":       vagas,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"\n[OK] {len(vagas)} vaga(s) salva(s) em '{OUTPUT_FILE}'")


def esta_no_docker():
 # Detecta se o bot está rodando dentro de um container Docker.

    return os.path.exists("/.dockerenv")


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────

def main():
    print("=" * 50)
    print("  Estágio Monitor — Bot Scraper")
    print("=" * 50)

    # Carrega a categoria escolhida pelo usuário
    categoria = carregar_preferencias()
    palavras_chave = CATEGORIAS[categoria]

    todas_vagas = []

    with sync_playwright() as p:
        # Detecta o ambiente e ajusta o headless automaticamente (headless=False → fora do Docker   headless=True  → dentro do Docker)
        modo_headless = esta_no_docker()
        if modo_headless:
            print("[INFO] Ambiente Docker detectado — rodando em modo headless.")
        else:
            print("[INFO] Ambiente local detectado — navegador visível.")

        # Inicia o navegador
        browser = p.chromium.launch(
            headless=modo_headless,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        page = browser.new_page(viewport={"width": 1280, "height": 800})

        print(f"\n[INFO] Iniciando busca com {len(palavras_chave)} palavra(s)-chave...\n")

        # Busca vagas para cada palavra-chave da categoria
        for palavra in palavras_chave:
            vagas = buscar_vagas_por_palavra(page, palavra)
            todas_vagas.extend(vagas)

        # Remove duplicatas antes de validar
        vagas_unicas = deduplicar(todas_vagas)
        print(f"\n[INFO] Total após deduplicação: {len(vagas_unicas)} vaga(s)")

        # Filtra vagas dentro do prazo de validade
        vagas_validas = [v for v in vagas_unicas if vaga_valida(v.get("data_publicacao", ""))]
        descartadas = len(vagas_unicas) - len(vagas_validas)
        if descartadas > 0:
            print(f"[INFO] {descartadas} vaga(s) descartada(s) por estarem fora do prazo de {VALIDADE_DIAS} dias.")
        print(f"[INFO] {len(vagas_validas)} vaga(s) válida(s) restantes.")

        # Complementa título e empresa das vagas, se necessário
        truncadas = [v for v in vagas_validas if "..." in v.get("titulo", "") or "..." in v.get("empresa", "")]
        if truncadas:
            print(f"\n[INFO] Complementando dados de {len(truncadas)} vaga(s) com informações truncadas...")
            vagas_validas = [complementar_dados_vaga(page, v) for v in vagas_validas]

        browser.close()

    # Adiciona a categoria em cada vaga
    for vaga in vagas_validas:
        vaga["categoria"] = categoria

    # Salva o resultado
    salvar_resultado(vagas_validas, categoria)

    print("\n[CONCLUÍDO] bot_scraper.py finalizado com sucesso.")
    print("=" * 50)


if __name__ == "__main__":
    main()