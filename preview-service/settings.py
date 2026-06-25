import os

E2B_API_KEY: str = os.environ.get("E2B_API_KEY", "")
INTERNAL_TOKEN: str = os.environ.get("PREVIEW_INTERNAL_TOKEN", "changeme-in-production")
REDIS_URL: str = os.environ.get("REDIS_URL", "redis://localhost:6379/1")

MAX_CONCURRENT: int = int(os.environ.get("PREVIEW_MAX_CONCURRENT", "10"))
DEFAULT_TTL: int = int(os.environ.get("PREVIEW_DEFAULT_TTL", "900"))   # 15 min

EGRESS_ALLOWLIST: list[str] = [
    "api.telegram.org",
    "pypi.org",
    "files.pythonhosted.org",
]

# ── Sprint 3: Database Providers ────────────────────────────────────────────────
# aineron's own PostgreSQL — used by AineronSchemaProvider for schema-per-project.
AINERON_DB_HOST: str = os.environ.get("DB_HOST", "db")
AINERON_DB_NAME: str = os.environ.get("DB_NAME", "neiro_db")
AINERON_DB_USER: str = os.environ.get("DB_USER", "neiro_user")
AINERON_DB_PASSWORD: str = os.environ.get("DB_PASSWORD", "")
AINERON_DB_PORT: int = int(os.environ.get("DB_PORT", "5432"))

# Fernet key shared with Django (src/aitext/crypto.py) — MUST match byte-for-byte
# so credentials encrypted on the Django side decrypt here.
FERNET_KEY: str = os.environ.get("PROJECT_CONNECTOR_FERNET_KEY", "")

NEON_DEFAULT_REGION: str = os.environ.get("NEON_DEFAULT_REGION", "aws-us-east-2")
