FROM python:3.11-slim

# Меняем репозитории на зеркала Яндекса (для стабильности)
RUN sed -i 's/deb.debian.org/mirror.yandex.ru/g' /etc/apt/sources.list.d/debian.sources && \
    sed -i 's/security.debian.org/mirror.yandex.ru/g' /etc/apt/sources.list.d/debian.sources

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    gcc \
    libffi-dev \
    musl-dev \
    libmagic1 \
    libpq-dev \
    redis-tools \
    curl \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Устанавливаем локаль UTF-8 (решает проблемы с кириллическими доменами)
ENV LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8

COPY src/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ .
