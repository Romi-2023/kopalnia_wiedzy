# pages/avatar.py
from __future__ import annotations

import streamlit as st

from core.state_init import init_core_state, init_router_state, ensure_default_dataset
from core.avatars import AVATAR_META, list_builtin_avatars
from core.profile import mark_dirty, get_profile_level
from core.routing import go_back_hard


GUEST_ONLY = {"cat_miner", "hero", "miner", "thief", "scientist", "young_wizard"}
LOGGED_FREE = {"cat_scientist", "miner_1", "scientist_1"}


def _is_guest(u) -> bool:
    return isinstance(u, str) and u.startswith("Gosc-")


def _as_set(v) -> set:
    if isinstance(v, set):
        return v
    if isinstance(v, (list, tuple)):
        return set([str(x) for x in v if x])
    return set()


def _unlock_spec(aid: str) -> dict:
    meta = AVATAR_META.get(aid, {}) or {}
    u = meta.get("unlock") or {}
    if not isinstance(u, dict):
        u = {}
    return u


def _cost_label(req_level: int, xp_cost: int, gems_cost: int) -> str:
    parts = []
    if req_level > 0:
        parts.append(f"lvl ≥ {req_level}")
    if xp_cost > 0:
        parts.append(f"{xp_cost} XP")
    if gems_cost > 0:
        parts.append(f"{gems_cost} 💎")
    return " • ".join(parts) if parts else "darmowy"


def _can_unlock(*, level: int, xp: int, gems: int, req_level: int, xp_cost: int, gems_cost: int) -> bool:
    if req_level and level < req_level:
        return False
    if xp < xp_cost:
        return False
    if gems < gems_cost:
        return False
    return True


