# pages/mapa_kopalni.py – Mapa kopalni (prosta: przedmioty + odblokowane)
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


# Nazwy przedmiotów do wyświetlenia (jeśli chcesz ładniejsze niż klucz z JSON)
SUBJECT_LABELS = {
    "matematyka": "Matematyka",
    "polski": "Język polski",
    "przyroda": "Przyroda",
    "historia": "Historia",
    "data_science": "Data Science",
}


def render() -> None:
    init_core_state()
    init_router_state(initial_page="Mapa kopalni")
    st.session_state["page"] = "Mapa kopalni"
    ensure_default_dataset()

    try:
        deps = _deps()
        load_tasks = deps.get("load_tasks", lambda: {})
        get_age_group = deps.get("get_age_group", lambda: "10-12")
        has_ever_done_subject = deps.get("has_ever_done_subject", lambda u, s: False)
        count_tasks_done_in_subject = deps.get("count_tasks_done_in_subject", lambda u, s: 0)
        load_supermoce = deps.get("load_supermoce", lambda: [])
        is_supermoc_unlocked = deps.get("is_supermoc_unlocked", lambda u, i: False)
        get_streak_badges = deps.get("get_streak_badges", lambda u: [])
        load_sciezka_data_science = deps.get("load_sciezka_data_science", lambda: [])
        is_sciezka_step_unlocked = deps.get("is_sciezka_step_unlocked", lambda u, s: False)
        top_nav_row = deps.get("top_nav_row", lambda *a, **k: None)
    except Exception as e:
        st.error(f"Nie udało się załadować zależności: {e}")
        st.stop()

    top_nav_row("🗺️ Mapa kopalni", back_default="Start", show_start=True)

    user = st.session_state.get("user")
    if not user or str(user).startswith("Gosc-"):
        st.info("Mapa kopalni pokazuje **twoje korytarze** – które przedmioty już odkryłeś. Zaloguj się, żeby zobaczyć postęp.")
        if st.button("⬅️ Wróć na Start", use_container_width=True):
            goto_hard("Start")
        return

    tasks = load_tasks()
    if not isinstance(tasks, dict):
        tasks = {}
    age_group = get_age_group() if callable(get_age_group) else get_age_group()
    subjects = sorted(s for s, v in tasks.items() if isinstance(v, dict))

    if not subjects:
        st.warning("Brak przedmiotów w bazie zadań.")
        if st.button("⬅️ Wróć na Start", use_container_width=True):
            goto_hard("Start")
        return

    # ---------- Ścieżka Data Science (5–7 kroków) ----------
    sciezka = load_sciezka_data_science() if callable(load_sciezka_data_science) else []
    if sciezka:
        st.markdown("### 📊 Ścieżka Data Science")
        st.caption("Kolejne kroki odblokowują się, gdy robisz Quiz danych i zadania z przedmiotów. To twoja droga do pierwszej przygody z danymi.")
        for step in sciezka:
            if not isinstance(step, dict):
                continue
            try:
                unlocked = is_sciezka_step_unlocked(str(user), step)
                status = "🔓" if unlocked else "🔒"
                num = step.get("order", "?")
                title = step.get("title", "?")
                desc = step.get("description", "")
                st.markdown(f"{status} **{num}. {title}**  \n{desc}")
                st.caption("")
            except Exception:
                st.caption(f"• {step.get('title', 'Krok')}")
        st.divider()

    st.markdown("### ⛏️ Korytarze (przedmioty)")
    st.caption("Każdy **korytarz** to przedmiot. Odkrywasz go, gdy ukończysz choć jedno zadanie z tego działu. Kliknij, żeby wejść do misji.")

    for subj in subjects:
        unlocked = has_ever_done_subject(str(user), subj)
        done_count = count_tasks_done_in_subject(str(user), subj)
        subj_tasks = (tasks.get(subj) or {}).get(age_group, []) if isinstance(tasks.get(subj), dict) else []
        total_tasks = len(subj_tasks) if isinstance(subj_tasks, list) else 0

        label = SUBJECT_LABELS.get(subj, subj.title())
        status = "🔓" if unlocked else "🔒"
        if unlocked and total_tasks > 0:
            sub = f"  •  {done_count} zadań ukończonych"
        elif total_tasks > 0:
            sub = f"  •  {total_tasks} zadań do odkrycia"
        else:
            sub = ""

        btn_label = f"{status}  {label}{sub}"
        if st.button(btn_label, use_container_width=True, key=f"mapa_subj_{subj}"):
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

    # ---------- Odznaki za serie (dni z rzędu) ----------
    streak_badges = get_streak_badges(str(user)) if callable(get_streak_badges) else []
    if streak_badges:
        st.divider()
        st.markdown("### 🏅 Odznaki za serie")
        st.caption("Loguj się i kończ Misję dnia kolejnego dnia – odbierzesz nagrody za 3, 7, 14 i 30 dni z rzędu.")
        for sb in streak_badges:
            status = "🔓" if sb.get("unlocked") else "🔒"
            st.markdown(f"{status} **{sb.get('emoji', '🏅')} {sb.get('label', '')}**")
        st.caption("")

    # ---------- Twoje supermoce (Data Science w stylu Minecraft) ----------
    supermoce_list = load_supermoce() if callable(load_supermoce) else []
    if supermoce_list:
        st.divider()
        st.markdown("### ⚡ Twoje supermoce")
        st.caption("Odblokujesz je, robiąc zadania z przedmiotów i Quiz danych. Każda to mała umiejętność Data Science.")
        for sm in supermoce_list:
            if not isinstance(sm, dict):
                continue
            unlocked = is_supermoc_unlocked(str(user), sm)
            emo = sm.get("emoji", "✨")
            name = sm.get("name", "?")
            desc = sm.get("description", "")
            status = "🔓" if unlocked else "🔒"
            st.markdown(f"{status} **{emo} {name}**  \n{desc}")
            st.caption("")  # odstęp

    st.divider()
    if st.button("📚 Zobacz listę przedmiotów (klasycznie)", use_container_width=True, key="mapa_go_przedmioty"):
        goto_hard("Przedmioty")


try:
    render()
except Exception:
    pass
