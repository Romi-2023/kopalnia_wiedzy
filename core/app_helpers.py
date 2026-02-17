# core/app_helpers.py
from __future__ import annotations

"""Public helper API used by pages/*.

IMPORTANT:
- This module must stay light and avoid importing heavy page code.
- UI is implemented in core.ui and re-exported here for backward compatibility.
"""

import os
import json
import random
import hashlib
from datetime import datetime, date, timedelta
from dateutil import tz

import streamlit as st

from core.persistence import _user_db_get, _user_db_set, _load_users, _save_users
from core.routing import set_url_page as _set_url_page

from core.config import BASE_DIR, DATASETS_PRESETS, TERMS_VERSION, LOGS_DIR

# --- MC state (single schema) ---
from core.mc_state import mc_default, mc_migrate


def ensure_mc_state(today: str | None = None) -> dict:
    """Ensure st.session_state['mc'] exists and matches schema."""
    mc = mc_migrate(st.session_state.get("mc"), today=today)
    st.session_state["mc"] = mc
    return mc

# --- Re-exports: UI ---
from core.ui import (
    top_nav_row,
    card,
    show_loot_popup,
    confetti_reward,
    load_lottie,
    st_lottie,
    _bytes_to_b64,
)

# --- Re-exports: security / auth ---
from core.security import hash_pw, verify_parent_pin, validate_login, validate_password

# --- Re-exports: profile / age_group ---
from core.profile import (
    get_age_group,
    age_to_group,
    apply_age_group_change,
    clear_age_group_dependent_state,
    load_profile_to_session,
    after_login_cleanup,
    current_level,
    get_profile_level,
    level_progress,
)

# --- Re-exports: avatars ---
from core.avatars import (
    AVATAR_META,
    list_builtin_avatars,
    get_avatar_image_bytes,
    get_avatar_frame,
    get_frame_for_user,
)

# --- Re-exports: classes ---
from core.classes import join_class, create_class, get_class_info, list_classes_by_teacher


def refresh_streak() -> None:
    """Bezpieczna synchronizacja streaka do session_state."""
    user = st.session_state.get("user")
    if not user or str(user).startswith("Gosc-"):
        return
    try:
        prof = _user_db_get(user) or {}
        r = prof.get("retention") or {}
        st.session_state["streak"] = int(r.get("streak", st.session_state.get("streak", 0)) or 0)
    except Exception:
        return


def log_event(event: str, meta: dict | None = None):
    """Prosty logger zdarzeń (sesja + profil usera)."""
    try:
        stamp = datetime.now(tz=tz.gettz("Europe/Warsaw")).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    rec: dict = {"time": stamp, "event": str(event)}
    if meta is not None:
        try:
            json.dumps(meta, ensure_ascii=False)
            rec["meta"] = meta
        except Exception:
            rec["meta"] = {"_meta_repr": repr(meta)}

    # 1) log w sesji
    try:
        st.session_state.setdefault("activity_log", [])
        st.session_state.activity_log.append(rec)
    except Exception:
        pass

    # 2) persist (tylko zalogowany)
    user = st.session_state.get("user")
    is_logged = bool(user) and not str(user).startswith("Gosc-")
    if is_logged:
        try:
            prof = _user_db_get(user) or {}
            prof.setdefault("events", [])
            prof["events"].append(rec)
            prof["events"] = prof["events"][-400:]
            _user_db_set(user, prof)
        except Exception:
            pass

    # 3) log do pliku (dla regresji) — działa też dla gościa
    try:
        os.makedirs(LOGS_DIR, exist_ok=True)
        log_path = os.path.join(LOGS_DIR, "app.log")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass

    # 4) streak tylko zalogowany
    if is_logged:
        try:
            refresh_streak()
        except Exception:
            pass

