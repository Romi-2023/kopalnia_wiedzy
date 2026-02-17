# core/state_init.py
from __future__ import annotations

import streamlit as st
from typing import Any, Optional


def ensure_default_dataset() -> None:
    """Misje i quizy oczekują pandas.DataFrame pod kluczem 'data'.

    W trybie multipage / po reloadach łatwo zgubić ten klucz, więc wstawiamy
    bezpieczny default (bez wywalania całej strony).
    """
    if st.session_state.get("data") is not None:
        return

    try:
        from core.app_helpers import make_dataset
        from core.config import DATASETS_PRESETS

        ag = str(st.session_state.get("age_group") or "10-12")
        presets = DATASETS_PRESETS.get(ag) or DATASETS_PRESETS.get("10-12") or {}

        cols = None
        if isinstance(presets, dict):
            cols = presets.get("Średni") or presets.get("Sredni")
            if not cols and len(presets) > 0:
                cols = next(iter(presets.values()))

        if not cols:
            cols = ["wiek", "wzrost_cm", "ulubiony_owoc", "miasto"]

        st.session_state["data"] = make_dataset(140, cols, seed=42)
        st.session_state.setdefault("dataset_name", "auto")
        return
    except Exception:
        # ultra-fallback: minimalny DF bez zależności
        try:
            import pandas as pd

            st.session_state["data"] = pd.DataFrame(
                {
                    "wiek": [10, 11, 12, 13],
                    "wzrost_cm": [140, 145, 150, 155],
                    "ulubiony_owoc": ["jabłko", "banan", "gruszka", "truskawka"],
                    "miasto": ["Kraków", "Warszawa", "Gdańsk", "Wrocław"],
                }
            )
            st.session_state["dataset_name"] = "fallback_auto"
        except Exception:
            pass


def init_router_state(initial_page: str = "Intro") -> None:
    """
    Same defaulty dla routera / nawigacji.
    Zero UI, zero walidacji, tylko brakujące klucze.
    """
    st.session_state.setdefault("page", initial_page)
    st.session_state.setdefault("page_widget", st.session_state.get("page", initial_page))
    st.session_state.setdefault("nav_history", ["Start"])
    st.session_state.setdefault("_goto", None)


def ensure_session_defaults() -> None:
    """
    Twoje bazowe klucze, które MUSZĄ istnieć, żeby UI nie wybuchał.
    Same setdefault, bez żadnych wywołań helperów.
    """
    st.session_state.setdefault("user", None)

    # auth/status
    st.session_state.setdefault("logged_in", False)
    st.session_state.setdefault("guest_mode", False)

    st.session_state.setdefault("xp", 0)
    st.session_state.setdefault("gems", 0)

    st.session_state.setdefault("stickers", set())
    st.session_state.setdefault("badges", set())

    st.session_state.setdefault("missions_state", {})
    st.session_state.setdefault("activity_log", [])

    st.session_state.setdefault("kid_name", "")
    st.session_state.setdefault("age", None)
    st.session_state.setdefault("age_group", "10-12")
    st.session_state.setdefault("dataset_name", None)

    st.session_state.setdefault("unlocked_games", set())
    st.session_state.setdefault("unlocked_avatars", set())
    st.session_state.setdefault("streak", 0)

    st.session_state.setdefault("memory_stats", {})
    # mc (missions UI state) – schema is migrated below
    st.session_state.setdefault("mc", None)

    # onboarding / intro
    st.session_state.setdefault("intro_done", False)
    st.session_state.setdefault("intro_entering", False)
    st.session_state.setdefault("intro_enter_ts", None)

    # UI/day markers
    st.session_state.setdefault("title_animated_date", None)

    # quiz
    st.session_state.setdefault("quiz_data_diff", "medium")

    st.session_state.setdefault("parent_unlocked", False)
    st.session_state.setdefault("class_code", None)

    # avatary
    st.session_state.setdefault("skin_b64", None)
    st.session_state.setdefault("avatar_id", None)

    # profile autosave flags
    st.session_state.setdefault("_profile_dirty", False)
    st.session_state.setdefault("_profile_dirty_fields", set())
    st.session_state.setdefault("_profile_last_autosave_ts", 0.0)

    # --- migrate/repair mc schema (single source of truth) ---
    try:
        from core.mc_state import mc_migrate
        from datetime import date

        st.session_state["mc"] = mc_migrate(st.session_state.get("mc"), today=str(date.today()))
    except Exception:
        # last-resort fallback: do not crash app on init
        st.session_state["mc"] = st.session_state.get("mc") if isinstance(st.session_state.get("mc"), dict) else None


