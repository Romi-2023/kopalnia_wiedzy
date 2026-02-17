# pyright: reportUndefinedVariable=false
from __future__ import annotations

import streamlit as st

from core.state_init import init_core_state, init_router_state, ensure_default_dataset
from core.routing import goto_hard


# Katalog naklejek: id -> (nazwa, emoji, skąd zdobyć)
STICKER_CATALOG = {
    "sticker_daily": ("Misja dnia", "📅", "Ukończ misję dnia"),
    "sticker_freeze": ("Zamrożenie", "❄️", "Bonus w misjach"),
    "sticker_bonus_master": ("Mistrz bonusów", "⭐", "Ukończ wszystkie 3 bonusy"),
    "sticker_lootbox": ("Skrzynka", "📦", "Otwórz skrzynkę"),
    "sticker_math": ("Matematyka", "🔢", "Misja: Matematyczny rozruch"),
    "sticker_lang": ("Język polski", "📖", "Misja: Polonistyczny skok"),
    "sticker_history": ("Historia", "🏛️", "Misja: Historyczna podróż"),
    "sticker_geo": ("Geografia", "🌍", "Misja: Geo-ekspedycja"),
    "sticker_phys": ("Fizyka", "⚛️", "Misja: Fizyczne laboratorium"),
    "sticker_chem": ("Chemia", "🧪", "Misja: Chemiczny miks"),
    "sticker_eng": ("Angielski", "📘", "Misja: English boost"),
    "sticker_bio": ("Biologia", "🧬", "Misja: Bio-misja"),
    "sticker_combo": ("Dobra passa", "🔥", "3 poprawne odpowiedzi z rzędu"),
    "sticker_master": ("Mistrz dnia", "👑", "20 pytań w jeden dzień"),
}


def _deps() -> dict:
    import core.app_helpers as ah
    return {k: getattr(ah, k) for k in dir(ah) if not k.startswith("__")}


def render() -> None:
    init_core_state()
    init_router_state(initial_page="Album naklejek")
    st.session_state["page"] = "Album naklejek"
    ensure_default_dataset()

    try:
        globals().update(_deps())
    except Exception as e:
        st.error("❌ Nie udało się załadować zależności.\n\n" + str(e))
        st.stop()

    top_nav_row("🗂️ Album naklejek", back_default="Start", show_start=True)

    st.markdown("<div class='big-title'>🗂️ Album naklejek</div>", unsafe_allow_html=True)

    user = st.session_state.get("user")
    if not user or (isinstance(user, str) and user.startswith("Gosc-")):
        st.info("Album naklejek jest dla zalogowanych. Zaloguj się, żeby zbierać i oglądać naklejki.")
        if st.button("⬅️ Wróć na Start", use_container_width=True):
            goto_hard("Start")
        return

    stickers = st.session_state.get("stickers", set())
    if not isinstance(stickers, set):
        stickers = set(stickers or [])

    collected = [sid for sid in STICKER_CATALOG if sid in stickers]
    missing = [sid for sid in STICKER_CATALOG if sid not in stickers]

    st.caption(f"Zebrane: **{len(collected)} / {len(STICKER_CATALOG)}** naklejek")
    st.markdown("---")

    st.markdown("### 🏷️ Twoje naklejki")
    st.markdown('<div class="d4k-cardgrid">', unsafe_allow_html=True)

    for sid in STICKER_CATALOG:
        name, emoji, hint = STICKER_CATALOG[sid]
        has_it = sid in stickers
        if has_it:
            st.markdown(
                f"""
                <div class="d4k-card" style="opacity:1;">
                    <div class="d4k-card__title">{emoji} {name}</div>
                    <div class="d4k-card__sub">{hint}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"""
                <div class="d4k-card" style="opacity:0.6;">
                    <div class="d4k-card__title">❓ ???</div>
                    <div class="d4k-card__sub">{name} – zbierz w misjach!</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("---")
    st.caption("Naklejki zdobywasz za ukończenie misji dnia, bonusów i zadań. Graj dalej, żeby zapełnić album! 🎯")


try:
    render()
except Exception:
    pass
