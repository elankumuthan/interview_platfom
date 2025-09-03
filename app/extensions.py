# app/extensions.py
import os
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

RATE_LIMIT_STORAGE_URI = os.getenv("RATE_LIMIT_STORAGE_URI", "memory://")
DEFAULT_RATE_LIMITS = os.getenv("DEFAULT_RATE_LIMITS", "300 per hour;50 per minute")

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=RATE_LIMIT_STORAGE_URI,
    default_limits=[r.strip() for r in DEFAULT_RATE_LIMITS.split(";") if r.strip()],
)