def init_app_state(*, default_data: Optional[Any] = None) -> None:
    """
    To jest ten blok 'defaults = {...}' z app.py – przeniesiony do modułu.
    Uwaga: default_data wstrzykujemy z app.py, bo make_dataset jest w app.py.
    """
    # --- twarde defaulty sesji (bezpieczne) ---
    ensure_session_defaults()

    # --- elementy, które były w Twoim defaults dict ---
    st.session_state.setdefault("hall_of_fame", [])
    st.session_state.setdefault("last_quest", None)
    st.session_state.setdefault("todays", None)
    st.session_state.setdefault("kids_mode", True)

    # dataset (wstrzyknięty)
    if default_data is not None and "data" not in st.session_state:
        st.session_state["data"] = default_data


def init_core_state() -> None:
    """Alias utrzymujący kompatybilność ze starym app.py.

    Po modularyzacji część plików (bootstrap) importuje init_core_state().
    Trzymamy to jako cienką nakładkę na init_app_state().
    """
    # 1) session defaults
    init_app_state(default_data=None)

    # 2) persistence MUST be initialized once per session.
    #    Po modularyzacji łatwo było to pominąć – efekt: brak kont,
    #    brak zapisu misji, "Nieprawidłowy login" mimo poprawnych danych.
    try:
        import os
        from core.config import DATA_DIR
        from core.persistence import init_persistence, ensure_kv_table

        # Preferuj DB url z secrets/env, ale aplikacja ma działać bez DB (file fallback).
        database_url = None
        try:
            database_url = st.secrets.get("DATABASE_URL")  # type: ignore[attr-defined]
        except Exception:
            database_url = None
        if not database_url:
            database_url = os.environ.get("DATABASE_URL")

        # psycopg2 opcjonalne – tylko jeśli DB URL istnieje
        psycopg2_module = None
        if database_url:
            try:
                import psycopg2  # type: ignore
                psycopg2_module = psycopg2
            except Exception:
                psycopg2_module = None

        init_persistence(data_dir=DATA_DIR, database_url=database_url, psycopg2_module=psycopg2_module)
        ensure_kv_table()

        # Codzienne kasowanie kont gości (Gosc-*) po zakończeniu dnia
        try:
            from core.persistence import run_daily_guest_cleanup_if_needed
            run_daily_guest_cleanup_if_needed()
        except Exception:
            pass

        # Jeśli użytkownik jest „zalogowany” w sesji, ale nie ma go już w bazie (np. po clear_all_users) – wyloguj.
        from core.persistence import _load_users
        u = st.session_state.get("user")
        if u and isinstance(u, str) and not u.startswith("Gosc-"):
            db = _load_users() or {}
            if u not in db:
                st.session_state["user"] = None
                st.session_state["logged_in"] = False
                st.session_state["mc"] = None
                st.session_state["kid_name"] = ""
                st.session_state["xp"] = 0
                st.session_state["gems"] = 0
                st.session_state["stickers"] = set()
                st.session_state["badges"] = set()
                st.session_state["streak"] = 0
    except Exception:
        # Persistencja ma nie wywalać UI.
        pass

def is_guest() -> bool:
    """Gość = tylko user typu 'Gosc-1234'. None to po prostu niezalogowany."""
    u = st.session_state.get("user")
    return isinstance(u, str) and u.startswith("Gosc-")

def is_logged_in() -> bool:
    """Zalogowany = user istnieje i nie jest gościem."""
    u = st.session_state.get("user")
    return bool(u) and not is_guest()


def is_parent_mode() -> bool:
    # u Ciebie: parent_unlocked + zakładka “Dla rodzica”
    return bool(st.session_state.get("parent_unlocked", False)) and (not st.session_state.get("kids_mode", True))
