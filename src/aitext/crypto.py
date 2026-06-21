from cryptography.fernet import Fernet
from django.conf import settings


def _fernet() -> Fernet:
    key = settings.PROJECT_CONNECTOR_FERNET_KEY
    if not key:
        raise RuntimeError('PROJECT_CONNECTOR_FERNET_KEY is not set')
    if isinstance(key, str):
        key = key.encode()
    return Fernet(key)


def encrypt_token(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    return _fernet().decrypt(ciphertext.encode()).decode()
