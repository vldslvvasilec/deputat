# Dockerfile

FROM python:3.11-slim

# Установим зависимости
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Создадим рабочую директорию
WORKDIR /app

# Скопируем зависимости и проект
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Указываем команду по умолчанию (будет переопределена в docker-compose)
CMD ["python3", "bot.py"]
