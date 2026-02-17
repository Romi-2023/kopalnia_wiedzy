# pyright: reportUndefinedVariable=false
from __future__ import annotations

import json
import os
import streamlit as st

from core.state_init import init_core_state, init_router_state, ensure_default_dataset
from core.routing import goto_hard


def _deps() -> dict:
    import core.app_helpers as ah
    return {k: getattr(ah, k) for k in dir(ah) if not k.startswith("__")}


def _load_lektury() -> dict:
    path = os.path.join("data", "lektury.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def render() -> None:
    init_core_state()
    init_router_state(initial_page="Lektury")
    st.session_state["page"] = "Lektury"
    ensure_default_dataset()

    try:
        globals().update(_deps())
    except Exception as e:
        st.error("❌ Nie udało się załadować zależności.\n\n" + str(e))
        st.stop()

    top_nav_row("📚 Lektury", back_default="Pomoce szkolne", show_start=True)

    st.markdown("<div class='big-title'>📚 Lektury</div>", unsafe_allow_html=True)
    st.caption("Powtórki z lektur i streszczenia – wybierz zakładkę poniżej.")

    lektury_data = _load_lektury()
    age_group = get_age_group() if "get_age_group" in globals() else "10-12"
    books = lektury_data.get(age_group, lektury_data.get("10-12", []))

    if not books:
        st.warning("Brak lektur dla Twojej grupy wiekowej. Wybierz inną zakładkę lub wróć później.")
        if st.button("⬅️ Wróć do Pomocy szkolnych", use_container_width=True):
            goto_hard("Pomoce szkolne")
        return

    tab_powtorki, tab_streszczenia = st.tabs(["📋 Powtórki z lektur", "📝 Streszczenia"])

    with tab_powtorki:
        st.markdown("### Plan wydarzeń, postacie, pytania")
        for b in books:
            title = b.get("title", "Bez tytułu")
            author = b.get("author", "")
            with st.expander(f"**{title}** — {author}"):
                if b.get("plan"):
                    st.markdown("**Plan wydarzeń:**")
                    for i, p in enumerate(b["plan"], 1):
                        st.markdown(f"{i}. {p}")
                if b.get("characters"):
                    st.markdown("**Postacie:**")
                    for c in b["characters"]:
                        st.markdown(f"- {c}")
                if b.get("themes"):
                    st.markdown("**Motywy:**")
                    for t in b["themes"]:
                        st.markdown(f"- {t}")
                if b.get("questions"):
                    st.markdown("**Pytania do lektury:**")
                    for q in b["questions"]:
                        st.markdown(f"- {q}")
                if b.get("quotes"):
                    st.markdown("**Cytaty:**")
                    for q in b["quotes"]:
                        st.markdown(f"> {q}")

    with tab_streszczenia:
        st.markdown("### Krótkie i rozszerzone streszczenia")
        for b in books:
            title = b.get("title", "Bez tytułu")
            author = b.get("author", "")
            with st.expander(f"**{title}** — {author}"):
                short = b.get("summary_short", "")
                if short:
                    st.markdown("**Streszczenie krótkie:**")
                    st.markdown(short)
                long_ = b.get("summary_long", "")
                if long_:
                    st.markdown("**Streszczenie rozszerzone:**")
                    st.markdown(long_.replace("\n\n", "\n\n"))


try:
    render()
except Exception:
    pass
