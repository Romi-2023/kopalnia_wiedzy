# core/missions.py
from __future__ import annotations

import os
import json
import random
import hashlib
from dataclasses import dataclass, field
from datetime import date, timedelta

# Nagrody za streak (dni z rzędu)
STREAK_MILESTONES = {
    3:  {"xp": 5,  "badge": "streak_3",  "emoji": "🔥"},
    7:  {"xp": 10, "badge": "streak_7",  "emoji": "🏅"},
    14: {"xp": 20, "badge": "streak_14", "emoji": "💎"},
    30: {"xp": 40, "badge": "streak_30", "emoji": "👑"},
}

def _today_key() -> str:
    """Klucz dnia w formacie YYYY-MM-DD (wystarczy do blokad dziennych)."""
    return date.today().strftime("%Y-%m-%d")

def _get_today_completion_key() -> str:
    # kompatybilne z app_helpers; tu wystarczy “dziś”
    return _today_key()

def _section_done_key(subject: str) -> str:
    # 1x dziennie per subject
    s = (subject or "").strip().lower()
    return f"section_done::{s}::{_today_key()}"

import streamlit as st
from core.persistence import _user_db_get, _user_db_set
from core.config import (
    XP_SCHOOL_TASK,
    XP_MISSION_TASK,
    XP_SECTION_BONUS,
    GEMS_SECTION_BONUS,
    BASE_DIR,
)
# --- soft-import helpers to avoid circular imports ---
try:
    from core.app_helpers import (
        add_xp, add_gems, autosave_if_dirty,
        show_loot_popup, confetti_reward,
        load_lottie, grant_sticker, save_progress,
        get_age_group,
        load_tasks, TASKS_FILE,
        target_difficulty, filter_by_difficulty, _normalize_task_item,
    )
except Exception:
    # fallbacki - missions.py ma nie wybuchać przy imporcie
    def add_xp(amount=0, *a, **k):
        try:
            st.session_state["xp"] = int(st.session_state.get("xp", 0) or 0) + int(amount or 0)
        except Exception:
            return None

    def add_gems(amount=0, *a, **k):
        try:
            st.session_state["gems"] = int(st.session_state.get("gems", 0) or 0) + int(amount or 0)
        except Exception:
            return None
    def autosave_if_dirty(*a, **k): return None
    def show_loot_popup(*a, **k): return None
    def confetti_reward(*a, **k): return None
    def load_lottie(*a, **k): return None
    def grant_sticker(sticker_id=None, *a, **k):
        try:
            if not sticker_id:
                return None
            st.session_state.setdefault("stickers", set())
            # jakby stickers było listą:
            if isinstance(st.session_state["stickers"], list):
                st.session_state["stickers"] = set(st.session_state["stickers"])
            st.session_state["stickers"].add(str(sticker_id))
        except Exception:
            return None

    def save_progress(*a, **k):
        # fallback: nic nie zapisujemy, ale przynajmniej nagrody w UI działają
        return None
    def get_age_group(*a, **k): return "7-9"
    def load_tasks(*a, **k): return {}
    TASKS_FILE = "data/tasks.json"
    def target_difficulty(*a, **k): return None
    def filter_by_difficulty(arr, diff): return arr
    def _normalize_task_item(it): return {"q": str(it)} if isinstance(it, str) else (it or {})

try:
    from streamlit_lottie import st_lottie
except Exception:
    st_lottie = None

@dataclass
class StreakState:
    streak: int = 0
    last_day: str | None = None
    freezes: int = 0
    freeze_used_days: set[str] = field(default_factory=set)

    def __post_init__(self):
        if self.freeze_used_days is None:
            self.freeze_used_days = set()