# --- Minimalne "airbagi" używane w różnych miejscach ---
def safe_rerun():
    """Kompatybilny rerun dla różnych wersji Streamlit."""
    try:
        st.rerun()
    except Exception:
        try:
            st.experimental_rerun()
        except Exception:
            return


# -------------------------------------------------
# XP / Gems persistence (brakujące klocki z app.py)
# -------------------------------------------------

def _today_key() -> str:
    try:
        return datetime.now(tz=tz.gettz("Europe/Warsaw")).strftime("%Y-%m-%d")
    except Exception:
        return datetime.now().strftime("%Y-%m-%d")



# -----------------------------------------------------------------------------
# Public date helpers
# -----------------------------------------------------------------------------
def today_key() -> str:
    """Public wrapper for the internal _today_key()."""
    return _today_key()

def save_progress() -> None:
    """Zapisuje minimum profilu (XP/💎/avatary) do bazy/JSON.

    Cel: funkcje nagród (misje/quizy) nie mogą "udawać", że zapisały postęp.
    """
    # Single source of truth: core.profile
    try:
        from core.profile import save_profile_from_session
        save_profile_from_session()
    except Exception:
        return


def autosave_if_dirty(*, force: bool = False) -> None:
    """Zapisuje profil tylko jeśli był zmieniony (debounce). force=True zapisuje od razu (np. przed wylogowaniem)."""
    try:
        from core.profile import autosave_if_dirty as _autosave
        _autosave(force=force)
    except Exception:
        # safe no-op
        return


def add_xp(amount: int, reason: str = "", *, daily_cap: int = 120) -> int:
    """Dodaj XP do sesji + profilu (jeśli zalogowany), z dziennym limitem.

    - Gość: tylko sesja (bez permanentnego zapisu).
    - Zalogowany: zapis + anti-farm limit XP/dzień.
    """
    try:
        amount_i = int(amount)
    except Exception:
        amount_i = 0

    if amount_i <= 0:
        return int(st.session_state.get("xp", 0) or 0)

    user = st.session_state.get("user")
    is_guest = (not user) or str(user).startswith("Gosc-")

    allowed = amount_i
    if (not is_guest) and daily_cap is not None and int(daily_cap) > 0:
        today = _today_key()
        prof = _user_db_get(user) or {}
        prof.setdefault("retention", {})
        r = prof["retention"]

        xp_day = r.get("xp_day")
        gained = int(r.get("xp_gained_today", 0) or 0)
        if xp_day != today:
            xp_day = today
            gained = 0

        remaining = max(0, int(daily_cap) - gained)
        allowed = min(allowed, remaining)

        # update counters even if allowed=0 (żeby UI mogło pokazać "limit")
        r["xp_day"] = today
        r["xp_gained_today"] = gained + allowed
        prof["retention"] = r
        _user_db_set(user, prof)

    if allowed <= 0:
        try:
            log_event("xp_cap_hit", {"requested": amount_i, "reason": reason, "cap": int(daily_cap)})
        except Exception:
            pass
        return int(st.session_state.get("xp", 0) or 0)

    st.session_state["xp"] = int(st.session_state.get("xp", 0) or 0) + allowed

    try:
        from core.profile import mark_dirty
        mark_dirty("xp")
    except Exception:
        pass

    try:
        meta = {"amount": allowed, "requested": amount_i}
        if reason:
            meta["reason"] = reason
        log_event("xp_add", meta)
    except Exception:
        pass

    try:
        autosave_if_dirty()
    except Exception:
        pass

    return int(st.session_state.get("xp", 0) or 0)


def add_gems(amount: int, reason: str = "") -> int:
    """Dodaj 💎 do sesji + profilu (zalogowany)."""
    try:
        amount_i = int(amount)
    except Exception:
        amount_i = 0
    if amount_i <= 0:
        return int(st.session_state.get("gems", 0) or 0)

    st.session_state["gems"] = int(st.session_state.get("gems", 0) or 0) + amount_i

    try:
        from core.profile import mark_dirty
        mark_dirty("gems")
    except Exception:
        pass

    try:
        meta = {"amount": amount_i}
        if reason:
            meta["reason"] = reason
        log_event("gems_add", meta)
    except Exception:
        pass

    try:
        autosave_if_dirty()
    except Exception:
        pass

    return int(st.session_state.get("gems", 0) or 0)


