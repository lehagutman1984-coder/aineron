# E2B custom template: Python + common web packages (pure-Python only, no Rust/C compile)
# Build: e2b template create aineron-python -d python.Dockerfile
FROM e2bdev/code-interpreter:latest

RUN pip install --no-cache-dir \
    flask \
    fastapi \
    "uvicorn[standard]" \
    httpx \
    requests \
    python-dotenv \
    redis

WORKDIR /app
