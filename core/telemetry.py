# core/telemetry.py
from __future__ import annotations

"""
core.telemetry

Jedno, stabilne API do logowania zdarzeń.

Zasady:
- import tego modułu NIE MA side-effectów
- log_event(...) NIGDY nie wywala aplikacji
- jedna ścieżka logów (LOGS_DIR z core.config)
"""

from typing import Optional, Dict, Any
from datetime import datetime
import json
import os

from core.config import LOGS_DIR


def log_event(event: str, meta: Optional[Dict[str, Any]] = None) -> None:
    """Bezpieczne logowanie eventów (sesja + plik).

    Ta funkcja:
    - nigdy nie rzuca wyjątku na zewnątrz
    - może być wołana z dowolnego miejsca (pages/core/helpers)
    """
    try:
        # --- rekord kanoniczny ---
        record = {
            "ts": datetime.utcnow().isoformat(),
            "event": str(event),
            "meta": meta or {},
        }

        # --- 1) spróbuj bogaty logger (session_state itp.) ---
        try:
            from core.app_helpers import log_event as _rich_log_event
        except Exception:
            _rich_log_event = None

        if callable(_rich_log_event):
            try:
                _rich_log_event(str(event), meta)
            except Exception:
                pass  # nawet bogaty logger nie może nas wywalić

        # --- 2) ZAWSZE spróbuj zapisać do pliku ---
        try:
            os.makedirs(LOGS_DIR, exist_ok=True)
            log_path = os.path.join(LOGS_DIR, "app.log")
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as e:
            # tylko print — zero raise
            print("LOG ERROR:", e)

    except Exception:
        # absolutnie nic nie propagujemy
        return
