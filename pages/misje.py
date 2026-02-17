# pyright: reportUndefinedVariable=false
from __future__ import annotations
import streamlit as st

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd

# runtime import (misje używają pd.DataFrame)
try:
    import pandas as pd  # type: ignore
except Exception:  # pragma: no cover
    pd = None  # type: ignore

import hashlib
import time as _time
import random as _random  # stdlib
from core.routing import goto_hard

def _task_id_from_text(text: str) -> str:
    """Stabilny ID z tekstu (bez zależności od app.py)."""
    try:
        return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()[:12]
    except Exception:
        return str(abs(hash(text)))[:12]


_DEPS_CACHE = None


def _deps() -> dict:
    """Zbiera zależności bez importu app.py (żeby uniknąć kółek)."""
    global _DEPS_CACHE
    if _DEPS_CACHE is not None:
        return _DEPS_CACHE

    import core.app_helpers as ah
    from core import missions as ms

    deps = {k: getattr(ah, k) for k in dir(ah) if not k.startswith("__")}
    deps.update({k: getattr(ms, k) for k in dir(ms) if not k.startswith("__")})

    _DEPS_CACHE = deps
    return deps


def render():
    # ✅ MULTIPAGE: nie dotykamy routera (page/query params), bo to powoduje pętle rerun/rozłączenia
    # Zostawiamy tylko bezpieczne defaulty sesji i dane.
    try:
        from core.state_init import ensure_session_defaults, ensure_default_dataset

        ensure_session_defaults()
        ensure_default_dataset()
    except Exception:
        # ultra-safe: nawet jeśli coś padnie, nie zabijamy strony
        pass

    deps = _deps()

    # ===== jawne powiązanie helperów (koniec magii globals()) =====
    def _require(name: str):
        fn = deps.get(name)
        if fn is None:
            raise RuntimeError(
                f"Brak funkcji '{name}' w deps. "
                f"Sprawdź czy jest w core.app_helpers albo core.missions."
            )
        return fn

    # bezpieczne (mogą nie istnieć — wtedy po prostu nic nie robią)
    log_event = deps.get("log_event", lambda *a, **k: None)
    top_nav_row = deps.get("top_nav_row", lambda *a, **k: None)

    # wymagane dla działania strony
    goto = _require("goto")

    get_daily_bonus_pack = _require("get_daily_bonus_pack")
    is_task_done = _require("is_task_done")
    mark_task_done = _require("mark_task_done")

    ensure_mc_state = _require("ensure_mc_state")
    daily_is_done = _require("daily_is_done")
    mark_daily_done = _require("mark_daily_done")

    get_profile = _require("get_profile")
    patch_profile = _require("patch_profile")

    add_xp = _require("add_xp")
    add_gems = _require("add_gems")
    grant_sticker = _require("grant_sticker")

    show_loot_popup = _require("show_loot_popup")
    confetti_reward = _require("confetti_reward")

    reward_school_section_once = _require("reward_school_section_once")
    claim_streak_lootbox = _require("claim_streak_lootbox")

    get_age_group = _require("get_age_group")
    load_tasks = deps.get("load_tasks", lambda *a, **k: {})
    target_difficulty = deps.get("target_difficulty", lambda *a, **k: None)
    filter_by_difficulty = deps.get("filter_by_difficulty", lambda arr, diff: arr)
    normalize_task_item = deps.get("_normalize_task_item", lambda it: it)
    pick_daily_chunk = deps.get("pick_daily_chunk", None)

    # pozostałe używane niżej (w Twoim kodzie występują jako gołe nazwy)
    apply_fantasy = _require("apply_fantasy")
    make_dataset = _require("make_dataset")
    DATASETS_PRESETS = _require("DATASETS_PRESETS")
    _today_key = _require("_today_key")
    _day_seed = _require("_day_seed")
    _time_to_next_daily_set_str = _require("_time_to_next_daily_set_str")
    _get_today_completion_key = _require("_get_today_completion_key")
    _guest_bonus_done_key = _require("_guest_bonus_done_key")

    show_exception = deps.get("show_exception")  # opcjonalne, na dole i tak jest try/except

    # --- LOTTIE / nagrody (między pytaniami + skrzynka na końcu) ---
    from pathlib import Path

    st_lottie = deps.get("st_lottie")          # opcjonalne
    load_lottie = deps.get("load_lottie")      # opcjonalne

    def _lottie_path(name: str) -> str:
        # assets/lottie/*.json (w root projektu)
        try:
            base = Path(__file__).resolve().parents[1] / "assets" / "lottie"
            return str(base / name)
        except Exception:
            return name  # fallback

    def _load_lottie_cached(name: str):
        """Ładuje lottie 1x na sesję (żeby nie mielić dysku przy rerunach)."""
        if not callable(load_lottie):
            return None
        cache = st.session_state.setdefault("_lottie_cache", {})
        if name in cache:
            return cache[name]
        anim = load_lottie(_lottie_path(name))
        cache[name] = anim
        return anim

    def _maybe_lottie(name: str, *, height: int = 140, loop: bool = False, key: str | None = None):
        anim = _load_lottie_cached(name)
        if anim and callable(st_lottie):
            try:
                st_lottie(anim, height=height, loop=loop, key=key)
            except Exception:
                pass

    def _render_reward_card(title: str, msg: str, *, key_prefix: str, lottie: str = "Successfully.json"):
        """Spójny wygląd 'Dobrze / Nagroda' między pytaniami."""
        _maybe_lottie(lottie, height=120, loop=False, key=f"{key_prefix}_lottie")
        if title:
            st.success(title)
        if msg:
            st.info(msg)

    def _render_chest_card(title: str, msg: str, *, key_prefix: str):
        """Skrzynka finałowa (Lottie)."""
        _maybe_lottie("Chest_Spawn.json", height=220, loop=False, key=f"{key_prefix}_chest")
        _maybe_lottie("Diamonds.json", height=140, loop=True, key=f"{key_prefix}_diamonds")
        if title:
            st.success(title)
        if msg:
            st.info(msg)

    # --- start UI ---
    # log tylko raz na wejście na stronę (żeby reruny nie spamowały)
    if st.session_state.get("_page") != "Misje":
        st.session_state["_page"] = "Misje"
        log_event("page_misje")

    top_nav_row("🗺 Misje", back_default="Start", show_start=True)

    # szybkie przełączenie trybu dla zalogowanego (gdyby wejście ze Startu się rozjechało)
    if bool(st.session_state.get("user")) and not (isinstance(st.session_state.get("user"), str) and str(st.session_state.get("user")).startswith("Gosc-")):
        cquick1, cquick2 = st.columns(2)
        with cquick1:
            if st.button("▶️ Misja dnia (zalogowany)", use_container_width=True, key="quick_daily_logged"):
                st.session_state["missions_view"] = "daily"
                st.session_state["_force_daily_once"] = True
                st.rerun()
        with cquick2:
            if st.button("🧩 Bonusy po dziennych", use_container_width=True, key="quick_bonus_logged"):
                st.session_state["missions_view"] = "bonus"
                st.rerun()

    # --- AUTO-GOŚĆ tylko gdy wybrano tryb Gościa ---
    u0 = st.session_state.get("user")
    is_logged = bool(u0) and isinstance(u0, str) and not u0.startswith("Gosc-")
    guest_mode_flag = bool(st.session_state.get("guest_mode"))

    # Debug flag z URL (?debug=1)
    try:
        dbg = st.query_params.get("debug")
        if isinstance(dbg, list):
            dbg = dbg[0] if dbg else None
        st.session_state["_debug_misje"] = (str(dbg).strip() in ("1", "true", "yes"))
    except Exception:
        pass

    # Jeśli jesteś zalogowany, NIE pozwalamy, żeby ?g=Gosc-... cokolwiek nadpisywało
    if is_logged:
        try:
            # czyścimy parametr gościa z URL, żeby inne strony też nie brały go na serio
            st.query_params.pop("g", None)
        except Exception:
            pass
    else:
        # 1) Spróbuj wziąć usera z query param (np. /misje?g=Gosc-1234)
        if not st.session_state.get("user"):
            try:
                qp = st.query_params
                g = qp.get("g")
                if isinstance(g, list):
                    g = g[0] if g else None
                if isinstance(g, str) and g.startswith("Gosc-"):
                    st.session_state["user"] = g
            except Exception:
                pass

            # 2) Jak nadal brak – stwórz gościa tylko jeśli tryb Gościa jest wybrany
            if not st.session_state.get("user") and guest_mode_flag:
                guest = f"Gosc-{_random.randint(1000, 9999)}"
                try:
                    from core.persistence import record_guest_signup, _load_users, _save_users
                    from datetime import datetime
                    record_guest_signup()
                    db = _load_users() or {}
                    db[guest] = {"created_at": datetime.utcnow().isoformat()}
                    _save_users(db)
                except Exception:
                    pass
                st.session_state["user"] = guest

    user = st.session_state.get("user")
    if not user:
        last_user = st.session_state.get("_last_user")
        if isinstance(last_user, str) and not last_user.startswith("Gosc-"):
            st.session_state["user"] = last_user
            user = last_user
    if not user:
        st.info("Zagraj jako Gość albo zaloguj się na Start 🙂")
        st.stop()
    is_guest_user = isinstance(user, str) and user.startswith("Gosc-")

    def bonus_is_done_today(user_: str) -> bool:
        # Gość: tylko blokada sesyjna
        if isinstance(user_, str) and user_.startswith("Gosc-"):
            return bool(st.session_state.get(_guest_bonus_done_key(), False))

        # Zalogowany: sprawdzamy realnie po zadaniach zapisanych w DB
        bonus_pack_ = get_daily_bonus_pack(user_, k=3)
        if not bonus_pack_:
            return True  # nie ma bonusów → nie blokuj „kompletu”

        for it in bonus_pack_:
            subject_ = (it.get("subject") or "").strip()
            task_ = it.get("task") or {}
            q_text_ = (task_.get("q") or "").strip()
            if not subject_ or not q_text_:
                continue
            if not is_task_done(user_, subject_, q_text_):
                return False
        return True

    # =========================================================
    # Minecraft Mobile Missions — JEDEN, wersjonowany stan w st.session_state["mc"]
    # =========================================================
    today = _today_key()
    mc = ensure_mc_state(today=today)
    # Upewnij się, że mc jest trwale w session_state (chroni przed pętlą gdy ensure_mc_state zwraca kopię)
    st.session_state["mc"] = mc

    # ---------------------------------------------------------
    # FIX: po modularyzacji mc (missions controller) bywał dzielony
    #      między różnymi użytkownikami w tej samej sesji (np. logowanie/
    #      tryb gościa). To powodowało, że Gość dziedziczył tryb/step "done"
    #      i nie mógł uruchomić misji.
    # ---------------------------------------------------------
    mc_user = mc.get("_user") if isinstance(mc, dict) else None
    if isinstance(mc, dict) and mc_user != str(user):
        # reset tylko przy zmianie usera (bez utraty innych kluczy sesji)
        mc = ensure_mc_state(today=today)
        mc["_user"] = str(user)
        mc["mode"] = "daily" if is_guest_user else "free"
        mc["step"] = 0
        st.session_state["mc"] = mc
        mc.setdefault("daily", {})
        mc["daily"].pop("toast", None)
        mc["daily"].pop("rewarded", None)
        mc["daily"].pop("q", None)
        mc["daily"].pop("ui", None)

        # 🔒 WAŻNE: przy zmianie usera wyczyść „migawki” nagród,
        # inaczej zalogowany może odziedziczyć skrzynkę po gościu (lub odwrotnie)
        mc["daily"].pop("interstitial", None)
        mc["daily"].pop("finish_reward", None)

        mc.setdefault("bonus", {})
        mc["bonus"].pop("toast", None)
        mc["bonus"].pop("ui", None)
        mc["bonus"].pop("interstitial", None)
        mc["bonus"].pop("finish_reward", None)
        mc["bonus"]["active_i"] = 0
        mc["bonus"].pop("done_day", None)

        st.session_state["mc"] = mc
        # wymuś świeży render po logowaniu (żeby nie łapać starego układu),
        # ale nie przerywaj, jeśli jest intencja wejścia w misję dnia
        if not st.session_state.get("missions_view"):
            st.rerun()


    # --- INTENCJA WEJŚCIA (np. ze Startu / po logowaniu) ---
    # NIE używamy pop() na wejściu, bo rerun może “zjeść” intencję zanim tryb się ustawi.
    view = st.session_state.pop("missions_view", None)
    forced_view = view in ("daily", "bonus", "done", "subject")
    force_daily_once = bool(st.session_state.pop("_force_daily_once", False))
    force_daily_until = float(st.session_state.pop("force_daily_until", 0) or 0)

    if view == "daily":
        mc["mode"] = "daily"
        if mc.get("mode") != "daily" or mc.get("step") is None:
            mc["step"] = 0

        mc.setdefault("daily", {})
        for k in ("q", "ui", "toast"):
            mc["daily"].pop(k, None)
        mc["daily"].pop("rewarded", None)

        # start dziennych ma zawsze zaczynać od pytania, nie od starej skrzynki
        mc["daily"].pop("interstitial", None)
        mc["daily"].pop("finish_reward", None)

        log_event("mc_daily_intent_seen", {"step": mc.get("step")})

    elif view == "bonus":
        mc["mode"] = "bonus"

        mc.setdefault("bonus", {})
        mc["bonus"].pop("toast", None)
        mc["bonus"].pop("interstitial", None)
        mc["bonus"].pop("finish_reward", None)
        mc["bonus"]["active_i"] = int(mc["bonus"].get("active_i", 0) or 0)

        log_event("mc_bonus_intent_seen")
    elif view == "done":
        mc["mode"] = "done"
        log_event("mc_done_intent_seen")
    elif view == "subject":
        mc["mode"] = "subject"
        mc["subject"] = st.session_state.get("bonus_subject")
        mc.setdefault("subject_ui", {})
        log_event("mc_subject_intent_seen", {"subject": mc.get("subject")})
    elif view is None:
        # Gość: domyślnie misja dnia, ale nie nadpisuj trybu „bonus”
        # Zalogowany: zachowaj aktualny tryb, chyba że nic nie wybrane
        if is_guest_user:
            if mc.get("mode") not in ("bonus", "subject", "daily"):
                mc["mode"] = "daily"
        else:
            if mc.get("mode") not in ("daily", "bonus", "done", "subject"):
                mc["mode"] = "free"

    # twarde wymuszenie misji dnia po kliknięciu na Start
    if force_daily_once:
        mc["mode"] = "daily"
        mc["step"] = 0
        mc.setdefault("daily", {})
        for k in ("q", "ui", "toast", "rewarded", "interstitial", "finish_reward"):
            mc["daily"].pop(k, None)
        mc["daily"].pop("rewarded_day", None)

    if (not is_guest_user) and (_time.time() < force_daily_until):
        mc["mode"] = "daily"
        mc["step"] = 0
        mc.setdefault("daily", {})
        for k in ("q", "ui", "toast", "rewarded", "interstitial", "finish_reward"):
            mc["daily"].pop(k, None)
        mc["daily"].pop("rewarded_day", None)

        st.session_state["mc"] = mc
        st.rerun()

    mc["locked"] = False
    st.session_state["mc"] = mc

    # Teraz dopiero czyścimy flagę (po utrwaleniu trybu)
    if forced_view:
        st.session_state.pop("missions_view", None)
    log_event("mc_after_intent_apply", {"mode": mc.get("mode"), "step": mc.get("step")})

    # DEBUG: pokaż źródło trybu (tylko jeśli włączone ręcznie)
    if st.session_state.get("_debug_misje"):
        with st.expander("🐛 Debug Misje"):
            st.write({
                "user": str(user),
                "is_guest": is_guest_user,
                "missions_view": view,
                "force_daily_once": force_daily_once,
                "mode": mc.get("mode"),
                "step": mc.get("step"),
            })


    # Dataset do misji
    df = st.session_state.get("data")
    if pd is None or df is None or not isinstance(df, pd.DataFrame) or df.empty or len(df.columns) == 0:
        st.info("Brak danych do misji dnia — wróć na Start i załaduj zestaw.")
        if st.button("🛠️ Wczytaj domyślny zestaw teraz"):
            st.session_state["data"] = make_dataset(
                140,
                DATASETS_PRESETS["10-12"]["Średni"],
                seed=42
            )
            st.rerun()
        st.stop()

    daily_state = mc.setdefault("daily", {})

    def _on_fantasy_change():
        st.session_state["_fantasy_toggle_changed"] = True

    # Fantasy mode: toggle globalny, ale dane dnia zamrażamy w mc["daily"]["df_used"]
    fantasy_val = st.toggle(
        "🧙 Fantasy mode (bajkowe dane)",
        key="fantasy_mode",
        value=bool(daily_state.get("_fantasy_mode", False)),
        on_change=_on_fantasy_change,
    )
    # Jeśli użytkownik zmienił tryb, wymuś przebudowę danych
    if st.session_state.pop("_fantasy_toggle_changed", False):
        for k in ("df_used", "q", "ui", "rewarded", "toast", "interstitial", "finish_reward"):
            daily_state.pop(k, None)
        daily_state["_fantasy_mode"] = bool(fantasy_val)
        mc["step"] = 0
        mc["daily"] = daily_state
        st.session_state["mc"] = mc
        st.rerun()

    # ✅ Jeśli gracz przełączy Fantasy mode w trakcie dnia, odświeżamy cache
    cur_fantasy = bool(st.session_state.get("fantasy_mode"))
    prev_fantasy = daily_state.get("_fantasy_mode")

    # 🟢 Pierwsze wejście — zapamiętaj tryb i ewentualnie wyczyść stary cache
    if prev_fantasy is None:
        daily_state["_fantasy_mode"] = cur_fantasy

        # jeśli mamy już zbudowany df z poprzedniego trybu, przebuduj go
        if "df_used" in daily_state:
            for k in ("df_used", "q", "ui", "toast"):
                daily_state.pop(k, None)

            mc["step"] = 0
            mc["daily"] = daily_state
            st.session_state["mc"] = mc
            st.rerun()

    # 🔁 Zmiana trybu fantasy ↔ normal
    elif prev_fantasy != cur_fantasy:
        for k in ("df_used", "q", "ui", "rewarded", "toast"):
            daily_state.pop(k, None)

        daily_state["_fantasy_mode"] = cur_fantasy
        mc["step"] = 0
        mc["daily"] = daily_state
        st.session_state["mc"] = mc
        st.rerun()

    # ✅ df_used zgodnie z aktualnym fantasy_mode
    # Zasada: jeśli df_used jest brakujące LUB wadliwe → regenerujemy, bez pętli rerun.
    df_used = daily_state.get("df_used")

    need_rebuild = (
        pd is None
        or (df_used is None)
        or (not isinstance(df_used, pd.DataFrame))
        or getattr(df_used, "empty", True)
    )

    if need_rebuild:
        log_event("mc_daily_df_used_rebuild", {
            "had_df_used": "df_used" in daily_state,
            "fantasy": bool(cur_fantasy),
            "df_rows": int(getattr(df, "shape", (0, 0))[0]),
            "df_cols": int(getattr(df, "shape", (0, 0))[1]),
        })

        df_used = df.copy()
        if cur_fantasy:
            try:
                df_used = apply_fantasy(df_used, seed=_day_seed(today))
            except Exception:
                df_used = df.copy()

        daily_state["df_used"] = df_used
        # utrwalamy cache w mc + session_state (żeby nie znikał przy rerun)
        mc["daily"] = daily_state
        st.session_state["mc"] = mc

    # =========================================================
    # HUD: streak / freeze / xp
    # =========================================================
    prof = get_profile(user) or {}
    ret = (prof.get("retention", {}) or {})
    streak = int(ret.get("streak", 0))
    freezes = int(ret.get("freezes", 0))

    h1, h2, h3, h4, h5 = st.columns([1.0, 1.0, 1.0, 1.25, 1.0])
    with h1:
        st.markdown(
            f"<div class='d4k-stat'>🔥 <b>Seria</b><br/><span class='d4k-stat-num'>{streak}</span> dni</div>",
            unsafe_allow_html=True
        )
    with h2:
        st.markdown(
            f"<div class='d4k-stat'>🧊 <b>Freeze</b><br/><span class='d4k-stat-num'>{freezes}</span> szt.</div>",
            unsafe_allow_html=True
        )
    with h3:
        xp = int(st.session_state.get("xp", prof.get("xp", 0)) or 0)
        st.markdown(
            f"<div class='d4k-stat'>✨ <b>XP</b><br/><span class='d4k-stat-num'>{xp}</span></div>",
            unsafe_allow_html=True
        )
    with h4:
        gems = int(st.session_state.get("gems", prof.get("gems", 0)) or 0)
        st.markdown(
            f"<div class='d4k-stat'>💎 <b>Diamenty</b><br/><span class='d4k-stat-num'>{gems}</span></div>",
            unsafe_allow_html=True
        )
    with h5:
        ag = get_age_group()
        st.markdown(
            f"<div class='d4k-stat'>👶 <b>Grupa</b><br/><span class='d4k-stat-num'>{ag}</span></div>",
            unsafe_allow_html=True
        )

    with st.expander("🧊 Co to robi?"):
        st.info(
            "Freeze Day ratuje serię, gdy ominiesz **1 dzień**.\n\n"
            "Przykład:\n"
            "Poniedziałek ✔️ → Wtorek ❌ → Środa ✔️\n\n"
            "Jeśli masz 🧊 Freeze, seria się **nie resetuje**."
        )

    if freezes > 0 and not ret.get("freeze_tutorial_seen", False):
        st.toast("🧊 Masz Freeze Day! To jest Twoja tarcza na 1 opuszczony dzień 😎", icon="🧊")
        ret["freeze_tutorial_seen"] = True
        patch_profile({"retention": ret}, user=user)

    st.caption(f"Seria dni: **{streak}**  •  🧊 Freeze: **{freezes}**")

    # Gość ma zawsze mieć dostęp do Misji Dnia.
    # Auto-przełączanie na "bonus" ma sens tylko dla kont zalogowanych (retencja/streak/DB).
    daily_toast = None  # daily toast czyścimy wcześniej, tu nie używamy
    if (
        (not forced_view)
        and (mc.get("mode") not in ("free", "subject"))
        and (not str(user).startswith("Gosc-"))
        and daily_is_done(user)
        and (not daily_toast)
    ):
        mc["mode"] = "bonus"


    def _guest_day_reward_if_done():
        today_key = _get_today_completion_key()
        if (
            st.session_state.get("guest_daily_done_day") == today_key
            and st.session_state.get("guest_bonus_done_day") == today_key
            and not st.session_state.get("guest_day_rewarded")
        ):
            add_gems(3, reason="guest_day_complete")
            st.session_state["guest_day_rewarded"] = today_key
            st.toast("💎 Skrzynka z diamentami! +3 💎", icon="💎")

    def _guest_both_done_today():
        """Czy gość zaliczył dziś i misję dnia, i bonusy."""
        today_key = _get_today_completion_key()
        return (
            st.session_state.get("guest_daily_done_day") == today_key
            and st.session_state.get("guest_bonus_done_day") == today_key
        )

    def _render_guest_all_done_screen():
        """Ekran po zakończeniu misji dnia + bonusów gościa: skrzynka + zachęta do logowania."""
        st.success("🎉 Misja dnia i bonusy na dziś zaliczone!")
        st.markdown("**💎 Skrzynka z diamentami** — za ukończenie obu zestawów otrzymujesz **+3 💎** (odebrane na koncie gościa).")
        st.markdown("---")
        st.markdown("**Zaloguj się**, żeby w pełni korzystać z aplikacji:")
        st.markdown("- zapisywany postęp i seria dni (streak),")
        st.markdown("- więcej misji i nagród,")
        st.markdown("- odblokowanie Skrzynki, quizów i innych portali.")
        if st.button("🏠 Przejdź na Start i zaloguj się", use_container_width=True, key="guest_all_done_to_start"):
            goto_hard("Start")
            return

    def render_guest_daily():
        if _guest_both_done_today():
            _render_guest_all_done_screen()
            return

        st.markdown("### 🧭 Misja dnia dla Gościa (5 zadań)")
        st.caption("To próbka możliwości — zestaw zmienia się codziennie.")

        df_base = daily_state.get("df_used") if isinstance(daily_state, dict) else None
        df_local = df_base if isinstance(df_base, pd.DataFrame) else df

        # ✅ wymuś Fantasy/Normal na danych Gościa niezależnie od cache
        fantasy_on = bool(st.session_state.get("fantasy_mode"))
        try:
            base_df = df_local.copy()
        except Exception:
            base_df = df_local
        fantasy_df = base_df
        if fantasy_on:
            try:
                fantasy_df = apply_fantasy(base_df.copy(), seed=_day_seed(today))
            except Exception:
                fantasy_df = base_df
        df_local = fantasy_df if fantasy_on else base_df

        # mały podgląd, żeby było widać różnice
        try:
            st.caption(f"Fantasy mode: {'ON' if fantasy_on else 'OFF'}")
        except Exception:
            pass
        if isinstance(base_df, pd.DataFrame):
            preview_cols = [c for c in base_df.columns if any(k in str(c).lower() for k in ["miasto", "owoc", "imie", "imię", "name", "city", "fruit"])]
            if preview_cols:
                with st.expander("👀 Podgląd danych (Fantasy)"):
                    try:
                        if fantasy_on:
                            st.table(fantasy_df[preview_cols].head(10))
                        else:
                            st.table(base_df[preview_cols].head(10))
                    except Exception:
                        try:
                            st.write((fantasy_df if fantasy_on else base_df)[preview_cols].head(10))
                        except Exception:
                            pass

        if pd is None or df_local is None or not isinstance(df_local, pd.DataFrame) or df_local.empty:
            st.info("Brak danych do misji — wróć na Start i załaduj zestaw.")
            return

        try:
            seed_txt = f"{_today_key()}::guest_daily"
            seed = int(hashlib.sha256(seed_txt.encode("utf-8")).hexdigest(), 16) % (2**32)
        except Exception:
            seed = 42
        rng = _random.Random(seed)

        done_key = f"guest_daily_done_{_today_key()}"
        done_set = st.session_state.setdefault(done_key, set())
        if not isinstance(done_set, set):
            done_set = set(done_set or [])
            st.session_state[done_key] = done_set

        num_cols = [c for c in df_local.columns if pd.api.types.is_numeric_dtype(df_local[c])]
        cat_cols = [c for c in df_local.columns if not pd.api.types.is_numeric_dtype(df_local[c])]

        if not num_cols:
            st.warning("Brak kolumn liczbowych do misji.")
            return

        col_max = rng.choice(num_cols)
        col_min = rng.choice([c for c in num_cols if c != col_max] or num_cols)
        col_avg = rng.choice(num_cols)
        col_unique = rng.choice([c for c in df_local.columns if df_local[c].nunique(dropna=True) > 1] or df_local.columns)
        col_cat = rng.choice(cat_cols) if cat_cols else None

        def _reward_once(mission_id: str, ok: bool):
            if not ok or mission_id in done_set:
                return
            add_xp(2, reason=f"guest_daily::{mission_id}")
            done_set.add(mission_id)
            st.session_state[done_key] = done_set

        def _choices_numeric(series, correct):
            if correct is None:
                return []
            if abs(float(correct) - round(float(correct))) < 1e-9:
                base = int(round(float(correct)))
                opts = [base, base - 1, base + 1, base + 2, base - 2]
                opts = [x for x in opts if x is not None]
                opts = list(dict.fromkeys(opts))
            else:
                base = float(correct)
                opts = [base, base - 0.5, base + 0.5, base + 1.0, base - 1.0]
                opts = [round(x, 2) for x in opts]
                opts = list(dict.fromkeys(opts))
            rng.shuffle(opts)
            return opts

        st.progress(min(1.0, len(done_set) / 5))
        st.caption(f"Postęp: **{len(done_set)} / 5** ✅")

        s_max = pd.to_numeric(df_local[col_max], errors="coerce").dropna()
        max_val = s_max.max() if not s_max.empty else None
        opts_max = _choices_numeric(s_max, max_val)
        if "max" not in done_set:
            with st.expander("👀 Podgląd danych (max)"):
                try:
                    st.table(s_max.describe().to_frame(name=col_max))
                except Exception:
                    st.write(s_max.describe())
            pick = st.radio(
                f"1) Jaka jest największa wartość w kolumnie **{col_max}**?",
                options=opts_max,
                key=f"guest_max_{_today_key()}",
                index=None,
            )
            if st.button("Sprawdź ✅", key="guest_max_check"):
                ok = pick is not None and float(pick) == float(max_val)
                if ok:
                    st.success("✅ Dobrze!")
                    _reward_once("max", ok)
                    st.rerun()
                else:
                    st.error(f"❌ Nie. Poprawna: **{max_val}**")
                    _reward_once("max", ok)
        else:
            st.success("✅ 1) Zaliczone")

        s_min = pd.to_numeric(df_local[col_min], errors="coerce").dropna()
        min_val = s_min.min() if not s_min.empty else None
        opts_min = _choices_numeric(s_min, min_val)
        if "min" not in done_set:
            with st.expander("👀 Podgląd danych (min)"):
                try:
                    st.table(s_min.describe().to_frame(name=col_min))
                except Exception:
                    st.write(s_min.describe())
            pick = st.radio(
                f"2) Jaka jest najmniejsza wartość w kolumnie **{col_min}**?",
                options=opts_min,
                key=f"guest_min_{_today_key()}",
                index=None,
            )
            if st.button("Sprawdź ✅", key="guest_min_check"):
                ok = pick is not None and float(pick) == float(min_val)
                if ok:
                    st.success("✅ Dobrze!")
                    _reward_once("min", ok)
                    st.rerun()
                else:
                    st.error(f"❌ Nie. Poprawna: **{min_val}**")
                    _reward_once("min", ok)
        else:
            st.success("✅ 2) Zaliczone")

        s_avg = pd.to_numeric(df_local[col_avg], errors="coerce").dropna()
        avg_val = round(float(s_avg.mean()), 1) if not s_avg.empty else None
        opts_avg = _choices_numeric(s_avg, avg_val)
        if "avg" not in done_set:
            with st.expander("👀 Podgląd danych (średnia)"):
                try:
                    st.table(s_avg.describe().to_frame(name=col_avg))
                except Exception:
                    st.write(s_avg.describe())
            pick = st.radio(
                f"3) Jaka jest średnia wartość w kolumnie **{col_avg}**?",
                options=opts_avg,
                key=f"guest_avg_{_today_key()}",
                index=None,
            )
            if st.button("Sprawdź ✅", key="guest_avg_check"):
                ok = pick is not None and float(pick) == float(avg_val)
                if ok:
                    st.success("✅ Dobrze!")
                    _reward_once("avg", ok)
                    st.rerun()
                else:
                    st.error(f"❌ Nie. Poprawna: **{avg_val}**")
                    _reward_once("avg", ok)
        else:
            st.success("✅ 3) Zaliczone")

        unique_val = int(df_local[col_unique].nunique(dropna=True)) if col_unique is not None else None
        opts_unique = _choices_numeric(df_local[col_unique], unique_val)
        if "uniq" not in done_set:
            with st.expander("👀 Podgląd danych (unikalne)"):
                try:
                    vc = df_local[col_unique].astype(str).value_counts().head(15).to_frame(name="liczba")
                    st.table(vc)
                except Exception:
                    pass
            pick = st.radio(
                f"4) Ile jest unikalnych wartości w kolumnie **{col_unique}**?",
                options=opts_unique,
                key=f"guest_uniq_{_today_key()}",
                index=None,
            )
            if st.button("Sprawdź ✅", key="guest_uniq_check"):
                ok = pick is not None and int(pick) == int(unique_val)
                if ok:
                    st.success("✅ Dobrze!")
                    _reward_once("uniq", ok)
                    st.rerun()
                else:
                    st.error(f"❌ Nie. Poprawna: **{unique_val}**")
                    _reward_once("uniq", ok)
        else:
            st.success("✅ 4) Zaliczone")

        if col_cat:
            vc = df_local[col_cat].astype(str).value_counts()
            correct = vc.index[0] if not vc.empty else None
            opts = list(vc.index[:4]) if len(vc.index) >= 4 else list(vc.index)
            rng.shuffle(opts)
            if "cat" not in done_set:
                with st.expander("👀 Podgląd danych (najczęstsze)"):
                    try:
                        st.table(vc.head(15).to_frame(name="liczba"))
                    except Exception:
                        pass
                pick = st.radio(
                    f"5) Co pojawia się najczęściej w kolumnie **{col_cat}**?",
                    options=opts,
                    key=f"guest_cat_{_today_key()}",
                    index=None,
                )
                if st.button("Sprawdź ✅", key="guest_cat_check"):
                    ok = pick == correct
                    if ok:
                        st.success("✅ Dobrze!")
                        _reward_once("cat", ok)
                        st.rerun()
                    else:
                        st.error(f"❌ Nie. Poprawna: **{correct}**")
                        _reward_once("cat", ok)
            else:
                st.success("✅ 5) Zaliczone")
        else:
            st.info("Brak kolumn tekstowych do 5. misji.")

        if done_set.issuperset({"max", "min", "avg", "uniq", "cat"} if col_cat else {"max", "min", "avg", "uniq"}):
            today_done_key = _get_today_completion_key()
            st.session_state["guest_daily_done_day"] = today_done_key
            _guest_day_reward_if_done()
            # Gdy oba zestawy zaliczone — od razu pokaż ekran ze skrzynią i zachętą do logowania
            if st.session_state.get("guest_bonus_done_day") == today_done_key:
                st.session_state["mc"] = mc
                st.rerun()

        c1, c2 = st.columns(2)
        with c1:
            if st.button("🧩 Bonusy (Gość)", use_container_width=True, key="guest_daily_to_bonus"):
                mc["mode"] = "bonus"
                st.session_state["mc"] = mc
                st.rerun()
        with c2:
            if st.button("🏠 Start", use_container_width=True, key="guest_daily_to_start"):
                goto_hard("Start")
                return

    def render_guest_bonus():
        if _guest_both_done_today():
            _render_guest_all_done_screen()
            return

        st.markdown("### 🎁 Bonusy dla Gościa (5 zadań)")
        st.caption("Bonusy są niezależne od Misji dnia i resetują się codziennie.")

        try:
            tasks = load_tasks()
        except Exception:
            tasks = {}

        age_group = get_age_group()
        pool = []
        if isinstance(tasks, dict):
            for subj, obj in tasks.items():
                if not isinstance(obj, dict):
                    continue
                arr = obj.get(age_group, [])
                if isinstance(arr, list):
                    for it in arr:
                        if isinstance(it, dict):
                            t = normalize_task_item(it)
                            t.setdefault("xp", 5)
                            pool.append({"subject": subj, "task": t})

        def _gen_math_task(rng, idx: int):
            a = rng.randint(2, 12)
            b = rng.randint(2, 12)
            op = rng.choice(["+", "-", "*"])
            if op == "+":
                correct_val = a + b
            elif op == "-":
                if b > a:
                    a, b = b, a
                correct_val = a - b
            else:
                correct_val = a * b
            options = [correct_val, correct_val + 1, max(0, correct_val - 1), correct_val + 2]
            options = list(dict.fromkeys(options))
            rng.shuffle(options)
            correct_idx = options.index(correct_val)
            return {
                "subject": "matematyka",
                "task": {
                    "type": "mcq",
                    "q": f"Policz: {a} {op} {b}",
                    "options": [str(x) for x in options],
                    "correct": correct_idx,
                    "xp": 5,
                },
            }

        # Jeśli jest mało pytań w tasks.json, dobijamy prostymi zadaniami
        if len(pool) < 10:
            try:
                today_key = _get_today_completion_key()
                seed = int(hashlib.sha256(f"guest_bonus::{today_key}".encode("utf-8")).hexdigest(), 16) % (2**32)
            except Exception:
                seed = 42
            rng_extra = _random.Random(seed)
            while len(pool) < 10:
                pool.append(_gen_math_task(rng_extra, len(pool)))

        if not pool:
            st.info("Brak zadań bonusowych w tasks.json.")
            return

        today_key = _get_today_completion_key()
        if callable(pick_daily_chunk):
            pack = pick_daily_chunk(pool, 5, salt=f"guest_bonus::{today_key}")
        else:
            pack = pool[:5]

        # jeśli mamy mniej niż 5 pytań, dobijamy powtórkami (deterministycznie)
        if pool and len(pack) < 5:
            i = 0
            while len(pack) < 5:
                pack.append(pool[i % len(pool)])
                i += 1

        done_key = f"guest_bonus_done_{today_key}"
        done_set = st.session_state.setdefault(done_key, set())
        if not isinstance(done_set, set):
            done_set = set(done_set or [])
            st.session_state[done_key] = done_set

        total = max(1, len(pack))
        st.progress(min(1.0, len(done_set) / total))
        st.caption(f"Postęp: **{len(done_set)} / {total}** ✅")

        # feedback z ostatniego sprawdzenia (żeby po rerun widać było Dobrze/Nie)
        feedback = st.session_state.get("guest_bonus_feedback") or {}
        feedback_tid = feedback.get("tid")

        for i, it in enumerate(pack, start=1):
            subject = (it.get("subject") or "").strip() or "Bonus"
            task = it.get("task") or {}
            q_text = (task.get("q") or "").strip()
            tid = _task_id_from_text(f"{subject}::{q_text}")

            st.markdown(f"**{i}. {subject.title()}**")
            st.write(q_text or "Brak treści pytania.")

            opts = task.get("options") or task.get("choices") or task.get("answers")
            if isinstance(opts, (tuple, set)):
                opts = list(opts)
            if not isinstance(opts, list):
                opts = []

            correct = task.get("correct")
            if correct is None:
                correct = task.get("answer")
            if correct is None:
                correct = task.get("a")
            if correct is not None:
                correct = str(correct).strip()
            if correct is not None and opts:
                c = str(correct).strip()
                if c.isdigit():
                    idx = int(c)
                    if 0 <= idx < len(opts):
                        correct = str(opts[idx]).strip()

            if tid in done_set:
                # tuż po sprawdzeniu pokaż Dobrze/Nie, potem Zaliczone
                if feedback_tid == tid:
                    if feedback.get("ok"):
                        st.success("✅ Dobrze!")
                    else:
                        st.error(f"❌ Nie. Poprawna: **{feedback.get('correct', '—')}**")
                    st.session_state["guest_bonus_feedback"] = None  # pokazane raz
                st.success("✅ Zaliczone")
                st.divider()
                continue

            # błąd po złej odpowiedzi (zadanie jeszcze nie zaliczone)
            if feedback_tid == tid and not feedback.get("ok"):
                st.error(f"❌ Nie. Poprawna: **{feedback.get('correct', '—')}**")
                st.session_state["guest_bonus_feedback"] = None

            if opts:
                pick = st.radio("Wybierz:", opts, key=f"guest_bonus_{tid}", index=None, label_visibility="collapsed")
            else:
                pick = st.text_input("Twoja odpowiedź:", key=f"guest_bonus_txt_{tid}").strip()

            if st.button("Sprawdź ✅", key=f"guest_bonus_check_{tid}"):
                if not pick:
                    st.warning("Podaj odpowiedź.")
                else:
                    ok = (str(pick).strip() == str(correct).strip()) if correct is not None else True
                    st.session_state["guest_bonus_feedback"] = {"tid": tid, "ok": ok, "correct": correct}
                    if ok:
                        done_set.add(tid)
                        st.session_state[done_key] = done_set
                        add_xp(int(task.get("xp", 5) or 5), reason="guest_bonus_ok")
                    st.session_state["mc"] = mc
                    st.rerun()
            st.divider()

        if len(done_set) >= len(pack):
            st.session_state["guest_bonus_done_day"] = today_key
            _guest_day_reward_if_done()
            # Gdy oba zestawy (misja dnia + bonusy) zaliczone — od razu pokaż ekran ze skrzynią i logowaniem
            if st.session_state.get("guest_daily_done_day") == today_key:
                st.session_state["mc"] = mc
                st.rerun()

        c1, c2 = st.columns(2)
        with c1:
            if st.button("🗺️ Misja dnia (Gość)", use_container_width=True, key="guest_bonus_to_daily"):
                mc["mode"] = "daily"
                st.session_state["mc"] = mc
                st.rerun()
        with c2:
            if st.button("🏠 Start", use_container_width=True, key="guest_bonus_to_start"):
                goto_hard("Start")
                return

    def render_bonus():
        if is_guest_user:
            render_guest_bonus()
            return
        # =========================================================
        # BONUSY (zadania szkolne) — jeden aktywny task + nawigacja
        # - działa także w trybie ćwiczeń (zadanie już zaliczone)
        # - bez overlay popupów (nie blokujemy klików)
        # =========================================================
        user_ = st.session_state.get("user") or ""
        if not user_:
            st.info("Zaloguj się na Start, aby korzystać z misji bonusowych 🙂")
            return

        def _subject_bonus_pack(subject: str, k: int = 3):
            subject = (subject or "").strip()
            if not subject:
                return []
            try:
                tasks = load_tasks()
            except Exception:
                tasks = {}
            subj_obj = (tasks or {}).get(subject) if isinstance(tasks, dict) else None
            if not isinstance(subj_obj, dict):
                return []

            age_group = get_age_group()
            arr = subj_obj.get(age_group, [])
            if not isinstance(arr, list) or not arr:
                return []

            try:
                diff = target_difficulty(f"school::{subject}")
                if diff:
                    arr = filter_by_difficulty(arr, diff)
            except Exception:
                pass

            try:
                arr = [normalize_task_item(it) for it in arr]
            except Exception:
                pass

            if callable(pick_daily_chunk):
                picked = pick_daily_chunk(arr, k, salt=f"school::{subject}")
            else:
                picked = arr[:k]

            out = []
            for it in picked:
                if isinstance(it, dict):
                    t = dict(it)
                    t.setdefault("xp", 5)
                    out.append({"subject": subject, "task": t})
            return out

        bonus_subject = None
        try:
            bonus_subject = (mc.get("bonus") or {}).get("subject") or st.session_state.get("bonus_subject")
            bonus_subject = bonus_subject.strip() if isinstance(bonus_subject, str) else None
        except Exception:
            bonus_subject = None

        def _logged_bonus_pack(k: int = 3):
            try:
                tasks = load_tasks()
            except Exception:
                tasks = {}

            age_group = get_age_group()
            pool = []
            if isinstance(tasks, dict):
                for subj, obj in tasks.items():
                    if not isinstance(obj, dict):
                        continue
                    arr = obj.get(age_group, [])
                    if isinstance(arr, list):
                        for it in arr:
                            if isinstance(it, dict):
                                t = normalize_task_item(it)
                                t.setdefault("xp", 5)
                                pool.append({"subject": subj, "task": t})

            if not pool:
                return []

            # filtruj zadania już zaliczone (żeby nie powtarzać)
            fresh = []
            for it in pool:
                _sub = (it.get("subject") or "").strip()
                _task = it.get("task") or {}
                _q = (_task.get("q") or "").strip()
                if not _sub or not _q:
                    continue
                if not is_task_done(user_, _sub, _q):
                    fresh.append(it)

            base = fresh if fresh else pool
            if callable(pick_daily_chunk):
                return pick_daily_chunk(base, k, salt=f"logged_bonus::{age_group}")
            return base[:k]

        if bonus_subject:
            bonus_pack = _subject_bonus_pack(bonus_subject, k=3)
        else:
            bonus_pack = _logged_bonus_pack(k=3) or []

        if not bonus_pack:
            if bonus_subject:
                st.info(f"Brak zadań dla przedmiotu: **{bonus_subject}**.")
            else:
                st.info("Dziś brak misji bonusowych.")
            return

        mc.setdefault("bonus", {})
        if bonus_subject:
            mc["bonus"]["subject"] = bonus_subject
        mc["bonus"].setdefault("active_i", 0)
        mc["bonus"].setdefault("ui", {})
        mc["bonus"].setdefault("toast", None)
        mc["bonus"].setdefault("interstitial", None)
        mc["bonus"].setdefault("finish_reward", None)

        # zapisujemy dzisiejszą paczkę bonusów w MC (żeby liczniki 1/3 były stabilne)
        mc["bonus"]["tasks"] = bonus_pack

        # --- Interstitial / nagrody między pytaniami (trzyma się na ekranie) ---
        inter = mc.get("bonus", {}).get("interstitial")
        if isinstance(inter, dict) and inter.get("active"):
            _render_reward_card(
                inter.get("title", "✅ Dobrze!"),
                inter.get("msg", "Następny krok ✅"),
                key_prefix=f"bonus_inter_{_get_today_completion_key()}_{inter.get('tid','x')}",
                lottie=inter.get("lottie", "Successfully.json"),
            )

            c1, c2 = st.columns(2)
            with c1:
                if st.button(
                    inter.get("button", "➡️ Dalej"),
                    use_container_width=True,
                    key=f"mc_bonus_inter_next_{_get_today_completion_key()}_{inter.get('tid','x')}",
                ):
                    # przejście dalej / koniec
                    if inter.get("action") == "finish":
                        # Koniec bonusów: pokaż najpierw mega-nagrodę (skrzynkę), dopiero potem start.
                        mc["bonus"]["interstitial"] = None
                        mc["bonus"]["done_day"] = _get_today_completion_key()

                        u = st.session_state.get("user") or ""
                        if isinstance(u, str) and u.startswith("Gosc-"):
                            st.session_state[_guest_bonus_done_key()] = True

                        # jeśli nie było jeszcze skrzynki – ustaw ją teraz
                        if not isinstance(mc.get("bonus", {}).get("finish_reward"), dict):
                            mc["bonus"]["finish_reward"] = {
                                "title": "💎 Nagroda za bonusy!",
                                "msg": "Ukończone misje bonusowe ✅",
                                "emoji": "🎁",
                            }

                        st.session_state["mc"] = mc
                        st.rerun()

                    # zwykłe przejście do kolejnego pytania
                    try:
                        mc["bonus"]["active_i"] = int(inter.get("next_i", mc["bonus"].get("active_i", 0)))
                    except Exception:
                        pass
                    mc["bonus"]["interstitial"] = None
                    st.session_state["mc"] = mc
                    st.rerun()

            with c2:
                if st.button(
                    "🔁 Zostań tutaj",
                    use_container_width=True,
                    key=f"mc_bonus_inter_stay_{_get_today_completion_key()}_{inter.get('tid','x')}",
                ):
                    mc["bonus"]["interstitial"] = None
                    st.session_state["mc"] = mc
                    st.rerun()
            return

        # --- Ekran nagrody za komplet bonusów (skrzynka + 💎, następna tura jutro) ---
        fr = mc.get("bonus", {}).get("finish_reward")
        if isinstance(fr, dict) and (fr.get("title") or fr.get("msg")):
            _render_chest_card(
                fr.get("title", "💎 Skrzynka!"),
                fr.get("msg", ""),
                key_prefix=f"bonus_finish_{_get_today_completion_key()}",
            )
            st.caption("💎 Diament dodany do Twojej puli. Skorzystaj z innych portali (Quiz, Skrzynka…) — następna tura pytań jutro.")
            st.markdown("📊 **Z twoich dzisiejszych misji:** ukończyłeś pakiet bonusowy (zadania szkolne). To buduje supermoce na Mapie kopalni.")
            if st.button("📖 Zobacz hasła w Słowniczku", use_container_width=True, key="bonus_finish_slowniczek"):
                goto_hard("Słowniczek")
                return
            c1, c2 = st.columns(2)
            with c1:
                if st.button("🏠 Wróć na start", use_container_width=True, key="bonus_finish_back"):
                    mc["bonus"]["finish_reward"] = None
                    st.session_state["mc"] = mc
                    goto_hard("Start")
                    return
            with c2:
                if st.button("✅ OK", use_container_width=True, key="bonus_finish_ok"):
                    mc["bonus"]["finish_reward"] = None
                    st.session_state["mc"] = mc
                    st.rerun()

            return

        # ✅ Bonusy na dziś już zaliczone — nie pokazuj pytań ponownie (raz na dzień)
        today_key_bonus = _get_today_completion_key()
        if mc.get("bonus", {}).get("done_day") == today_key_bonus:
            st.success("✅ Bonusy na dziś już ukończone!")
            st.caption("Następna tura pytań jutro. Skorzystaj z innych portali (Quiz, Skrzynka…).")
            if st.button("🏠 Wróć na Start", use_container_width=True, key="bonus_already_done_start"):
                goto_hard("Start")
                return
            return

        # ✅ done_today: komplet zrobiony dziś (persistuje się przez is_task_done/DB)
        def _bonus_all_done_today(u: str) -> bool:
            try:
                for _it in bonus_pack:
                    _sub = (_it.get("subject") or "").strip()
                    _task = _it.get("task") or {}
                    _q = (_task.get("q") or "").strip()
                    if not _q:
                        continue
                    if not is_task_done(u, _sub, _q):
                        return False
                return True
            except Exception:
                return False

        done_today = _bonus_all_done_today(user_)

        total = len(bonus_pack)
        active_i = int(mc["bonus"].get("active_i", 0) or 0)
        if active_i < 0:
            active_i = 0
        if active_i > total - 1:
            active_i = total - 1
        mc["bonus"]["active_i"] = active_i

        it = bonus_pack[active_i] if bonus_pack else {}
        subject = (it.get("subject") or "").strip() or "Bonus"
        task = it.get("task") or {}
        q_text = (task.get("q") or "").strip()

        # stabilny task id (przedmiot + treść pytania)
        tid = _task_id_from_text(f"{subject}::{q_text}")

        ui = mc["bonus"]["ui"].get(tid) or {}
        ui.setdefault("selected", None)
        ui.setdefault("checked", False)
        ui.setdefault("ok", None)
        mc["bonus"]["ui"][tid] = ui

        # Pasek postępu (bonusy zalogowanego)
        st.progress(min(1.0, (active_i + 1) / max(1, total)))
        st.caption(f"Postęp: **{active_i + 1} / {total}** ✅")

        st.header(f"{active_i+1}. 📌 {subject.title()}")
        if q_text:
            st.write(q_text)
        else:
            st.info("Brak treści pytania w zadaniu.")
            return

        # --- odpowiedzi / formaty zadań (różne pliki mogą używać różnych kluczy) ---
        correct_text = task.get("correct")
        if correct_text is None:
            correct_text = task.get("answer")
        if correct_text is None:
            correct_text = task.get("a")
        if correct_text is not None:
            correct_text = str(correct_text).strip()

        opts = task.get("options")
        if opts is None:
            opts = task.get("choices")
        if opts is None:
            opts = task.get("answers")
        if isinstance(opts, (tuple, set)):
            opts = list(opts)
        if not isinstance(opts, list):
            opts = []

        # --- normalizacja poprawnej odpowiedzi ---
        # W części plików "correct" bywa indeksem (np. 0), a nie tekstem odpowiedzi.
        if correct_text is not None and opts:
            ct = str(correct_text).strip()
            if ct.isdigit():
                idx = int(ct)
                if 0 <= idx < len(opts):
                    correct_text = str(opts[idx]).strip()

        # ---------------- UI: po sprawdzeniu — zawsze pokaż feedback (poprawność/błąd) i nawigację ---
        if ui.get("checked"):
            if done_today:
                st.caption("🧪 Tryb ćwiczeń (zadanie już zaliczone — nagrody zablokowane).")

            # Wyraźna informacja o poprawności lub błędzie (nad rozwiązaniami)
            if correct_text is None:
                st.success("✅ Zadanie zaliczone (brak klucza odpowiedzi w pliku).")
            else:
                if ui.get("ok"):
                    st.success("✅ **Dobra odpowiedź!**")
                else:
                    st.error("❌ **Nie tym razem.** Poprawna odpowiedź: **" + str(correct_text) + "**")
                    if st.button(
                        "🔁 Popraw odpowiedź",
                        use_container_width=True,
                        key=f"mc_bonus_retry_{_get_today_completion_key()}_{tid}",
                    ):
                        ui["checked"] = False
                        ui["ok"] = None
                        mc["bonus"]["ui"][tid] = ui
                        st.session_state["mc"] = mc
                        st.rerun()

            # --- NAWIGACJA: przejście do następnego pytania ---
            can_go_next = bool(done_today or (ui.get("ok") is True) or (correct_text is None))
            if can_go_next:
                st.divider()
                is_last = active_i >= total - 1

                cnav1, cnav2 = st.columns(2)
                with cnav1:
                    if not is_last:
                        if st.button(
                            f"➡️ Następne ({active_i+2}/{total})",
                            use_container_width=True,
                            key=f"mc_bonus_next_{_get_today_completion_key()}_{tid}",
                        ):
                            mc["bonus"]["active_i"] = min(active_i + 1, total - 1)
                            st.session_state["mc"] = mc
                            st.rerun()
                    else:
                        st.caption("To było ostatnie zadanie w zestawie.")

                with cnav2:
                    if is_last:
                        if st.button(
                            "🏁 Koniec bonusów",
                            use_container_width=True,
                            key=f"mc_bonus_finish_{_get_today_completion_key()}_{tid}",
                        ):
                            mc["bonus"]["done_day"] = _get_today_completion_key()

                            u = st.session_state.get("user") or ""
                            if isinstance(u, str) and u.startswith("Gosc-"):
                                st.session_state[_guest_bonus_done_key()] = True

                            # pokaż skrzynkę zamiast przechodzić dalej
                            mc["bonus"].setdefault("finish_reward", None)
                            if not isinstance(mc["bonus"].get("finish_reward"), dict):
                                mc["bonus"]["finish_reward"] = {
                                    "title": "💎 Nagroda za bonusy!",
                                    "msg": "Ukończone misje bonusowe ✅",
                                    "emoji": "🎁",
                                }

                            st.session_state["mc"] = mc
                            st.rerun()
            return

        # ---- wybór odpowiedzi (radio = widoczna zaznaczona odpowiedź) ----
        with st.expander("🧠 Rozwiąż", expanded=True):
            if opts:
                choice = st.radio(
                    "Wybierz odpowiedź:",
                    options=opts,
                    key=f"mc_bonus_radio_{_get_today_completion_key()}_{tid}",
                    index=opts.index(ui["selected"]) if ui.get("selected") in opts else None,
                    label_visibility="collapsed",
                )
                if choice is not None:
                    ui["selected"] = str(choice)
                    mc["bonus"]["ui"][tid] = ui
                    st.session_state["mc"] = mc
            else:
                # fallback: odpowiedź tekstowa
                ui["selected"] = st.text_input(
                    "Twoja odpowiedź:",
                    value=str(ui.get("selected") or ""),
                    key=f"mc_bonus_text_{_get_today_completion_key()}_{tid}",
                ).strip()
                mc["bonus"]["ui"][tid] = ui
                st.session_state["mc"] = mc

        # ---- sprawdzanie ----
        disabled_check = not bool(ui.get("selected"))
        if st.button(
            "🔎 Sprawdź",
            use_container_width=True,
            disabled=disabled_check,
            key=f"mc_bonus_check_{_get_today_completion_key()}_{tid}",
        ):
            chosen = str(ui.get("selected") or "").strip()

            if correct_text is None:
                ok = True
            else:
                ok = (chosen == correct_text)

            ui["checked"] = True
            ui["ok"] = bool(ok)
            mc["bonus"]["ui"][tid] = ui

            # nagrody tylko jeśli nie jest to tryb ćwiczeń (bez interstitial — feedback widać pod pytaniem)
            if ok and (not done_today):
                xp_gain = int(task.get("xp", 5) or 5)
                try:
                    mark_task_done(user_, subject, q_text, xp_gain=xp_gain)
                except Exception:
                    st.session_state["xp"] = int(st.session_state.get("xp", 0) or 0) + xp_gain
                # nagroda główna za komplet bonusów (1x dziennie) — przy ostatnim zadaniu
                try:
                    if _bonus_all_done_today(user_):
                        today_key = _get_today_completion_key()
                        if mc["bonus"].get("master_reward_day") != today_key:
                            add_xp(10, reason="bonus_master_done")
                            add_gems(1, reason="bonus_master_done")
                            grant_sticker("sticker_bonus_master")
                            mc["bonus"]["master_reward_day"] = today_key
                            mc["bonus"].setdefault("finish_reward", None)
                            mc["bonus"]["finish_reward"] = {
                                "title": "💎 MEGA NAGRODA! Skrzynka z diamentami!",
                                "msg": "+10 XP • +1 💎 • naklejka ✅",
                                "emoji": "🎁",
                            }
                        mc["bonus"]["done_day"] = today_key
                except Exception:
                    pass

            st.session_state["mc"] = mc

            # Ostatnie pytanie poprawne — od razu zakończ bonusy (ekran skrzynki)
            if ok and active_i >= total - 1 and total > 0:
                today_key_end = _get_today_completion_key()
                mc["bonus"]["done_day"] = today_key_end
                if not isinstance(mc.get("bonus", {}).get("finish_reward"), dict):
                    mc["bonus"]["finish_reward"] = {
                        "title": "💎 Nagroda za bonusy!",
                        "msg": "Ukończone misje bonusowe ✅",
                        "emoji": "🎁",
                    }
                st.session_state["mc"] = mc
                st.rerun()

            # Po poprawnej odpowiedzi — przejdź do następnego pytania (nie ostatnie)
            if ok and active_i < total - 1:
                st.toast("✅ Dobra odpowiedź!", icon="✅")
                mc["bonus"]["active_i"] = min(active_i + 1, total - 1)
                st.session_state["mc"] = mc
            st.rerun()


    # =========================================================
    # RENDERERY
    # =========================================================
    from typing import Any

    def preview_box(title: str, df_preview: Any, key: str, *, expanded: bool = True):
        # key używamy jako stabilny klucz expander'a (unikamy glitchy przy rerunach)
        with st.expander(f"👀 Podgląd danych – {title}", expanded=expanded):
            # st.table jest zauważalnie lżejsze na mobile niż dataframe
            try:
                st.table(df_preview)
            except Exception:
                # fallback gdyby to był np. list/dict
                st.write(df_preview)


    def render_done_screen():
        toast = None  # daily toast czyścimy wcześniej, tu nie używamy

        done_src = mc.get("done_source") or "daily"
        if done_src == "free":
            st.success("🎉 Zestaw misji ukończony! Super robota! 🎁")
        else:
            st.success("🎉 Misja dnia zaliczona! Super robota! 🎁")
        st.markdown(
            "📊 **Z twoich dzisiejszych misji:** zaliczyłeś całą misję dnia. "
            "Każdy taki dzień przybliża ci odznaki za serie (3, 7, 14, 30 dni) i supermoce na Mapie kopalni."
        )
        if st.button("📖 Zobacz hasła w Słowniczku", use_container_width=True, key="done_slowniczek"):
            goto_hard("Słowniczek")
            return
        # ✅ Nagroda końcowa (skrzynka z diamentami) — widoczna bez st.info
        fr = None
        try:
            fr = mc.get("daily", {}).get("finish_reward")
        except Exception:
            fr = None
        if isinstance(fr, dict) and (fr.get("title") or fr.get("msg")):
            st.success(f"{fr.get('emoji','🎁')} **{fr.get('title','Nagroda!')}** — {fr.get('msg','')}")

        try:
            st.caption(f"Nowy zestaw misji pojawi się jutro. Zostało **{_time_to_next_daily_set_str()}** do resetu 🕛")
        except Exception:
            pass
        st.markdown("**Skorzystaj z innych portali** (Quiz danych, Skrzynka, Avatar…) — następna tura pytań jutro.")

        u = st.session_state.get("user")
        if not u or str(u).startswith("Gosc-"):
            st.caption("🔐 Zaloguj się, żeby odblokować więcej możliwości (postęp, streak, nagrody, historia).")


        if False and toast:
            confetti_reward()

            title = toast.get("title", "✅ Dobrze!")
            msg = toast.get("msg", "+1 krok")
            emoji = toast.get("emoji", "✨")

            # Toast jest nieinwazyjny (nie blokuje klików), w przeciwieństwie do overlay/popup.
            st.toast(f"{title} — {msg}", icon=emoji)

            total = int(toast.get("total", 1))
            cur_i = int(toast.get("i", 1))

            c1, c2 = st.columns(2)
            with c1:
                if cur_i < total:
                    if st.button(
                        f"➡️ Dalej ({cur_i+1}/{total})",
                        use_container_width=True,
                        key="bonus_toast_next_btn",
                    ):
                        mc["bonus"]["toast"] = None
                        mc["bonus"]["active_i"] = min(int(mc["bonus"].get("active_i", 0)) + 1, total - 1)
                        st.session_state["mc"] = mc
                        st.rerun()
                else:
                    if st.button("🏁 Koniec bonusów", use_container_width=True, key="bonus_toast_finish_btn"):
                        mc["bonus"]["toast"] = None
                        mc["bonus"]["done_day"] = _get_today_completion_key()

                        u = st.session_state.get("user") or ""
                        if isinstance(u, str) and u.startswith("Gosc-"):
                            st.session_state[_guest_bonus_done_key()] = True

                        mc["bonus"]["finish_reward"] = {
                            "title": "🏆 Mega bonus!",
                            "msg": "Ukończone wszystkie misje bonusowe!",
                            "emoji": "🎁",
                        }

                        st.session_state["mc"] = mc
                        goto_hard("Start")
                        return

            with c2:
                if st.button("🔁 Zostań tutaj", use_container_width=True, key="bonus_toast_stay_btn"):
                    mc["bonus"]["toast"] = None
                    st.session_state["mc"] = mc
                    st.rerun()
            return


        c1, c2 = st.columns(2)
        with c1:
            if st.button("🗺️ Misja dnia", key="mc_bonus_back_daily", use_container_width=True):
                mc["mode"] = "daily"
                st.rerun()
        with c2:
            if st.button("🏠 Start", key="mc_bonus_back_start", use_container_width=True):
                log_event("misje_click_start")
                goto_hard("Start")
                return

        st.markdown("### 🧩 Misje bonusowe (zadania szkolne)")
        render_bonus()
        return


    def render_free():
        # Zalogowany nie powinien widzieć „Misji niezależnych”
        if not is_guest_user:
            st.info("Misje niezależne są tylko dla Gościa. Wybierz „Misja dnia (zalogowany)” powyżej.")
            return
        st.markdown("### 🧭 Misje niezależne (codzienny zestaw)")
        st.caption("Ten zestaw jest niezależny od Misji dnia i resetuje się codziennie.")

        df_base = daily_state.get("df_used") if isinstance(daily_state, dict) else None
        df_local = df_base if isinstance(df_base, pd.DataFrame) else df

        if pd is None or df_local is None or not isinstance(df_local, pd.DataFrame) or df_local.empty:
            st.info("Brak danych do misji — wróć na Start i załaduj zestaw.")
            return

        # deterministic daily seed (independent from daily missions)
        try:
            seed_txt = f"{_today_key()}::free"
            seed = int(hashlib.sha256(seed_txt.encode("utf-8")).hexdigest(), 16) % (2**32)
        except Exception:
            seed = 42
        rng = _random.Random(seed)

        done_key = f"free_done_{_today_key()}"
        done_set = st.session_state.setdefault(done_key, set())
        if not isinstance(done_set, set):
            done_set = set(done_set or [])
            st.session_state[done_key] = done_set

        num_cols = [c for c in df_local.columns if pd.api.types.is_numeric_dtype(df_local[c])]
        cat_cols = [c for c in df_local.columns if not pd.api.types.is_numeric_dtype(df_local[c])]

        if not num_cols:
            st.warning("Brak kolumn liczbowych do misji.")
            return

        # pick columns deterministically
        col_max = rng.choice(num_cols)
        col_min = rng.choice([c for c in num_cols if c != col_max] or num_cols)
        col_cat = rng.choice(cat_cols) if cat_cols else None

        def _reward_once(mission_id: str, ok: bool):
            if not ok:
                return
            if mission_id in done_set:
                return
            add_xp(4, reason=f"free_mission::{mission_id}")
            done_set.add(mission_id)
            st.session_state[done_key] = done_set

        def _choices_numeric(series, correct):
            if correct is None:
                return []
            if abs(float(correct) - round(float(correct))) < 1e-9:
                base = int(round(float(correct)))
                opts = [base, base - 1, base + 1, base + 2, base - 2]
                opts = [x for x in opts if x is not None]
                opts = list(dict.fromkeys(opts))
            else:
                base = float(correct)
                opts = [base, base - 0.5, base + 0.5, base + 1.0, base - 1.0]
                opts = [round(x, 2) for x in opts]
                opts = list(dict.fromkeys(opts))
            rng.shuffle(opts)
            return opts

        st.markdown("#### 1) Największa wartość")
        s_max = pd.to_numeric(df_local[col_max], errors="coerce").dropna()
        max_val = s_max.max() if not s_max.empty else None
        opts_max = _choices_numeric(s_max, max_val)
        key_max = f"free_max_{_today_key()}"
        if "max" in done_set:
            st.success("✅ Zaliczone")
        else:
            pick = st.radio(
                f"Jaka jest największa wartość w kolumnie **{col_max}**?",
                options=opts_max,
                key=key_max,
                index=None,
            )
            if st.button("Sprawdź ✅", key=f"{key_max}_check"):
                ok = pick is not None and float(pick) == float(max_val)
                if ok:
                    st.success("✅ Dobrze!")
                    _reward_once("max", ok)
                    st.rerun()
                else:
                    st.error(f"❌ Nie. Poprawna: **{max_val}**")
                    _reward_once("max", ok)

        st.markdown("#### 2) Najmniejsza wartość")
        s_min = pd.to_numeric(df_local[col_min], errors="coerce").dropna()
        min_val = s_min.min() if not s_min.empty else None
        opts_min = _choices_numeric(s_min, min_val)
        key_min = f"free_min_{_today_key()}"
        if "min" in done_set:
            st.success("✅ Zaliczone")
        else:
            pick = st.radio(
                f"Jaka jest najmniejsza wartość w kolumnie **{col_min}**?",
                options=opts_min,
                key=key_min,
                index=None,
            )
            if st.button("Sprawdź ✅", key=f"{key_min}_check"):
                ok = pick is not None and float(pick) == float(min_val)
                if ok:
                    st.success("✅ Dobrze!")
                    _reward_once("min", ok)
                    st.rerun()
                else:
                    st.error(f"❌ Nie. Poprawna: **{min_val}**")
                    _reward_once("min", ok)

        if col_cat:
            st.markdown("#### 3) Najczęstsza odpowiedź")
            vc = df_local[col_cat].astype(str).value_counts()
            correct = vc.index[0] if not vc.empty else None
            opts = list(vc.index[:3]) if len(vc.index) >= 3 else list(vc.index)
            if correct and correct not in opts:
                opts.append(correct)
            rng.shuffle(opts)

            key_cat = f"free_cat_{_today_key()}"
            if "cat" in done_set:
                st.success("✅ Zaliczone")
            else:
                pick = st.radio(
                    f"Co pojawia się najczęściej w kolumnie **{col_cat}**?",
                    options=opts,
                    key=key_cat,
                    index=None,
                )
                if st.button("Sprawdź ✅", key=f"{key_cat}_check"):
                    ok = pick == correct
                    if ok:
                        st.success("✅ Dobrze!")
                        _reward_once("cat", ok)
                        st.rerun()
                    else:
                        st.error(f"❌ Nie. Poprawna: **{correct}**")
                        _reward_once("cat", ok)
        else:
            st.info("Brak kolumn tekstowych do 3. misji.")

        # bonus za komplet
        if done_set.issuperset({"max", "min", "cat"} if col_cat else {"max", "min"}):
            if st.session_state.get("free_rewarded_day") != _today_key():
                add_gems(1, reason="free_mission_complete")
                st.session_state["free_rewarded_day"] = _today_key()
                st.toast("🎁 Bonus za komplet: +1 💎", icon="🎁")
            st.success("✅ Dzisiejszy zestaw ukończony!")
            try:
                st.caption(f"Następny zestaw: {_time_to_next_daily_set_str()}")
            except Exception:
                pass

    def render_subject():
        # subject musi przetrwać rerun (mc_migrate zachowuje "subject"; fallback z bonus i session)
        subject = (mc.get("subject") or mc.get("bonus", {}).get("subject") or st.session_state.get("bonus_subject") or "").strip()
        if subject and not mc.get("subject"):
            mc["subject"] = subject
            st.session_state["mc"] = mc

        def _go_subject_list():
            try:
                if hasattr(st, "switch_page"):
                    try:
                        st.switch_page("pages/przedmioty.py")
                        return
                    except Exception:
                        try:
                            st.switch_page("przedmioty.py")
                            return
                        except Exception:
                            pass
            except Exception:
                pass
            try:
                from core.routing import set_url_page
                set_url_page("Przedmioty")
            except Exception:
                pass
            st.session_state["page"] = "Przedmioty"
            st.session_state["_goto"] = "Przedmioty"
            st.rerun()

        if not subject:
            st.info("Wybierz przedmiot w zakładce „Przedmioty szkolne”.")
            if st.button("📚 Wróć do listy przedmiotów", use_container_width=True, key="subject_back_list"):
                _go_subject_list()
            return

        if st.button("⬅️ Wróć do listy przedmiotów", use_container_width=True, key="subject_back_to_list"):
            _go_subject_list()
            return

        st.markdown(f"### 📚 {subject.title()} — pakiet 10 zadań")
        st.caption("Ten pakiet jest niezależny od Misji dnia.")

        try:
            tasks = load_tasks()
        except Exception:
            tasks = {}

        age_group = get_age_group()
        subj_obj = (tasks or {}).get(subject) if isinstance(tasks, dict) else None
        arr = subj_obj.get(age_group, []) if isinstance(subj_obj, dict) else []

        if not isinstance(arr, list) or not arr:
            st.warning("Brak zadań dla tego przedmiotu w tasks.json.")
            return

        try:
            diff = target_difficulty(f"school::{subject}")
            if diff:
                arr = filter_by_difficulty(arr, diff)
        except Exception:
            pass

        try:
            arr = [normalize_task_item(it) for it in arr]
        except Exception:
            pass

        if callable(pick_daily_chunk):
            pack = pick_daily_chunk(arr, 10, salt=f"subject::{subject}")
        else:
            pack = arr[:10]

        today_key = _get_today_completion_key()
        done_key = f"subject_done::{today_key}::{subject}"
        done_set = st.session_state.setdefault(done_key, set())
        if not isinstance(done_set, set):
            done_set = set(done_set or [])
            st.session_state[done_key] = done_set

        st.progress(min(1.0, len(done_set) / max(1, len(pack))))
        st.caption(f"Postęp: **{len(done_set)} / {len(pack)}** ✅")

        total_xp = 0
        for i, task in enumerate(pack, start=1):
            q_text = (task.get("q") or "").strip()
            if not q_text:
                continue
            tid = _task_id_from_text(f"{subject}::{q_text}")
            total_xp += int(task.get("xp", 5) or 5)

            st.markdown(f"**{i}. {q_text}**")

            opts = task.get("options") or task.get("choices") or task.get("answers")
            if isinstance(opts, (tuple, set)):
                opts = list(opts)
            if not isinstance(opts, list):
                opts = []

            correct = task.get("correct")
            if correct is None:
                correct = task.get("answer")
            if correct is None:
                correct = task.get("a")
            if correct is not None:
                correct = str(correct).strip()

            if correct is not None and opts:
                c = str(correct).strip()
                if c.isdigit():
                    idx = int(c)
                    if 0 <= idx < len(opts):
                        correct = str(opts[idx]).strip()

            if tid in done_set:
                st.success("✅ Zaliczone")
                st.divider()
                continue

            if opts:
                pick = st.radio("Wybierz:", opts, key=f"subj_{tid}", index=None, label_visibility="collapsed")
            else:
                pick = st.text_input("Twoja odpowiedź:", key=f"subj_txt_{tid}").strip()

            if st.button("Sprawdź ✅", key=f"subj_check_{tid}"):
                if not pick:
                    st.warning("Podaj odpowiedź.")
                else:
                    ok = (str(pick).strip() == str(correct).strip()) if correct is not None else True
                    if ok:
                        st.success("✅ Dobrze!")
                        done_set.add(tid)
                        st.session_state[done_key] = done_set
                        st.rerun()
                    else:
                        st.error(f"❌ Nie. Poprawna: **{correct}**")
            st.divider()

        reward_key = f"subject_rewarded::{today_key}::{subject}"
        if len(done_set) >= len(pack) and not st.session_state.get(reward_key):
            add_xp(total_xp, reason=f"subject_pack::{subject}")
            st.session_state[reward_key] = True
            st.toast(f"🎁 Pakiet ukończony! +{total_xp} XP", icon="🎁")
            st.success("✅ Dzisiejszy pakiet ukończony!")

    def render_daily():
        if is_guest_user:
            render_guest_daily()
            return
        rng = _random.Random(_day_seed(today))

        if "q" not in mc["daily"]:
            mc["daily"]["q"] = {}

        q = mc["daily"]["q"]
        step = int(mc.get("step", 0))
        log_event("mc_daily_render", {"mode": mc.get("mode"), "step": int(mc.get("step", 0) or 0)})
        # safety: gdy step jest spoza 0..2 (stary stan / błąd), resetujemy
        if step not in (0, 1, 2):
            log_event("mc_daily_bad_step_reset", {"step": step})
            mc["step"] = 0
            mc.setdefault("daily", {})
            for k in ("q", "ui", "toast"):
                mc["daily"].pop(k, None)
            st.session_state["mc"] = mc
            st.rerun()
        log_event("mc_debug_step_state", {
            "step": int(mc.get("step", 0) or 0),
            "has_q1_fb": bool(mc.get("daily", {}).get("ui", {}).get("q1_feedback")),
            "has_q2_fb": bool(mc.get("daily", {}).get("ui", {}).get("q2_feedback")),
        })

        # 🎁 Ekran nagrody finałowej za misję dnia (nie znika po sekundzie)
        fr = mc.get("daily", {}).get("finish_reward")
        if isinstance(fr, dict) and (fr.get("title") or fr.get("msg")):
            _render_chest_card(
                fr.get("title", "💎 Skrzynka!"),
                fr.get("msg", ""),
                key_prefix=f"daily_finish_{today}",
            )

            if st.button("🏠 Wróć na start", use_container_width=True, key="daily_finish_back"):
                mc["daily"]["finish_reward"] = None
                st.session_state["mc"] = mc
                goto_hard("Start")
                return

            return

        mode_now = str(mc.get("mode") or "daily")

        # ✅ Tryb "Misje" (niezależny od Misji dnia): blokada tylko sesyjna per dzień
        if mode_now == "free":
            if st.session_state.get("free_done_day") == today:
                st.info("Zestaw misji jest już ukończony na dziś 🙂")
                try:
                    st.caption(f"Następny zestaw: {_time_to_next_daily_set_str()}")
                except Exception:
                    pass
                if st.button("🏠 Start", use_container_width=True, key="free_done_to_start"):
                    goto_hard("Start")
                    return
                return

        # ✅ Zalogowany: jeśli misja dnia już zrobiona dziś, nie pokazuj starej skrzynki ani pytań.
        # (Skrzynka pokazuje się tylko jako "pending" tuż po ukończeniu.)
        u_cur = st.session_state.get("user") or ""
        is_guest_local = isinstance(u_cur, str) and u_cur.startswith("Gosc-")
        if (mode_now != "free") and (not is_guest_local) and daily_is_done(str(u_cur)):
            st.info("Misja dnia jest już ukończona na dziś 🙂")
            try:
                st.caption(f"Następny zestaw: {_time_to_next_daily_set_str()}")
            except Exception:
                pass

            c1, c2 = st.columns(2)
            with c1:
                if st.button("🧩 Misje bonusowe", use_container_width=True, key="daily_done_to_bonus"):
                    mc["mode"] = "bonus"
                    st.session_state["mc"] = mc
                    st.rerun()
            with c2:
                if st.button("🏠 Start", use_container_width=True, key="daily_done_to_start"):
                    goto_hard("Start")
                    return
            return

        # --- Interstitial: nagrody między pytaniami (nie modal, nie blokuje klików) ---
        daily_ui = mc.setdefault("daily", {})
        interstitial = daily_ui.get("interstitial")
        if isinstance(interstitial, dict) and interstitial.get("active"):
            title = interstitial.get("title", "🎁 Nagroda")
            msg = interstitial.get("msg", "")
            details = interstitial.get("details")
            # Lottie + czytelny komunikat (jak w starych wersjach)
            _render_reward_card(
                title,
                msg,
                key_prefix=f"daily_inter_{today}_{interstitial.get('step')}",
                lottie=interstitial.get("lottie", "Successfully.json"),
            )
            if details:
                st.caption(str(details))

            c1, c2 = st.columns(2)
            with c1:
                if st.button(
                    interstitial.get("button", "➡️ Dalej"),
                    use_container_width=True,
                    key=f"mc_inter_next_{today}_{interstitial.get('step')}",
                ):
                    # wyczyść feedback bieżącego pytania (żeby nie wracało)
                    clear_key = interstitial.get("clear_key")
                    try:
                        if clear_key:
                            mc.get("daily", {}).get("ui", {}).pop(str(clear_key), None)
                    except Exception:
                        pass

                    daily_ui["interstitial"] = None
                    mc["step"] = int(interstitial.get("next_step", mc.get("step", 0)))
                    st.session_state["mc"] = mc
                    st.rerun()

            with c2:
                if st.button(
                    "🔁 Zostań tutaj",
                    use_container_width=True,
                    key=f"mc_inter_stay_{today}_{interstitial.get('step')}",
                ):
                    # zamknij nagrodę i zostań na bieżącym pytaniu
                    daily_ui["interstitial"] = None
                    st.session_state["mc"] = mc
                    st.rerun()

            return
        # =========================================================
        # Interstitial (nagroda/feedback między pytaniami) — trzyma się na ekranie,
        # dopóki gracz nie kliknie „Dalej”. Dzięki temu nie ma „przebłysku” po rerunie.
        # =========================================================
        inter = mc.get("daily", {}).get("interstitial")
        if isinstance(inter, dict) and inter.get("active"):
            st.success(f"{inter.get('emoji','✨')} {inter.get('title','')} — {inter.get('msg','')}")
            details = inter.get("details")
            if details:
                st.caption(str(details))

            if st.button(
                inter.get("button", "➡️ Dalej"),
                use_container_width=True,
                key=f"mc_inter_next_{today}_{inter.get('step','x')}",
            ):
                next_step = int(inter.get("next_step", step + 1) or (step + 1))
                clear_key = inter.get("clear_key")
                if clear_key:
                    try:
                        mc.get("daily", {}).get("ui", {}).pop(str(clear_key), None)
                    except Exception:
                        pass

                mc["daily"]["interstitial"] = None
                mc["step"] = next_step
                st.session_state["mc"] = mc
                st.rerun()
            return

        # --- Pasek postępu (zalogowany: misja dnia 3 kroki) ---
        st.progress(min(1.0, (step + 1) / 3))
        st.caption(f"Postęp: **{step + 1} / 3** ✅")

        # --- 1/3 unikalne wartości w losowej kolumnie ---
        if step == 0:
            mc.setdefault("daily", {}).setdefault("ui", {})
            fb = mc["daily"]["ui"].get("q1_feedback")

            if "q1" not in q:
                cols = [c for c in df_used.columns if df_used[c].nunique(dropna=True) > 1]
                if not cols:
                    log_event("mc_daily_abort_no_cols", {"cols": list(df_used.columns)})
                    st.info("Za mało danych do misji dnia (brak sensownych kolumn).")
                    return

                col = rng.choice(cols)
                correct = int(df_used[col].nunique(dropna=True))

                candidates = [
                    max(1, correct - 2),
                    max(1, correct - 1),
                    correct + 1,
                    correct + 2,
                    correct + 3,
                ]
                distractors = [x for x in dict.fromkeys(candidates) if x != correct]
                rng.shuffle(distractors)
                opts = [correct] + distractors[:3]
                rng.shuffle(opts)

                q["q1"] = {"col": col, "correct": correct, "opts": opts}

            col = q["q1"]["col"]
            correct = int(q["q1"]["correct"])
            opts = list(q["q1"]["opts"])

            st.markdown(f"### 1/3 Ile jest **unikalnych** wartości w kolumnie: **{col}** ?")

            # --- cache ciężkich obliczeń dla tego samego pytania (żeby reruny nie mieliły) ---
            ui = mc["daily"]["ui"]
            cache_key = f"q1::{today}::{col}"

            cache = ui.get("_cache")
            if not isinstance(cache, dict):
                cache = {}
                ui["_cache"] = cache

            if cache.get("key") != cache_key:
                s = df_used[col].astype(str)
                cache["sample_list"] = df_used[col].head(20).astype(str).tolist()
                cache["vc"] = (
                    s.value_counts(dropna=False)
                    .head(15)
                    .rename_axis(col)
                    .reset_index(name="liczba")
                )
                cache["key"] = cache_key
                st.session_state["mc"] = mc

            sample_list = cache.get("sample_list", [])
            vc = cache.get("vc")

            with st.expander(
                "👀 Podgląd danych (pomaga policzyć)",
                expanded=True
            ):
                st.caption("Top 15 najczęstszych wartości:")
                if vc is not None:
                    st.table(vc)  # lżejsze niż st.dataframe

            if fb:
                ok = bool(fb.get("ok"))
                chosen = fb.get("chosen")
                chosen_str = str(chosen) if chosen is not None else "—"

                if ok:
                    st.success(f"✅ Dobrze! Wybrałeś: **{chosen_str}**")

                    if not fb.get("shown"):
                        fb["shown"] = True
                        mc["daily"]["ui"]["q1_feedback"] = fb

                    # ✅ nagroda za pytanie 1/3 (XP) — 1x na dzień, także dla Gościa


                    daily_rewards = mc.setdefault("daily", {}).setdefault("q_rewarded", {})


                    today_key = _get_today_completion_key()


                    key = f"{today_key}::q1"


                    if not daily_rewards.get(key):
                        try:
                            add_xp(2, reason="daily_q1_ok")
                        except Exception:
                            st.session_state["xp"] = int(st.session_state.get("xp", 0) or 0) + 2
                        daily_rewards[key] = True

                    # Po poprawnej — od razu następne pytanie (zalogowany)
                    mc["daily"]["ui"].pop("q1_feedback", None)
                    mc["step"] = 1
                    st.session_state["mc"] = mc
                    st.toast("✅ Dobrze! +2 XP", icon="✅")
                    st.rerun()

                else:
                    st.error(f"❌ Nie tym razem 🙂 Wybrałeś: **{chosen_str}**")
                    st.caption(f"Poprawna odpowiedź: **{correct}**")
                    if st.button("🔁 Spróbuj ponownie", use_container_width=True, key="mc_q1_retry"):
                        mc["daily"]["ui"].pop("q1_feedback", None)
                        st.session_state["mc"] = mc
                        st.rerun()

                return

            choice = st.radio(
                "Wybierz odpowiedź:",
                options=opts,
                key=f"mc_q1_radio_{today}_{col}",
                index=None,
                label_visibility="collapsed",
            )
            if st.button("Sprawdź ✅", key=f"mc_q1_check_{today}_{col}", use_container_width=True):
                if choice is not None:
                    mc["daily"]["ui"]["q1_feedback"] = {"ok": int(choice) == correct, "chosen": choice}
                    st.session_state["mc"] = mc
                    st.rerun()
            return

        # --- 2/3 najczęstsza wartość w kolumnie tekstowej ---
        if step == 1:
            mc.setdefault("daily", {}).setdefault("ui", {})
            fb = mc["daily"]["ui"].get("q2_feedback")

            obj_cols = [c for c in df_used.columns if df_used[c].dtype == "object" and df_used[c].nunique() > 1]
            if not obj_cols:
                log_event("mc_daily_skip_step2_no_obj_cols", {"cols": list(df_used.columns)})
                st.info("Brak kolumn tekstowych — przeskakuję krok 2.")
                mc["step"] = 2
                st.session_state["mc"] = mc
                st.rerun()
                return

            if "q2" not in q:
                col = rng.choice(obj_cols)
                vc_full = df_used[col].astype(str).value_counts()
                correct = str(vc_full.index[0])

                top = list(vc_full.index[: min(8, len(vc_full.index))])
                pool = [str(x) for x in top if str(x) != correct]
                pick = rng.sample(pool, k=min(3, len(pool))) if pool else []
                opts = [correct] + pick
                rng.shuffle(opts)

                q["q2"] = {"col": col, "correct": correct, "opts": opts}

            col = q["q2"]["col"]
            correct = str(q["q2"]["correct"])
            opts = list(q["q2"]["opts"])

            st.markdown(f"### 2/3 Jaka wartość jest **najczęstsza** w kolumnie: **{col}** ?")

            ui = mc["daily"]["ui"]
            cache_key = f"q2::{today}::{col}"

            cache = ui.get("_cache2")
            if not isinstance(cache, dict):
                cache = {}
                ui["_cache2"] = cache

            if cache.get("key") != cache_key:
                cache["vc20"] = (
                    df_used[col].astype(str)
                    .value_counts(dropna=False)
                    .head(20)
                    .rename_axis(col)
                    .reset_index(name="liczba")
                )
                cache["key"] = cache_key
                st.session_state["mc"] = mc

            with st.expander(f"👀 Podgląd danych – kolumna: {col} (TOP 20 value_counts)", expanded=True):
                st.table(cache.get("vc20"))

            if fb:
                ok = bool(fb.get("ok"))
                chosen = fb.get("chosen")
                chosen_str = str(chosen) if chosen is not None else "—"

                if ok:
                    st.success(f"✅ Dobrze! Wybrałeś: **{chosen_str}**")

                    if not fb.get("shown"):
                        fb["shown"] = True
                        mc["daily"]["ui"]["q2_feedback"] = fb

                    # ✅ nagroda za pytanie 2/3 (XP) — 1x na dzień, także dla Gościa


                    daily_rewards = mc.setdefault("daily", {}).setdefault("q_rewarded", {})


                    today_key = _get_today_completion_key()


                    key = f"{today_key}::q2"


                    if not daily_rewards.get(key):


                        try:


                            add_xp(2, reason="daily_q2_ok")


                        except Exception:


                            st.session_state["xp"] = int(st.session_state.get("xp", 0) or 0) + 2


                        daily_rewards[key] = True



                    # Po poprawnej — od razu następne pytanie (zalogowany)
                    mc["daily"]["ui"].pop("q2_feedback", None)
                    mc["step"] = 2
                    st.session_state["mc"] = mc
                    st.toast("✅ Dobrze! +2 XP", icon="✅")
                    st.rerun()

                else:
                    st.error(f"❌ Nie tym razem 🙂 Wybrałeś: **{chosen_str}**")
                    st.caption(f"Poprawna odpowiedź: **{correct}**")
                    if st.button("🔁 Spróbuj ponownie", use_container_width=True, key="mc_q2_retry"):
                        mc["daily"]["ui"].pop("q2_feedback", None)
                        st.session_state["mc"] = mc
                        st.rerun()
                return

            choice = st.radio(
                "Wybierz odpowiedź:",
                options=opts,
                key=f"mc_q2_radio_{today}_{col}",
                index=None,
                label_visibility="collapsed",
            )
            if st.button("Sprawdź ✅", key=f"mc_q2_check_{today}_{col}", use_container_width=True):
                if choice is not None:
                    mc["daily"]["ui"]["q2_feedback"] = {"ok": str(choice) == correct, "chosen": str(choice)}
                    st.session_state["mc"] = mc
                    st.rerun()
            return

        # --- 3/3 max w kolumnie liczbowej + zakończenie ---
        if step == 2:
            mc.setdefault("daily", {}).setdefault("ui", {})
            fb = mc["daily"]["ui"].get("q3_feedback")

            num_cols = [c for c in df_used.columns if pd.api.types.is_numeric_dtype(df_used[c])]
            if not num_cols:
                log_event("mc_daily_abort_no_num_cols", {"cols": list(df_used.columns)})
                st.warning("Nie mam danych liczbowych do pytania 3/3.")
                st.info("Możesz wrócić jutro — albo przełącz dataset na Start 🙂")
                return
            if "q3" not in q:
                col = rng.choice(num_cols)
                s = pd.to_numeric(df_used[col], errors="coerce").dropna()

                if s.empty:
                    found = None
                    for c in num_cols:
                        ss = pd.to_numeric(df_used[c], errors="coerce").dropna()
                        if not ss.empty:
                            found = (c, ss)
                            break
                    if not found:
                        st.warning("Nie znalazłem sensownej kolumny liczbowej.")
                        return
                    col, s = found

                max_val = float(s.max())
                if abs(max_val - round(max_val)) < 1e-9:
                    correct = int(round(max_val))
                    is_float = False
                else:
                    correct = round(max_val, 2)
                    is_float = True

                if not is_float:
                    candidates = [correct, correct - 1, correct + 1, correct + 2, correct - 2, correct + 3]
                    opts = sorted({x for x in candidates if x is not None})
                else:
                    candidates = [
                        correct,
                        round(correct - 0.5, 2),
                        round(correct + 0.5, 2),
                        round(correct + 1.0, 2),
                        round(correct - 1.0, 2),
                        round(correct + rng.uniform(-2.0, 2.0), 2),
                    ]
                    opts = list(dict.fromkeys(candidates))
                    rng.shuffle(opts)

                q["q3"] = {"col": col, "correct": correct, "opts": opts, "is_float": is_float}

            col = q["q3"]["col"]
            correct = q["q3"]["correct"]
            opts = list(q["q3"]["opts"])
            is_float = bool(q["q3"].get("is_float", False))

            st.markdown(f"### 3/3 Jaka jest **największa** wartość w kolumnie: **{col}** ?")

            s = pd.to_numeric(df_used[col], errors="coerce").dropna()
            desc = s.describe().to_frame(name=col)
            top = s.sort_values(ascending=False).head(20).to_frame(name=col)

            preview_box(f"kolumna: {col} (describe)", desc, key=f"pv_q3_desc_{today}_{col}")
            preview_box(f"kolumna: {col} (TOP 20 największych)", top, key=f"pv_q3_top_{today}_{col}")

            if fb:
                ok = bool(fb.get("ok"))
                chosen = fb.get("chosen")
                chosen_str = str(chosen) if chosen is not None else "—"

                if ok:
                    st.success(f"✅ Dobrze! Wybrałeś: **{chosen_str}**")

                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("🎉 Zakończ misję dnia", use_container_width=True, key="mc_q3_finish"):
                            mc["daily"]["ui"].pop("q3_feedback", None)

                            u = st.session_state.get("user")
                            is_guest = (not u) or (isinstance(u, str) and u.startswith("Gosc-"))

                            mode_now = str(mc.get("mode") or "daily")

                            if mode_now == "free":
                                today_key = _get_today_completion_key()
                                st.session_state["free_done_day"] = today_key

                                add_xp(10, reason="free_mission_done")
                                add_gems(2, reason="free_mission_done")

                                mc.setdefault("daily", {})
                                mc["daily"]["finish_reward"] = {
                                    "title": "🎁 Zestaw misji ukończony!",
                                    "msg": "+10 XP • +2 💎",
                                    "emoji": "🎁",
                                }
                                mc["done_source"] = "free"
                                mc["mode"] = "done"
                                st.session_state["mc"] = mc
                                st.rerun()
                            else:
                                info = {}
                                try:
                                    info = mark_daily_done(u)
                                except Exception:
                                    info = {}

                                new_streak = int(info.get("streak", 0) or 0)

                                if info.get("freeze_used"):
                                    grant_sticker("sticker_freeze")
                                    st.toast("🧊 Freeze Day! Seria uratowana 😎", icon="🧊")

                                if not is_guest:
                                    try:
                                        claim_streak_lootbox(u, new_streak)
                                    except Exception:
                                        pass

                                mc.setdefault("daily", {})
                                today_key = _get_today_completion_key()

                                # nagroda raz na DZIEŃ
                                if mc["daily"].get("rewarded_day") != today_key:

                                    add_xp(12, reason="daily_mission_done")
                                    grant_sticker("sticker_daily")
                                    add_gems(3, reason="daily_mission_done")  # 💎 skrzynka z diamentami
                                    mc["daily"]["rewarded_day"] = today_key

                                    # zapamiętaj na ekran DONE (żeby było widać po przejściu)
                                    mc["daily"]["finish_reward"] = {
                                        "title": "💎 Skrzynka z diamentami!",
                                        "msg": "+12 XP • +3 💎 • naklejka ✅",
                                        "emoji": "🎁",
                                    }

                                    st.session_state["mc"] = mc

                                # ✅ zawsze ustaw finish_reward (nawet jeśli nagroda była już dziś odebrana)
                                mc.setdefault("daily", {})
                                if not isinstance(mc.get("daily", {}).get("finish_reward"), dict):
                                    mc["daily"]["finish_reward"] = {"title": "💎 Skrzynka z diamentami!", "msg": "+12 XP • +3 💎 • naklejka ✅", "emoji": "🎁"}
                                st.session_state["mc"] = mc

                                log_event("mc_daily_done_ok")

                                mc.setdefault("daily", {})
                                mc["daily"]["finish_reward"] = {
                                    "title": "💎 Skrzynka z diamentami!",
                                    "msg": "+12 XP • naklejka ✅ • +3 💎",
                                    "emoji": "🎁",
                                }

                                mc["done_source"] = "daily"
                                mc["mode"] = "done"
                                st.session_state["mc"] = mc
                                st.rerun()
                    with c2:
                        if st.button("🔁 Zostań tutaj", use_container_width=True, key="mc_q3_stay"):
                            mc["daily"]["ui"].pop("q3_feedback", None)
                            st.rerun()
                else:
                    st.error(f"❌ Nie tym razem 🙂 Wybrałeś: **{chosen_str}**")
                    st.caption(f"Poprawna odpowiedź: **{correct}**")
                    if st.button("🔁 Spróbuj jeszcze raz", use_container_width=True, key="mc_q3_retry"):
                        mc["daily"]["ui"].pop("q3_feedback", None)
                        st.rerun()
                return

            choice = st.radio(
                "Wybierz odpowiedź:",
                options=opts,
                key=f"mc_q3_radio_{today}_{col}",
                index=None,
                label_visibility="collapsed",
            )
            if st.button("Sprawdź ✅", key=f"mc_q3_check_{today}_{col}", use_container_width=True):
                if choice is not None:
                    if is_float:
                        ok = (float(choice) == float(correct))
                    else:
                        ok = (int(choice) == int(correct))
                    mc["daily"]["ui"]["q3_feedback"] = {"ok": ok, "chosen": str(choice)}
                    st.session_state["mc"] = mc
                    log_event("mc_daily_q3_answered")
                    st.rerun()
            return

    log_event("mc_mode_before_render", {
        "mode": mc.get("mode"),
        "step": mc.get("step"),
        "forced_view": forced_view,
        "locked": mc.get("locked"),
    })

    # =========================================================
    # Jeden renderer ekranu
    # =========================================================
    if mc.get("mode") == "bonus":
        render_bonus()
    elif mc.get("mode") == "done":
        render_done_screen()
    elif mc.get("mode") == "free":
        render_free()
    elif mc.get("mode") == "subject":
        render_subject()
    else:
        render_daily()


# Multipage (st.switch_page): uruchom render() także przy wejściu bez routera
try:
    render()
except Exception as e:
    st.exception(e)  # <-- to zawsze pokaże błąd na stronie
