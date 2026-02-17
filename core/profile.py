# core/profile.py
from __future__ import annotations

from datetime import datetime
import streamlit as st

from core.persistence import _user_db_get, _user_db_set, _load_users
from core.routing import set_url_page, goto

"""core/profile.py

Ten moduł trzyma "jedną prawdę" o profilu i zapisie postępu.
Ważne: zapis do storage robimy wyłącznie przez autosave_if_dirty(),
żeby uniknąć chaosu i wyścigów.
"""

# Keys that we persist from st.session_state into the user's profile.
# Trzymamy minimalny, stabilny zestaw.
PROFILE_PERSIST_KEYS = (
    "xp",
    "gems",
    "kid_name",
    "age_group",
    "avatar_id",
    "skin_b64",
    "unlocked_games",
    "unlocked_avatars",
    "streak",
    "badges",
    "stickers",
    "class_code",
)


def get_profile(user: str | None = None) -> dict:
    """Pobiera profil użytkownika z storage.

    Strony NIE powinny wołać bezpośrednio _user_db_get/_user_db_set.
    Gość zwraca pusty profil.
    """
    if user is None:
        user = st.session_state.get("user")
    if not user or str(user).startswith("Gosc-"):
        return {}
    return _user_db_get(str(user)) or {}


def _deep_merge(dst: dict, src: dict) -> dict:
    for k, v in (src or {}).items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            dst[k] = _deep_merge(dst.get(k, {}), v)
        else:
            dst[k] = v
    return dst


def patch_profile(updates: dict, *, user: str | None = None) -> None:
    """Bezpiecznie nadpisuje wybrane pola profilu (merge), bez dotykania session_state.

    Używaj do pól, których nie trzymamy w session_state (np. retention).
    """
    if user is None:
        user = st.session_state.get("user")
    if not user or str(user).startswith("Gosc-"):
        return

    u = str(user)
    prof = _user_db_get(u) or {}
    prof = _deep_merge(prof, dict(updates or {}))
    _user_db_set(u, prof)


def mark_dirty(*fields: str) -> None:
    """Oznacza profil jako zmieniony w tej sesji.

    Wołaj po każdej zmianie stanu profilu (XP, 💎, avatary, unlocki, itd.).
    """
    st.session_state["_profile_dirty"] = True
    s = st.session_state.get("_profile_dirty_fields")
    if not isinstance(s, set):
        s = set()
    for f in fields:
        if isinstance(f, str) and f:
            s.add(f)
    st.session_state["_profile_dirty_fields"] = s


def _profile_user() -> str | None:
    u = st.session_state.get("user")
    if not u or str(u).startswith("Gosc-"):
        return None
    return str(u)


def save_profile_from_session() -> None:
    """Zapisuje profil użytkownika na podstawie st.session_state.

    Zasada: nie nadpisujemy całego profilu "na ślepo" – robimy merge z tym co jest
    w bazie/kv, żeby nie zgubić pól, których ta wersja UI akurat nie dotyka.
    """
    user = _profile_user()
    if not user:
        return

    prof = _user_db_get(user) or {}

    # scalar
    prof["xp"] = int(st.session_state.get("xp", prof.get("xp", 0)) or 0)
    prof["gems"] = int(st.session_state.get("gems", prof.get("gems", 0)) or 0)
    if "kid_name" in st.session_state:
        prof["kid_name"] = st.session_state.get("kid_name")
    if "age_group" in st.session_state:
        prof["age_group"] = st.session_state.get("age_group")

    # avatar
    if "avatar_id" in st.session_state:
        prof["avatar_id"] = st.session_state.get("avatar_id")
    if "skin_b64" in st.session_state:
        prof["skin_b64"] = st.session_state.get("skin_b64")

    # sets -> lists
    def _as_list(key: str) -> list:
        v = st.session_state.get(key, prof.get(key))
        if isinstance(v, set):
            return sorted(list(v))
        if isinstance(v, list):
            return v
        if v is None:
            return []
        return [v]

    prof["badges"] = _as_list("badges")
    prof["stickers"] = _as_list("stickers")

    # unlock sets
    ug = st.session_state.get("unlocked_games")
    if isinstance(ug, set):
        prof["unlocked_games"] = sorted(list(ug))
    ua = st.session_state.get("unlocked_avatars")
    if isinstance(ua, set):
        prof["unlocked_avatars"] = sorted(list(ua))

    # streak
    if "streak" in st.session_state:
        try:
            prof["streak"] = int(st.session_state.get("streak") or 0)
        except Exception:
            pass

    _user_db_set(user, prof)


