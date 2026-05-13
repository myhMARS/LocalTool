import hashlib
import json
import os
from base64 import urlsafe_b64encode

from cryptography.fernet import Fernet
from pydantic import BaseModel, Field

CONFIG_DIR = os.path.expanduser("~/.localtool")
CONFIG_FILE = os.path.join(CONFIG_DIR, "email.conf")
SESSION_KEY_FILE = os.path.join(CONFIG_DIR, ".session_key")


class AccountConfig(BaseModel):
    """Per-account IMAP / SMTP settings."""

    name: str = ""
    email: str = ""
    imap_host: str = ""
    imap_port: int = 993
    smtp_host: str = ""
    smtp_port: int = 587
    password: str = ""


class AppConfig(BaseModel):
    """Top-level application configuration (supports multi-account)."""

    accounts: list[AccountConfig] = Field(default_factory=lambda: [AccountConfig()])
    active: int = 0

    @property
    def active_account(self) -> AccountConfig:
        return self.accounts[self.active]


def derive_key(password: str, salt: bytes) -> bytes:
    raw = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600000, 32)
    return urlsafe_b64encode(raw)


def _load_raw(password: str) -> dict | None:
    """Decrypt and return raw dict from config file."""
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


def _raw_to_config(data: dict) -> AppConfig:
    """Convert raw dict to AppConfig, normalizing legacy single-account format."""
    if "accounts" not in data:
        data = {"accounts": [data], "active": 0}
    return AppConfig.model_validate(data)


def load_config(password: str) -> AppConfig | None:
    data = _load_raw(password)
    if data is None:
        return None
    return _raw_to_config(data)


def save_config(password: str, config: AppConfig):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    salt = os.urandom(16)
    key = derive_key(password, salt)
    ciphertext = Fernet(key).encrypt(json.dumps(config.model_dump()).encode())
    with open(CONFIG_FILE, "wb") as f:
        f.write(salt + ciphertext)
    os.chmod(CONFIG_FILE, 0o600)


def load_config_with_key(key: bytes) -> AppConfig | None:
    if not os.path.exists(CONFIG_FILE):
        return None
    with open(CONFIG_FILE, "rb") as f:
        _ = f.read(16)
        ciphertext = f.read()
    try:
        plain = Fernet(key).decrypt(ciphertext)
        return _raw_to_config(json.loads(plain))
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


def unlock_config() -> AppConfig | None:
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
