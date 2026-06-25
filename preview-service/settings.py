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
