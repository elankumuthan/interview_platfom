import base64
import hmac
import os
from hashlib import sha256
from typing import Union

from cryptography.fernet import Fernet, InvalidToken


# --- Key loading -------------------------------------------------------------

def _load_data_key() -> bytes:
    """
    Load the symmetric key for field encryption (Fernet).
    Expect DATA_ENC_KEY as a urlsafe base64 32-byte key.
    Generate one with:
      python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    """
    key = os.environ.get("DATA_ENC_KEY")
    if not key:
        raise RuntimeError("DATA_ENC_KEY not set")
    try:
        raw = base64.urlsafe_b64decode(key)
    except Exception as e:
        raise RuntimeError("DATA_ENC_KEY must be urlsafe base64 (Fernet key)") from e
    if len(raw) != 32:
        raise RuntimeError("DATA_ENC_KEY must decode to 32 bytes")
    return key.encode("utf-8")  # Fernet expects the base64 text


def _load_hmac_key() -> bytes:
    """
    Load the secret for deterministic HMAC indexing (e.g., username/email).
    HMAC_KEY can be any bytes; we accept either raw text or hex.
    """
    key = os.environ.get("HMAC_KEY")
    if not key:
        raise RuntimeError("HMAC_KEY not set")
    # Allow hex-encoded or plain string
    try:
        return bytes.fromhex(key)
    except ValueError:
        return key.encode("utf-8")


# Singletons
_FERNET: Fernet | None = None
_HMAC_KEY: bytes | None = None


def _fernet() -> Fernet:
    global _FERNET
    if _FERNET is None:
        _FERNET = Fernet(_load_data_key())
    return _FERNET


def _hmac_key() -> bytes:
    global _HMAC_KEY
    if _HMAC_KEY is None:
        _HMAC_KEY = _load_hmac_key()
    return _HMAC_KEY


# --- Public helpers used by your models / init -------------------------------

def encrypt_field(value: str) -> bytes:
    """
    Encrypt a string -> ciphertext bytes suitable for a PostgreSQL BYTEA column.
    """
    if value is None:
        return None  # type: ignore[return-value]
    token: bytes = _fernet().encrypt(value.encode("utf-8"))
    return token


def decrypt_field(value: Union[bytes, memoryview, None]) -> str | None:
    """
    Decrypt BYTEA column -> original string.
    """
    if value is None:
        return None
    if isinstance(value, memoryview):
        value = value.tobytes()
    try:
        plain: bytes = _fernet().decrypt(value)
    except InvalidToken:
        # Key rotated or data corrupted
        raise RuntimeError("Failed to decrypt field (invalid token).")
    return plain.decode("utf-8")


def hmac_index(value: str) -> str:
    """
    Deterministically derive a constant-time, non-reversible index for lookups.
    We lowercase to make lookups case-insensitive for usernames/emails.
    Returns a 64-char hex digest (SHA-256).
    """
    if value is None:
        return None  # type: ignore[return-value]
    msg = value.strip().lower().encode("utf-8")
    digest = hmac.new(_hmac_key(), msg, sha256).hexdigest()
    return digest
