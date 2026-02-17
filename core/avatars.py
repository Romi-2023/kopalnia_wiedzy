# core/avatars.py
from __future__ import annotations

import os
from typing import Dict, List, Optional

from core.config import ASSETS_DIR
from core.ui import _bytes_to_b64

# extracted from app.py (single source)
AVATAR_META = {
  # ------------------------------------------------------------
  # GOŚĆ (darmowe i TYLKO dla gościa) — dokładnie te 6
  # ------------------------------------------------------------
  "cat_miner":      {"name": "Kot Górnik (Gość)",          "group": "guest",      "unlock": {"type": "guest"}},
  "hero":           {"name": "Bohater (Gość)",             "group": "guest",      "unlock": {"type": "guest"}},
  "miner":          {"name": "Górnik (Gość)",              "group": "guest",      "unlock": {"type": "guest"}},
  "thief":          {"name": "Złodziejaszek (Gość)",       "group": "guest",      "unlock": {"type": "guest"}},
  "scientist":      {"name": "Naukowiec (Gość)",           "group": "guest",      "unlock": {"type": "guest"}},
  "young_wizard":   {"name": "Młody Czarodziej (Gość)",    "group": "guest",      "unlock": {"type": "guest"}},

  # ------------------------------------------------------------
  # ZALOGOWANI (darmowe)
  # ------------------------------------------------------------
  "cat_scientist":  {"name": "Kot Naukowiec",              "group": "starter",    "unlock": {"type": "free"}},
  "miner_1":        {"name": "Górnik",                     "group": "starter",    "unlock": {"type": "free"}},
  "scientist_1":    {"name": "Naukowiec 1",                "group": "starter",    "unlock": {"type": "free"}},

  # ------------------------------------------------------------
  # OD BLOKUJ / KUP (XP / poziom / diamenty) — reszta
  # Uwaga: "combo" oznacza warunek poziomu + koszt (XP i/lub 💎).
  # ------------------------------------------------------------
  "scientist_2":    {"name": "Naukowiec 2",                "group": "knowledge",  "unlock": {"type": "combo", "level": 7,  "xp": 90,  "gems": 0}},
  "wizard":         {"name": "Czarodziej Wiedzy",          "group": "fantasy",    "unlock": {"type": "combo", "level": 10, "xp": 140, "gems": 0}},
  "dwarf":          {"name": "Krasnolud",                  "group": "adventure",  "unlock": {"type": "combo", "level": 12, "xp": 180, "gems": 1}},
  "scientist_3":    {"name": "Naukowiec 3",                "group": "knowledge",  "unlock": {"type": "combo", "level": 14, "xp": 240, "gems": 1}},
  "defender":       {"name": "Obrońca Kopalni",            "group": "legendary",  "unlock": {"type": "combo", "level": 16, "xp": 320, "gems": 2}},
  "bomber":         {"name": "Bombowiec",                  "group": "fun",        "unlock": {"type": "combo", "level": 18, "xp": 0,   "gems": 3}},
  "miner_bomber":   {"name": "Górnik Saper",               "group": "fun",        "unlock": {"type": "combo", "level": 22, "xp": 0,   "gems": 5}},
  "fairy":          {"name": "Wróżka Inżynier",            "group": "fantasy",    "unlock": {"type": "combo", "level": 24, "xp": 260, "gems": 3}},
  "scientist_4":    {"name": "Naukowiec 4",                "group": "knowledge",  "unlock": {"type": "combo", "level": 26, "xp": 420, "gems": 2}},
  "miner_robot":    {"name": "Górnik Robot",               "group": "premium",    "unlock": {"type": "combo", "level": 28, "xp": 0,   "gems": 7}},
  "fairy_queen":    {"name": "Królowa Wróżek",             "group": "premium",    "unlock": {"type": "combo", "level": 32, "xp": 0,   "gems": 10}},
  "king":           {"name": "Król Kopalni",               "group": "premium",    "unlock": {"type": "combo", "level": 36, "xp": 0,   "gems": 12}},
  "dragon":         {"name": "Smok Kryptonitu",            "group": "premium",    "unlock": {"type": "combo", "level": 40, "xp": 0,   "gems": 15}},
  "portal_premium": {"name": "Portal Premium",             "group": "premium",    "unlock": {"type": "combo", "level": 45, "xp": 0,   "gems": 18}},
  "ovl":            {"name": "OVL (Sekretny)",              "group": "premium",    "unlock": {"type": "combo", "level": 50, "xp": 0,   "gems": 20}},
}

def list_builtin_avatars() -> List[dict]:
    """Lista wbudowanych avatarów.

    UI w kilku miejscach oczekuje listy obiektów z polem `id`.
    W starym kodzie istniało też pole `path` – ścieżka do pliku PNG.
    Tutaj odtwarzamy to zachowanie, żeby uniknąć KeyError.
    """
    out: List[dict] = []
    if isinstance(AVATAR_META, dict):
        for key, meta in AVATAR_META.items():
            m = dict(meta or {})
            m.setdefault("name", str(key))
            m.setdefault("group", "starter")
            m.setdefault("unlock", {"type": "free"})
            m["id"] = key

            # Back-compat: ścieżka i nazwa pliku jak w starej wersji
            path = _avatar_path(key)
            m.setdefault("file", os.path.basename(path))
            m.setdefault("path", path)

            out.append(m)
    return out

def _avatar_path(avatar_key: str) -> str:
    # Most files are named exactly like the key, fallback to meta 'file' if present
    meta = AVATAR_META.get(avatar_key, {}) if isinstance(AVATAR_META, dict) else {}
    fname = meta.get("file") or f"{avatar_key}.png"
    return os.path.join(ASSETS_DIR, "avatars", fname)

def get_avatar_image_bytes(avatar_key: str) -> bytes:
    path = _avatar_path(avatar_key)
    try:
        with open(path, "rb") as f:
            return f.read()
    except Exception:
        return b""

def get_frame_for_user(user: str | None, level: int, is_guest: bool = False) -> str:
    """Zwraca klasę CSS ramki avatara.

    - `level` oczekujemy w skali 0..100
    - gość zawsze `frame-wood`
    """
    if is_guest or (not user) or str(user).startswith("Gosc-"):
        return "frame-wood"

    try:
        lvl = int(level)
    except Exception:
        lvl = 0
    lvl = max(0, min(100, lvl))

    # Progi (propozycja startowa):
    # wood: 0–9, stone: 10–24, copper: 25–39, iron: 40–59,
    # gold: 60–79, diamond: 80–94, netherite: 95–100
    if lvl >= 95:
        return "frame-netherite"
    if lvl >= 80:
        return "frame-diamond"
    if lvl >= 60:
        return "frame-gold"
    if lvl >= 40:
        return "frame-iron"
    if lvl >= 25:
        return "frame-copper"
    if lvl >= 10:
        return "frame-stone"
    return "frame-wood"


def get_avatar_frame(user: str | None, level: int = 0) -> str:
    """Back-compat: stara nazwa funkcji używana w kilku miejscach."""
    return get_frame_for_user(user=user, level=level, is_guest=False)
