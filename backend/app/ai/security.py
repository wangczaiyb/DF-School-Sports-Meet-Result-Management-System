from __future__ import annotations

import base64
import hashlib
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from ..config import get_settings


def _get_encryption_key() -> bytes:
    """Derive 256-bit encryption key from application secret_key."""
    settings = get_settings()
    return hashlib.sha256(settings.secret_key.encode("utf-8")).digest()


def encrypt_api_key(plain_key: str) -> str:
    """Encrypt plain API key into a base64 string containing nonce + ciphertext."""
    if not plain_key:
        return ""
    key = _get_encryption_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plain_key.encode("utf-8"), None)
    return base64.b64encode(nonce + ciphertext).decode("ascii")


def decrypt_api_key(ciphertext_b64: str) -> str:
    """Decrypt a base64 string back into plain API key."""
    if not ciphertext_b64:
        return ""
    try:
        raw = base64.b64decode(ciphertext_b64.encode("ascii"))
        if len(raw) < 13:
            return ""
        nonce = raw[:12]
        ciphertext = raw[12:]
        key = _get_encryption_key()
        aesgcm = AESGCM(key)
        decrypted = aesgcm.decrypt(nonce, ciphertext, None)
        return decrypted.decode("utf-8")
    except Exception:
        return ""


def mask_api_key(plain_key: str) -> str:
    """Mask plain API key for UI display (e.g. sk-**************8Fd)."""
    if not plain_key:
        return ""
    s = plain_key.strip()
    if len(s) <= 8:
        return "********"
    if len(s) <= 12:
        return s[:2] + "******" + s[-2:]
    prefix = s[:3]
    suffix = s[-3:]
    return f"{prefix}**************{suffix}"


def is_masked_key(key_str: str) -> bool:
    """Check if the provided key string is already masked."""
    if not key_str:
        return False
    return "******" in key_str or "*" in key_str
