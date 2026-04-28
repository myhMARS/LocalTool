import hashlib
import json
import os
from base64 import urlsafe_b64encode

from cryptography.fernet import Fernet

CONFIG_DIR = os.path.expanduser("~/.localtool")
CONFIG_FILE = os.path.join(CONFIG_DIR, "email.conf")
SESSION_KEY_FILE = os.path.join(CONFIG_DIR, ".session_key")


def derive_key(password: str, salt: bytes) -> bytes:
    raw = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600000, 32)
    return urlsafe_b64encode(raw)


def load_config(password: str) -> dict | None:
    if not os.path.exists(CONFIG_FILE):
        return None
    with open(CONFIG_FILE, "rb") as f:
        salt = f.read(16)
        ciphertext = f.read()
    key = derive_key(password, salt)
    try:
        plain = Fernet(key).decrypt(ciphertext)
        return json.loads(plain)
    except Exception:
        return None


def save_config(password: str, data: dict):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    salt = os.urandom(16)
    key = derive_key(password, salt)
    ciphertext = Fernet(key).encrypt(json.dumps(data).encode())
    with open(CONFIG_FILE, "wb") as f:
        f.write(salt + ciphertext)
    os.chmod(CONFIG_FILE, 0o600)


def load_config_with_key(key: bytes) -> dict | None:
    if not os.path.exists(CONFIG_FILE):
        return None
    with open(CONFIG_FILE, "rb") as f:
        _ = f.read(16)
        ciphertext = f.read()
    try:
        plain = Fernet(key).decrypt(ciphertext)
        return json.loads(plain)
    except Exception:
        return None


def cache_session_key(password: str):
    with open(CONFIG_FILE, "rb") as f:
        salt = f.read(16)
    key = derive_key(password, salt)
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(SESSION_KEY_FILE, "wb") as f:
        f.write(key)
    os.chmod(SESSION_KEY_FILE, 0o600)


def unlock_config() -> dict | None:
    pwd = os.environ.get("EMAIL_MASTER_KEY", "")
    if pwd:
        cfg = load_config(pwd)
        if cfg:
            return cfg
    if os.path.exists(SESSION_KEY_FILE):
        try:
            with open(SESSION_KEY_FILE, "rb") as f:
                key = f.read()
            cfg = load_config_with_key(key)
            if cfg:
                return cfg
        except Exception:
            pass
    return None
