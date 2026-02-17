# pyright: reportUndefinedVariable=false
import streamlit as st

from core.state_init import init_core_state, init_router_state, ensure_default_dataset
from core.routing import goto_hard


def _deps() -> dict:
    """Zbiera zależności bez importu app.py (żeby uniknąć kółek)."""
    import core.app_helpers as ah
    from core import missions as ms
    deps = {k: getattr(ah, k) for k in dir(ah) if not k.startswith('__')}
    deps.update({k: getattr(ms, k) for k in dir(ms) if not k.startswith('__')})
    return deps


def render():
    # ✅ multipage-safe bootstrap
    init_core_state()
    init_router_state(initial_page="Skrzynka")
    st.session_state["page"] = "Skrzynka"
    ensure_default_dataset()
    # ---- wstrzyknięcie zależności (tylko wymagane symbole) ----
    try:
        globals().update(_deps())
    except Exception as e:
        st.error(
            "❌ Nie udało się załadować zależności skrzynki z app.py.\n\n"
            f"Szczegóły: {e}"
        )
        st.stop()

    kid_emoji = globals().get("KID_EMOJI", "🧒")

    log_event("page_skrzynka")
    top_nav_row("📦 Skrzynka", back_default="Start", show_start=True)

    # ---- UI ----
    st.markdown(f"<div class='big-title'>💎 {kid_emoji} Skrzynka</div>", unsafe_allow_html=True)

    # ---- dostęp tylko dla zalogowanych ----
    user = st.session_state.get("user")
    if not user or (isinstance(user, str) and user.startswith("Gosc-")):
        st.info("Skrzynka jest dla zalogowanych. Gość może grać w misje, ale 💎 odkłada się do konta 🙂")
        st.stop()

    # ---- saldo ----
    gems = int(st.session_state.get("gems", 0))
    st.markdown(f"### Masz teraz: **💎 {gems}**")
    st.caption("💡 Diamenty dostajesz za osiągnięcia / misje (a my zaraz podepniemy kolejne źródła 💎).")

    st.markdown("---")
    SAPER_GAME_ID = "saper"
    SAPER_UNLOCK_COST = 5

    st.markdown("## 💣 Gra Saper (odblokowanie)")

    if is_game_unlocked(SAPER_GAME_ID):
        st.success("Gra Saper jest już odblokowana ✅")
        if st.button("💣 Wejdź do Gry Saper", use_container_width=True):
            goto_hard("Saper")
            st.stop()
    else:
        st.info(f"Koszt odblokowania: **💎 {SAPER_UNLOCK_COST}**")

        if gems < SAPER_UNLOCK_COST:
            st.warning("Masz za mało 💎 — wróć po misjach 😉")

        if st.button(f"🔓 Odblokuj za 💎 {SAPER_UNLOCK_COST}", use_container_width=True):
            ok = unlock_game(SAPER_GAME_ID, SAPER_UNLOCK_COST)
            if ok:
                anim = load_lottie(os.path.join(BASE_DIR, "assets", "Diamonds.json"))
                if anim:
                    st_lottie(anim, speed=1.0, loop=False, height=220, key="lottie_unlock_saper")
                st.success("Odblokowano! ✨")

                if st.button("➡️ Startuj Saper", use_container_width=True):
                    goto_hard("Saper")
                    st.stop()
            else:
                st.error("Nie udało się odblokować (za mało 💎).")


# Multipage (st.switch_page): uruchom render() także przy wejściu bez routera
try:
    render()
except Exception as e:
    try:
        from core.ui import show_exception
        show_exception(e)
    except Exception:
        pass
