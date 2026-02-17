# core/admin_auth.py – logowanie do panelu nadzoru przez Authenticator (TOTP)
from __future__ import annotations

import os
import json
from typing import Tuple

try:
    import pyotp
except ImportError:
    pyotp = None

from core.config import DATA_DIR

ADMIN_CONFIG_FILE = os.path.join(DATA_DIR, "admin_config.json") if DATA_DIR else None
ADMIN_SESSION_KEY = "nadzor_verified_at"
ADMIN_SESSION_TTL_SEC = 30 * 60  # 30 minut


def _load_admin_config() -> dict:
    if not ADMIN_CONFIG_FILE or not os.path.isfile(ADMIN_CONFIG_FILE):
        return {}
    try:
        with open(ADMIN_CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_admin_config(config: dict) -> None:
    if not ADMIN_CONFIG_FILE:
        return
    try:
        os.makedirs(os.path.dirname(ADMIN_CONFIG_FILE), exist_ok=True)
        with open(ADMIN_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def get_totp_secret() -> str | None:
    """Sekret TOTP: zmienna środowiskowa ADMIN_TOTP_SECRET ma pierwszeństwo, potem plik."""
    secret = os.environ.get("ADMIN_TOTP_SECRET", "").strip()
    if secret:
        return secret
    config = _load_admin_config()
    return (config.get("totp_secret") or "").strip() or None


def set_totp_secret(secret: str) -> None:
    """Zapisuje sekret w pliku (np. po pierwszej generacji)."""
    if not secret:
        return
    config = _load_admin_config()
    config["totp_secret"] = secret.strip()
    _save_admin_config(config)


def generate_totp_secret() -> str:
    """Generuje nowy sekret TOTP (base32)."""
    if pyotp is None:
        raise RuntimeError("Brak biblioteki pyotp. Zainstaluj: pip install pyotp")
    return pyotp.random_base32()


def verify_totp(code: str) -> bool:
    """Sprawdza 6-cyfrowy kod z Authenticatora. Zwraca True jeśli poprawny."""
    if not code or not code.strip():
        return False
    secret = get_totp_secret()
    if not secret or pyotp is None:
        return False
    try:
        totp = pyotp.TOTP(secret)
        return totp.verify(code.strip().replace(" ", ""), valid_window=1)
    except Exception:
        return False


def get_provisioning_uri(label: str = "KopalniaWiedzy-Nadzor") -> str:
    """URI do dodania w Authenticatorze (np. Google Authenticator)."""
    secret = get_totp_secret()
    if not secret or pyotp is None:
        return ""
    return pyotp.TOTP(secret).provisioning_uri(name=label, issuer_name="Kopalnia Wiedzy")


def is_admin_session_valid(now_ts: float) -> bool:
    """Czy sesja nadzoru jest jeszcze ważna (TTL)."""
    import streamlit as st
    verified_at = st.session_state.get(ADMIN_SESSION_KEY)
    if verified_at is None:
        return False
    try:
        return (now_ts - float(verified_at)) < ADMIN_SESSION_TTL_SEC
    except Exception:
        return False


def set_admin_session_valid() -> None:
    """Oznacza sesję jako zalogowaną do nadzoru."""
    import time
    import streamlit as st
    st.session_state[ADMIN_SESSION_KEY] = time.time()


def clear_admin_session() -> None:
    """Wylogowanie z panelu nadzoru."""
    import streamlit as st
    st.session_state.pop(ADMIN_SESSION_KEY, None)