def grant_sticker(sticker_id: str) -> None:
    """Dodaje naklejkę do profilu (jeśli jeszcze jej nie ma)."""
    if not isinstance(sticker_id, str) or not sticker_id:
        return
    s = st.session_state.get("stickers")
    if not isinstance(s, set):
        s = set(s or [])
    if sticker_id in s:
        return
    s.add(sticker_id)
    st.session_state["stickers"] = s
    try:
        from core.profile import mark_dirty
        mark_dirty("stickers")
    except Exception:
        pass
    try:
        autosave_if_dirty()
    except Exception:
        pass

def safe_load_json(path: str, default):
    """Bezpieczny odczyt JSON.

    Zachowujemy tę funkcję dla kompatybilności ze starszym kodem,
    ale faktyczny I/O delegujemy do warstwy persistence (single source of truth).
    """
    try:
        from core.persistence import read_json_file
        return read_json_file(path, default)
    except Exception:
        return default

def days_since_epoch() -> int:
    return (date.today() - date(2025, 1, 1)).days

def ensure_difficulty(items: list, mode: str = "split_30_50_20") -> list:
    """
    Jeśli item nie ma 'difficulty', nadaje je automatycznie.
    split_30_50_20:
      - pierwsze 30% easy
      - kolejne 50% medium
      - ostatnie 20% hard
    """
    if not items:
        return items

    n = len(items)
    if mode == "split_30_50_20":
        a = int(0.30 * n)
        b = int(0.80 * n)  # 30% + 50%
        for i, it in enumerate(items):
            if "difficulty" not in it or not it["difficulty"]:
                if i < a:
                    it["difficulty"] = "easy"
                elif i < b:
                    it["difficulty"] = "medium"
                else:
                    it["difficulty"] = "hard"
    else:
        for it in items:
            it.setdefault("difficulty", "medium")

    return items

def _normalize_task_item(it):
    """Ujednolica format zadania szkolnego/bonusu."""
    if isinstance(it, str):
        return {"q": it, "type": "text", "answer": None}
    if isinstance(it, dict):
        q = (it.get("q") or it.get("text") or "").strip()
        t = (it.get("type") or "text").strip()
        out = dict(it)
        out["q"] = q
        out["type"] = t
        return out
    return {"q": "", "type": "text", "answer": None}

def filter_by_difficulty(items: list, diff: str) -> list:
    """
    Obsługuje opcjonalne pole item["difficulty"] in {"easy","medium","hard"}.
    Jeśli brak — traktujemy jako "medium".
    """
    if not items:
        return []
    filtered = [it for it in items if (it.get("difficulty") or "medium") == diff]
    return filtered if filtered else items  # fallback: nie blokuj gry jak brak tagów

def _skill_init():
    """Inicjalizuje magazyn umiejętności w session_state."""
    if "skill" not in st.session_state or not isinstance(st.session_state.get("skill"), dict):
        st.session_state["skill"] = {}

def get_skill(domain: str) -> float:
    """Zwraca skill 0..1 (domyślnie 0.5)."""
    _skill_init()
    try:
        return float(st.session_state["skill"].get(domain, 0.5))
    except Exception:
        return 0.5

def target_difficulty(domain: str) -> str:
    """
    Mapuje skill -> poziom trudności.
    """
    s = get_skill(domain)
    if s < 0.40:
        return "easy"
    if s < 0.70:
        return "medium"
    return "hard"

