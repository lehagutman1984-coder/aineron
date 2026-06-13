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