def update_streak(state: StreakState, today: str) -> tuple[StreakState, str, str | None]:
    """
    Zwraca: (nowy_stan, event, gap_day)
    event: "first" | "continue" | "freeze" | "reset" | "same_day"
    gap_day: dzień uratowany freeze (YYYY-MM-DD) lub None
    """
    if state.last_day == today:
        return state, "same_day", None

    if not state.last_day:
        return StreakState(1, today, state.freezes, set(state.freeze_used_days)), "first", None

    y, m, d = map(int, state.last_day.split("-"))
    last = date(y, m, d)
    y2, m2, d2 = map(int, today.split("-"))
    cur = date(y2, m2, d2)
    diff = (cur - last).days

    if diff == 1:
        return StreakState(state.streak + 1, today, state.freezes, set(state.freeze_used_days)), "continue", None

    if diff == 2:
        gap = (cur - timedelta(days=1)).strftime("%Y-%m-%d")
        used = set(state.freeze_used_days)
        if state.freezes > 0 and gap not in used:
            used.add(gap)
            return StreakState(state.streak + 1, today, state.freezes - 1, used), "freeze", gap
        return StreakState(1, today, state.freezes, used), "reset", None

    if diff > 2:
        return StreakState(1, today, state.freezes, set(state.freeze_used_days)), "reset", None

    # diff <= 0 (np. zmiana zegara) – nie psuj
    return StreakState(max(1, state.streak), today, state.freezes, set(state.freeze_used_days)), "same_day", None


def _is_guest(user: str) -> bool:
    return isinstance(user, str) and user.startswith("Gosc-")

def _guest_daily_done_key() -> str:
    return f"guest_daily_done::{_today_key()}"

def _guest_bonus_done_key() -> str:
    return f"guest_bonus_done::{_today_key()}"

def get_retention_state(user: str) -> dict:
    profile = _user_db_get(user) or {}
    profile.setdefault(
        "retention",
        {
            "streak": 0,
            "last_day": None,
            "daily_done": [],
            "freezes": 0,           # 🧊 ile ma “freeze day”
            "freeze_used": [],      # daty “uratowane” freeze (YYYY-MM-DD)
            "claimed": [],          # milestone streak już odebrane (np. [3,7,14])
        },
    )
    return profile

def save_retention_state(user: str, profile: dict) -> None:
    _user_db_set(user, profile)

def daily_is_done(user: str) -> bool:
    # Gość: blokada w tej sesji (u Ciebie już tak jest robione)
    if isinstance(user, str) and user.startswith("Gosc-"):
        k = f"guest_daily_done::{_today_key()}"
        return bool(st.session_state.get(k, False))

    # Zalogowany: czy dzisiejszy klucz jest w retention.daily_done
    profile = _user_db_get(user) or {}
    r = profile.get("retention", {})
    done = set(r.get("daily_done") or [])
    return _today_key() in done


def mark_daily_done(user: str) -> dict:
    today = _today_key()

    # --- GOŚĆ: blokada powtórki w tej sesji (na dziś) ---
    if isinstance(user, str) and user.startswith("Gosc-"):
        k = f"guest_daily_done::{today}"
        if st.session_state.get(k, False):
            return {"streak": 0, "freeze_used": False, "gap_day": None}
        st.session_state[k] = True
        return {"streak": 0, "freeze_used": False, "gap_day": None}

    # --- ZALOGOWANY: Twoja logika retention/streak ---
    profile = get_retention_state(user)
    r = profile.setdefault("retention", {})

    # jeżeli już dziś zaliczone – nie rób drugi raz
    done = set(r.get("daily_done") or [])
    if today in done:
        return {
            "streak": int(r.get("streak", 0)),
            "freeze_used": False,
            "gap_day": None,
        }

    state = StreakState(
        streak=int(r.get("streak", 0) or 0),
        last_day=r.get("last_day"),
        freezes=int(r.get("freezes", 0) or 0),
        freeze_used_days=set(r.get("freeze_used") or []),
    )

    new_state, event, gap_day = update_streak(state, today)

    r["freeze_used"] = sorted(new_state.freeze_used_days)
    r["streak"] = int(new_state.streak)
    r["last_day"] = new_state.last_day
    r["freezes"] = int(new_state.freezes)

    freeze_used = (event == "freeze")

    # daily_done
    done.add(today)
    r["daily_done"] = sorted(done)

    save_retention_state(user, profile)

    return {
        "streak": int(new_state.streak),
        "freeze_used": bool(freeze_used),
        "gap_day": gap_day,
    }