def _stable_shuffle(arr, seed_text: str):
    """Deterministyczne tasowanie (zawsze to samo dla tego samego seed_text)."""
    if not arr:
        return []
    # stabilny seed -> Random
    seed_int = int(hashlib.sha256(str(seed_text).encode("utf-8")).hexdigest(), 16) % (10**12)
    rnd = random.Random(seed_int)
    out = list(arr)
    rnd.shuffle(out)
    return out

def pick_daily_chunk(items, k, day_idx: int | None = None, salt: str = ""):
    """
    Zwraca deterministyczny dzienny kawałek (k elementów) z listy items.
    - Jeśli day_idx=None, liczymy go automatycznie wg daty (Europe/Warsaw).
    - salt pozwala rozdzielić "źródła" (np. image::..., data::..., school::...).
    """
    if not items:
        return []

    k = max(1, min(int(k), len(items)))

    # auto day_idx (Warsaw), żeby wywołania bez day_idx nie wywalały TypeError
    if day_idx is None:
        warsaw = tz.gettz("Europe/Warsaw")
        today = datetime.now(tz=warsaw).date()
        day_idx = (today - date(2025, 1, 1)).days

    shuffled = _stable_shuffle(items, f"{salt}::day::{day_idx}")
    start = (int(day_idx) * k) % len(shuffled)
    return [shuffled[(start + i) % len(shuffled)] for i in range(k)]

def _day_seed(salt="Kopalnia Wiedzy"):
    txt = f"{date.today().isoformat()}::{salt}"
    return int(hashlib.sha256(txt.encode("utf-8")).hexdigest(), 16) % (2**32)

def _get_today_completion_key():
    return _today_key()

