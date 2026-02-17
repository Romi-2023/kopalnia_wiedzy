# pages/slowniczek.py – Słowniczek (pojęcia / hasła)
from __future__ import annotations

import json
import os
import streamlit as st

from core.config import BASE_DIR
from core.state_init import init_core_state, init_router_state, ensure_default_dataset
from core.routing import goto_hard


def _load_slowniczek() -> list[dict]:
    """Wczytuje definicje z plików w data/glossary/*.json (klucz=hasło, wartość=definicja)."""
    glossary_dir = os.path.join(BASE_DIR, "data", "glossary")
    out: list[dict] = []
    if not os.path.isdir(glossary_dir):
        return out
    for fname in sorted(os.listdir(glossary_dir)):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(glossary_dir, fname)
        category = fname[:-5].replace("_", " ").strip()  # np. dane_i_statystyka -> dane i statystyka
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                continue
            for term, definition in data.items():
                if term and (definition or "").strip():
                    out.append({
                        "term": term.strip(),
                        "definition": str(definition).strip(),
                        "category": category,
                    })
        except Exception:
            continue
    return out


def _deps() -> dict:
    from core.app_helpers import top_nav_row
    return {"top_nav_row": top_nav_row}


def render() -> None:
    init_core_state()
    init_router_state(initial_page="Słowniczek")
    st.session_state["page"] = "Słowniczek"
    ensure_default_dataset()

    try:
        deps = _deps()
        top_nav_row = deps.get("top_nav_row", lambda *a, **k: None)
    except Exception:
        top_nav_row = lambda *a, **k: None

    top_nav_row("📖 Słowniczek", back_default="Start", show_start=True)

    st.markdown("### 📖 Słowniczek")
    st.caption("Wyjaśnienia pojęć – przydatne przy Misjach i Quizach.")

    entries = _load_slowniczek()
    if not entries:
        st.info("Brak haseł w słowniczku. Umieść pliki JSON w **data/glossary/** (klucz = hasło, wartość = definicja).")
        return

    categories = sorted({e.get("category") or "" for e in entries if e.get("category")})
    col_search, col_cat = st.columns([2, 1])
    with col_search:
        search = st.text_input("🔍 Szukaj pojęcia", placeholder="np. średnia, dane...", key="slowniczek_search")
    with col_cat:
        filter_cat = st.selectbox(
            "Dział",
            ["Wszystkie"] + categories,
            key="slowniczek_category",
        )
    search_lower = (search or "").strip().lower()

    shown = entries
    if filter_cat and filter_cat != "Wszystkie":
        shown = [e for e in shown if (e.get("category") or "") == filter_cat]
    if search_lower:
        shown = [
            e for e in shown
            if search_lower in (e.get("term") or "").lower() or search_lower in (e.get("definition") or "").lower()
        ]

    if not shown:
        st.caption("Nie znaleziono haseł pasujących do wyszukiwania lub filtra.")
        return

    st.caption(f"Hasła: **{len(shown)}**" + (f" z {len(entries)}" if len(shown) != len(entries) else "") + ".")
    st.markdown("---")

    for item in shown:
        term = item.get("term") or "?"
        definition = item.get("definition") or ""
        category = item.get("category") or ""
        label = f"**{term}**" + (f" *({category})*" if category else "")
        with st.expander(label, expanded=False):
            st.markdown(definition)


try:
    render()
except Exception:
    pass
