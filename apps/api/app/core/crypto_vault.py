"""
Application-level Secret Encryption Vault for Master API Keys & Custom Providers.
Implements AES-256-GCM symmetric authenticated encryption.
"""
import base64
import hashlib
import os
from typing import Optional
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app.core.config import settings

VAULT_PREFIX = "enc:v1:"


def _get_encryption_key() -> bytes:
    """Derives a 32-byte (256-bit) encryption key from settings.SECRET_KEY."""
    raw_secret = settings.SECRET_KEY or "btp-super-secret-master-key-vault-2026-production"
    return hashlib.sha256(raw_secret.encode("utf-8")).digest()


def encrypt_api_key(plaintext: Optional[str]) -> str:
    """
    Encrypts an API key or sensitive token using AES-256-GCM.
    Returns a prefixed base64 string: 'enc:v1:<base64(nonce + ciphertext + tag)>'.
    """
    if not plaintext:
        return ""
    plaintext = plaintext.strip()
    if plaintext.startswith(VAULT_PREFIX):
        return plaintext  # Already encrypted

    key = _get_encryption_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)  # 96-bit nonce for AES-GCM
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    
    encoded = base64.urlsafe_b64encode(nonce + ciphertext).decode("utf-8")
    return f"{VAULT_PREFIX}{encoded}"


def decrypt_api_key(encrypted_str: Optional[str]) -> str:
    """
    Decrypts an encrypted API key string.
    If the string is not prefixed with 'enc:v1:', it is returned as plain text for legacy compatibility.
    """
    if not encrypted_str:
        return ""
    encrypted_str = encrypted_str.strip()
    if not encrypted_str.startswith(VAULT_PREFIX):
        return encrypted_str  # Legacy plain text

    payload = encrypted_str[len(VAULT_PREFIX):]
    try:
        raw_data = base64.urlsafe_b64decode(payload.encode("utf-8"))
        if len(raw_data) < 28:  # 12-byte nonce + at least 16-byte tag
            return ""
        nonce = raw_data[:12]
        ciphertext = raw_data[12:]
        
        key = _get_encryption_key()
        aesgcm = AESGCM(key)
        decrypted_bytes = aesgcm.decrypt(nonce, ciphertext, None)
        return decrypted_bytes.decode("utf-8")
    except Exception as e:
        # If decryption fails (e.g. key rotation or corrupted string)
        return ""


def mask_api_key(plaintext: Optional[str]) -> str:
    """
    Returns a masked representation of an API key for safe UI display.
    """
    if not plaintext:
        return ""
    # If encrypted, decrypt first to produce accurate mask
    real_key = decrypt_api_key(plaintext) if plaintext.startswith(VAULT_PREFIX) else plaintext
    if not real_key:
        return ""
    if len(real_key) > 12:
        return f"{real_key[:4]}••••••••••••{real_key[-4:]}"
    elif len(real_key) > 6:
        return f"{real_key[:2]}••••••{real_key[-2:]}"
    return "••••••••"