def get_daily_bonus_pack(user: str, k: int = 3) -> list:
    """
    Zwraca dzisiejszy pakiet bonusów (k zadań) w formacie:
    [{"subject": "matematyka", "task": {"q": "...", "xp": 5, ...}}, ...]
    - deterministyczny na dzień (żadnych losowań na rerun)
    - dopasowany do age_group
    """
    # 1) wczytaj tasks.json przez warstwę persistence (single source of truth)
    #    load_tasks() już ma sensowne fallbacki (DB -> data/tasks.json -> tasks.json)
    try:
        TASKS = load_tasks()
    except Exception:
        TASKS = {}

    if not isinstance(TASKS, dict) or not TASKS:
        return []

    age_group = get_age_group()

    # jakie przedmioty bierzemy (muszą istnieć w tasks.json)
    subjects = [s for s in TASKS.keys() if isinstance(TASKS.get(s), dict)]
    if not subjects:
        return []

    # 2) deterministyczny seed: dzień + user (żeby każdy miał “swoje” bonusy)
    today_key = _get_today_completion_key()
    seed_text = f"bonus::{today_key}::{user}::{age_group}"
    seed_int = int(hashlib.sha256(seed_text.encode("utf-8")).hexdigest(), 16) % (10**12)
    rng = random.Random(seed_int)

    # 3) zbuduj pulę kandydatów
    pool = []
    for subj in subjects:
        subj_obj = TASKS.get(subj, {})
        arr = subj_obj.get(age_group, [])
        if not isinstance(arr, list) or not arr:
            continue

        # filtr trudności jeśli masz tagi difficulty
        try:
            diff = target_difficulty(f"school::{subj}")
            arr2 = filter_by_difficulty(arr, diff)
        except Exception:
            arr2 = arr

        # ujednolicenie formatu (string/dict) -> dict z q
        for it in arr2:
            t = _normalize_task_item(it)
            q = (t.get("q") or "").strip()
            if not q:
                continue
            # xp default 5
            if "xp" not in t:
                t["xp"] = 5
            pool.append({"subject": subj, "task": t})

    if not pool:
        return []

    # 4) wybór k sztuk bez powtórzeń (deterministycznie)
    rng.shuffle(pool)
    picked = pool[: max(1, int(k))]

    return picked

def claim_streak_lootbox(user: str, streak: int):
    """
    Jeśli streak trafił w milestone i nie był odebrany → daje nagrodę 1x.
    Lootbox ma 25% szans na 🧊 Freeze (dodatkowy zasób).
    """
    if not user or str(user).startswith("Gosc-"):
        return  # dla gościa pomijamy (możemy to zmienić później)

    profile = get_retention_state(user)
    r = profile["retention"]
    claimed = set(r.get("claimed") or [])

    if streak in STREAK_MILESTONES and streak not in claimed:
        reward = STREAK_MILESTONES[streak]
        xp_gain = int(reward.get("xp", 0))
        badge = reward.get("badge")
        emoji = reward.get("emoji", "📦")

        # --- base rewards ---
        st.session_state["xp"] = int(st.session_state.get("xp", 0) or 0) + int(xp_gain)

        if badge:
            st.session_state.setdefault("badges", set())
            if isinstance(st.session_state["badges"], list):
                st.session_state["badges"] = set(st.session_state["badges"])
            st.session_state["badges"].add(badge)

        grant_sticker("sticker_lootbox")

        # --- 25% chance for FREEZE (deterministic, anti-rerun farm) ---
        # seed zależy od user + milestone, więc nie da się "wyklikać"
        seed = f"freeze_drop::{user}::{streak}::{_today_key()}"
        roll = (int(hashlib.sha256(seed.encode("utf-8")).hexdigest(), 16) % 100) / 100.0
        got_freeze = roll < 0.25

        if got_freeze:
            r["freezes"] = int(r.get("freezes", 0)) + 1

        # --- mark claimed (once) + persist ---
        claimed.add(streak)
        r["claimed"] = sorted(claimed)
        save_retention_state(user, profile)
        save_progress()

        # --- UI feedback ---
        extra = " + 🧊 Freeze!" if got_freeze else ""
        st.toast(f"📦 Skrzynka serii! +{xp_gain} XP • {badge}{extra}", icon=emoji)
        st.balloons()

        
