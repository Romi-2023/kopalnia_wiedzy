# pyright: reportUndefinedVariable=false

import os
import time
import random
import re
import secrets
from datetime import date, datetime

import streamlit as st
from core.theme import apply_theme

# Stabilne logowanie (nigdy nie wywali strony)
from core.telemetry import log_event as telemetry_log
from core.state_init import init_core_state, init_router_state, ensure_default_dataset, is_guest, is_logged_in

from core.routing import goto, goto_hard
from core.config import CONTACT_EMAIL
from core.persistence import load_contest_participants, save_contest_participants, record_guest_signup

# Linki wsparcia (uzupełnij swoimi – używane w zakładce „Wsparcie i konkursy”)
SUPPORT_BUYMEACOFFEE_URL = "https://buymeacoffee.com/knoppromanu"
SUPPORT_PAYPAL_URL = "https://paypal.me/RomanKnopp726"

def _deps() -> dict:
    """
    Lazy-import zależności z app.py.
    To rozwiązuje 2 problemy naraz:
    - NameError na brakujących helperach (log_event, card, itp.)
    - ryzyko circular-import przy ładowaniu stron
    """
    from core.app_helpers import (
        # UI / navigation
        top_nav_row,
        show_loot_popup,
        confetti_reward,
        _set_url_page,
        card,
        # lottie / assets
        load_lottie,
        st_lottie,
        BASE_DIR,
        _bytes_to_b64,
        # auth / users
        _load_users,
        _save_users,
        verify_parent_pin,
        hash_pw,
        validate_login,
        validate_password,
        load_profile_to_session,
        after_login_cleanup,
        autosave_if_dirty,
        # age group / misc
        get_age_group,
        age_to_group,
        apply_age_group_change,
        clear_age_group_dependent_state,
        # avatars / presets
        list_builtin_avatars,
        get_avatar_image_bytes,
        get_avatar_frame,
        AVATAR_META,
        TERMS_VERSION,
        DATASETS_PRESETS,
        # class / teacher
        join_class,
        create_class,
        get_class_info,
        list_classes_by_teacher,
        # XP/level
        get_profile_level,
        level_progress,
        # daily reset
        _time_to_next_daily_set_str,
        # rada dnia
        get_tip_of_day,
    )
    return locals()



