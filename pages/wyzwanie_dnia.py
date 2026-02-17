# pages/wyzwanie_dnia.py – jedno zadanie dziennie (~2 min)
from __future__ import annotations

import streamlit as st

from core.state_init import init_core_state, init_router_state, ensure_default_dataset
from core.routing import goto_hard


def _deps() -> dict:
    import core.app_helpers as ah
    from core import missions as ms
    deps = {k: getattr(ah, k) for k in dir(ah) if not k.startswith("__")}
    deps.update({k: getattr(ms, k) for k in dir(ms) if not k.startswith("__")})
    return deps


def _task_id_from_text(text: str) -> str:
    import hashlib
    try:
        return hashlib.sha256(("task::" + (text or "").strip()).encode("utf-8")).hexdigest()[:12]
    except Exception:
        return str(abs(hash(text)))[:12]


def render() -> None:
    init_core_state()
    init_router_state(initial_page="Wyzwanie dnia")
    st.session_state["page"] = "Wyzwanie dnia"
    ensure_default_dataset()

    try:
        deps = _deps()
        get_daily_bonus_pack = deps.get("get_daily_bonus_pack", lambda u, k=3: [])
        is_task_done = deps.get("is_task_done", lambda u, s, t: False)
        mark_task_done = deps.get("mark_task_done", lambda u, s, t, xp=None: None)
        top_nav_row = deps.get("top_nav_row", lambda *a, **k: None)
    except Exception as e:
        st.error(f"Nie udało się załadować zależności: {e}")
        st.stop()

    top_nav_row("⚡ Wyzwanie dnia", back_default="Start", show_start=True)

    user = st.session_state.get("user")
    if not user:
        st.info("Zaloguj się lub graj jako Gość, żeby wziąć udział w Wyzwaniu dnia.")
        if st.button("⬅️ Wróć na Start", use_container_width=True):
            goto_hard("Start")
        return

    pack = get_daily_bonus_pack(str(user), k=1)
    if not pack:
        st.info("Dziś brak zadań w puli. Wróć jutro!")
        if st.button("⬅️ Wróć na Start", use_container_width=True):
            goto_hard("Start")
        return

    it = pack[0]
    subject = (it.get("subject") or "").strip() or "Zadanie"
    task = it.get("task") or {}
    q_text = (task.get("q") or "").strip()
    xp_val = int(task.get("xp", 5) or 5)

    if not q_text:
        st.warning("Brak treści pytania.")
        if st.button("⬅️ Wróć na Start", use_container_width=True):
            goto_hard("Start")
        return

    already_done = is_task_done(str(user), subject, q_text)
    if already_done:
        st.success("✅ **Wyzwanie dnia ukończone!** Możesz wrócić jutro po kolejne.")
        st.balloons()
        if st.button("⬅️ Wróć na Start", use_container_width=True):
            goto_hard("Start")
        return

    st.caption("Jedno zadanie na dziś (~2 min). Poprawna odpowiedź = +XP.")
    st.markdown(f"**{subject.title()}**")
    st.markdown(f"**{q_text}**")

    opts = task.get("options") or task.get("choices") or task.get("answers")
    if isinstance(opts, (tuple, set)):
        opts = list(opts)
    if not isinstance(opts, list):
        opts = []

    correct_raw = task.get("correct")
    if correct_raw is None:
        correct_raw = task.get("answer") or task.get("a")
    correct_str = None
    if correct_raw is not None:
        correct_str = str(correct_raw).strip()
        if opts and correct_str.isdigit():
            idx = int(correct_str)
            if 0 <= idx < len(opts):
                correct_str = str(opts[idx]).strip()

    tid = _task_id_from_text(f"{subject}::{q_text}")
    key_radio = f"wyzwanie_radio_{tid}"
    key_btn = f"wyzwanie_btn_{tid}"

    if opts:
        pick = st.radio("Wybierz:", opts, key=key_radio, index=None, label_visibility="collapsed")
    else:
        pick = st.text_input("Twoja odpowiedź:", key=key_radio, value="").strip()

    if st.button("Sprawdź ✅", key=key_btn, use_container_width=True):
        has_answer = (pick is not None and str(pick).strip() != "") if opts else (bool((pick or "").strip()))
        if not has_answer:
            st.warning("Wybierz lub wpisz odpowiedź.")
        else:
            ok = (str(pick).strip() == correct_str) if correct_str is not None else False
            if ok:
                mark_task_done(str(user), subject, q_text, xp_gain=xp_val)
                st.success(f"✅ Dobrze! **+{xp_val} XP**")
                st.balloons()
                st.session_state["_wyzwanie_just_done"] = True
                st.rerun()
            else:
                st.error(f"❌ Nie. Poprawna odpowiedź: **{correct_str or '—'}**")

    if st.button("⬅️ Wróć na Start (bez odpowiedzi)", use_container_width=True, key="wyzwanie_back"):
        goto_hard("Start")


try:
    render()
except Exception:
    pass
