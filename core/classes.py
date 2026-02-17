# core/classes.py
from __future__ import annotations

import re
import secrets
from datetime import datetime
from typing import Tuple, Optional

import streamlit as st
from core.persistence import _load_classes, _save_classes

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # bez I,O,0,1 (czytelność)
CODE_LEN = 6


def _generate_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LEN))


def create_class(label: str, created_by: str) -> Tuple[Optional[str], str]:
    """Tworzy klasę i zwraca (kod_klasy, komunikat). Nauczyciel dostaje kod do rozdania dzieciom."""
    label = (label or "").strip()[:60] or "Klasa"
    if not (created_by or "").strip():
        return None, "Musisz być zalogowany, aby utworzyć klasę."

    classes = _load_classes() or {}
    for _ in range(20):
        code = _generate_code()
        if code not in classes:
            break
    else:
        return None, "Nie udało się wygenerować unikalnego kodu. Spróbuj ponownie."

    rec = {
        "label": label,
        "created_by": created_by,
        "members": [],
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    classes[code] = rec
    _save_classes(classes)
    return code, f"Utworzono klasę **{label}**. Kod do podania dzieciom: **{code}**"


def get_class_info(code: str) -> Optional[dict]:
    """Zwraca dane klasy (label, members, ...) lub None."""
    code = (code or "").strip().upper()
    if not code:
        return None
    classes = _load_classes() or {}
    return classes.get(code) if isinstance(classes.get(code), dict) else None


def list_classes_by_teacher(created_by: str) -> list:
    """Zwraca listę klas utworzonych przez danego użytkownika (nauczyciela)."""
    if not (created_by or "").strip():
        return []
    classes = _load_classes() or {}
    out = []
    for code, rec in classes.items():
        if isinstance(rec, dict) and rec.get("created_by") == created_by:
            members = rec.get("members") or []
            out.append({"code": code, "label": rec.get("label", ""), "members": members, "rec": rec})
    return sorted(out, key=lambda x: x.get("rec", {}).get("created_at", ""), reverse=True)


def join_class(class_code: str, nick: str) -> Tuple[bool, str]:
    code = (class_code or "").strip().upper()
    if not code:
        return False, "Podaj kod klasy."
    if not re.match(r"^[A-Z0-9\-]{3,20}$", code):
        return False, "Kod wygląda podejrzanie."
    nick = (nick or "").strip()[:40] or "Gracz"

    classes = _load_classes() or {}
    rec = classes.get(code)
    if not isinstance(rec, dict):
        # allow join only if class exists
        return False, "Nie znaleziono klasy o takim kodzie."

    members = rec.get("members") or []
    if not isinstance(members, list):
        members = []
    # store nick (and optionally user)
    user = st.session_state.get("user") or ""
    entry = {"nick": nick, "user": user} if user else {"nick": nick}
    members.append(entry)
    # keep last 200
    rec["members"] = members[-200:]
    classes[code] = rec
    _save_classes(classes)
    st.session_state["class_code"] = code
    return True, "Dołączono do klasy!"