def autosave_if_dirty(*, force: bool = False) -> None:
    """Bezpieczny autosave profilu.

    - Gość: brak zapisu.
    - Debounce: zapis max co ~2s.
    - force=True: zapis od razu.
    """
    user = _profile_user()
    if not user:
        return

    dirty = bool(st.session_state.get("_profile_dirty", False))
    if not dirty and not force:
        return

    now = datetime.utcnow().timestamp()
    last = float(st.session_state.get("_profile_last_autosave_ts", 0.0) or 0.0)
    if (not force) and (now - last < 2.0):
        return

    save_profile_from_session()
    st.session_state["_profile_dirty"] = False
    st.session_state["_profile_dirty_fields"] = set()
    st.session_state["_profile_last_autosave_ts"] = now

def _xp_total_for_level(level: int) -> int:
    """Krzywa progresji (sumaryczne XP wymagane do osiągnięcia poziomu).

    Założenia:
    - level 0..100
    - do okolic 60 poziomu progres jest dość płynny
    - po ~60 działa softcap (ciągle rośnie, ale wolniej)
    """
    lvl = max(0, min(100, int(level)))
    # bazowa krzywa: ~3500 XP do 100 (bez softcapu)
    return int(0.30 * (lvl ** 2) + 5 * lvl)


def get_profile_level(xp: int) -> int:
    """Przelicza XP na poziom 0..100 (z softcapem po ~60).

    Uwaga: to jest "jedna prawda" dla całej aplikacji.
    """
    try:
        raw_xp = int(xp or 0)
    except Exception:
        raw_xp = 0
    raw_xp = max(0, raw_xp)

    # softcap po progu odpowiadającemu ~60 lvl
    cap_lvl = 60
    cap_xp = _xp_total_for_level(cap_lvl)
    if raw_xp > cap_xp:
        # po softcapie XP "waży" mniej – spowalnia wbijanie 100
        effective_xp = cap_xp + int((raw_xp - cap_xp) * 0.40)
    else:
        effective_xp = raw_xp

    # znajdź największy level taki, że xp_total(level) <= effective_xp
    lo, hi = 0, 100
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if _xp_total_for_level(mid) <= effective_xp:
            lo = mid
        else:
            hi = mid - 1
    return int(lo)


def current_level(xp: int) -> int:
    """Back-compat: stara nazwa, ale nowa skala (0..100)."""
    return get_profile_level(xp)


def level_progress(xp: int) -> dict:
    """Pomocniczo do UI: zwraca level + postęp do następnego."""
    lvl = get_profile_level(xp)
    cur = _xp_total_for_level(lvl)
    nxt = _xp_total_for_level(min(100, lvl + 1))
    try:
        raw_xp = int(xp or 0)
    except Exception:
        raw_xp = 0
    # uwaga: progress liczymy względem *effective_xp*, bo to faktyczna progresja
    cap_xp = _xp_total_for_level(60)
    if raw_xp > cap_xp:
        effective_xp = cap_xp + int((raw_xp - cap_xp) * 0.40)
    else:
        effective_xp = max(0, raw_xp)
    span = max(1, nxt - cur)
    frac = max(0.0, min(1.0, (effective_xp - cur) / span))
    return {
        "level": lvl,
        "xp_effective": effective_xp,
        "xp_raw": max(0, raw_xp),
        "xp_level_start": cur,
        "xp_next_level": nxt,
        "progress": float(frac),
        "to_next": max(0, nxt - effective_xp),
    }

def age_to_group(age: int | None) -> str:
    try:
        a = int(age or 0)
    except Exception:
        a = 0
    if a <= 0:
        return "7-9"
    if 7 <= a <= 9:
        return "7-9"
    if 10 <= a <= 12:
        return "10-12"
    return "13-14"

def get_age_group() -> str:
    ag = st.session_state.get("age_group")
    if isinstance(ag, str) and ag:
        return ag
    # fallback from profile
    user = st.session_state.get("user")
    if user and not str(user).startswith("Gosc-"):
        prof = _user_db_get(user) or {}
        ag2 = prof.get("age_group") or prof.get("kid_age_group")
        if isinstance(ag2, str) and ag2:
            st.session_state["age_group"] = ag2
            return ag2
    st.session_state["age_group"] = "7-9"
    return "7-9"

def clear_age_group_dependent_state() -> None:
    # Clear caches that depend on age_group
    for k in [
        "cached_tasks",
        "quiz_dataset",
        "quiz_state",
        "daily_bonus_pack",
        "missions_today",
        "tasks_today",
    ]:
        if k in st.session_state:
            try:
                del st.session_state[k]
            except Exception:
                st.session_state[k] = None

