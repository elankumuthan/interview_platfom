from passlib.hash import argon2

# tune costs to your VM; these are sane defaults
_ARGON = argon2.using(time_cost=3, memory_cost=102400, parallelism=8)

def hash_password(pw: str) -> str:
    return _ARGON.hash(pw)

def verify_password(hashval: str, pw: str) -> bool:
    try:
        return _ARGON.verify(pw, hashval)
    except Exception:
        return False
