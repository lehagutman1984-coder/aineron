#!/bin/bash
# Быстрый деплой — только если менялся Python/фронтенд код, но НЕ менялись
# requirements.txt / Dockerfile. Не пересобирает образы.

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}  Быстрый деплой (без пересборки)    ${NC}"
echo -e "${GREEN}======================================${NC}"

echo -e "${YELLOW}Подтягиваем код...${NC}"
git pull origin main

echo -e "${YELLOW}Перезапускаем Python-сервисы (код монтирован как volume)...${NC}"
# --force-recreate обязателен: код меняется только на диске (volume), конфиг
# самого контейнера — нет, поэтому обычный `up -d` считает контейнер
# актуальным и НЕ перезапускает процесс — новый код молча не подхватывается
# (баг найден 2026-08-11: web не перезапускался 4 дня несмотря на редеплои).
# daphne — тоже Python/Django-процесс (ASGI, SSE) и ранее был пропущен здесь.
docker-compose up -d --no-build --force-recreate web daphne celery_worker celery_beat

echo -e "${YELLOW}Применяем миграции...${NC}"
docker-compose exec -T web python manage.py migrate --noinput

echo -e "${YELLOW}Пересобираем и перезапускаем фронтенд...${NC}"
docker-compose build frontend
docker-compose up -d frontend

# --force-recreate выше даёт web/daphne новый IP в docker-сети — nginx держит
# резолвленный upstream/keepalive-соединения на старый и без рестарта отдаёт
# 502, пока не истечёт TTL сам (найдено 2026-08-11: живой прод несколько
# секунд отдавал 502 на /api/ после первого прогона с --force-recreate).
echo -e "${YELLOW}Перезапускаем nginx (иначе держит IP старого web-контейнера)...${NC}"
docker-compose restart nginx

echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}  Статус контейнеров:                ${NC}"
echo -e "${GREEN}======================================${NC}"
docker-compose ps

echo -e "${GREEN}Быстрый деплой завершён!${NC}"
echo -e "Сайт: ${YELLOW}https://aineron.ru${NC}"
