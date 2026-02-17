# core/security.py
from __future__ import annotations

import json
import os
import re
import secrets
import hashlib
from typing import Tuple

from core.config import DATA_DIR
from core.persistence import kv_get_json, kv_set_json, read_json_file, write_json_file_atomic

PARENT_PIN_FILE = os.path.join(DATA_DIR, "parent_pin.json")
FORBIDDEN_LOGINS_FILE = os.path.join(DATA_DIR, "forbidden_logins.txt")

# Wymagania: login 7–20 znaków; hasło min 8 znaków, min 1 litera i 1 cyfra
LOGIN_MIN_LEN = 7
LOGIN_MAX_LEN = 20
LOGIN_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
PASSWORD_MIN_LEN = 8
PASSWORD_NEEDS_LETTER = True
PASSWORD_NEEDS_DIGIT = True


def _load_forbidden_logins() -> set:
    """Wczytuje listę niedozwolonych słów z data/forbidden_logins.txt."""
    out = set()
    path = FORBIDDEN_LOGINS_FILE
    if not path or not os.path.isfile(path):
        return out
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip().lower()
                if line and not line.startswith("#"):
                    out.add(line)
    except Exception:
        pass
    return out


def validate_login(login: str) -> Tuple[bool, str]:
    """
    Sprawdza login: długość 7–20, znaki A–Z a–z 0–9 _ -, brak wulgaryzmów.
    Zwraca (True, "") gdy OK, (False, "komunikat błędu") gdy nie.
    """
    s = (login or "").strip()
    if len(s) < LOGIN_MIN_LEN:
        return False, f"Login musi mieć co najmniej {LOGIN_MIN_LEN} znaków."
    if len(s) > LOGIN_MAX_LEN:
        return False, f"Login może mieć co najwyżej {LOGIN_MAX_LEN} znaków."
    if not LOGIN_PATTERN.fullmatch(s):
        return False, "Login: tylko litery, cyfry oraz znaki _ i - (bez spacji)."
    low = s.lower()
    forbidden = _load_forbidden_logins()
    if low in forbidden:
        return False, "Ten login jest niedozwolony."
    for word in forbidden:
        if word and word in low:
            return False, "Login zawiera niedozwolone słowo."
    return True, ""


def validate_password(password: str) -> Tuple[bool, str]:
    """
    Sprawdza hasło: min 8 znaków, co najmniej jedna litera i jedna cyfra.
    Zwraca (True, "") gdy OK, (False, "komunikat błędu") gdy nie.
    """
    p = password or ""
    if len(p) < PASSWORD_MIN_LEN:
        return False, f"Hasło musi mieć co najmniej {PASSWORD_MIN_LEN} znaków."
    if PASSWORD_NEEDS_LETTER and not re.search(r"[A-Za-z]", p):
        return False, "Hasło musi zawierać co najmniej jedną literę."
    if PASSWORD_NEEDS_DIGIT and not re.search(r"\d", p):
        return False, "Hasło musi zawierać co najmniej jedną cyfrę."
    return True, ""

def hash_text(text: str) -> str:
    return hashlib.sha256(str(text).encode("utf-8")).hexdigest()

def hash_pw(password: str, salt: str) -> str:
    return hashlib.sha256((str(password) + str(salt)).encode("utf-8")).hexdigest()

def _load_pin_file() -> dict:
    return read_json_file(PARENT_PIN_FILE, {}) or {}


def _save_pin_file(rec: dict) -> None:
    try:
        os.makedirs(os.path.dirname(PARENT_PIN_FILE), exist_ok=True)
    except Exception:
        pass
    write_json_file_atomic(PARENT_PIN_FILE, rec)


def _ensure_parent_pin_record() -> None:
    rec = kv_get_json("parent_pin", None)
    if rec is None:
        rec = _load_pin_file() or None
    if not isinstance(rec, dict) or "salt" not in rec or "hash" not in rec:
        # default PIN: 0000 (user can change later)
        salt = secrets.token_hex(8)
        h = hash_text(salt + "0000")
        rec = {"salt": salt, "hash": h}
        kv_set_json("parent_pin", rec)
        _save_pin_file(rec)

def get_parent_pin_record() -> Tuple[str, str]:
    _ensure_parent_pin_record()
    rec = kv_get_json("parent_pin", None)
    if rec is None:
        rec = _load_pin_file()
    if not isinstance(rec, dict):
        return ("", "")
    return str(rec.get("salt","")), str(rec.get("hash",""))

def set_parent_pin(new_pin: str) -> None:
    _ensure_parent_pin_record()
    salt = secrets.token_hex(8)
    h = hash_text(salt + str(new_pin))
    rec = {"salt": salt, "hash": h}
    kv_set_json("parent_pin", rec)
    _save_pin_file(rec)

def verify_parent_pin(pin: str) -> bool:
    salt, h = get_parent_pin_record()
    if not salt or not h:
        return False
    return hash_text(salt + str(pin)) == h
