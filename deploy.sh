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

echo -e "${YELLOW}Запускаем контейнеры...${NC}"
docker-compose up -d

echo -e "${YELLOW}Ожидаем запуска базы данных...${NC}"
sleep 10

# Миграции уже выполняются в command web, но на всякий случай
echo -e "${YELLOW}Применяем миграции (если нужно)...${NC}"
docker-compose exec -T web python manage.py migrate --noinput

# modeltranslation: заполнить *_ru из исходных колонок (идемпотентно)
docker-compose exec -T web python manage.py update_translation_fields || true

echo -e "${YELLOW}Устанавливаем Telegram webhook...${NC}"
docker-compose exec -T web python manage.py setup_webhook || echo -e "${YELLOW}setup_webhook пропущен (нет токена или команды)${NC}"

echo -e "${YELLOW}Регистрируем периодические задачи Celery Beat...${NC}"
docker-compose exec -T web python manage.py setup_periodic_tasks

echo -e "${YELLOW}Заполняем юридические документы (оферта, политика)...${NC}"
docker-compose exec -T web python manage.py setup_legal_documents --force || echo -e "${YELLOW}setup_legal_documents пропущен${NC}"

echo -e "${YELLOW}Засеиваем системные AI-персоны...${NC}"
docker-compose exec -T web python manage.py seed_personas || echo -e "${YELLOW}seed_personas пропущен${NC}"

echo -e "${YELLOW}Засеиваем бесплатные модели OpenRouter (Groq заблокирован из РФ)...${NC}"
docker-compose exec -T web python manage.py add_openrouter_free_models || echo -e "${YELLOW}add_openrouter_free_models пропущен${NC}"

echo -e "${YELLOW}Засеиваем бесплатные модели Z.ai (GLM-*-Flash)...${NC}"
docker-compose exec -T web python manage.py add_zai_free_models || echo -e "${YELLOW}add_zai_free_models пропущен${NC}"

echo -e "${YELLOW}Засеиваем бесплатные модели Cloudflare Workers AI...${NC}"
docker-compose exec -T web python manage.py add_cloudflare_free_models || echo -e "${YELLOW}add_cloudflare_free_models пропущен${NC}"

echo -e "${YELLOW}Включаем перевод промтов на английский для Flux (img2img на русском не работал)...${NC}"
docker-compose exec -T web python manage.py enable_flux_translation || echo -e "${YELLOW}enable_flux_translation пропущен${NC}"

echo -e "${YELLOW}Собираем статические файлы...${NC}"
docker-compose exec -T web python manage.py collectstatic --noinput

echo -e "${YELLOW}Создаем суперпользователя (если отсутствует)...${NC}"
docker-compose exec -T web python manage.py shell -c "
from django.contrib.auth import get_user_model
import os
User = get_user_model()
if User.objects.filter(is_superuser=True).exists():
    print('Суперпользователь уже существует — пропускаем')
else:
    User.objects.create_superuser(
        username=os.getenv('DJANGO_SUPERUSER_USERNAME', 'admin'),
        email=os.getenv('DJANGO_SUPERUSER_EMAIL', 'admin@example.com'),
        password=os.getenv('DJANGO_SUPERUSER_PASSWORD') or None,
    )
    print('Суперпользователь создан')
" || echo -e "${YELLOW}Шаг суперпользователя пропущен (ошибка не критична)${NC}"

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