def render() -> None:
    # ✅ multipage-safe bootstrap
    init_core_state()
    init_router_state(initial_page="Avatar")
    st.session_state["page"] = "Avatar"
    ensure_default_dataset()

    st.title("🧑‍🚀 Avatary")

    user = st.session_state.get("user")
    if not user:
        st.info("Zaloguj się lub graj jako Gość, żeby wybrać avatar 🙂")
        if st.button("⬅️ Wróć", use_container_width=True, key="avatar_back_no_user"):
            go_back_hard()
        return

    is_guest = _is_guest(user)
    xp = int(st.session_state.get("xp", 0) or 0)
    gems = int(st.session_state.get("gems", 0) or 0)
    level = int(get_profile_level(xp) or 0)

    # Odblokowane: tylko dla zalogowanych. Gość zawsze ma dostęp do guest-only.
    unlocked = _as_set(st.session_state.get("unlocked_avatars"))

    if not is_guest:
        # zawsze zapewnij darmowe dla zalogowanych (bez względu na stan profilu)
        unlocked |= set(LOGGED_FREE)
        # nie mieszaj guest-only do profilu zalogowanego
        unlocked -= set(GUEST_ONLY)
        st.session_state["unlocked_avatars"] = unlocked

    current = st.session_state.get("avatar_id")

    # Lekki panel statusu (żeby było jasne czemu coś jest zablokowane)
    if is_guest:
        st.caption("Tryb: **Gość** — dostępne są tylko avatary gościa (darmowe).")
    else:
        st.caption(f"Tryb: **Zalogowany** — poziom: **{level}**, zasoby: **{xp} XP**, **{gems} 💎**")

    builtins = list_builtin_avatars() or []
    if not builtins:
        st.warning("Brak avatarów w assets/avatars/. Dodaj PNG do tego folderu.")
        if st.button("⬅️ Wróć", use_container_width=True, key="avatar_back_no_assets"):
            go_back_hard()
        return

    # Filtr: gość widzi tylko guest-only; zalogowany nie widzi guest-only (żeby nie było zamieszania)
    filtered = []
    for a in builtins:
        aid = a.get("id")
        if not aid:
            continue
        if is_guest:
            if aid in GUEST_ONLY:
                filtered.append(a)
        else:
            if aid not in GUEST_ONLY:
                filtered.append(a)

    st.markdown("---")
    cols = st.columns(3)

    for i, a in enumerate(filtered):
        aid = a.get("id")
        path = a.get("path")
        if not aid or not path:
            continue

        meta = AVATAR_META.get(aid, {}) or {}
        nice = meta.get("name", aid)
        unlock = _unlock_spec(aid)
        utype = str(unlock.get("type") or "free")

        # Ustal wymagania/koszty
        req_level = int(unlock.get("level", 0) or 0)
        xp_cost = int(unlock.get("xp", 0) or 0)
        gems_cost = int(unlock.get("gems", 0) or 0)

        if utype == "xp":
            xp_cost = int(unlock.get("value", xp_cost) or 0)
        if utype == "gems":
            gems_cost = int(unlock.get("value", gems_cost) or 0)
        if utype == "combo":
            pass
        if utype == "free":
            req_level = 0
            xp_cost = 0
            gems_cost = 0

        is_current = (aid == current)

        # Dostępność:
        if is_guest:
            is_available = (aid in GUEST_ONLY)  # zawsze
            can_buy = False
        else:
            # darmowe albo już odblokowane
            is_available = (aid in unlocked) or (utype == "free") or is_current
            can_buy = (not is_available) and (utype in ("xp", "gems", "combo", "level"))

        with cols[i % 3]:
            st.image(path, use_container_width=True)
            st.caption(nice)

            if is_current:
                st.success("✅ Aktualny")
            else:
                # wybór
                if st.button("✅ Wybierz", use_container_width=True, key=f"pick_{aid}", disabled=not is_available):
                    st.session_state["avatar_id"] = aid
                    st.session_state["skin_b64"] = None
                    try:
                        mark_dirty("avatar_id", "skin_b64")
                    except Exception:
                        pass
                    st.toast("Avatar zmieniony!", icon="🧑‍🚀")
                    st.rerun()

            # zakup / blokada
            if (not is_guest) and (not is_available):
                label = _cost_label(req_level, xp_cost, gems_cost)

                can_unlock_now = _can_unlock(
                    level=level, xp=xp, gems=gems,
                    req_level=req_level, xp_cost=xp_cost, gems_cost=gems_cost
                )

                if can_buy:
                    if st.button(f"🔓 Odblokuj ({label})", use_container_width=True, key=f"buy_{aid}", disabled=not can_unlock_now):
                        # odejmij zasoby (XP i/lub 💎) i dodaj do odblokowanych
                        st.session_state["xp"] = max(0, int(st.session_state.get("xp", 0) or 0) - xp_cost)
                        st.session_state["gems"] = max(0, int(st.session_state.get("gems", 0) or 0) - gems_cost)

                        ua = _as_set(st.session_state.get("unlocked_avatars"))
                        ua.add(aid)
                        st.session_state["unlocked_avatars"] = ua

                        try:
                            mark_dirty("xp", "gems", "unlocked_avatars")
                        except Exception:
                            pass

                        st.toast("Odblokowano avatar!", icon="🔓")
                        st.rerun()
                else:
                    # typy w przyszłości: np. streak/badge — na razie pokazujemy twardo
                    st.info(f"🔒 Zablokowany • {label}")

                if not can_unlock_now:
                    # mała podpowiedź czemu zablokowane
                    hints = []
                    if req_level and level < req_level:
                        hints.append(f"brakuje poziomu ({level}/{req_level})")
                    if xp < xp_cost:
                        hints.append(f"brakuje XP ({xp}/{xp_cost})")
                    if gems < gems_cost:
                        hints.append(f"brakuje 💎 ({gems}/{gems_cost})")
                    if hints:
                        st.caption("Nie możesz jeszcze odblokować: " + ", ".join(hints))

    # Odznaki za serie (dla zalogowanych)
    if not is_guest and user:
        try:
            from core.app_helpers import get_streak_badges
            streak_badges = get_streak_badges(str(user))
            if streak_badges:
                with st.expander("🏅 Odznaki za serie", expanded=False):
                    st.caption("Kończ Misję dnia kolejnego dnia – odbierzesz nagrody za 3, 7, 14 i 30 dni z rzędu.")
                    for sb in streak_badges:
                        status = "🔓" if sb.get("unlocked") else "🔒"
                        st.markdown(f"{status} {sb.get('emoji', '🏅')} **{sb.get('label', '')}**")
        except Exception:
            pass

    st.markdown("---")
    if st.button("⬅️ Wróć", use_container_width=True, key="avatar_back"):
        go_back_hard()


# Multipage (st.switch_page): uruchom render() także przy wejściu bez routera
try:
    render()
except Exception:
    pass
