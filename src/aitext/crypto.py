from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


def _fernet() -> Fernet:
    key = settings.PROJECT_CONNECTOR_FERNET_KEY
    if not key:
        raise RuntimeError('PROJECT_CONNECTOR_FERNET_KEY is not set')
    if isinstance(key, str):
        key = key.encode()
    try:
        return Fernet(key)
    except (ValueError, Exception) as e:
        raise RuntimeError(f'Invalid PROJECT_CONNECTOR_FERNET_KEY: {e}') from e


def encrypt_token(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as e:
        raise RuntimeError('Не удалось расшифровать токен — неверный ключ или повреждённые данные') from e
