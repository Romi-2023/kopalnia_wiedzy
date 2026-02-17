# app.py (slim bootstrap)
from __future__ import annotations

import streamlit as st

# Wyłączenie tylko komunikatów systemowych (info/warning); poprawność odpowiedzi i nagrody zostają.
def _noop(*args, **kwargs):
    pass
st.info = _noop
st.warning = _noop

from core.state_init import init_core_state, init_router_state, ensure_default_dataset
from core.theme import apply_theme
from core.routing import apply_router, dispatch, VALID_PAGES
from ui.bottom_nav import bottom_nav
from core.profile import autosave_if_dirty

 # (dataset fallback jest w core.state_init.ensure_default_dataset)

def _apply_extra_css() -> None:
    """Load optional CSS file from ui/minecraft.css if present."""
    try:
        with open("ui/minecraft.css", "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except Exception:
        # CSS is optional; theme.py already injects base styling.
        pass


### Dataset fallback przeniesiony do core.state_init.ensure_default_dataset()


def main() -> None:
    st.set_page_config(
        page_title="Kopalnia Wiedzy",
        page_icon="🟩",
        layout="wide",
        initial_sidebar_state="collapsed",
        menu_items=None,
    )

    # --- 1) minimal state defaults ---
    init_core_state()
    init_router_state(initial_page="Intro")

    # --- 2) dataset must exist for Misje/Quiz ---
    ensure_default_dataset()

    # --- 3) router (URL <-> session) ---
    apply_router(show_sidebar_nav=False)

    # --- 4) global style ---
    apply_theme(page=str(st.session_state.get("page", "")))
    _apply_extra_css()

    # --- 5) render current page ---
    dispatch()

    # --- 6) one safe autosave point per rerun ---
    try:
        autosave_if_dirty(force=False)
    except Exception:
        pass
    # --- 7) mobile bottom navigation (bez paska na panelu nadzoru) ---
    if st.session_state.get("page") != "Nadzor":
        bottom_nav(valid_pages=VALID_PAGES)
    return  # nie zwracaj obiektu Streamlit (DeltaGenerator), żeby nie wyświetlał się w IDE


if __name__ == "__main__":
    main()
