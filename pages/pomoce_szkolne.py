# pyright: reportUndefinedVariable=false
from __future__ import annotations

import streamlit as st

from core.state_init import init_core_state, init_router_state, ensure_default_dataset
from core.routing import goto_hard


def _deps() -> dict:
    """Zależności z app_helpers (top_nav_row, card itd.)."""
    import core.app_helpers as ah
    return {k: getattr(ah, k) for k in dir(ah) if not k.startswith("__")}


def render() -> None:
    init_core_state()
    init_router_state(initial_page="Pomoce szkolne")
    st.session_state["page"] = "Pomoce szkolne"
    ensure_default_dataset()

    try:
        globals().update(_deps())
    except Exception as e:
        st.error("❌ Nie udało się załadować zależności.\n\n" + str(e))
        st.stop()

    top_nav_row("🧰 Pomoce szkolne", back_default="Start", show_start=True)

    st.markdown("<div class='big-title'>🧰 Pomoce szkolne</div>", unsafe_allow_html=True)
    st.caption("Powtórki z lektur, streszczenia i przygotowanie do karty rowerowej.")

    st.markdown("---")
    st.markdown("### 📌 Wybierz pomoc")

    st.markdown('<div class="d4k-cardgrid">', unsafe_allow_html=True)

    card(
        "Powtórki z lektur",
        "Plan wydarzeń, postacie, pytania do lektur 📚",
        "📚",
        target="Lektury",
        color="primary",
        key="card_pomoce_powtorki",
    )
    card(
        "Streszczenia",
        "Krótkie i rozszerzone streszczenia lektur 📝",
        "📝",
        target="Lektury",
        color="success",
        key="card_pomoce_streszczenia",
    )
    card(
        "Moja pierwsza karta rowerowa",
        "Nauka, testy i egzamin próbny 🚲",
        "🚲",
        target="Karta rowerowa",
        color="fun",
        key="card_pomoce_rower",
    )

    st.markdown("</div>", unsafe_allow_html=True)


try:
    render()
except Exception:
    pass