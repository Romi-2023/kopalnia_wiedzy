# pyright: reportUndefinedVariable=false
import os
import streamlit as st

from core.state_init import init_core_state, init_router_state, ensure_default_dataset


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
    init_router_state(initial_page="Quiz danych")
    st.session_state["page"] = "Quiz danych"
    ensure_default_dataset()
    # ---- wstrzyknięcie zależności (tylko wymagane symbole) ----
    try:
        globals().update(_deps())
    except Exception as e:
        st.error(
            "❌ Nie udało się załadować zależności quizu danych z app.py.\n\n"
            f"Szczegóły: {e}"
        )
        st.stop()

    kid_emoji = globals().get("KID_EMOJI", "🧒")

    # ---- start strony ----
    log_event("page_quiz_danych")

    # ✅ tylko JEDEN top_nav_row (wcześniej miałeś dwa)
    top_nav_row(f"📊 {kid_emoji} Quiz danych", back_default="Start", show_start=True)

    # ---- wczytanie bazy pytań ----
    data_dir = globals().get("DATA_DIR", "data")
    dq_path = os.path.join(data_dir, "quizzes", "data_quiz.json")
    dq = safe_load_json(dq_path, default={"items": []})
    all_items = dq.get("items", [])

    if not all_items:
        st.warning("Brak pytań w bazie. Uzupełnij data/quizzes/data_quiz.json 🙂")
        st.stop()

    # ✅ upewnij się, że pytania mają difficulty
    try:
        all_items = ensure_difficulty(list(all_items))
    except Exception:
        pass

    # --- dzienna rotacja (szybki quiz = 5 pytań gdy wejście z Startu) ---
    day_idx = days_since_epoch()
    quick_mode = st.session_state.pop("quiz_quick_mode", False)
    k_daily = min(5, len(all_items)) if quick_mode else min(10, len(all_items))

    # --- poziom 1..3 (konto / profil) ---
    user = st.session_state.get("user") or "guest"
    lvl = 2
    try:
        lvl = int(skill_get_level(user, "data_quiz"))  # 1..3
    except Exception:
        lvl = 2
    lvl = max(1, min(3, int(lvl)))

    # =========================================================
    # ✅ WYBÓR TRUDNOŚCI + blokady poziomów
    # =========================================================
    labels = {"easy": "🟢 Easy", "medium": "🟡 Medium", "hard": "🔴 Hard"}

    # domyślny wybór: medium jeśli odblokowane, inaczej easy
    st.session_state.setdefault("quiz_data_diff", "medium" if lvl >= 2 else "easy")
    prev = st.session_state["quiz_data_diff"]

    picked = st.radio(
        "Trudność:",
        options=["easy", "medium", "hard"],
        index=["easy", "medium", "hard"].index(prev),
        format_func=lambda x: labels.get(x, x),
        horizontal=True,
        key="quiz_data_diff_picker",
    )

    # blokady: medium od 2/3, hard od 3/3
    locked = (picked == "medium" and lvl < 2) or (picked == "hard" and lvl < 3)

    if picked != prev:
        if locked:
            st.warning(
                "🔒 Ten poziom jest jeszcze zablokowany. "
                "Odblokujesz go, gdy podniesiesz poziom (2/3 lub 3/3)."
            )
            # cofamy wybór
            st.session_state["quiz_data_diff"] = prev
            st.rerun()
        else:
            st.session_state["quiz_data_diff"] = picked
            # czyścimy odpowiedzi poprzedniego zestawu (żeby nie mieszać stanów)
            for k in list(st.session_state.keys()):
                if see := k.startswith("dq_"):
                    st.session_state.pop(k, None)
            st.rerun()

    diff = st.session_state["quiz_data_diff"]

    # --- forma dzisiaj ---
    note = f"Tryb: {diff.upper()} • poziom: {lvl}/3"
    render_form_bar("Twoja forma dzisiaj", diff, note)

    # czytelne komunikaty o blokadach
    if lvl < 2:
        st.caption("🔒 Medium odblokuje się na poziomie 2/3.")
    elif lvl < 3:
        st.caption("🔒 Hard odblokuje się na poziomie 3/3.")

    # --- pula pytań wg trudności ---
    pool = filter_by_difficulty(all_items, diff) or all_items

    # --- filtr po poziomie (jeśli masz taką logikę) ---
    pool = filter_items_by_level(pool, lvl) or pool

    # --- wybór dzisiejszego zestawu (deterministycznie, inny dla diff / szybki) ---
    salt = f"data_quiz::quick::{diff}::{lvl}" if quick_mode else f"data_quiz::{diff}::{lvl}"
    items = pick_daily_chunk(pool, k_daily, day_idx, salt)

    if quick_mode:
        st.caption(f"⚡ **Szybki quiz:** {len(items)} pytań.")
    else:
        st.caption(f"Dzisiejszy zestaw: {len(items)} pytań (z {len(all_items)} w całej bazie).")

    # --- progres dzienny + anty-farm (per dzień + diff + poziom; osobny dla szybkiego) ---
    today_key = _today_key()
    suf = "_quick" if quick_mode else ""
    prog_key = f"dq_done_{today_key}_{diff}_{lvl}{suf}"
    att_key = f"dq_att_{today_key}_{diff}_{lvl}{suf}"

    done_set = st.session_state.setdefault(prog_key, set())
    att_set = st.session_state.setdefault(att_key, set())

    # XP za pytanie zależnie od trybu
    xp_per_q = {"easy": 2, "medium": 3, "hard": 4}.get(diff, 2)

    st.progress(min(1.0, (len(done_set) / max(1, len(items)))))
    st.caption(f"Postęp: **{len(done_set)} / {len(items)}** ✅")

    # ---- pytania ----
    for i, t in enumerate(items, start=1):
        q = t.get("q", "")
        opts = t.get("options", [])
        corr = int(t.get("correct", 0))

        # stabilny ID pytania (żeby liczyć progres i nie dublować nagród)
        try:
            base = f"dq::{q}"
            qid = hashlib.sha256(base.encode("utf-8")).hexdigest()[:8]
        except Exception:
            qid = f"{i}"

        already_done = qid in done_set
        if already_done:
            st.caption("✅ Zaliczone (tryb ćwiczeń — bez XP)")

        st.markdown(f"**{i}. {q}**")

        # ✅ stabilniejsze klucze: nie mieszamy _today_key() w kilku miejscach na raz
        radio_key = f"dq_{today_key}_{diff}_{lvl}_{i}{suf}"
        btn_key = f"dq_check_{today_key}_{diff}_{lvl}_{i}{suf}"

        choice = st.radio(
            "Wybierz:",
            opts,
            key=radio_key,
            label_visibility="collapsed",
            index=None,
        )

        if st.button("Sprawdź ✅", key=btn_key):
            if choice is None:
                st.warning("Wybierz odpowiedź.")
                continue

            # log-friendly skrót pytania
            try:
                short_q = q if len(q) <= 60 else q[:57] + "..."
            except Exception:
                short_q = ""

            # rejestr próby (jeśli będziesz kiedyś chciał limitować próby)
            if qid:
                att_set.add(qid)
                st.session_state[att_key] = att_set

            is_correct = bool(opts) and (opts.index(choice) == corr)

            if is_correct:
                st.success("✅ Dobrze!")

                # ✅ XP tylko raz za pytanie dziennie (anti-farm)
                if qid and (qid not in done_set):
                    add_xp(xp_per_q, reason=f"data_quiz::{diff}")
                    done_set.add(qid)
                    st.session_state[prog_key] = done_set

                update_skill("quiz_data", True)

                try:
                    new_lvl = skill_update(user, "data_quiz", True)
                    if int(new_lvl) != int(lvl):
                        st.toast(f"Poziom trudności zmieniony na {new_lvl}/3 🎯")
                except Exception:
                    pass

                try:
                    log_event(f"quiz_ok::data::{qid}::{short_q}")
                except Exception:
                    pass
            else:
                correct_label = opts[corr] if (opts and 0 <= corr < len(opts)) else ""
                st.error(f"❌ Nie. Poprawna: **{correct_label}**.")

                update_skill("quiz_data", False)

                try:
                    new_lvl = skill_update(user, "data_quiz", False)
                    if int(new_lvl) != int(lvl):
                        st.toast(f"Poziom trudności zmieniony na {new_lvl}/3 🧩")
                except Exception:
                    pass

                try:
                    chosen = choice or ""
                    log_event(f"quiz_fail::data::{qid}::{short_q}::{chosen}::{correct_label}")
                except Exception:
                    pass

    # ---- data storytelling: podsumowanie po ukończeniu zestawu ----
    if len(items) > 0 and len(done_set) >= len(items):
        st.divider()
        st.success("✅ Zestaw ukończony!")
        st.markdown(
            f"📊 **Z twoich odpowiedzi:** poprawnie rozwiązałeś **{len(done_set)}** z **{len(items)}** pytań. "
            "To buduje twój poziom w Quiz danych i supermoce na Mapie kopalni."
        )
        if st.button("📖 Zobacz hasła w Słowniczku", use_container_width=True, key="quiz_done_slowniczek"):
            from core.routing import goto_hard
            goto_hard("Słowniczek")
            return


# Multipage (st.switch_page): uruchom render() także przy wejściu bez routera
try:
    render()
except Exception as e:
    try:
        from core.ui import show_exception
        show_exception(e)
    except Exception:
        pass
