"""
Fernet encrypt/decrypt for the preview-service db layer.

Sprint 3 — code-complete, not integration-tested.

Byte-compatible with Django's src/aitext/crypto.py: both sides read the same
PROJECT_CONNECTOR_FERNET_KEY env var, so credentials encrypted by Django decrypt
here and vice-versa. Never log plaintext produced by these helpers.
"""
import sys
import os

from cryptography.fernet import Fernet, InvalidToken

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import settings


def _fernet() -> Fernet:
    key = settings.FERNET_KEY
    if not key:
        raise RuntimeError("PROJECT_CONNECTOR_FERNET_KEY is not set")
    if isinstance(key, str):
        key = key.encode()
    try:
        return Fernet(key)
    except Exception as e:  # noqa: BLE001 — surface a clean error, never the key
        raise RuntimeError(f"Invalid PROJECT_CONNECTOR_FERNET_KEY: {e}") from e


def encrypt(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as e:
        raise RuntimeError(
            "Failed to decrypt — wrong key or corrupted data"
        ) from e