def render():
    # ✅ multipage-safe bootstrap (gdy użytkownik wejdzie bezpośrednio na /start)
    init_core_state()
    init_router_state(initial_page="Start")
    st.session_state["page"] = "Start"
    ensure_default_dataset()

    apply_theme(page="start")

    # Mniejsze przerwy pionowe na Start (logowanie, „Grasz z klasą?”)
    st.markdown("""
    <style>
    /* Start: mniej rozstrzelone bloki */
    .block-container section[data-testid="stVerticalBlock"] { gap: 0.5rem !important; }
    .block-container .stMarkdown:not(.stAlert) { margin-bottom: 0.25rem !important; }
    .block-container [data-testid="stCaptionContainer"] { margin-top: 0.05rem !important; margin-bottom: 0.25rem !important; }
    .block-container hr { margin: 0.5rem 0 !important; }
    .block-container div[data-testid="column"] { padding-top: 0 !important; }
    </style>
    """, unsafe_allow_html=True)

    # --- Najpierw wciągnij zależności do tego modułu ---
    try:
        globals().update(_deps())
    except Exception as e:
        st.error(
            "Start nie mógł zaimportować helperów z app.py (możliwy import w kółko / błąd w app.py).\n\n"
            f"Szczegóły: {e}"
        )
        st.stop()

    telemetry_log("page_start")

    # ✅ FIX: pewne źródło bazy użytkowników w tym pliku (żeby logowanie nie waliło NameError na db)
    try:
        db = _load_users()
        if db is None:
            db = {}
    except Exception:
        db = {}

    # 🎁 Nagroda po zakończeniu bonusów (odpala się tylko raz)
    mc = st.session_state.get("mc") or {}
    finish = (mc.get("bonus") or {}).get("finish_reward")

    if finish:
        show_loot_popup(
            finish.get("title", "🏆 Mega bonus!"),
            finish.get("msg", "Ukończone wszystkie misje bonusowe!"),
            finish.get("emoji", "🎁"),
        )

        try:
            time.sleep(1.75)
        except Exception:
            pass

        try:
            anim_chest = load_lottie(os.path.join(BASE_DIR, "assets", "Chest_Spawn.json"))
        except Exception:
            anim_chest = None

        if anim_chest:
            st_lottie(anim_chest, speed=1.0, loop=False, height=260, key="lottie_bonus_finish")
        else:
            try:
                confetti_reward()
            except Exception:
                pass

        if "mc" in st.session_state and isinstance(st.session_state["mc"], dict):
            if "bonus" in st.session_state["mc"] and isinstance(st.session_state["mc"]["bonus"], dict):
                st.session_state["mc"]["bonus"].pop("finish_reward", None)

    # ---------------------------------
    # Status użytkownika
    # ---------------------------------
    u = st.session_state.get("user")
    is_logged = is_logged_in()
    guest_mode = bool(is_guest())  # ✅ FIX: traktujemy is_guest jako funkcję
    if is_logged:
        st.session_state["guest_mode"] = False

    def lock_if_guest() -> bool:
        """Gość ma dostęp tylko do Misji dnia + bonusów po misjach."""
        return not is_logged

    today = str(date.today())
    animate_today = st.session_state.get("title_animated_date") != today
    if animate_today:
        st.session_state["title_animated_date"] = today

    # ---------------------------------
    # HERO
    # ---------------------------------
    title_nick = st.session_state.get("kid_name") or ("Gość" if guest_mode else "Gracz")
    xp = int(st.session_state.get("xp", 0) or 0)
    try:
        lvl_info = level_progress(xp)
        level_txt = f"L{lvl_info['level']}"
    except Exception:
        level_txt = f"L{get_profile_level(xp) if 'get_profile_level' in globals() else 0}"

    DEFAULT_TITLE_AVATAR_ID = "scientist_1"

    # 🧑‍🚀 Skórka (base64) – jeśli brak, pokaż fallback
    skin_b64 = st.session_state.get("skin_b64")
    avatar_id = st.session_state.get("avatar_id")

    if skin_b64:
        skin_html = f"<img src='data:image/png;base64,{skin_b64}' alt='skin'/>"
    else:
        av_bytes = get_avatar_image_bytes(avatar_id) if avatar_id else None
        if not av_bytes:
            av_bytes = get_avatar_image_bytes(DEFAULT_TITLE_AVATAR_ID)

        if av_bytes:
            av_b64 = _bytes_to_b64(av_bytes)
            skin_html = f"<img src='data:image/png;base64,{av_b64}' alt='avatar'/>"
        else:
            skin_html = "<div class='d4k-skin-fallback'>🧑‍🚀</div>"

    # level w skali 0..100 (jedna prawda)
    level = get_profile_level(xp)

    frame = ""
    try:
        frame = get_avatar_frame(st.session_state.get("user"), level)
    except Exception:
        frame = ""

    hero_html = f"""
    <div class="d4k-panel d4k-panel-light" style="
        border:3px solid #1f2937; border-radius:18px; box-shadow:0 10px 0 rgba(31,41,55,.25);
        padding:16px 16px 14px 16px; margin-top:4px;
        background: linear-gradient(180deg, rgba(255,255,255,.95), rgba(243,244,246,.95));
    ">
      <div class="d4k-hero-row {'mc-title-animate' if animate_today else ''}" style="
        flex-direction: column;
        justify-content: center;
        gap: 12px;
        font-family: var(--ui);
        line-height:1;
    ">
        <div style="display:flex; align-items:center; justify-content:center; gap:10px; width:100%;">
            <div style="text-align:center;">
            <div style="
                font-family: var(--mc);
                font-size: 22px;
                letter-spacing: 1.2px;
                line-height: 1.05;
                text-shadow: 0 2px 0 rgba(0,0,0,.12);
            ">KOPALNIA</div>

            <div style="
                font-family: var(--mc);
                font-size: 18px;
                letter-spacing: 1.1px;
                margin-top: 6px;
                text-shadow: 0 2px 0 rgba(0,0,0,.12);
            ">WIEDZY</div>
            </div>
        </div>

        <div class="d4k-avatar-wrap">
          <div class="avatar-frame {frame}">
            <div class="avatar-core">
              <div class="d4k-skin-slot">
                {skin_html}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="d4k-start-subtitle" style="font-family:'VT323', monospace; font-size:20px; margin-top:4px;">
        Minecraftowy świat misji, quizów i nagród — wchodzisz?
      </div>

      <div style="margin-top:10px; display:flex; gap:10px; flex-wrap:wrap;">
        <div class="d4k-pill">👤 <b>{title_nick}</b></div>
        <div class="d4k-pill">🧱 <b>{level_txt}</b></div>
        <div class="d4k-pill">✨ <b>{int(st.session_state.get('xp',0) or 0)} XP</b></div>
        <div class="d4k-pill">💎 <b>{int(st.session_state.get('gems',0) or 0)}</b></div>
        <div class="d4k-pill">👶 <b>{get_age_group()}</b></div>
      </div>
    </div>
    """

    hero_html = "\n".join(line.lstrip() for line in hero_html.splitlines()).strip()
    st.markdown(hero_html, unsafe_allow_html=True)

    # ====== ZMIANA AVATARA: jeden klik, bez popovera (stabilne na mobile/bottom-nav) ======
    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    u = st.session_state.get("user")
    is_guest_local = isinstance(u, str) and u.startswith("Gosc-")
    is_logged_local = bool(u) and not is_guest_local

    if is_guest_local:
        st.info("Gość może wybrać darmowy avatar 🙂")
        if st.button("🧑‍🚀 Zmień avatar", use_container_width=True, key="start_change_avatar_btn"):
            goto_hard("Avatar")
            st.stop()

    elif is_logged_local:
        if st.button("🧑‍🚀 Zmień avatar", use_container_width=True, key="start_logged_change_avatar"):
            goto_hard("Avatar")
            st.stop()
    else:
        st.info("Zaloguj się lub graj jako Gość, by zmienić avatar 🙂")

    # -------------------------------
    # MICRO-WOW (raz dziennie)
    # -------------------------------
    today = str(date.today())
    wow_key = "start_wow_shown_date"
    if st.session_state.get(wow_key) != today:
        anim = None
        try:
            candidate = os.path.join(BASE_DIR, "assets", "Start_Wow.json")
            if os.path.exists(candidate):
                anim = load_lottie(candidate)
        except Exception:
            anim = None

        if anim:
            st_lottie(anim, speed=1.0, loop=False, height=170, key="start-wow")
        else:
            st.toast("✨ Nowy dzień = nowa misja!", icon="✨")

        st.session_state[wow_key] = today

    # ---------------------------------
    # Komunikat: nowy zestaw każdego dnia
    # ---------------------------------
    try:
        ttn = _time_to_next_daily_set_str()
        st.caption(f"🆕 **Nowy zestaw misji i Quiz danych** czeka każdego dnia. Do następnego zestawu: **{ttn}** 🕛")
    except Exception:
        pass

    try:
        tip = get_tip_of_day()
        if tip:
            with st.expander("💡 Rada dnia", expanded=False):
                st.caption(tip)
    except Exception:
        pass

    # ---------------------------------
    # Główne CTA
    # ---------------------------------
    cta1, cta2 = st.columns(2)

    with cta1:
        if is_logged or guest_mode:
            if st.button("🚀 START MISJI DNIA", use_container_width=True, key="start_mission_btn"):
                # Powiedz stronie Misji, że ma odpalić tryb "daily"
                st.session_state["missions_view"] = "daily"
                st.session_state["_force_daily_once"] = True
                st.session_state["_last_user"] = st.session_state.get("user")
                st.session_state["force_daily_until"] = time.time() + 5.0

                # (opcjonalnie) log kliknięcia – bardzo pomaga w regresji
                telemetry_log("start_click_mission_day")

                goto_hard("Misje")
                st.stop()
        else:
            st.info("Wybierz tryb Gościa lub zaloguj się, aby uruchomić Misję dnia.")

    with cta2:
        # pokazuj "Graj jako Gość" tylko gdy NIE jesteś już gościem
        if (not is_logged) and (not guest_mode):
            if st.button("⚡ Graj jako Gość", use_container_width=True, key="start_cta_guest"):
                guest = "Gosc-" + str(random.randint(1000, 9999))
                try:
                    record_guest_signup()
                    db = _load_users() or {}
                    db[guest] = {"created_at": datetime.utcnow().isoformat()}
                    _save_users(db)
                except Exception:
                    pass
                st.session_state["user"] = guest
                st.session_state["guest_mode"] = True
                st.session_state.setdefault("xp", 0)
                st.session_state.setdefault("badges", set())
                st.session_state.setdefault("stickers", set())
                st.session_state.setdefault("gems", 0)
                st.session_state.setdefault("unlocked_games", set())
                st.session_state.setdefault("unlocked_avatars", set())
                st.session_state.setdefault("missions_state", {})
                st.session_state.setdefault("memory_stats", {})
                st.session_state.setdefault("activity_log", [])
                st.session_state.pop("mc", None)

                goto("Misje")
                st.stop()
        elif guest_mode:
            st.button("✅ Grasz jako Gość", use_container_width=True, disabled=True, key="guest_active_info")
            
        elif is_logged:
            st.button("✅ Zalogowany", use_container_width=True, disabled=True, key="logged_active_info")

    # ---------------------------------
    # Wyzwanie dnia (1 zadanie, ~2 min)
    # ---------------------------------
    if is_logged or guest_mode:
        try:
            u = st.session_state.get("user")
            pack_w = get_daily_bonus_pack(str(u or ""), k=1)
            wyzwanie_done = False
            if pack_w:
                it0 = pack_w[0]
                subj = (it0.get("subject") or "").strip()
                q_text = ((it0.get("task") or {}).get("q") or "").strip()
                if subj and q_text:
                    wyzwanie_done = is_task_done(str(u), subj, q_text)
            if wyzwanie_done:
                st.caption("✅ **Wyzwanie dnia** ukończone. Jutro kolejne!")
            else:
                if st.button("⚡ Wyzwanie dnia (1 zadanie, ~2 min)", use_container_width=True, key="start_wyzwanie_btn"):
                    goto_hard("Wyzwanie dnia")
                    st.stop()
            # Szybki quiz: 5 pytań z Quizu danych
            if st.button("📊 Szybki quiz (5 pytań)", use_container_width=True, key="start_szybki_quiz_btn"):
                st.session_state["quiz_quick_mode"] = True
                goto_hard("Quiz danych")
                st.stop()
        except Exception:
            pass

    # ---------------------------------
    # Zakładki: bezpośrednio pod CTA (przejrzyściej)
    # ---------------------------------
    st.markdown('<div class="portal-tabs">', unsafe_allow_html=True)
    tab_parent, tab_teacher, tab_support = st.tabs([
        "👨‍👩‍👧 Dla rodzica", "🏫 Dla nauczyciela", "❤️ Wsparcie i konkursy"
    ])
    st.markdown("</div>", unsafe_allow_html=True)

    # ========= TAB: RODZIC =========
    with tab_parent:
        if guest_mode:
            st.warning("Grasz jako Gość. Aby zapisywać postępy i odblokować portale — zaloguj się lub załóż konto.")
        st.info(
            "🔐 **Dla rodzica:** logowanie, rejestracja i ustawienia konta.\n\n"
            "Tip: po logowaniu odblokują się dodatkowe światy i postępy będą zapisywane.",
            icon="👨‍👩‍👧",
        )

        if is_logged:
            st.success(f"✅ Zalogowano jako: **{u}**")

            st.markdown("### 🎚️ Poziom trudności (grupa wiekowa)")

            ag_now = get_age_group()
            ag_opts = list(DATASETS_PRESETS.keys())

            try:
                ag_idx = ag_opts.index(ag_now)
            except Exception:
                ag_idx = 0

            pin_col, sel_col, btn_col = st.columns([1.2, 1.6, 1.0])

            with pin_col:
                pin = st.text_input("PIN rodzica", type="password", key="start_ag_pin")

            with sel_col:
                new_ag = st.selectbox(
                    "Grupa wiekowa",
                    ag_opts,
                    index=ag_idx,
                    key="start_age_group_picker",
                )

            with btn_col:
                if st.button("✅ Zastosuj", use_container_width=True, key="start_ag_apply"):
                    if not verify_parent_pin(pin):
                        st.error("Zły PIN.")
                    else:
                        apply_age_group_change(u, new_ag)
                        clear_age_group_dependent_state()
                        st.rerun()

            col1, col2 = st.columns([3, 1])
            with col2:
                if st.button("Wyloguj", use_container_width=True, key="logout_start"):
                    # Najpierw zapisz postęp do bazy, żeby użytkownik nie tracił go po wylogowaniu.
                    try:
                        autosave_if_dirty(force=True)
                    except Exception:
                        pass
                    st.session_state.user = None
                    st.session_state.logged_in = False
                    st.session_state.xp = 0
                    st.session_state.badges = set()
                    st.session_state.stickers = set()
                    st.session_state.gems = 0
                    st.session_state.unlocked_games = set()
                    st.session_state.memory_stats = {}
                    st.session_state["_profile_snapshot"] = None
                    goto("Start")
                    return

            st.caption("Panel rodzica znajdziesz w zakładce **Panel rodzica** (na dole nawigacji).")

        else:
            with st.expander("🔐 Logowanie / rejestracja", expanded=True):
                if "auth_mode" not in st.session_state:
                    st.session_state.auth_mode = "Zaloguj"

                mode = st.radio(
                    "Tryb",
                    ["Zaloguj", "Zarejestruj"],
                    horizontal=True,
                    index=0 if st.session_state.auth_mode == "Zaloguj" else 1,
                    key="start_auth_mode_radio",
                )
                st.session_state.auth_mode = mode

                if mode == "Zaloguj":
                    li_user = st.text_input("Login", key="li_user")
                    li_pass = st.text_input("Hasło", type="password", key="li_pass")

                    if st.button("Zaloguj ✅", use_container_width=True, key="start_login_btn"):
                        if li_user not in db or li_user.startswith("_"):
                            st.error("Nieprawidłowy login lub hasło.")
                        else:
                            rec = db[li_user]
                            salt = rec.get("salt", "")

                            if rec.get("password_hash") != hash_pw(li_pass, salt):
                                st.error("Nieprawidłowy login lub hasło.")
                            else:
                                if load_profile_to_session(li_user):
                                    after_login_cleanup(li_user)
                                    st.session_state["guest_mode"] = False
                                    st.success(f"Zalogowano jako **{li_user}** 🎉")
                                    st.rerun()
                                else:
                                    st.error("Nie udało się wczytać profilu użytkownika.")

                    st.markdown('<span id="d4k-admin-btn-marker"></span>', unsafe_allow_html=True)
                    st.markdown("""
                    <style>
                    /* Przycisk Panel administratora – mniejszy, normalny przypadek */
                    #d4k-admin-btn-marker ~ div div[data-testid="column"]:last-child div[data-testid="stButton"] button {
                        font-size: 12px !important; text-transform: none !important; letter-spacing: normal !important;
                        padding: 6px 12px !important; font-family: var(--ui), system-ui, sans-serif !important;
                    }
                    </style>
                    """, unsafe_allow_html=True)
                    _ac1, _ac2 = st.columns([6, 1])
                    with _ac2:
                        if st.button("Panel administratora", key="start_admin_btn", use_container_width=True):
                            st.session_state["page"] = "Nadzor"
                            st.session_state["_goto"] = "Nadzor"
                            try:
                                st.switch_page("app.py")
                            except Exception:
                                goto("Nadzor")
                            st.stop()

                else:
                    re_user = st.text_input("Nowy login (7–20 znaków, litery/cyfry/_-)", key="re_user")
                    re_pass = st.text_input("Hasło (min. 8 znaków, litera + cyfra)", type="password", key="re_pass")
                    re_pass2 = st.text_input("Powtórz hasło", type="password", key="re_pass2")

                    default_nick = (
                        random.choice(["Lama", "Kometa", "Zorza", "Atlas", "Pixel", "Foka", "Błysk"])
                        + "-" + str(random.randint(10, 99))
                    )
                    kid_name = st.text_input("Nick dziecka w aplikacji", value=default_nick, key="kid_name_in")
                    age_in = st.number_input("Wiek dziecka", min_value=7, max_value=14, step=1, value=10, key="age_in")

                    st.markdown("**Przed założeniem konta przeczytaj:**")
                    with st.expander("📜 Regulamin", expanded=False):
                        st.markdown("""
**Regulamin Kopalni Wiedzy**

1. **Przechowywanie danych.**  
   Aplikacja korzysta z bazy danych działającej na serwerze twórcy aplikacji. Dane użytkowników są przechowywane wyłącznie na tym serwerze i nie są przekazywane osobom trzecim ani wykorzystywane do celów komercyjnych. Nie stosujemy zewnętrznej analityki ani śledzenia. Dane są wykorzystywane wyłącznie do działania aplikacji (logowanie, profile, postępy, statystyki wewnętrzne).

2. **Brak danych osobowych.** Nie prosimy o imię i nazwisko ani e-mail. Login w aplikacji może być **pseudonimem**.

3. **Hasła i bezpieczeństwo.** Hasła są haszowane (z solą) i zapisywane na serwerze. Dbaj o silne hasło i nie udostępniaj go innym.

4. **Profil dziecka.** Postępy (XP, odznaki, naklejki) zapisywane są na serwerze aplikacji. Możesz je w każdej chwili usunąć w **Panelu rodzica** (zakładka Start).

5. **PIN rodzica.** Panel rodzica jest zabezpieczony PIN-em ustawianym w aplikacji.

6. **Treści edukacyjne.** Aplikacja ma charakter edukacyjny i **nie zastępuje** zajęć szkolnych. Dokładamy starań, by treści były poprawne, ale mogą się zdarzyć błędy.

7. **Pliki użytkownika.** Jeżeli wgrywasz własne dane (np. CSV), pozostają one na Twoim urządzeniu.

8. **Odpowiedzialne korzystanie.** Korzystaj z aplikacji zgodnie z prawem i zasadami dobrego wychowania.

9. **Zmiany regulaminu.** Regulamin może się zmienić wraz z rozwojem aplikacji; aktualna wersja jest zawsze tutaj.
                        """)
                        if st.button("Oznacz jako przeczytane", key="reg_read_btn"):
                            st.session_state["_reg_read"] = True
                            st.rerun()
                    with st.expander("🔒 Polityka prywatności i regulamin konkursów", expanded=False):
                        st.markdown("""
**1. Postanowienia ogólne**  
1. Niniejszy regulamin określa zasady udziału w konkursach organizowanych w ramach projektu **Kopalnia Wiedzy** (dalej: „Konkurs”).  
2. Organizatorem Konkursu jest właściciel i administrator aplikacji Kopalnia Wiedzy (dalej: „Organizator”).  
3. Konkurs nie jest grą losową, loterią fantową, zakładem wzajemnym ani żadną inną formą gry wymagającą zgłoszenia do właściwych organów administracyjnych.  
4. Konkurs jest przeprowadzany w celach edukacyjnych i promocyjnych, a nagrody mają charakter drobnych upominków rzeczowych.

**2. Uczestnicy**  
1. Uczestnikiem Konkursu może być osoba pełnoletnia działająca jako rodzic lub opiekun prawny dziecka korzystającego z aplikacji Kopalnia Wiedzy.  
2. Rodzic/opiekun zgłasza udział dziecka w Konkursie poprzez formularz dostępny w zakładce **„Wsparcie i konkursy”**.  
3. Zgłoszenie udziału oznacza akceptację niniejszego regulaminu.

**3. Zasady uczestnictwa**  
1. Warunkiem przystąpienia do Konkursu jest dokonanie dobrowolnego wsparcia projektu poprzez dowolną wpłatę („darowiznę”) lub spełnienie innych warunków określonych w opisie konkretnej edycji Konkursu.  
2. Kwota wsparcia nie wpływa na szanse zwycięstwa, chyba że opis Konkursu stanowi inaczej (np. system losów).  
3. Zgłoszenie do Konkursu wymaga podania: imienia i nazwiska rodzica/opiekuna, adresu e-mail do kontaktu, opcjonalnie loginu dziecka w aplikacji.  
4. Wszystkie dane są wykorzystywane wyłącznie do przeprowadzenia Konkursu oraz kontaktu z osobami nagrodzonymi.

**4. Przebieg i rozstrzygnięcie Konkursu**  
1. Losowanie zwycięzców odbywa się z wykorzystaniem narzędzia dostępnego w panelu administratora aplikacji Kopalnia Wiedzy lub niezależnego skryptu losującego.  
2. W zależności od opisu edycji Konkursu losowanie może odbywać się: „każde zgłoszenie = 1 los”, „unikalny adres e-mail = 1 los”, lub według kryteriów punktowych (np. ranking XP dziecka).  
3. Wyniki losowania są zapisywane w formie elektronicznej i przechowywane dla celów dowodowych przez Organizatora.  
4. Organizator skontaktuje się ze zwycięzcami drogą e-mailową w celu ustalenia formy przekazania nagrody.

**5. Nagrody**  
1. Nagrody mają charakter upominków rzeczowych (np. książki edukacyjne, gry logiczne, zestawy kreatywne).  
2. Nagrody nie podlegają wymianie na gotówkę ani inne świadczenia.  
3. Organizator pokrywa koszty wysyłki nagród na terenie Polski.  
4. W przypadku braku kontaktu ze strony zwycięzcy przez **14 dni** od ogłoszenia wyników, nagroda przepada i może zostać przyznana innej osobie.

**6. Dane osobowe**  
1. Administratorem danych osobowych jest Organizator.  
2. Dane uczestników są przetwarzane wyłącznie na potrzeby przeprowadzenia Konkursu i przekazania nagród.  
3. Uczestnik ma prawo dostępu do swoich danych, ich poprawiania oraz żądania usunięcia.  
4. Dane nie są przekazywane podmiotom trzecim.

**7. Reklamacje**  
1. Reklamacje dotyczące Konkursu można kierować do Organizatora na adres kontaktowy wskazany w aplikacji.  
2. Reklamacje będą rozpatrywane w terminie do 14 dni od ich zgłoszenia.  
3. Decyzja Organizatora w sprawie reklamacji jest ostateczna.

**8. Postanowienia końcowe**  
1. Organizator zastrzega sobie prawo do zmian regulaminu, o ile nie wpływają one na prawa uczestników zdobyte przed zmianą.  
2. Organizator może unieważnić Konkurs w przypadku stwierdzenia nadużyć lub zdarzeń losowych uniemożliwiających jego prawidłowe przeprowadzenie.  
3. W sprawach nieuregulowanych regulaminem zastosowanie mają przepisy prawa polskiego.
                        """)
                        if st.button("Oznacz jako przeczytane", key="privacy_read_btn"):
                            st.session_state["_privacy_read"] = True
                            st.rerun()

                    terms_ok = bool(st.session_state.get("_reg_read")) and bool(st.session_state.get("_privacy_read"))
                    accept = st.checkbox(
                        "Akceptuję regulamin",
                        key="accept_terms",
                        disabled=not terms_ok,
                        help="Najpierw otwórz i przeczytaj Regulamin oraz Politykę prywatności powyżej.",
                    )
                    if not terms_ok:
                        st.caption("📋 Przeczytaj Regulamin i Politykę prywatności oraz oznacz oba jako przeczytane, aby odblokować tę opcję.")
                    parent_ok = st.checkbox("Jestem rodzicem/opiekunem i wyrażam zgodę", key="parent_ok")

                    if st.button("Załóż konto ✅", use_container_width=True, key="start_register_btn"):
                        ok_log, err_log = validate_login(re_user or "")
                        ok_pw, err_pw = validate_password(re_pass or "")
                        if not re_user or not re_pass:
                            st.error("Podaj login i hasło.")
                        elif not ok_log:
                            st.error(err_log)
                        elif not ok_pw:
                            st.error(err_pw)
                        elif re_user in db:
                            st.error("Taki login już istnieje.")
                        elif re_pass != re_pass2:
                            st.error("Hasła się różnią.")
                        elif not terms_ok:
                            st.error("Przeczytaj Regulamin i Politykę prywatności oraz oznacz oba jako przeczytane.")
                        elif not accept:
                            st.error("Musisz zaakceptować regulamin.")
                        elif not parent_ok:
                            st.error("Potrzebna jest zgoda rodzica/opiekuna.")
                        else:
                            salt = secrets.token_hex(8)
                            age_int = int(age_in)
                            db[re_user] = {
                                "salt": salt,
                                "password_hash": hash_pw(re_pass, salt),
                                "xp": 0,
                                "stickers": [],
                                "badges": [],
                                "gems": 0,
                                "unlocked_games": [],
                                "memory": {},
                                "kid_name": kid_name.strip() or re_user,
                                "age": age_int,
                                "age_group": age_to_group(age_int),
                                "accepted_terms_version": TERMS_VERSION,
                                "created_at": datetime.utcnow().isoformat(),
                            }
                            _save_users(db)

                            st.session_state.user = re_user
                            st.session_state["guest_mode"] = False
                            st.session_state.xp = 0
                            st.session_state.gems = 0
                            st.session_state.badges = set()
                            st.session_state.stickers = set()
                            st.session_state.unlocked_games = set()
                            st.session_state.memory_stats = {}
                            st.session_state.missions_state = {}

                            mc = st.session_state.get("mc") or {}
                            if isinstance(mc, dict):
                                mc.get("daily", {}).pop("toast", None)
                                mc.get("bonus", {}).pop("toast", None)
                            st.session_state["mc"] = mc

                            st.session_state.kid_name = db[re_user]["kid_name"]
                            st.session_state.age = age_int
                            st.session_state.age_group = db[re_user]["age_group"]
                            st.success("Konto utworzone! ✅ Możesz się zalogować.")
                            goto("Start")
                            st.stop()

    # ========= TAB: NAUCZYCIEL =========
    with tab_teacher:
        st.markdown("### 🏫 Dla nauczyciela")
        if not is_logged:
            st.caption("Zaloguj się lub załóż konto – po zalogowaniu możesz tworzyć klasy, zarządzać kodem i korzystać z całej aplikacji (portale, misje, quizy).")
            with st.expander("🔐 Logowanie / rejestracja", expanded=True):
                if "auth_mode_teacher" not in st.session_state:
                    st.session_state.auth_mode_teacher = "Zaloguj"
                mode_t = st.radio(
                    "Tryb",
                    ["Zaloguj", "Zarejestruj"],
                    horizontal=True,
                    index=0 if st.session_state.auth_mode_teacher == "Zaloguj" else 1,
                    key="teacher_auth_mode_radio",
                )
                st.session_state.auth_mode_teacher = mode_t

                if mode_t == "Zaloguj":
                    li_user_t = st.text_input("Login", key="teacher_li_user")
                    li_pass_t = st.text_input("Hasło", type="password", key="teacher_li_pass")
                    if st.button("Zaloguj ✅", use_container_width=True, key="teacher_login_btn"):
                        if (li_user_t or "") not in db or (li_user_t or "").startswith("_"):
                            st.error("Nieprawidłowy login lub hasło.")
                        else:
                            rec = db.get(li_user_t, {})
                            salt = rec.get("salt", "")
                            if rec.get("password_hash") != hash_pw(li_pass_t or "", salt):
                                st.error("Nieprawidłowy login lub hasło.")
                            else:
                                if load_profile_to_session(li_user_t):
                                    after_login_cleanup(li_user_t)
                                    st.session_state["guest_mode"] = False
                                    st.success(f"Zalogowano jako **{li_user_t}** 🎉")
                                    st.rerun()
                                else:
                                    st.error("Nie udało się wczytać profilu.")
                else:
                    re_user_t = st.text_input("Nowy login (7–20 znaków, litery/cyfry/_-)", key="teacher_re_user")
                    re_pass_t = st.text_input("Hasło (min. 8 znaków, litera + cyfra)", type="password", key="teacher_re_pass")
                    re_pass2_t = st.text_input("Powtórz hasło", type="password", key="teacher_re_pass2")
                    default_nick_t = (
                        random.choice(["Lama", "Kometa", "Zorza", "Atlas", "Pixel", "Foka", "Błysk"])
                        + "-" + str(random.randint(10, 99))
                    )
                    kid_name_t = st.text_input("Nick dziecka w aplikacji", value=default_nick_t, key="teacher_kid_name_in")
                    age_in_t = st.number_input("Wiek dziecka", min_value=7, max_value=14, step=1, value=10, key="teacher_age_in")

                    st.markdown("**Przed założeniem konta przeczytaj:**")
                    with st.expander("📜 Regulamin", expanded=False):
                        st.markdown("""
**Regulamin Kopalni Wiedzy**

1. **Przechowywanie danych.**  
   Aplikacja korzysta z bazy danych działającej na serwerze twórcy aplikacji. Dane użytkowników są przechowywane wyłącznie na tym serwerze i nie są przekazywane osobom trzecim ani wykorzystywane do celów komercyjnych. Nie stosujemy zewnętrznej analityki ani śledzenia. Dane są wykorzystywane wyłącznie do działania aplikacji (logowanie, profile, postępy, statystyki wewnętrzne).

2. **Brak danych osobowych.** Nie prosimy o imię i nazwisko ani e-mail. Login w aplikacji może być **pseudonimem**.

3. **Hasła i bezpieczeństwo.** Hasła są haszowane (z solą) i zapisywane na serwerze. Dbaj o silne hasło i nie udostępniaj go innym.

4. **Profil dziecka.** Postępy (XP, odznaki, naklejki) zapisywane są na serwerze aplikacji. Możesz je w każdej chwili usunąć w **Panelu rodzica** (zakładka Start).

5. **PIN rodzica.** Panel rodzica jest zabezpieczony PIN-em ustawianym w aplikacji.

6. **Treści edukacyjne.** Aplikacja ma charakter edukacyjny i **nie zastępuje** zajęć szkolnych. Dokładamy starań, by treści były poprawne, ale mogą się zdarzyć błędy.

7. **Pliki użytkownika.** Jeżeli wgrywasz własne dane (np. CSV), pozostają one na Twoim urządzeniu.

8. **Odpowiedzialne korzystanie.** Korzystaj z aplikacji zgodnie z prawem i zasadami dobrego wychowania.

9. **Zmiany regulaminu.** Regulamin może się zmienić wraz z rozwojem aplikacji; aktualna wersja jest zawsze tutaj.
                        """)
                        if st.button("Oznacz jako przeczytane", key="teacher_reg_read_btn"):
                            st.session_state["_reg_read"] = True
                            st.rerun()
                    with st.expander("🔒 Polityka prywatności i regulamin konkursów", expanded=False):
                        st.markdown("""
**1. Postanowienia ogólne**  
1. Niniejszy regulamin określa zasady udziału w konkursach organizowanych w ramach projektu **Kopalnia Wiedzy** (dalej: „Konkurs”).  
2. Organizatorem Konkursu jest właściciel i administrator aplikacji Kopalnia Wiedzy (dalej: „Organizator”).  
3. Konkurs nie jest grą losową, loterią fantową, zakładem wzajemnym ani żadną inną formą gry wymagającą zgłoszenia do właściwych organów administracyjnych.  
4. Konkurs jest przeprowadzany w celach edukacyjnych i promocyjnych, a nagrody mają charakter drobnych upominków rzeczowych.

**2. Uczestnicy**  
1. Uczestnikiem Konkursu może być osoba pełnoletnia działająca jako rodzic lub opiekun prawny dziecka korzystającego z aplikacji Kopalnia Wiedzy.  
2. Rodzic/opiekun zgłasza udział dziecka w Konkursie poprzez formularz dostępny w zakładce **„Wsparcie i konkursy”**.  
3. Zgłoszenie udziału oznacza akceptację niniejszego regulaminu.

**3. Zasady uczestnictwa**  
1. Warunkiem przystąpienia do Konkursu jest dokonanie dobrowolnego wsparcia projektu poprzez dowolną wpłatę („darowiznę”) lub spełnienie innych warunków określonych w opisie konkretnej edycji Konkursu.  
2. Kwota wsparcia nie wpływa na szanse zwycięstwa, chyba że opis Konkursu stanowi inaczej (np. system losów).  
3. Zgłoszenie do Konkursu wymaga podania: imienia i nazwiska rodzica/opiekuna, adresu e-mail do kontaktu, opcjonalnie loginu dziecka w aplikacji.  
4. Wszystkie dane są wykorzystywane wyłącznie do przeprowadzenia Konkursu oraz kontaktu z osobami nagrodzonymi.

**4. Przebieg i rozstrzygnięcie Konkursu**  
1. Losowanie zwycięzców odbywa się z wykorzystaniem narzędzia dostępnego w panelu administratora aplikacji Kopalnia Wiedzy lub niezależnego skryptu losującego.  
2. W zależności od opisu edycji Konkursu losowanie może odbywać się: „każde zgłoszenie = 1 los”, „unikalny adres e-mail = 1 los”, lub według kryteriów punktowych (np. ranking XP dziecka).  
3. Wyniki losowania są zapisywane w formie elektronicznej i przechowywane dla celów dowodowych przez Organizatora.  
4. Organizator skontaktuje się ze zwycięzcami drogą e-mailową w celu ustalenia formy przekazania nagrody.

**5. Nagrody**  
1. Nagrody mają charakter upominków rzeczowych (np. książki edukacyjne, gry logiczne, zestawy kreatywne).  
2. Nagrody nie podlegają wymianie na gotówkę ani inne świadczenia.  
3. Organizator pokrywa koszty wysyłki nagród na terenie Polski.  
4. W przypadku braku kontaktu ze strony zwycięzcy przez **14 dni** od ogłoszenia wyników, nagroda przepada i może zostać przyznana innej osobie.

**6. Dane osobowe**  
1. Administratorem danych osobowych jest Organizator.  
2. Dane uczestników są przetwarzane wyłącznie na potrzeby przeprowadzenia Konkursu i przekazania nagród.  
3. Uczestnik ma prawo dostępu do swoich danych, ich poprawiania oraz żądania usunięcia.  
4. Dane nie są przekazywane podmiotom trzecim.

**7. Reklamacje**  
1. Reklamacje dotyczące Konkursu można kierować do Organizatora na adres kontaktowy wskazany w aplikacji.  
2. Reklamacje będą rozpatrywane w terminie do 14 dni od ich zgłoszenia.  
3. Decyzja Organizatora w sprawie reklamacji jest ostateczna.

**8. Postanowienia końcowe**  
1. Organizator zastrzega sobie prawo do zmian regulaminu, o ile nie wpływają one na prawa uczestników zdobyte przed zmianą.  
2. Organizator może unieważnić Konkurs w przypadku stwierdzenia nadużyć lub zdarzeń losowych uniemożliwiających jego prawidłowe przeprowadzenie.  
3. W sprawach nieuregulowanych regulaminem zastosowanie mają przepisy prawa polskiego.
                        """)
                        if st.button("Oznacz jako przeczytane", key="teacher_privacy_read_btn"):
                            st.session_state["_privacy_read"] = True
                            st.rerun()

                    terms_ok_t = bool(st.session_state.get("_reg_read")) and bool(st.session_state.get("_privacy_read"))
                    accept_t = st.checkbox(
                        "Akceptuję regulamin",
                        key="teacher_accept_terms",
                        disabled=not terms_ok_t,
                        help="Najpierw otwórz i przeczytaj Regulamin oraz Politykę prywatności powyżej.",
                    )
                    if not terms_ok_t:
                        st.caption("📋 Przeczytaj Regulamin i Politykę prywatności oraz oznacz oba jako przeczytane, aby odblokować tę opcję.")
                    parent_ok_t = st.checkbox("Jestem rodzicem/opiekunem i wyrażam zgodę", key="teacher_parent_ok")
                    if st.button("Załóż konto ✅", use_container_width=True, key="teacher_register_btn"):
                        ok_log_t, err_log_t = validate_login(re_user_t or "")
                        ok_pw_t, err_pw_t = validate_password(re_pass_t or "")
                        if not re_user_t or not re_pass_t:
                            st.error("Podaj login i hasło.")
                        elif not ok_log_t:
                            st.error(err_log_t)
                        elif not ok_pw_t:
                            st.error(err_pw_t)
                        elif re_user_t in db:
                            st.error("Taki login już istnieje.")
                        elif re_pass_t != re_pass2_t:
                            st.error("Hasła się różnią.")
                        elif not terms_ok_t:
                            st.error("Przeczytaj Regulamin i Politykę prywatności oraz oznacz oba jako przeczytane.")
                        elif not accept_t:
                            st.error("Musisz zaakceptować regulamin.")
                        elif not parent_ok_t:
                            st.error("Potrzebna jest zgoda rodzica/opiekuna.")
                        else:
                            salt = secrets.token_hex(8)
                            age_int_t = int(age_in_t)
                            db[re_user_t] = {
                                "salt": salt,
                                "password_hash": hash_pw(re_pass_t, salt),
                                "xp": 0, "stickers": [], "badges": [], "gems": 0, "unlocked_games": [], "memory": {},
                                "kid_name": (kid_name_t or "").strip() or re_user_t,
                                "age": age_int_t,
                                "age_group": age_to_group(age_int_t),
                                "accepted_terms_version": TERMS_VERSION,
                                "created_at": datetime.utcnow().isoformat(),
                            }
                            _save_users(db)
                            st.session_state.user = re_user_t
                            st.session_state["guest_mode"] = False
                            st.session_state.xp = 0
                            st.session_state.gems = 0
                            st.session_state.badges = set()
                            st.session_state.stickers = set()
                            st.session_state.unlocked_games = set()
                            st.session_state.memory_stats = {}
                            st.session_state.missions_state = {}
                            mc = st.session_state.get("mc") or {}
                            if isinstance(mc, dict):
                                mc.get("daily", {}).pop("toast", None)
                                mc.get("bonus", {}).pop("toast", None)
                            st.session_state["mc"] = mc
                            st.session_state.kid_name = db[re_user_t]["kid_name"]
                            st.session_state.age = age_int_t
                            st.session_state.age_group = db[re_user_t]["age_group"]
                            st.success("Konto utworzone! ✅ Zalogowano.")
                            st.rerun()
        else:
            st.success(f"✅ Zalogowano jako: **{u}**")
            st.info(
                "Masz **pełny dostęp do aplikacji**: portale (Misje, Quiz, Skrzynka, Pomoce szkolne itd.) "
                "są powyżej na tej stronie (portale). Tu w zakładkach zarządzasz kontem i **klasami**."
            )
            st.markdown("---")
            st.markdown("#### ➕ Utwórz nową klasę")
            st.caption("Podaj nazwę, wygeneruj kod i rozdaj go dzieciom. Uczniowie wpisują kod powyżej w sekcji **„Grasz z klasą?”**.")
            with st.expander("Utwórz klasę", expanded=True):
                class_label = st.text_input("Nazwa klasy (np. 4a, Matematyka 2025)", key="teacher_new_class_name", placeholder="4a")
                if st.button("Utwórz klasę i wygeneruj kod", key="teacher_create_btn", use_container_width=True):
                    code, msg = create_class(class_label or "Klasa", u)
                    if code:
                        st.session_state["teacher_last_code"] = code
                        st.success(msg)
                        st.info(f"📋 **Kod do skopiowania i podania dzieciom:** `{code}`")
                    else:
                        st.warning(msg)

            my_classes = list_classes_by_teacher(u)
            if my_classes:
                st.markdown("**Twoje klasy:**")
                for item in my_classes:
                    code, label, members = item["code"], item.get("label", ""), item.get("members", [])
                    with st.expander(f"📌 {label or code} — kod **{code}** ({len(members)} os.)"):
                        st.caption(f"Kod: `{code}` — podaj go uczniom.")
                        if members:
                            st.markdown("**Ekipa:**")
                            for m in members[-50:]:
                                nick = m.get("nick", "?")
                                usr = m.get("user", "")
                                st.markdown(f"- {nick}" + (f" *(zalog.: {usr})*" if usr else ""))
                        else:
                            st.caption("Jeszcze nikt nie dołączył. Podaj dzieciom kod powyżej.")

            st.markdown("**Zobacz ekipę po kodzie** (np. gdy kod utworzył inny nauczyciel):")
            view_code = st.text_input("Wpisz kod klasy", key="teacher_view_code", placeholder="A7K9Q2").strip().upper()
            if view_code and st.button("Pokaż ekipę", key="teacher_view_btn"):
                info = get_class_info(view_code)
                if info:
                    label = info.get("label", "")
                    members = info.get("members", [])
                    st.caption(f"Klasa: {label or view_code}")
                    if members:
                        for m in members[-50:]:
                            nick = m.get("nick", "?")
                            usr = m.get("user", "")
                            st.markdown(f"- {nick}" + (f" *({usr})*" if usr else ""))
                    else:
                        st.caption("Brak dołączonych osób.")
                else:
                    st.warning("Nie ma klasy o takim kodzie.")

    # ========= TAB: WSPARCIE I KONKURSY =========
    with tab_support:
        st.markdown("### ❤️ Wsparcie projektu")
        st.markdown(
            "**Kopalnia Wiedzy** to bezpłatna aplikacja – zależy nam, żeby każdy mógł z niej korzystać. "
            "Jeśli chcesz wesprzeć rozwój projektu (serwery, nowe treści, konkursy), "
            "będziemy bardzo wdzięczni – każda kwota ma znaczenie."
        )
        st.caption("Wsparcie jest dobrowolne. Aplikacja działa tak samo niezależnie od tego, czy wspierasz projekt, czy nie.")
        st.markdown("---")
        st.markdown("**Jak możesz pomóc?**")
        st.markdown("- 💳 **Wsparcie finansowe** – jeśli masz taką możliwość:")
        if SUPPORT_BUYMEACOFFEE_URL or SUPPORT_PAYPAL_URL:
            c1, c2 = st.columns(2)
            if SUPPORT_BUYMEACOFFEE_URL:
                with c1:
                    st.link_button("☕ Buy Me a Coffee", SUPPORT_BUYMEACOFFEE_URL, use_container_width=True)
            if SUPPORT_PAYPAL_URL:
                with c2:
                    st.link_button("💳 PayPal", SUPPORT_PAYPAL_URL, use_container_width=True)
            st.caption("Dziękujemy za każdą kawę i każdą złotówkę 💚")
        else:
            st.caption(f"Darowizna przez serwis płatności lub kontakt: {CONTACT_EMAIL}")
        st.markdown("- 📢 **Polecenie** – powiedz o Kopalni Wiedzy nauczycielom, rodzicom lub znajomym.")
        st.markdown(f"- 💡 **Pomysły** – masz sugestie? [Napisz do nas](mailto:{CONTACT_EMAIL}) – chętnie je przeczytamy.")
        st.markdown(f"- 📧 **Kontakt:** {CONTACT_EMAIL}")
        st.markdown("---")
        st.markdown("### 🏆 Konkursy")
        st.markdown("Informacje o **konkursach i wyzwaniach** dla klas i graczy pojawią się tutaj. Warto zaglądać! 🎯")

        with st.expander("📝 Zapisz się do konkursu", expanded=False):
            st.caption("Zgłoszenie do konkursu (imię i nazwisko opiekuna, e-mail, opcjonalnie login dziecka).")
            parent_name = st.text_input("Imię i nazwisko rodzica/opiekuna", key="contest_parent_name", placeholder="np. Anna Kowalska")
            email = st.text_input("Adres e-mail do kontaktu", key="contest_email", placeholder="np. anna@example.com")
            child_login = st.text_input("Login dziecka w aplikacji (opcjonalnie)", key="contest_child_login", placeholder="pozostaw puste, jeśli nie dotyczy")
            if st.button("Zgłoś udział w konkursie", key="contest_submit"):
                parent_name = (parent_name or "").strip()
                email = (email or "").strip()
                child_login = (child_login or "").strip()
                if not parent_name or not email:
                    st.error("Podaj imię i nazwisko opiekuna oraz adres e-mail.")
                else:
                    participants = load_contest_participants()
                    # unikamy duplikatów po e-mailu
                    if any(p.get("email", "").strip().lower() == email.lower() for p in participants):
                        st.info("Ten adres e-mail jest już zgłoszony do konkursu.")
                    else:
                        kid_name = ""
                        if child_login and is_logged and st.session_state.get("user") == child_login:
                            kid_name = (st.session_state.get("mc", {}).get("kid_name") or "").strip() or child_login
                        participants.append({
                            "parent_name": parent_name,
                            "email": email,
                            "login": child_login or "",
                            "kid_name": kid_name,
                            "registered_at": datetime.now().isoformat(),
                        })
                        save_contest_participants(participants)
                        st.success("Dziękujemy! Zgłoszenie do konkursu zostało zapisane.")

    # ---------------------------------
    # Portale: tylko dla zalogowanych (gość nie widzi zablokowanych kart)
    # ---------------------------------
    locked_notice = st.session_state.pop("locked_notice", None)
    if locked_notice and not is_logged:
        st.warning(f"🔒 {locked_notice} Zaloguj się w zakładce **Dla rodzica**, by odblokować.")

    if is_logged:
        if locked_notice:
            st.markdown(
                f"""
                <div class="d4k-panel d4k-panel-light" style="
                    border:2px solid #1f2937; border-radius:16px;
                    box-shadow:0 6px 0 rgba(31,41,55,.18);
                    padding:12px 12px; background:#ffffff;
                    margin:12px 0;
                ">
                <div style="font-family:'VT323', monospace; font-size:24px; line-height:1;">
                    🔒 Portal zablokowany
                </div>
                <div style="font-family:'VT323', monospace; font-size:20px; opacity:.95; margin-top:6px;">
                    {locked_notice}
                </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            c1, c2 = st.columns([1, 1])
            with c1:
                if st.button("👨‍👩‍👧 Przejdź do Panelu rodzica", use_container_width=True, key="locked_go_parent"):
                    goto("Panel rodzica")
                    st.stop()
            with c2:
                if st.button("🏠 Wróć do portali", use_container_width=True, key="locked_back_portals"):
                    goto("Start")
                    st.stop()

        st.markdown("### 🗺️ Wybierz portal")
        st.caption("Spokojnie, tu nie ma creeperów… chyba 👇")
        if "show_more_portals" not in st.session_state:
            st.session_state.show_more_portals = False

        st.markdown('<div class="d4k-cardgrid">', unsafe_allow_html=True)
        card("Mapa kopalni", "Twoje korytarze i postęp 🗺️", "⛏️",
             target="Mapa kopalni", color="reward",
             locked=False, key="card_mapa_kopalni", on_locked_msg="")
        card("Przedmioty szkolne", "Powtórki z lekcji 🧠", "📚",
             target="Przedmioty szkolne", color="primary",
             locked=False, key="card_school_world", on_locked_msg="")
        card("Poznaj dane", "Odkryj wykresy i liczby 🔎", "🔎",
             target="Poznaj dane", color="success",
             locked=False, key="card_learn_data_world", on_locked_msg="")
        card("Plac zabaw", "Symulacje i zabawy 🎲", "🎮",
             target="Plac zabaw", color="fun",
             locked=False, key="card_play_world", on_locked_msg="")
        card("Więcej", "Inne portale i tryby ➕", "➕",
             target=None, color="reward",
             locked=False, key="card_more_world", on_locked_msg="")
        st.markdown("</div>", unsafe_allow_html=True)

        if st.session_state.get("card_more_world"):
            st.session_state.show_more_portals = not st.session_state.show_more_portals
            st.rerun()

        if st.session_state.show_more_portals:
            st.caption("✨ Dodatkowe portale:")
            st.markdown('<div class="d4k-cardgrid">', unsafe_allow_html=True)
            card("Mapa kopalni", "Korytarze i postęp ⛏️", "⛏️", target="Mapa kopalni", color="reward",
                 locked=False, key="card_more_mapa", on_locked_msg="")
            card("Misje", "Zadania i XP ⚔️", "🗺️", target="Misje", color="reward",
                 locked=False, key="card_missions")
            card("Quiz obrazkowy", "Zgaduj i zdobywaj 💎", "🖼️", target="Quiz obrazkowy", color="primary",
                 locked=False, key="card_picquiz", on_locked_msg="")
            card("Quiz danych", "Dla ciekawych świata 🌍", "📊", target="Quiz danych", color="success",
                 locked=False, key="card_dataquiz", on_locked_msg="")
            card("Gra Saper", "Odkrywaj pola 💣", "💣", target="Saper", color="fun",
                 locked=False, key="card_saper", on_locked_msg="")
            card("Pomoce szkolne", "Narzędzia i pomoce 🧰", "🧰", target="Pomoce szkolne", color="primary",
                 locked=False, key="card_helpers", on_locked_msg="")
            card("Słowniczek", "Pojęcia i hasła 📖", "📖", target="Słowniczek", color="primary",
                 locked=False, key="card_slowniczek", on_locked_msg="")
            card("Album naklejek", "Twoje łupy 🏷️", "🗂️", target="Album naklejek", color="reward",
                 locked=False, key="card_album", on_locked_msg="")
            card("Hall of Fame", "Ranking i chwała ✨", "🏅", target="Hall of Fame", color="fun",
                 locked=False, key="card_hof", on_locked_msg="")
            st.markdown("</div>", unsafe_allow_html=True)

    elif guest_mode:
        st.caption("Jako gość masz dostęp do **Misji dnia** (przycisk 🚀 powyżej). Zaloguj się w zakładce **Dla rodzica**, by odblokować wszystkie portale.")

    # ---------------------------------
    # Grasz z klasą? — na samym dole
    # ---------------------------------
    st.divider()
    st.markdown("### 🏫 Grasz z klasą?")
    st.caption("Masz **kod od nauczyciela**? Wpisz go poniżej i dołącz do ekipy. *(Kod tworzy nauczyciel w zakładce **„Dla nauczyciela”**.)*")
    cc1, cc2 = st.columns([2, 1])
    with cc1:
        class_code_in = st.text_input("Kod klasy (np. A7K9Q2)", key="join_class_code")
        nick_in = st.text_input("Nick dziecka (np. Pixel-12)", key="join_class_nick")
    with cc2:
        if st.button("Dołącz ✅", use_container_width=True, key="join_class_btn"):
            ok, msg = join_class(
                class_code_in,
                (nick_in.strip() or st.session_state.get("kid_name") or "Gracz"),
            )
            if ok:
                st.success(msg)
                log_event("class_joined")
            else:
                st.warning(msg)
    if st.session_state.get("class_code"):
        st.caption(f"✅ Aktualna klasa: `{st.session_state.get('class_code')}`")

try:
    render()
except Exception as e:
    try:
        from core.ui import show_exception
        show_exception(e)
    except Exception:
        pass