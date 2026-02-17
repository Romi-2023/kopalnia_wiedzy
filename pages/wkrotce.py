from __future__ import annotations

import streamlit as st

from core.state_init import init_core_state, init_router_state, ensure_default_dataset
from core.routing import go_back_hard


def render() -> None:
    # ✅ multipage-safe bootstrap
    init_core_state()
    init_router_state(initial_page="Wkrótce")
    st.session_state["page"] = "Wkrótce"
    ensure_default_dataset()

    st.title("🧱 Portal w budowie")

    portal = str(st.session_state.get("portal_target") or "").strip()
    if portal:
        st.info(f"**{portal}** jest w trakcie budowy. Już wkrótce będzie dostępny.")
    else:
        st.info("Ten portal jest w trakcie budowy. Już wkrótce będzie dostępny.")

    st.markdown("---")
    if st.button("⬅️ Wróć na Start", use_container_width=True, key="wkrotce_back"):
        go_back_hard("Start")


# Multipage (st.switch_page): uruchom render() także przy wejściu bez routera
try:
    render()
except Exception:
    pass
