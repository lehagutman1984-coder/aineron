#!/bin/bash

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Начинаем деплой проекта Нейросети${NC}"
echo -e "${GREEN}========================================${NC}"

if [ ! -d "src" ]; then
    echo -e "${RED}Ошибка: Папка src не найдена!${NC}"
    exit 1
fi

echo -e "${YELLOW}Останавливаем старые контейнеры...${NC}"
docker-compose down

echo -e "${YELLOW}Собираем Docker образы...${NC}"
docker-compose build

# ---------- Studio sandbox images ----------
echo -e "${YELLOW}Собираем sandbox-образ для Studio...${NC}"
docker build -f Dockerfile.sandbox -t aineron-sandbox:latest .

echo -e "${YELLOW}Собираем Playwright-образ для Studio (необязательно)...${NC}"
docker build -f Dockerfile.playwright -t aineron-playwright:latest . || echo -e "${YELLOW}Playwright-образ не собран (пропускаем)${NC}"

echo -e "${YELLOW}Запускаем контейнеры...${NC}"
docker-compose up -d

echo -e "${YELLOW}Ожидаем запуска базы данных...${NC}"
sleep 10

# Миграции уже выполняются в command web, но на всякий случай
echo -e "${YELLOW}Применяем миграции (если нужно)...${NC}"
docker-compose exec -T web python manage.py migrate --noinput

echo -e "${YELLOW}Собираем статические файлы...${NC}"
docker-compose exec -T web python manage.py collectstatic --noinput

echo -e "${YELLOW}Создаем суперпользователя...${NC}"
docker-compose exec -T web python manage.py createsuperuser --noinput --username admin --email admin@example.com || echo -e "${YELLOW}Суперпользователь уже существует${NC}"

# ---------- Studio seeds ----------
echo -e "${YELLOW}Засеиваем шаблоны Studio...${NC}"
docker-compose exec -T web python manage.py seed_templates

# ---------- Gitea (manual step reminder) ----------
echo -e "${YELLOW}-------------------------------------------${NC}"
echo -e "${YELLOW}РУЧНОЙ ШАГ (если Gitea только что поднят):${NC}"
echo -e "${YELLOW}  1. Зайдите на https://aineron.ru/git/      ${NC}"
echo -e "${YELLOW}  2. Создайте admin-аккаунт и токен          ${NC}"
echo -e "${YELLOW}  3. Добавьте в .env:                        ${NC}"
echo -e "${YELLOW}       GITEA_DB_PASSWORD=<пароль>            ${NC}"
echo -e "${YELLOW}       STUDIO_GITEA_ADMIN_TOKEN=<токен>      ${NC}"
echo -e "${YELLOW}  4. Перезапустите: docker-compose restart web celery_studio${NC}"
echo -e "${YELLOW}-------------------------------------------${NC}"

# Очищаем conntrack для устранения проблем с соединениями после перезапуска
echo -e "${YELLOW}Очищаем таблицу conntrack...${NC}"
conntrack -F 2>/dev/null || echo -e "${YELLOW}conntrack не установлен, пропускаем...${NC}"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Статус контейнеров:${NC}"
echo -e "${GREEN}========================================${NC}"
docker-compose ps

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Последние логи веб-приложения:${NC}"
echo -e "${GREEN}========================================${NC}"
docker-compose logs --tail=20 web

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Деплой завершен успешно!${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "Сайт доступен по адресу: ${YELLOW}https://aineron.ru${NC}"
echo -e "Админка: ${YELLOW}https://aineron.ru/admin${NC}"
echo -e "Для просмотра логов: ${YELLOW}docker-compose logs -f [service]${NC}"
echo -e "${GREEN}========================================${NC}"
