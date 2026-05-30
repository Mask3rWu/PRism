import os

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


def ensure_fernet_key() -> None:
    """Generate a Fernet key if one is not configured."""
    if settings.FERNET_KEY:
        return

    key = Fernet.generate_key().decode()
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")

    with open(env_path, "a") as f:
        f.write(f"\nFERNET_KEY={key}\n")

    settings.FERNET_KEY = key
    print(f"\n{'=' * 60}")
    print("  Generated new FERNET_KEY and appended to backend/.env")
    print(f"  Key: {key}")
    print(f"{'=' * 60}\n")
