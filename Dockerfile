FROM python:3.11-slim

# Define o diretório de trabalho
WORKDIR /app

# Instala dependências do sistema necessárias para o Playwright/Chromium
RUN apt-get update && apt-get install -y \
    cron \
    curl \
    wget \
    gnupg \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libc6 \
    libcairo2 \
    libcups2 \
    libdbus-1-3 \
    libexpat1 \
    libfontconfig1 \
    libgbm1 \
    libgcc1 \
    libglib2.0-0 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libstdc++6 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxi6 \
    libxrandr2 \
    libxrender1 \
    libxss1 \
    libxtst6 \
    lsb-release \
    xdg-utils \
    --no-install-recommends && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copia o arquivo de dependências Python
COPY requirements.txt .

# Instala as dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Instala o Chromium do Playwright
RUN playwright install chromium

# Copia todos os arquivos do projeto para o container
COPY . .

# Copia e configura o crontab
COPY crontab /etc/cron.d/estagio-monitor
RUN chmod 0644 /etc/cron.d/estagio-monitor && \
    crontab /etc/cron.d/estagio-monitor

# Cria o arquivo de log do cron
RUN touch /var/log/cron.log

# Comando de inicialização:
# 1. Inicia o cron em background
# 2. Inicia o bot_telegram em modo configuração (escuta /start continuamente)
# 3. Exibe o log do cron em tempo real
CMD ["sh", "-c", "cron && python /app/bot_telegram.py & tail -f /var/log/cron.log"]