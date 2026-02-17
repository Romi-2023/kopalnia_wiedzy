# pyright: reportUndefinedVariable=false
from __future__ import annotations

import streamlit as st

from core.state_init import init_core_state, init_router_state, ensure_default_dataset
from core.routing import goto_hard


def _deps() -> dict:
    import core.app_helpers as ah
    return {k: getattr(ah, k) for k in dir(ah) if not k.startswith("__")}


def render() -> None:
    init_core_state()
    init_router_state(initial_page="Hall of Fame")
    st.session_state["page"] = "Hall of Fame"
    ensure_default_dataset()

    try:
        globals().update(_deps())
    except Exception as e:
        st.error("❌ Nie udało się załadować zależności.\n\n" + str(e))
        st.stop()

    top_nav_row("🏅 Hall of Fame", back_default="Start", show_start=True)

    st.markdown("<div class='big-title'>🏅 Hall of Fame</div>", unsafe_allow_html=True)

    user = st.session_state.get("user")
    if not user or (isinstance(user, str) and user.startswith("Gosc-")):
        st.info("Ranking jest dla zalogowanych. Zaloguj się, żeby zobaczyć tabelę i swoje miejsce.")
        if st.button("⬅️ Wróć na Start", use_container_width=True):
            goto_hard("Start")
        return

    db = _load_users() or {}
    get_level = get_profile_level if "get_profile_level" in globals() else (lambda xp: max(0, int(xp or 0) // 50))

    rows = []
    for username, prof in db.items():
        if not isinstance(username, str) or username.startswith("Gosc-"):
            continue
        xp = int(prof.get("xp", 0) or 0)
        r = prof.get("retention") or {}
        streak = int(prof.get("streak") or r.get("streak", 0) or 0)
        kid_name = (prof.get("kid_name") or "").strip()
        display_name = kid_name or f"Gracz {username[-3:] if len(username) >= 3 else '?'}"
        level = get_level(xp)
        rows.append((display_name, level, xp, streak, username))

    rows.sort(key=lambda r: (r[1], r[2]), reverse=True)
    top = rows[:50]

    st.caption("Ranking według poziomu i XP. Seria = dni z rzędu z ukończoną misją.")
    st.markdown("---")

    if not top:
        st.info("Jeszcze nikt nie zdobył punktów. Bądź pierwszy – graj w misje!")
        if st.button("⬅️ Wróć na Start", use_container_width=True, key="hof_back_empty"):
            goto_hard("Start")
        return

    current_user = str(user)
    for i, (display_name, level, xp, streak, username) in enumerate(top, 1):
        is_me = username == current_user
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"<strong>{i}.</strong>"
        name_cell = f"{medal} {display_name}" + (" <em>(Ty)</em>" if is_me else "")
        border_color = "#52c41a" if is_me else "#d9d9d9"
        bg = "rgba(82, 196, 26, 0.15)" if is_me else "rgba(0,0,0,0.03)"
        st.markdown(
            f"<div style='padding:8px 12px; margin:4px 0; border-radius:8px; "
            f"background:{bg}; border-left:4px solid {border_color};'>"
            f"<span style='font-weight:bold;'>{name_cell}</span> &nbsp; "
            f"Poziom <strong>{level}</strong> &nbsp; <strong>{xp}</strong> XP &nbsp; 🔥 {streak} serii"
            f"</div>",
            unsafe_allow_html=True,
        )

    st.markdown("---")
    st.caption("Zdobywaj XP w misjach i przedmiotach, żeby awansować w rankingu! 🚀")


try:
    render()
except Exception:
    pass
