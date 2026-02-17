from __future__ import annotations

import streamlit as st

from core.state_init import init_core_state, init_router_state, ensure_default_dataset
from core.routing import goto_hard


def _deps() -> dict:
    """Zbiera zależności bez importu app.py (żeby uniknąć kółek)."""
    import core.app_helpers as ah
    from core import missions as ms
    deps = {k: getattr(ah, k) for k in dir(ah) if not k.startswith("__")}
    deps.update({k: getattr(ms, k) for k in dir(ms) if not k.startswith("__")})
    return deps


def render() -> None:
    # ✅ multipage-safe bootstrap
    init_core_state()
    init_router_state(initial_page="Przedmioty")
    st.session_state["page"] = "Przedmioty"
    ensure_default_dataset()

    try:
        globals().update(_deps())
    except Exception as e:
        st.error(
            "❌ Nie udało się załadować zależności przedmiotów.\n\n"
            f"Szczegóły: {e}"
        )
        st.stop()

    top_nav_row("📚 Przedmioty szkolne", back_default="Start", show_start=True)

    tasks = load_tasks() if "load_tasks" in globals() else {}
    age_group = get_age_group() if "get_age_group" in globals() else "10-12"

    subjects = [s for s, v in (tasks or {}).items() if isinstance(v, dict)]
    subjects = sorted(subjects)

    if not subjects:
        st.warning("Brak przedmiotów w bazie zadań (tasks.json).")
        return

    st.caption("Wybierz przedmiot, aby rozpocząć misje bonusowe z tego działu.")

    for subj in subjects:
        subj_tasks = (tasks.get(subj) or {}).get(age_group, []) if isinstance(tasks, dict) else []
        count = len(subj_tasks) if isinstance(subj_tasks, list) else 0

        label = f"{subj.title()}  •  {count} zadań"
        if st.button(label, use_container_width=True, key=f"subject_{subj}"):
            st.session_state["missions_view"] = "subject"
            st.session_state["bonus_subject"] = subj

            mc = st.session_state.get("mc") or {}
            if not isinstance(mc, dict):
                mc = {}
            mc.setdefault("bonus", {})
            mc["bonus"]["subject"] = subj
            st.session_state["mc"] = mc

            goto_hard("Misje")
            st.stop()


# Multipage (st.switch_page): uruchom render() także przy wejściu bez routera
try:
    render()
except Exception:
    pass