def _time_to_next_daily_set_str() -> str:
    warsaw = tz.gettz("Europe/Warsaw")
    now = datetime.now(tz=warsaw)
    tomorrow = (now + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    delta = tomorrow - now
    sec = max(0, int(delta.total_seconds()))
    h = sec // 3600
    m = (sec % 3600) // 60
    return f"{h:02d}:{m:02d}"

def skill_get_level(user: str, quiz_key: str) -> int:
    profile = _get_skill_profile(user)
    q = profile["skill"].get(quiz_key, {})
    lvl = int(q.get("level", 1))
    return max(1, min(3, lvl))  # 1..3

def skill_update(user: str, quiz_key: str, ok: bool) -> int:
    """Zapisuje wynik (ok/nie) i aktualizuje level 1..3 na bazie ostatnich 10."""
    profile = _get_skill_profile(user)
    q = profile["skill"].setdefault(quiz_key, {"level": 1, "last": []})

    last = list(q.get("last", []))
    last.append(1 if ok else 0)
    last = last[-10:]  # rolling window
    q["last"] = last

    acc = sum(last) / len(last) if last else 0.0
    lvl = int(q.get("level", 1))

    # proste progi: rośnie gdy idzie świetnie, spada gdy słabo
    if len(last) >= 5 and acc >= 0.8 and lvl < 3:
        lvl += 1
    elif len(last) >= 5 and acc <= 0.4 and lvl > 1:
        lvl -= 1

    q["level"] = lvl
    profile["skill"][quiz_key] = q
    _save_skill_profile(user, profile)
    return lvl

def update_skill(domain: str, ok: bool):
    """
    Prosty EMA: ok=True podbija, ok=False obniża.
    """
    _skill_init()
    prev = get_skill(domain)
    alpha = 0.15
    target = 1.0 if ok else 0.0
    st.session_state["skill"][domain] = (1 - alpha) * prev + alpha * target


def estimate_item_difficulty(question: str, options: list | None = None) -> int:
    """Heuristic difficulty 1..3 based on question length and options count."""
    try:
        q = str(question or "")
    except Exception:
        q = ""
    try:
        opt_count = len(options or [])
    except Exception:
        opt_count = 0

    q_len = len(q.strip())

    if opt_count <= 2:
        base = 1
    elif opt_count <= 4:
        base = 2
    else:
        base = 3

    if q_len >= 140:
        base += 1

    return max(1, min(3, int(base)))


def filter_items_by_level(items: list, level: int) -> list:
    """Zwraca pytania <= level (jeśli jest pole difficulty) albo wg heurystyki."""
    out = []
    for it in items:
        d = it.get("difficulty")
        if isinstance(d, int):
            diff = d
        else:
            diff = estimate_item_difficulty(it.get("q", ""), it.get("options", []))
        if diff <= level:
            out.append(it)
    # jeśli filtr uciął za mocno, oddaj wszystko (żeby quiz nie był pusty)
    return out if out else items

def is_game_unlocked(game_id: str) -> bool:
    unlocked = st.session_state.get("unlocked_games", set())
    if not isinstance(unlocked, set):
        unlocked = set(unlocked or [])
        st.session_state["unlocked_games"] = unlocked
    return game_id in unlocked

def unlock_game(game_id: str, cost: int) -> bool:
    """Odblokuj grę za klejnoty. Zwraca True jeśli odblokowano (lub było już odblokowane)."""
    gems = int(st.session_state.get("gems", 0) or 0)
    if gems < int(cost):
        return False

    unlocked = st.session_state.get("unlocked_games", set())
    if not isinstance(unlocked, set):
        unlocked = set(unlocked or [])

    if game_id in unlocked:
        return True

    unlocked.add(game_id)
    st.session_state["unlocked_games"] = unlocked
    st.session_state["gems"] = gems - int(cost)

    try:
        from core.profile import mark_dirty
        mark_dirty("unlocked_games", "gems")
    except Exception:
        pass

    try:
        autosave_if_dirty()
    except Exception:
        try:
            save_progress()
        except Exception:
            pass
    return True

# -----------------------------------------------------------------------------
# Fantasy-mode mappings (used in misje)
# -----------------------------------------------------------------------------
FANTASY_CITIES = ["Krainogród", "Miodolin", "Zefiriada", "Księżycolas", "Wróżkowo", "Słonecznikowo", "Tęczomir", "Gwizdacz"]
FANTASY_FRUITS = ["smocze jabłuszko", "tęczowa truskawka", "kosmiczny banan", "fioletowa gruszka", "złoty ananas", "śnieżna jagoda"]
FANTASY_NAMES = ["Aurelka", "Kosmo", "Iskierka", "Nimbus", "Gaja", "Tygrys", "Mira", "Leo", "Fruzia", "Błysk", "Luna", "Kornik"]

def _map_choice(value: str, pool: list, salt: str) -> str:
    key = f"{value}|{date.today().isoformat()}|{salt}"
    h = hashlib.sha256(key.encode("utf-8")).digest()
    return pool[h[0] % len(pool)]

def apply_fantasy(df: pd.DataFrame, seed: int | None = None) -> pd.DataFrame:
    """
    Fantasy-mode dla DataFrame.
    Jeśli podasz seed, mapowania i jitter będą deterministyczne (np. per dzień).
    """
    try:
        import pandas as pd  # type: ignore
    except Exception:
        return df

    if df is None:
        return df
    df = df.copy()

    # prefix do soli, żeby deterministycznie zmieniać wyniki (np. dziennie)
    prefix = f"{seed}:" if seed is not None else ""

    cols_lower = {c: c.lower() for c in df.columns}
    for c in df.columns:
        name = cols_lower[c]

        if "miasto" in name or "city" in name:
            df[c] = df[c].astype(str).apply(lambda v: _map_choice(v, FANTASY_CITIES, prefix + "city"))

        if "owoc" in name or "fruit" in name:
            df[c] = df[c].astype(str).apply(lambda v: _map_choice(v, FANTASY_FRUITS, prefix + "fruit"))

        if "imię" in name or "imie" in name or "name" in name:
            df[c] = df[c].astype(str).apply(lambda v: _map_choice(v, FANTASY_NAMES, prefix + "name"))

        # ✅ poprawka: pd.api (a nie api)
        if pd.api.types.is_numeric_dtype(df[c]):
            if any(k in name for k in ["wzrost", "cm", "waga", "kg", "height", "mass"]):
                jitter_fn = globals().get("jitter_numeric_col")
                if callable(jitter_fn):
                    df[c] = jitter_fn(df[c], pct=0.03, salt=prefix + f"jitter:{c}")
            elif "wiek" in name or "age" in name:
                # nie ruszamy wieku (zostawiamy realny)
                pass

    return df

# -----------------------------------------------------------------------------
# Demo datasets (used in misje / quiz)
# -----------------------------------------------------------------------------
FAV_FRUITS = ["jabłko", "banan", "truskawka", "winogrono", "arbuz"]
FAV_ANIMALS = ["kot", "pies", "zebra", "słoń", "lama", "delfin"]
COLORS = ["czerwony", "zielony", "niebieski", "żółty", "fioletowy"]
CITIES = ["Warszawa", "Kraków", "Gdańsk", "Wrocław"]

def make_dataset(n: int, cols: List[str], seed: int = 42) -> pd.DataFrame:
    try:
        import pandas as pd  # type: ignore
    except Exception:
        return None  # pandas not available

    # lokalny RNG (nie psuje globalnego random)
    rnd = random.Random(seed)

    # bezpieczeństwo / stabilność
    n = int(n)
    if n < 0:
        n = 0
    if n > 10_000:   # bezpieczny limit żeby nie ubić telefonu
        n = 10_000

    # unikamy duplikatów kolumn i dziwnych wartości
    cols = [c.strip() for c in cols if isinstance(c, str) and c.strip()]
    cols = list(dict.fromkeys(cols))  # zachowuje kolejność, usuwa duplikaty

    data: Dict[str, list] = {}

    if "wiek" in cols:
        data["wiek"] = [rnd.randint(7, 14) for _ in range(n)]

    if "wzrost_cm" in cols:
        data["wzrost_cm"] = [round(rnd.gauss(140, 12), 1) for _ in range(n)]

    if "ulubiony_owoc" in cols:
        data["ulubiony_owoc"] = [rnd.choice(FAV_FRUITS) for _ in range(n)]

    if "ulubione_zwierze" in cols:
        data["ulubione_zwierze"] = [rnd.choice(FAV_ANIMALS) for _ in range(n)]

    if "ulubiony_kolor" in cols:
        data["ulubiony_kolor"] = [rnd.choice(COLORS) for _ in range(n)]

    if "wynik_matematyka" in cols:
        data["wynik_matematyka"] = [max(0, min(100, int(rnd.gauss(70, 15)))) for _ in range(n)]

    if "wynik_plastyka" in cols:
        data["wynik_plastyka"] = [max(0, min(100, int(rnd.gauss(75, 12)))) for _ in range(n)]

    if "miasto" in cols:
        data["miasto"] = [rnd.choice(CITIES) for _ in range(n)]

    return pd.DataFrame(data)


DATASETS_PRESETS: Dict[str, Dict[str, List[str]]] = {
    "7-9": {
        "Łatwy (mały)": ["wiek", "ulubiony_owoc", "miasto"],
        "Łatwy+ (z kolorem)": ["wiek", "ulubiony_owoc", "ulubiony_kolor", "miasto"],
    },
    "10-12": {
        "Średni": ["wiek", "wzrost_cm", "ulubiony_owoc", "miasto"],
        "Średni+": ["wiek", "wzrost_cm", "ulubiony_owoc", "ulubione_zwierze", "miasto"],
    },
    "13-14": {
        "Zaawansowany": ["wiek", "wzrost_cm", "wynik_matematyka", "wynik_plastyka", "miasto", "ulubiony_owoc"],
        "Zaawansowany+": ["wiek", "wzrost_cm", "wynik_matematyka", "wynik_plastyka", "miasto", "ulubiony_owoc", "ulubione_zwierze"],
    },
}

# --- bottom nav (moduł) ---
try:
    from ui.bottom_nav import bottom_nav as _bottom_nav
except Exception:
    _bottom_nav = None  # ultra-safe

def render_form_bar(title: str, active: str, note: str = ""):
    # active: "easy" | "medium" | "hard"
    labels = [("easy", "🟢 Easy"), ("medium", "🟡 Medium"), ("hard", "🔴 Hard")]
    pills = []
    for key, lab in labels:
        cls = "d4k-formbar-pill active" if key == active else "d4k-formbar-pill"
        pills.append(f"<div class='{cls}'>{lab}</div>")

    st.markdown(
        f"""
        <div class="d4k-formbar">
          <div class="d4k-formbar-title">📈 <b>{title}</b></div>
          <div class="d4k-formbar-row">
            {''.join(pills)}
          </div>
          {f"<div class='d4k-formbar-sub'>{note}</div>" if note else ""}
        </div>
        """,
        unsafe_allow_html=True,
    )



# -----------------------------------------------------------------------------
# Facade: re-export helpers from other core modules for pages/*
# -----------------------------------------------------------------------------
from core.routing import goto, go_back, qp_get  # noqa: F401
from core.ui import card, top_nav_row  # noqa: F401
from core.security import hash_pw, verify_parent_pin, validate_login, validate_password  # noqa: F401
from core.profile import (
    age_to_group, get_age_group, get_profile_level, level_progress,
    load_profile_to_session, after_login_cleanup,
    apply_age_group_change, clear_age_group_dependent_state,
    mark_dirty, autosave_if_dirty, save_profile_from_session,
    get_profile, patch_profile,
)  # noqa: F401
from core.classes import join_class, create_class, get_class_info, list_classes_by_teacher  # noqa: F401
from core.avatars import list_builtin_avatars, get_avatar_frame, get_avatar_image_bytes  # noqa: F401
from core.persistence import _load_users, _save_users  # noqa: F401


# -----------------------------------------------------------------------------
# Tasks loading (used by missions)
# -----------------------------------------------------------------------------
TASKS_FILE = os.path.join("data", "tasks.json")

def load_tasks(path: str | None = None) -> dict:
    """Wczytaj tasks.json jako dict: subject -> age_group -> list[zadań]."""
    # 1) jeśli persistence jest zainicjalizowane – bierzemy stamtąd (DB lub plik)
    try:
        from core.persistence import _load_tasks as _persist_load_tasks
        tasks = _persist_load_tasks()
        return tasks if isinstance(tasks, dict) else {}
    except Exception:
        pass

    # 2) fallback: plik (dev)
    p = path or TASKS_FILE
    raw = safe_load_json(p, default={})
    return raw if isinstance(raw, dict) else {}


# -----------------------------------------------------------------------------
# Supermoce Data Science (mapa kopalni, profil)
# -----------------------------------------------------------------------------
SUPERMOCE_FILE = os.path.join("data", "supermoce.json")


def load_supermoce(path: str | None = None) -> list:
    """Wczytaj listę supermocy z data/supermoce.json."""
    p = path or SUPERMOCE_FILE
    raw = safe_load_json(p, default=[])
    return raw if isinstance(raw, list) else []


def is_supermoc_unlocked(user: str | None, item: dict) -> bool:
    """
    Czy użytkownik odblokował daną supermoc.
    item: dict z polami unlock_type, unlock_subject | unlock_quiz, unlock_min_level.
    """
    if not user or str(user).startswith("Gosc-"):
        return False
    user = str(user)
    t = (item.get("unlock_type") or "").strip().lower()
    if t == "subject":
        subj = (item.get("unlock_subject") or "").strip()
        if not subj:
            return False
        try:
            from core.missions import has_ever_done_subject
            return has_ever_done_subject(user, subj)
        except Exception:
            return False
    if t == "quiz_level":
        quiz_key = (item.get("unlock_quiz") or "").strip()
        min_lvl = int(item.get("unlock_min_level", 1) or 1)
        if not quiz_key:
            return False
        lvl = skill_get_level(user, quiz_key)
        return lvl >= min_lvl
    return False


# -----------------------------------------------------------------------------
# Rada dnia (tip z data/tips.json, rotacja dzienna)
# -----------------------------------------------------------------------------
TIPS_FILE = os.path.join("data", "tips.json")


def load_tips(path: str | None = None) -> list:
    """Wczytaj listę rad z data/tips.json."""
    p = path or TIPS_FILE
    raw = safe_load_json(p, default=[])
    return raw if isinstance(raw, list) else []


def get_tip_of_day() -> str:
    """Jedna rada na dziś (deterministyczna wg daty)."""
    tips = load_tips()
    if not tips:
        return ""
    try:
        from datetime import date
        day_idx = (date.today() - date(2025, 1, 1)).days
        idx = day_idx % len(tips)
        tip = tips[idx]
        return str(tip).strip() if tip else ""
    except Exception:
        return str(tips[0]).strip() if tips else ""


# -----------------------------------------------------------------------------
# Ścieżka Data Science (5–7 kroków na Mapie kopalni)
# -----------------------------------------------------------------------------
SCIEZKA_DATA_SCIENCE_FILE = os.path.join("data", "sciezka_data_science.json")


def load_sciezka_data_science(path: str | None = None) -> list:
    """Wczytaj kroki ścieżki Data Science z data/sciezka_data_science.json."""
    p = path or SCIEZKA_DATA_SCIENCE_FILE
    raw = safe_load_json(p, default=[])
    if not isinstance(raw, list):
        return []
    return sorted(raw, key=lambda x: int(x.get("order", 0)))


def is_sciezka_step_unlocked(user: str | None, step: dict) -> bool:
    """Czy krok ścieżki jest odblokowany. unlock_type: always | quiz_level | subject."""
    if (step.get("unlock_type") or "").strip().lower() == "always":
        return True
    if not user or str(user).startswith("Gosc-"):
        return False
    user = str(user)
    t = (step.get("unlock_type") or "").strip().lower()
    if t == "quiz_level":
        quiz_key = (step.get("unlock_quiz") or "").strip()
        min_lvl = int(step.get("unlock_min_level", 1) or 1)
        return quiz_key and skill_get_level(user, quiz_key) >= min_lvl
    if t == "subject":
        subj = (step.get("unlock_subject") or "").strip()
        if not subj:
            return False
        try:
            from core.missions import has_ever_done_subject
            return has_ever_done_subject(user, subj)
        except Exception:
            return False
    return False


# -----------------------------------------------------------------------------
# Odznaki za serie (streak) – tylko odczyt do wyświetlenia
# -----------------------------------------------------------------------------
def get_streak_badges(user: str | None) -> list[dict]:
    """
    Zwraca listę odznak za serie (3, 7, 14, 30 dni) z informacją, które już odebrane.
    Każdy element: {"days": int, "emoji": str, "label": str, "unlocked": bool}.
    """
    try:
        from core.missions import STREAK_MILESTONES, get_retention_state
    except Exception:
        return []
    if not user or str(user).startswith("Gosc-"):
        return [
            {"days": d, "emoji": m.get("emoji", "🏅"), "label": f"{d} dni z rzędu", "unlocked": False}
            for d, m in sorted(STREAK_MILESTONES.items())
        ]
    profile = get_retention_state(str(user))
    claimed = set(profile.get("retention", {}).get("claimed") or [])
    out = []
    for days, meta in sorted(STREAK_MILESTONES.items()):
        out.append({
            "days": days,
            "emoji": meta.get("emoji", "🏅"),
            "label": f"{days} dni z rzędu",
            "unlocked": days in claimed,
        })
    return out

