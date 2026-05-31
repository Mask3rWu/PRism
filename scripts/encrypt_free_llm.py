#!/usr/bin/env python3
"""Encrypt the free LLM configuration for PRism.

Usage:
    python scripts/encrypt_free_llm.py \
        --url https://api.openai.com/v1 \
        --api-key sk-xxxxxxxx \
        --model gpt-4o

This writes backend/free_llm_config.enc which is committed to the repo.
The matching decryption key is hardcoded in backend/core/free_llm.py.
"""

import argparse
import json
import os
import sys

from cryptography.fernet import Fernet

_FERNET_KEY = b"iHJ93LtfFE1ZjYBJcAPDIyaupK3KdJsPqOT1imtBsiM="

OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "backend", "free_llm_config.enc")


def main():
    parser = argparse.ArgumentParser(description="Encrypt free LLM config for PRism")
    parser.add_argument("--url", required=True, help="LLM base URL (e.g. https://api.openai.com/v1)")
    parser.add_argument("--api-key", required=True, help="LLM API key")
    parser.add_argument("--model", required=True, help="LLM model name (e.g. gpt-4o)")
    args = parser.parse_args()

    config = {
        "endpoint": args.url.rstrip("/"),
        "api_key": args.api_key,
        "model": args.model,
    }

    f = Fernet(_FERNET_KEY)
    encrypted = f.encrypt(json.dumps(config).encode())

    with open(OUT_PATH, "wb") as fh:
        fh.write(encrypted)

    print(f"Encrypted config saved to {OUT_PATH}")
    print(f"  endpoint: {config['endpoint']}")
    print(f"  model:    {config['model']}")


if __name__ == "__main__":
    main()
