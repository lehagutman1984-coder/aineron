# E2B custom template: Python 3.11 + Django/DRF + PostgreSQL driver pre-installed
# Build: e2b template build --name aineron-django --dockerfile django.Dockerfile
# After build: set E2B_TEMPLATE_DJANGO=<template_id> in .env
FROM e2bdev/code-interpreter:latest

RUN pip install --no-cache-dir \
    django==5.0.0 \
    djangorestframework==3.15.0 \
    django-cors-headers==4.3.0 \
    django-environ==0.11.0 \
    psycopg2-binary==2.9.9 \
    uvicorn[standard]==0.30.0 \
    daphne==4.1.0 \
    celery==5.4.0 \
    redis==5.0.0 \
    pillow==10.4.0 \
    httpx==0.27.0 \
    gunicorn==22.0.0 \
    whitenoise==6.7.0

WORKDIR /app
