FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .

RUN pip install --no-cache-dir \
    fastapi>=0.115.0 \
    uvicorn[standard]>=0.30.0 \
    redis>=5.0.0 \
    cryptography>=42.0.0 \
    psycopg2-binary>=2.9.0 \
    httpx>=0.27.0 \
    e2b>=2.0.0

COPY . .

EXPOSE 8001

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "2"]
