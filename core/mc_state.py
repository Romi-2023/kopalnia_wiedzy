"""Minecraft mission UI state (st.session_state['mc']).

We keep a single, versioned schema so pages never have to guess keys/types.
The state is JSON-serializable and safe to reset on schema upgrades.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional


MC_SCHEMA_VERSION = 1


def mc_default(today: Optional[str] = None) -> Dict[str, Any]:
    today_str = today or str(date.today())
    return {
        "v": MC_SCHEMA_VERSION,
        "today": today_str,
        "mode": "daily",  # daily | bonus | done
        "step": 0,
        "locked": False,
        "daily": {
            "q": {},
            "ui": {},
            "toast": None,
            "rewarded": False,
            "df_used": None,
        },
        "bonus": {
            "ui": {},
            "toast": None,
            "active_i": 0,
            "done_day": None,
            "finish_reward": None,
        },
    }


def _as_dict(x: Any) -> Dict[str, Any]:
    return x if isinstance(x, dict) else {}


def mc_migrate(existing: Any, today: Optional[str] = None) -> Dict[str, Any]:
    """Upgrade/repair any existing state into the current schema."""
    base = mc_default(today=today)
    cur = _as_dict(existing)
    if not cur:
        return base

    out = base
    for k in ("today", "mode", "step", "locked", "_user", "subject"):
        if k in cur:
            out[k] = cur.get(k)

    out["daily"].update(_as_dict(cur.get("daily")))
    out["bonus"].update(_as_dict(cur.get("bonus")))

    # normalize
    out["v"] = MC_SCHEMA_VERSION
    out["today"] = str(out.get("today") or (today or str(date.today())))
    out["mode"] = str(out.get("mode") or "daily")
    try:
        out["step"] = int(out.get("step") or 0)
    except Exception:
        out["step"] = 0
    out["locked"] = bool(out.get("locked", False))

    # ensure nested
    if not isinstance(out.get("daily"), dict):
        out["daily"] = base["daily"].copy()
    if not isinstance(out.get("bonus"), dict):
        out["bonus"] = base["bonus"].copy()

    out["daily"].setdefault("q", {})
    out["daily"].setdefault("ui", {})
    out["daily"].setdefault("toast", None)
    out["daily"].setdefault("rewarded", False)
    out["daily"].setdefault("df_used", None)
    if not isinstance(out["daily"].get("q"), dict):
        out["daily"]["q"] = {}
    if not isinstance(out["daily"].get("ui"), dict):
        out["daily"]["ui"] = {}

    out["bonus"].setdefault("ui", {})
    out["bonus"].setdefault("toast", None)
    out["bonus"].setdefault("active_i", 0)
    out["bonus"].setdefault("done_day", None)
    out["bonus"].setdefault("finish_reward", None)
    if not isinstance(out["bonus"].get("ui"), dict):
        out["bonus"]["ui"] = {}
    try:
        out["bonus"]["active_i"] = int(out["bonus"].get("active_i") or 0)
    except Exception:
        out["bonus"]["active_i"] = 0

    # day change: reset UI parts; preserve pending finish_reward (Start will consume it)
    today_str = today or str(date.today())
    if str(out.get("today")) != str(today_str):
        pending = _as_dict(out.get("bonus", {})).get("finish_reward")
        out = mc_default(today=today_str)
        if pending:
            out["bonus"]["finish_reward"] = pending
    return out