def apply_age_group_change(new_group: str) -> None:
    if not isinstance(new_group, str) or not new_group:
        return
    st.session_state["age_group"] = new_group
    clear_age_group_dependent_state()

    try:
        mark_dirty("age_group")
        autosave_if_dirty(force=False)
    except Exception:
        # safe no-op
        pass

def load_profile_to_session(username: str) -> bool:
    if not username:
        return False
    # profile in kv store
    prof = _user_db_get(username) or {}
    st.session_state["user"] = username
    st.session_state["logged_in"] = True
    st.session_state["xp"] = int(prof.get("xp", st.session_state.get("xp", 0)) or 0)
    st.session_state["gems"] = int(prof.get("gems", st.session_state.get("gems", 0)) or 0)
    st.session_state["badges"] = set(prof.get("badges", []) or [])
    st.session_state["stickers"] = set(prof.get("stickers", []) or [])

    # --- Gry odblokowane (jednorazowa opłata, zapis w profilu) ---
    ug = prof.get("unlocked_games")
    if isinstance(ug, list):
        st.session_state["unlocked_games"] = set([str(x) for x in ug if x])
    else:
        st.session_state.setdefault("unlocked_games", set())

    # --- AVATARY: odblokowane ---
    ua = prof.get("unlocked_avatars")
    if isinstance(ua, list):
        st.session_state["unlocked_avatars"] = set([str(x) for x in ua if x])
    else:
        # fallback: zachowaj to co już było w sesji albo ustaw pusty zbiór
        st.session_state.setdefault("unlocked_avatars", set())

    # ✅ ZASADY AVATARÓW (bez mieszania gościa i zalogowanego):
    # - 6 guest-only: nie mają prawa "przeskoczyć" na zalogowanego
    # - 3 darmowe dla zalogowanych: zawsze traktuj jako odblokowane
    guest_only = {"cat_miner", "hero", "miner", "thief", "scientist", "young_wizard"}
    logged_free = {"cat_scientist", "miner_1", "scientist_1"}

    ua_set = st.session_state.get("unlocked_avatars")
    if not isinstance(ua_set, set):
        ua_set = set(ua_set) if isinstance(ua_set, (list, tuple)) else set()

    # usuń guest-only z unlocków zalogowanego (żeby nie mieszać profili)
    ua_set = {x for x in ua_set if x and (x not in guest_only)}
    # dodaj darmowe dla zalogowanych
    ua_set |= logged_free
    st.session_state["unlocked_avatars"] = ua_set
    if "kid_name" in prof:
        st.session_state["kid_name"] = prof.get("kid_name")

    # --- AVATAR: nowy format + kompatybilność wstecz ---
    # Nowy zapis:
    st.session_state["avatar_id"] = prof.get("avatar_id")
    st.session_state["skin_b64"] = prof.get("skin_b64")

    # Stary zapis (legacy): prof["avatar"] typu "builtin:miner"
    legacy = prof.get("avatar")
    if (not st.session_state.get("avatar_id")) and isinstance(legacy, str) and legacy.startswith("builtin:"):
        st.session_state["avatar_id"] = legacy.split(":", 1)[1]
        st.session_state["skin_b64"] = None

    
    # ✅ Jeśli ktoś miał ustawiony avatar guest-only, to po zalogowaniu podstaw bezpieczny darmowy.
    try:
        guest_only = {"cat_miner", "hero", "miner", "thief", "scientist", "young_wizard"}
        if st.session_state.get("avatar_id") in guest_only:
            st.session_state["avatar_id"] = "miner_1"
            st.session_state["skin_b64"] = None
    except Exception:
        pass

# Jak ktoś ma jeszcze starą wartość "avatar" (bez builtin:), zostaw jako awaryjne:
    st.session_state["avatar"] = legacy

    if "age_group" in prof:
        st.session_state["age_group"] = prof.get("age_group") or st.session_state.get("age_group", "7-9")

    if "streak" in prof:
        try:
            st.session_state["streak"] = int(prof.get("streak") or 0)
        except Exception:
            st.session_state["streak"] = 0

    return True


def after_login_cleanup(username: str) -> None:
    # Minimal cleanup + go Start
    try:
        st.session_state["page"] = "Start"
    except Exception:
        pass
    try:
        set_url_page("Start")
    except Exception:
        pass
    try:
        goto("Start")
    except Exception:
        pass