def mark_task_done(user: str, subject: str, task_text: str, xp_gain: int | None = None):
    if xp_gain is None:
        xp_gain = XP_SCHOOL_TASK

    profile = _user_db_get(user) or {}

    # ensure containers
    profile.setdefault("school_tasks", {})
    today = _get_today_completion_key()
    day_map = profile["school_tasks"].setdefault(today, {})
    subj_list = day_map.setdefault(subject, [])

    tid = _task_id_from_text(task_text)

    # tylko raz dziennie za to zadanie
    if tid not in subj_list:
        subj_list.append(tid)

        # ✅ nagroda jednym, spójnym mechanizmem (log + autosave)
        try:
            add_xp(int(xp_gain), reason=f"bonus::{subject}")
        except Exception:
            # awaryjnie: chociaż podbij XP w sesji
            st.session_state["xp"] = int(st.session_state.get("xp", 0) or 0) + int(xp_gain)

    # ✅ bardzo ważne: zaktualizuj xp/gems w profilu zanim zapiszesz cały dict
    try:
        profile["xp"] = int(st.session_state.get("xp", 0) or 0)
    except Exception:
        pass
    try:
        profile["gems"] = int(st.session_state.get("gems", 0) or 0)
    except Exception:
        pass

    _user_db_set(user, profile)


def is_task_done(user: str, subject: str, task_text: str) -> bool:
    profile = _user_db_get(user)
    if not profile:
        return False

    today = _get_today_completion_key()
    tid = _task_id_from_text(task_text)

    try:
        return tid in profile.get("school_tasks", {}).get(today, {}).get(subject, [])
    except Exception:
        return False


def count_tasks_done_in_subject(user: str, subject: str) -> int:
    """Łączna liczba zadań ukończonych w danym przedmiocie (wszystkie dni)."""
    profile = _user_db_get(user)
    if not profile:
        return 0
    total = 0
    for day_data in (profile.get("school_tasks") or {}).values():
        if not isinstance(day_data, dict):
            continue
        ids = day_data.get(subject)
        if isinstance(ids, list):
            total += len(ids)
    return total


def has_ever_done_subject(user: str, subject: str) -> bool:
    """Czy użytkownik kiedykolwiek ukończył choć jedno zadanie z tego przedmiotu."""
    return count_tasks_done_in_subject(user, subject) > 0
    
def reward_school_section_once(user: str, subject: str):
    """
    Nagradza ukończenie całego działu (np. komplet dziennych zadań z przedmiotu).
    1x dziennie na przedmiot – PERSISTENTNIE (nie tylko w sesji).
    """
    if not user or str(user).startswith("Gosc-"):
        return

    flag = _section_done_key(subject)

    # 1) szybki bezpiecznik w sesji
    if st.session_state.get(flag, False):
        return

    # 2) persistent check w profilu
    profile = _user_db_get(user) or {}
    done_flags = profile.get("daily_flags", [])
    if isinstance(done_flags, str):
        done_flags = [done_flags]
    if not isinstance(done_flags, list):
        done_flags = []

    if flag in done_flags:
        st.session_state[flag] = True
        return

    # XP + (opcjonalnie) 💎
    add_xp(XP_SECTION_BONUS, reason=f"section::{subject}")
    if GEMS_SECTION_BONUS > 0:
        add_gems(GEMS_SECTION_BONUS, reason=f"section::{subject}")

    # animacja “loot”
    try:
        anim = load_lottie(os.path.join(BASE_DIR, "assets", "Bloo Cool.json"))
    except Exception:
        anim = None

    if anim and st_lottie:
        st_lottie(anim, speed=1.0, loop=False, height=200, key=f"lottie_section_{flag}")
    else:
        try:
            confetti_reward()
        except Exception:
            pass

    show_loot_popup("🏁 Dział ukończony!", f"+{XP_SECTION_BONUS} XP • +{GEMS_SECTION_BONUS} 💎", "🎁")

    # 3) zapisz flagę: raz dziennie per subject
    done_flags.append(flag)
    profile["daily_flags"] = done_flags
    _user_db_set(user, profile)

    st.session_state[flag] = True

    # 4) bezpieczny autosave (żeby xp/gems też się utrwaliły)
    try:
        autosave_if_dirty()
    except Exception:
        pass

def _task_id_from_text(text: str) -> str:
    return hashlib.sha256(("task::" + text).encode("utf-8")).hexdigest()[:12]

