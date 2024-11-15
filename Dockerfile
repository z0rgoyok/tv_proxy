FROM python:3.10-slim

# Установка необходимых пакетов
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Создание рабочей директории
WORKDIR /app

# Создание директории для логов
RUN mkdir -p /var/log/m3u8proxy && \
    chown -R nobody:nogroup /var/log/m3u8proxy

# Копирование зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кода приложения
COPY proxy_server.py .

# Пользователь без привилегий
USER nobody

# Команда запуска
CMD gunicorn \
    --workers ${WORKERS:-4} \
    --timeout ${TIMEOUT:-300} \
    --max-requests ${MAX_REQUESTS:-1000} \
    --bind 0.0.0.0:5001 \
    --access-logfile /var/log/m3u8proxy/access.log \
    --error-logfile /var/log/m3u8proxy/error.log \
    proxy_server:app