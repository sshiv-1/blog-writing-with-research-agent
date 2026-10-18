from __future__ import annotations

import os
from typing import Optional, Tuple
from cryptography.fernet import Fernet, InvalidToken


_FERNET_KEY_INSTRUCTIONS = (
    "APP_ENCRYPTION_KEY is unset or invalid. "
    "Generate a 32-byte key using: "
    "python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
)


def _get_fernet() -> Fernet:
    """Instantiate and return a Fernet cipher, or raise RuntimeError if key is missing/invalid."""
    key = os.getenv("APP_ENCRYPTION_KEY")
    if not key or not key.strip():
        raise RuntimeError(_FERNET_KEY_INSTRUCTIONS)
    try:
        return Fernet(key.strip().encode("utf-8"))
    except Exception as exc:
        raise RuntimeError(_FERNET_KEY_INSTRUCTIONS) from None


def encrypt_key(plain_key: str) -> Tuple[str, str]:
    """
    Encrypt an API key using symmetric Fernet encryption.
    Caps length to 512 characters.
    Extracts the last 4 characters for display purposes.
    Clears plaintext from local scope before returning.

    Returns:
        tuple of (ciphertext, key_last4)
    """
    if not plain_key or not isinstance(plain_key, str):
        raise ValueError("API key must be a non-empty string.")

    cleaned = plain_key.strip()
    if len(cleaned) > 512:
        raise ValueError("API key exceeds maximum length of 512 characters.")

    fernet = _get_fernet()
    last4 = cleaned[-4:] if len(cleaned) >= 4 else cleaned

    try:
        ciphertext = fernet.encrypt(cleaned.encode("utf-8")).decode("utf-8")
    finally:
        # Clear plaintext reference
        cleaned = ""
        plain_key = ""

    return ciphertext, last4


def decrypt_key(ciphertext: str) -> str:
    """
    Decrypt a Fernet ciphertext back to the original API key string.
    Raises ValueError on invalid ciphertext or key mismatch.
    """
    if not ciphertext or not isinstance(ciphertext, str):
        raise ValueError("Ciphertext must be a non-empty string.")

    fernet = _get_fernet()
    try:
        return fernet.decrypt(ciphertext.strip().encode("utf-8")).decode("utf-8")
    except InvalidToken:
        raise ValueError("Failed to decrypt API key: invalid ciphertext or mismatched APP_ENCRYPTION_KEY.")
    except Exception as exc:
        raise ValueError("Failed to decrypt API key.") from None
