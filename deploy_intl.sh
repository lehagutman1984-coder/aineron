#!/bin/bash
# Деплой международного инстанса (aineron.net) — GLOBAL_EXPANSION_PLAN.md, G3.
# Запускается на intl-сервере из /opt/aineron: bash deploy_intl.sh
set -e
cd "$(dirname "$0")"

echo "=== aineron.net: деплой международного инстанса ==="

if [ -d .git ]; then
    git pull origin main || echo "[WARN] git pull не удался — деплою текущее состояние"
fi

docker compose -f docker-compose.intl.yml up -d --build

echo "=== Ожидание web-контейнера (миграции идут при старте) ==="
sleep 10
docker compose -f docker-compose.intl.yml exec -T web python manage.py migrate --noinput
# modeltranslation: заполнить *_ru из исходных колонок (идемпотентно)
docker compose -f docker-compose.intl.yml exec -T web python manage.py update_translation_fields || true

# nginx кэширует IP upstream-контейнеров при старте: после пересоздания web/frontend
# он бьёт по мёртвым адресам (502). Рестарт — обязателен.
docker compose -f docker-compose.intl.yml restart nginx

echo "=== Готово. Статус: ==="
docker compose -f docker-compose.intl.yml ps
