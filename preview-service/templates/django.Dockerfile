# E2B custom template: Django + DRF (no psycopg2 — project installs it from requirements.txt)
# Build: e2b template create aineron-django -d django.Dockerfile
FROM e2bdev/code-interpreter:latest

RUN pip install --no-cache-dir \
    django \
    djangorestframework \
    django-cors-headers \
    django-environ \
    "uvicorn[standard]" \
    daphne \
    redis \
    httpx \
    gunicorn \
    whitenoise

WORKDIR /app
