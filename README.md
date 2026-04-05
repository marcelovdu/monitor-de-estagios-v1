# 🎓 Estágio Monitor

Sistema de automação web desenvolvido em Python com Playwright para monitorar vagas de estágio no portal [IEL Amazonas](https://carreiras.iel.org.br/AM), registrá-las no Google Sheets e notificar o usuário via Telegram — tudo rodando de forma autônoma em Docker, agendado por Cron.

---

## 🤖 Os 3 Bots

| Bot | Arquivo | Responsabilidade |
|---|---|---|
| 🔍 Scraper | `bot_scraper.py` | Coleta vagas do IEL/AM por palavra-chave |
| 📊 Sheets | `bot_sheets.py` | Registra vagas novas no Google Sheets |
| 📲 Telegram | `bot_telegram.py` | Configura preferências e envia notificações |

---

## 🗂️ Estrutura do Projeto

```
estagio-monitor/
├── bot_scraper.py        # Bot de coleta de vagas
├── bot_sheets.py         # Bot de registro na planilha
├── bot_telegram.py       # Bot de notificação e configuração
├── requirements.txt      # Dependências Python
├── Dockerfile            # Imagem do container
├── docker-compose.yml    # Orquestração do container
├── crontab               # Agendamento dos bots
├── credentials.json      # Service Account Google (não versionar)
├── .env                  # Variáveis de ambiente (não versionar)
├── user_prefs.json       # Preferência do usuário (gerado em runtime)
├── vagas_temp.json       # Dados temporários entre bots (gerado em runtime)
└── README.md
```

---

## ⚙️ Pré-requisitos

- Python 3.11+
- Docker e Docker Compose
- Conta no Google Cloud com Sheets API habilitada
- Bot do Telegram criado via @BotFather

---

## 🚀 Configuração

### 1. Variáveis de ambiente

Crie o arquivo `.env` na raiz do projeto:

```env
TELEGRAM_TOKEN=seu_token_aqui
TELEGRAM_CHAT_ID=seu_chat_id_aqui
SPREADSHEET_ID=id_da_planilha_aqui
TZ=America/Manaus
```

### 2. Credenciais do Google

Coloque o arquivo `credentials.json` da Service Account na raiz do projeto e compartilhe a planilha com o e-mail da Service Account como Editor.

### 3. Planilha Google Sheets

Crie uma planilha com uma aba chamada `vagas` e os seguintes cabeçalhos na primeira linha:

```
titulo | empresa | localizacao | categoria | modalidade | salario | data_publicacao | link | data_registrado | notificado
```

---

## ▶️ Como usar

### Configurar preferência (primeira vez)

Execute o bot do Telegram em modo configuração:

```bash
python bot_telegram.py
```

Envie `/start` no Telegram, selecione sua categoria de interesse na enquete e aguarde a confirmação. Para trocar de categoria, envie `/start` novamente.

### Executar manualmente (teste)

```bash
# 1. Coletar vagas
python bot_scraper.py

# 2. Registrar na planilha
python bot_sheets.py

# 3. Notificar via Telegram
python bot_telegram.py --notificar
```

### Executar com Docker

```bash
# Build e inicialização
docker-compose up --build -d

# Acompanhar logs do cron em tempo real
docker-compose logs -f

# Parar o container
docker-compose down
```

---

## ⏰ Agendamento (Cron)

Os bots são executados automaticamente a cada 6 horas (00:00, 06:00, 12:00, 18:00):

```
00:00 → bot_scraper.py   (coleta vagas)
00:05 → bot_sheets.py    (registra novas)
00:10 → bot_telegram.py  (notifica usuário)
```

---

## 📋 Categorias disponíveis

| Categoria | Palavras-chave |
|---|---|
| 💻 Tecnologia | sistemas, desenvolvimento, computação, informática |
| 🏥 Saúde | enfermagem, nutrição, farmácia, biomedicina |
| 📊 Administração | administração, gestão, recursos humanos, contabilidade, economia |
| 📣 Comunicação | marketing, publicidade, design, jornalismo, comunicação |
| 🏗️ Engenharia | engenharia, civil, elétrica, produção |
| 🔧 Técnico | técnico, segurança, análises, eletrotécnica, edificações |
| 🎓 Educação | pedagogia, matemática, física, química, educação física |
| ⚖️ Direito/Outros | direito, turismo, serviço social |

---

## 🔧 Constantes configuráveis

| Arquivo | Constante | Padrão | Descrição |
|---|---|---|---|
| `bot_scraper.py` | `LIMITE_PAGINAS` | `5` | Máximo de páginas por palavra-chave |
| `bot_scraper.py` | `VALIDADE_DIAS` | `60` | Vagas mais antigas são descartadas |
| `bot_telegram.py` | `LIMITE_VAGAS_POR_ENVIO` | `5` | Máximo de vagas por notificação |

---

## 🔒 Segurança

- Nunca versione `.env` e `credentials.json`
- Ambos estão listados no `.gitignore`
- As credenciais são injetadas via volume no Docker

---

## 👨‍💻 Desenvolvido por

Projeto desenvolvido para o curso de **Introdução ao Python para RPA**
**IFAM / AX Academy — Digital Transformation**
Professor: Anderson Gadelha Fontoura