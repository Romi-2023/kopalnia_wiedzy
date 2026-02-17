# pyright: reportUndefinedVariable=false
from __future__ import annotations

import json
import os
import random
import streamlit as st

from core.state_init import init_core_state, init_router_state, ensure_default_dataset
from core.routing import goto_hard


def _deps() -> dict:
    import core.app_helpers as ah
    return {k: getattr(ah, k) for k in dir(ah) if not k.startswith("__")}


def _load_json(rel_path: str) -> dict:
    path = os.path.join("data", rel_path)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def render() -> None:
    init_core_state()
    init_router_state(initial_page="Karta rowerowa")
    st.session_state["page"] = "Karta rowerowa"
    ensure_default_dataset()

    try:
        globals().update(_deps())
    except Exception as e:
        st.error("❌ Nie udało się załadować zależności.\n\n" + str(e))
        st.stop()

    top_nav_row("🚲 Karta rowerowa", back_default="Pomoce szkolne", show_start=True)

    st.markdown("<div class='big-title'>🚲 Moja pierwsza karta rowerowa</div>", unsafe_allow_html=True)
    st.caption("Nauka teorii, testy i egzamin próbny.")

    teoria = _load_json(os.path.join("rower", "rower_teoria.json"))
    quiz_data = _load_json(os.path.join("rower", "rower_quiz.json"))
    questions_all = quiz_data.get("questions", [])

    tab_nauka, tab_testy, tab_egzamin = st.tabs(["📖 Nauka", "✏️ Testy", "📋 Egzamin próbny"])

    # ---- Zakładka: Nauka ----
    with tab_nauka:
        st.markdown("### Teoria – przygotowanie do karty rowerowej")
        sections = teoria.get("sections", [])
        if not sections:
            st.info("Brak danych z teorią. Plik rower/rower_teoria.json może być pusty.")
        for sec in sections:
            st.markdown(f"#### {sec.get('label', '')}")
            st.caption(sec.get("description", ""))
            for topic in sec.get("topics", []):
                with st.expander(topic.get("title", "")):
                    st.markdown(topic.get("text", ""))
                    if topic.get("bullet_points"):
                        for bp in topic["bullet_points"]:
                            st.markdown(f"- {bp}")
                    if topic.get("tip"):
                        st.success(f"💡 {topic['tip']}")

    # ---- Zakładka: Testy ----
    with tab_testy:
        st.markdown("### Testy – sprawdź się")
        if not questions_all:
            st.info("Brak pytań w bazie.")
        else:
            idx_key = "rower_test_idx"
            st.session_state.setdefault(idx_key, 0)
            idx = min(st.session_state[idx_key], len(questions_all) - 1) if questions_all else 0
            q = questions_all[idx]
            st.markdown(f"**Pytanie {idx + 1} / {len(questions_all)}**")
            st.markdown(f"**{q.get('question', '')}**")
            opts = q.get("options", [])
            correct_idx = int(q.get("correct", 0))
            chosen = st.radio("Wybierz odpowiedź:", opts, key="rower_test_radio", label_visibility="collapsed")
            if chosen:
                user_idx = opts.index(chosen) if chosen in opts else -1
                if user_idx == correct_idx:
                    st.success("✅ Dobrze!")
                    st.caption(q.get("explanation", ""))
                else:
                    st.error("❌ Niepoprawnie.")
                    st.caption(f"Poprawna odpowiedź: **{opts[correct_idx]}**")
                    st.caption(q.get("explanation", ""))
            col1, col2 = st.columns(2)
            with col1:
                if st.button("⏮️ Poprzednie", key="rower_prev") and idx > 0:
                    st.session_state[idx_key] = idx - 1
                    st.rerun()
            with col2:
                if st.button("Następne ⏭️", key="rower_next") and idx < len(questions_all) - 1:
                    st.session_state[idx_key] = idx + 1
                    st.rerun()

    # ---- Zakładka: Egzamin próbny ----
    with tab_egzamin:
        st.markdown("### Egzamin próbny – losowe pytania, wynik na końcu")
        if not questions_all:
            st.info("Brak pytań w bazie.")
        else:
            exam_size = min(15, len(questions_all))
            if "rower_exam_questions" not in st.session_state or "rower_exam_answers" not in st.session_state:
                st.session_state["rower_exam_questions"] = random.sample(questions_all, exam_size)
                st.session_state["rower_exam_answers"] = {}

            exam_q = st.session_state["rower_exam_questions"]
            exam_answers = st.session_state["rower_exam_answers"]
            current_key = "rower_exam_current"
            st.session_state.setdefault(current_key, 0)
            current = min(st.session_state[current_key], len(exam_q) - 1)

            if current < len(exam_q):
                q = exam_q[current]
                st.markdown(f"**Pytanie {current + 1} / {len(exam_q)}**")
                st.markdown(f"**{q.get('question', '')}**")
                opts = q.get("options", [])
                ans = st.radio("Odpowiedź:", opts, key="rower_exam_radio", label_visibility="collapsed")
                if ans:
                    exam_answers[current] = opts.index(ans) if ans in opts else -1
                    st.session_state["rower_exam_answers"] = exam_answers
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("⏮️ Wstecz", key="exam_prev") and current > 0:
                        st.session_state[current_key] = current - 1
                        st.rerun()
                with col2:
                    if st.button("Dalej ⏭️", key="exam_next"):
                        if current < len(exam_q) - 1:
                            st.session_state[current_key] = current + 1
                            st.rerun()
                        else:
                            st.session_state[current_key] = len(exam_q)
                            st.rerun()
            else:
                # Koniec egzaminu – pokaż wynik
                correct_count = 0
                for i, q in enumerate(exam_q):
                    if exam_answers.get(i) == int(q.get("correct", 0)):
                        correct_count += 1
                st.success(f"**Wynik: {correct_count} / {len(exam_q)}**")
                if correct_count >= len(exam_q) * 0.8:
                    st.balloons()
                    st.markdown("Świetnie! Jesteś gotowy/a na egzamin. 🚲")
                else:
                    st.markdown("Powtórz naukę i testy, potem spróbuj ponownie.")
                if st.button("🔄 Rozpocznij egzamin od nowa", key="exam_restart"):
                    st.session_state.pop("rower_exam_questions", None)
                    st.session_state.pop("rower_exam_answers", None)
                    st.session_state.pop("rower_exam_current", None)
                    st.session_state.pop("rower_exam_finished", None)
                    st.rerun()


try:
    render()
except Exception:
    pass
