import base64, os, hmac, hashlib
from cryptography.fernet import Fernet, InvalidToken
from flask import current_app

def _fernet():
    key = current_app.config["DATA_ENC_KEY"]
    return Fernet(key)

def _hmac_key():
    # DATA_HMAC_KEY is base64 urlsafe
    return base64.urlsafe_b64decode(current_app.config["DATA_HMAC_KEY"])

def enc_str(s: str) -> bytes:
    return _fernet().encrypt(s.encode("utf-8"))

def dec_str(b: bytes) -> str:
    return _fernet().decrypt(b).decode("utf-8")

def hmac_index(value: str) -> str:
    # deterministic index for equality lookup; normalize to lower
    key = _hmac_key()
    v = value.strip().lower().encode("utf-8")
    return hmac.new(key, v, hashlib.sha256).hexdigest()
