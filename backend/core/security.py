from cryptography.fernet import Fernet

from backend.core.config import settings


def encrypt_token(token: str) -> str:
    """Encrypt a PAT token using Fernet symmetric encryption."""
    f = Fernet(settings.FERNET_KEY.encode())
    return f.encrypt(token.encode()).decode()


def decrypt_token(encrypted_token: str) -> str:
    """Decrypt a Fernet-encrypted PAT token."""
    f = Fernet(settings.FERNET_KEY.encode())
    return f.decrypt(encrypted_token.encode()).decode()
