# E2B custom template: Python 3.11 + common data/web packages pre-installed
# Build: e2b template build --name aineron-python --dockerfile python.Dockerfile
# After build: set E2B_TEMPLATE_PYTHON=<template_id> in .env
FROM e2bdev/code-interpreter:latest

RUN pip install --no-cache-dir \
    flask==3.1.0 \
    fastapi==0.115.0 \
    uvicorn[standard]==0.30.0 \
    httpx==0.27.0 \
    requests==2.32.0 \
    psycopg2-binary==2.9.9 \
    sqlalchemy==2.0.0 \
    pydantic==2.7.0 \
    python-dotenv==1.0.0 \
    redis==5.0.0 \
    celery==5.4.0 \
    pillow==10.4.0 \
    pandas==2.2.0 \
    numpy==1.26.0

WORKDIR /app
