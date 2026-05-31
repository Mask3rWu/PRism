"""Decrypt the free LLM configuration bundled with the repository.

The Fernet key is hardcoded — anyone with the source can decrypt the config.
This is NOT meant to be secure; it just avoids plaintext API keys in the repo.
"""

import json
import os

from cryptography.fernet import Fernet

_FERNET_KEY = b"iHJ93LtfFE1ZjYBJcAPDIyaupK3KdJsPqOT1imtBsiM="


def get_free_llm_config() -> dict | None:
    """Decrypt and return the bundled free LLM config, or None."""
    enc_path = os.path.join(os.path.dirname(__file__), "..", "free_llm_config.enc")
    if not os.path.exists(enc_path):
        return None
    f = Fernet(_FERNET_KEY)
    with open(enc_path, "rb") as fh:
        raw = f.decrypt(fh.read())
    return json.loads(raw)
