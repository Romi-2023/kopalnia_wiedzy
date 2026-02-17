from __future__ import annotations

import random
import time
import streamlit as st

from core.state_init import init_core_state, init_router_state, ensure_default_dataset
from core.routing import go_back_hard


def render() -> None:
    # ✅ multipage-safe bootstrap
    init_core_state()
    init_router_state(initial_page="Plac zabaw")
    st.session_state["page"] = "Plac zabaw"
    ensure_default_dataset()

    st.title("🎮 Plac zabaw")
    st.caption("Szybkie mini‑zabawy bez ryzyka i bez utraty postępów.")

    st.markdown("---")

    # --- Mini‑gra 1: Szybki klik ---
    st.subheader("⚡ Szybki klik (10 sekund)")
    if "play_clicks" not in st.session_state:
        st.session_state["play_clicks"] = 0
    if "play_start_ts" not in st.session_state:
        st.session_state["play_start_ts"] = None

    col1, col2 = st.columns(2)
    with col1:
        if st.button("▶️ Start", use_container_width=True, key="play_clicks_start"):
            st.session_state["play_clicks"] = 0
            st.session_state["play_start_ts"] = time.time()
    with col2:
        if st.button("🧹 Reset", use_container_width=True, key="play_clicks_reset"):
            st.session_state["play_clicks"] = 0
            st.session_state["play_start_ts"] = None

    start_ts = st.session_state.get("play_start_ts")
    if start_ts:
        elapsed = time.time() - start_ts
        remaining = max(0, 10 - int(elapsed))
        st.caption(f"Pozostało: **{remaining}s**")

        if elapsed <= 10:
            if st.button("🟢 Klik!", use_container_width=True, key="play_clicks_btn"):
                st.session_state["play_clicks"] += 1
                st.rerun()
        else:
            st.success(f"Koniec! Wynik: **{st.session_state['play_clicks']}** klików.")

    if not start_ts:
        st.info(f"Wynik: **{st.session_state['play_clicks']}** klików")

    st.markdown("---")

    # --- Mini‑gra 2: Rzut kostką ---
    st.subheader("🎲 Rzut kostką")
    if "play_dice" not in st.session_state:
        st.session_state["play_dice"] = None
    if st.button("🎲 Rzuć", use_container_width=True, key="play_dice_btn"):
        st.session_state["play_dice"] = random.randint(1, 6)
    if st.session_state.get("play_dice"):
        st.write(f"Wypadło: **{st.session_state['play_dice']}**")

    st.markdown("---")

    # --- Mini‑gra 3: Moneta ---
    st.subheader("🪙 Orzeł czy reszka")
    if "play_coin" not in st.session_state:
        st.session_state["play_coin"] = None
    if st.button("🪙 Rzuć monetą", use_container_width=True, key="play_coin_btn"):
        st.session_state["play_coin"] = random.choice(["Orzeł", "Reszka"])
    if st.session_state.get("play_coin"):
        st.write(f"Wypadło: **{st.session_state['play_coin']}**")

    st.markdown("---")
    if st.button("⬅️ Wróć na Start", use_container_width=True, key="play_back"):
        go_back_hard("Start")


# Multipage (st.switch_page): uruchom render() także przy wejściu bez routera
try:
    render()
except Exception:
    pass
