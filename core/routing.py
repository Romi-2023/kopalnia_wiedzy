# core/routing.py
from __future__ import annotations

import os
from pathlib import Path
from typing import Set

import streamlit as st


# Jeśli multipage (st.switch_page) robi problemy (a często robi, gdy masz własny router
# i wspólny bootstrap w app.py), wyłącz to jednym przełącznikiem.
#
# Domyślnie: OFF (stabilniej) – aplikacja działa jako single-script + dispatch().
# Jeśli chcesz multipage, ustaw zmienną środowiskową D4K_USE_MULTIPAGE=1.
USE_MULTIPAGE = os.getenv("D4K_USE_MULTIPAGE", "0").strip() == "1"

# ✅ Źródło prawdy: lista stron (router + nav + walidacja)
VALID_PAGES: Set[str] = {"Intro","Start","Misje","Skrzynka","Quiz danych","Quiz obrazkowy","Avatar","Wkrótce","Przedmioty","Plac zabaw","Saper","Pomoce szkolne","Lektury","Karta rowerowa","Album naklejek","Hall of Fame","Słowniczek","Mapa kopalni","Wyzwanie dnia","Nadzor"}

# Alias dla portali, które nie mają jeszcze własnej strony (Nadz = skrót/obcięcie Nadzor)
ALIAS_PAGES = {
    "Nadz": "Nadzor",
    "Przedmioty szkolne": "Przedmioty",
    "Poznaj dane": "Quiz danych",
    "Plac zabaw": "Plac zabaw",
    "Quiz obrazkowy": "Quiz obrazkowy",
    "Gra Memory": "Saper",
    "Pomoce szkolne": "Pomoce szkolne",
    "Album naklejek": "Album naklejek",
    "Hall of Fame": "Hall of Fame",
    "Panel rodzica": "Start",
}

# --- Multipage mapping: nazwa -> plik w pages/ ---
# Dopisuj kolejne, kiedy masz odpowiednie pliki w pages/.
_PAGE_MAP = {
    "Intro": "pages/intro.py",
    "Start": "pages/start.py",
    "Misje": "pages/misje.py",
    "Quiz danych": "pages/quiz_danych.py",
    "Quiz obrazkowy": "pages/quiz_obrazkowy.py",
    "Skrzynka": "pages/skrzynka.py",
    "Avatar": "pages/avatar.py",
    "Wkrótce": "pages/wkrotce.py",
    "Przedmioty": "pages/przedmioty.py",
    "Plac zabaw": "pages/plac_zabaw.py",
    "Saper": "pages/saper.py",
    "Pomoce szkolne": "pages/pomoce_szkolne.py",
    "Lektury": "pages/lektury.py",
    "Karta rowerowa": "pages/karta_rowerowa.py",
    "Album naklejek": "pages/album_naklejek.py",
    "Hall of Fame": "pages/hall_of_fame.py",
    "Słowniczek": "pages/slowniczek.py",
    "Mapa kopalni": "pages/mapa_kopalni.py",
    "Wyzwanie dnia": "pages/wyzwanie_dnia.py",
    "Nadzor": "pages/nadzor.py",
    # "Panel rodzica": "pages/panel_rodzica.py",
}

# root projektu: .../core/routing.py -> parents[1] = katalog z app.py
_ROOT = Path(__file__).resolve().parents[1]


def _sanitize_page(p: str, default: str = "Start") -> str:
    p = (p or "").strip()
    if p in ALIAS_PAGES:
        # zapamiętaj oryginalną nazwę portalu do ekranu "Wkrótce"
        st.session_state["portal_target"] = p
        p = ALIAS_PAGES[p]
    return p if p in VALID_PAGES else default


def qp_get(key: str, default=None):
    """Czytaj query param w zgodny sposób (nowe/legacy Streamlit)."""
    try:
        v = st.query_params.get(key)
        return v if v is not None else default
    except Exception:
        try:
            v = st.experimental_get_query_params().get(key, [default])[0]
            return v
        except Exception:
            return default


def set_url_page(p: str) -> None:
    """
    Ustawia ?p=... w URL, ale NIE gubi innych parametrów (np. ?g=Gosc-xxxx).
    Nie dotyka URL jeśli nic się nie zmienia (anti-flicker).
    """
    # 1) aktualne parametry
    try:
        current = dict(st.query_params)
        current = {k: (v[0] if isinstance(v, list) and v else v) for k, v in current.items()}
    except Exception:
        current = st.experimental_get_query_params() or {}
        current = {k: (v[0] if isinstance(v, list) and v else v) for k, v in current.items()}

    # 2) docelowe
    desired = dict(current)
    desired["p"] = p

    user = st.session_state.get("user")
    if isinstance(user, str) and user.startswith("Gosc-"):
        desired["g"] = user
    else:
        desired.pop("g", None)

    if desired == current:
        return

    try:
        st.query_params.clear()
        for k, v in desired.items():
            st.query_params[k] = v
    except Exception:
        st.experimental_set_query_params(**desired)


def push_history(p: str) -> None:
    """Trzyma historię odwiedzanych stron (max 50)."""
    st.session_state.setdefault("nav_history", ["Start"])
    hist = st.session_state.get("nav_history") or ["Start"]
    if not hist:
        hist = ["Start"]

    if hist[-1] != p:
        hist.append(p)

    st.session_state["nav_history"] = hist[-50:]


def _switch_page_if_possible(page_name: str) -> bool:
    """
    Multipage: przełącz stronę maksymalnie kompatybilnie.
    Streamlit bywa kapryśny: raz woli ścieżkę, raz nazwę strony.
    """
    rel = _PAGE_MAP.get(page_name)
    if not rel:
        return False
    if (not USE_MULTIPAGE) or (not hasattr(st, "switch_page")):
        return False

    # 1) najpierw spróbuj standardowo: ścieżka względna
    try:
        st.switch_page(rel)  # np. "pages/misje.py"
        return True
    except Exception:
        pass

    # 2) czasem pomaga sama nazwa pliku (bez "pages/")
    try:
        st.switch_page(rel.split("/")[-1])  # np. "misje.py"
        return True
    except Exception:
        pass

    # 3) a czasem Streamlit chce "title" strony (jak w sidebarze)
    # (różne wersje różnie to interpretują)
    try:
        st.switch_page(page_name)  # np. "Misje"
        return True
    except Exception:
        pass

    # 4) awaryjnie: absolutna ścieżka do pliku
    try:
        target = _ROOT / rel
        if target.exists():
            st.switch_page(str(target))
            return True
    except Exception:
        pass

    return False


def _switch_page_any(page_name: str) -> bool:
    """Try st.switch_page regardless of USE_MULTIPAGE (fallback for multipage runs)."""
    rel = _PAGE_MAP.get(page_name)
    if not rel or not hasattr(st, "switch_page"):
        return False

    # 1) relative path
    try:
        st.switch_page(rel)
        return True
    except Exception:
        pass

    # 2) filename only
    try:
        st.switch_page(rel.split("/")[-1])
        return True
    except Exception:
        pass

    # 3) page title
    try:
        st.switch_page(page_name)
        return True
    except Exception:
        pass

    # 4) absolute path
    try:
        target = _ROOT / rel
        if target.exists():
            st.switch_page(str(target))
            return True
    except Exception:
        pass

    return False


def goto(p: str) -> None:
    """
    Jedna nawigacja dla całej apki (STABILNIE):
    - domyślnie: single-app (session_state + query param + rerun)
    - multipage: tylko jeśli jawnie włączone envem (D4K_USE_MULTIPAGE=1)
    """
    p = _sanitize_page(p, default="Start")

    # spójny stan
    st.session_state["page"] = p
    st.session_state["page_widget"] = p

    try:
        push_history(p)
    except Exception:
        pass

    # ✅ multipage TYLKO gdy jawnie włączone (inaczej miesza i psuje kliki po loginie)
    try:
        use_mp = bool(st.session_state.get("_use_multipage"))
    except Exception:
        use_mp = False

    # Jeżeli masz globalną flagę USE_MULTIPAGE w tym module – użyj jej:
    try:
        use_mp = use_mp or bool(USE_MULTIPAGE)
    except Exception:
        pass

    if use_mp:
        # multipage: przełącz stronę i wyjdź
        if _switch_page_if_possible(p):
            return

    # ✅ single-app: ustaw query param i wymuś rerun
    try:
        set_url_page(p)  # ustawia ?p=...
    except Exception:
        pass

    st.session_state["_goto"] = p
    st.rerun()


def goto_hard(p: str) -> None:
    """Navigation that tries st.switch_page even if multipage is off."""
    p = _sanitize_page(p, default="Start")
    if _switch_page_any(p):
        return
    goto(p)


def go_back(default: str = "Start") -> None:
    hist = st.session_state.get("nav_history") or ["Start"]
    if len(hist) >= 2:
        hist.pop()
        prev = hist[-1]
    else:
        prev = default
        hist = [default]
    st.session_state["nav_history"] = hist
    goto(prev)


def go_back_hard(default: str = "Start") -> None:
    """Back navigation that can work in multipage runs."""
    hist = st.session_state.get("nav_history") or ["Start"]
    if len(hist) >= 2:
        hist.pop()
        prev = hist[-1]
    else:
        prev = default
        hist = [default]
    st.session_state["nav_history"] = hist
    goto_hard(prev)


def apply_router(*, show_sidebar_nav: bool = False) -> None:
    """
    1) Session -> sanitize
    2) URL ?p=... -> session (jeśli poprawne), inaczej hard fallback do Start
    3) URL ?g=Gosc-... -> ustaw gościa (minimalnie, bez avatarów)
    """
    # --- 0) obsługa goto() (session -> page) ---
    skip_qp_sync = False
    pending = st.session_state.pop("_goto", None)
    if isinstance(pending, str) and pending.strip():
        pending = pending.strip()
        if pending in VALID_PAGES:
            st.session_state["page"] = pending
            if show_sidebar_nav:
                st.session_state["page_widget"] = pending
            try:
                push_history(pending)
            except Exception:
                pass
            set_url_page(pending)
            # Jeśli goto() było źródłem nawigacji, nie nadpisuj
            # stroną z query-param w tym samym rerunie.
            skip_qp_sync = True

    # --- 1) sesja: twarda walidacja ---
    cur = _sanitize_page(st.session_state.get("page", "Start"))
    if cur != st.session_state.get("page"):
        st.session_state["page"] = cur
        set_url_page(cur)

    # --- 2) URL -> sesja ---
    if not skip_qp_sync:
        qp = qp_get("p", None)
        if isinstance(qp, str) and qp.strip():
            qp_clean = qp.strip()
            qp_resolved = ALIAS_PAGES.get(qp_clean, qp_clean)  # Nadz -> Nadzor itp.

            if qp_resolved in VALID_PAGES and qp_resolved != st.session_state.get("page"):
                st.session_state["page"] = qp_resolved
                if show_sidebar_nav:
                    st.session_state["page_widget"] = qp_clean
                try:
                    push_history(qp_resolved)
                except Exception:
                    pass

            elif qp_resolved not in VALID_PAGES:
                st.session_state["page"] = "Start"
                set_url_page("Start")

    # --- 3) guest from URL ---
    g = qp_get("g", None)
    if isinstance(g, str):
        g = g.strip()

    if (not st.session_state.get("user")) and isinstance(g, str) and g.startswith("Gosc-"):
        st.session_state["user"] = g
        st.session_state.setdefault("xp", 0)
        st.session_state.setdefault("gems", 0)
        st.session_state.setdefault("badges", set())
        st.session_state.setdefault("stickers", set())
        st.session_state.setdefault("unlocked_games", set())
        st.session_state.setdefault("unlocked_avatars", set())
        st.session_state.setdefault("memory_stats", {})
        st.session_state.setdefault("missions_state", {})
        st.session_state.setdefault("activity_log", [])
        st.session_state.setdefault("age_group", "10-12")


def dispatch() -> None:
    """Import and render the current page module safely.

    Expects each pages/*.py module to expose render().
    """
    import importlib
    from pathlib import Path

    page = _sanitize_page(str(st.session_state.get("page", "Start")))
    st.session_state["page"] = page  # keep sanitized

    rel = _PAGE_MAP.get(page) or _PAGE_MAP.get("Start")
    if not rel:
        st.error("Brak konfiguracji stron (_PAGE_MAP).")
        return

    module_name = f"pages.{Path(rel).stem}"

    try:
        mod = importlib.import_module(module_name)
    except Exception as e:
        st.error(f"Nie mogę załadować strony: {page} ({module_name}).")
        try:
            from core.ui import show_exception
            show_exception(e)
        except Exception:
            pass
        # hard fallback
        if page != "Start":
            st.session_state["_goto"] = "Start"
            st.rerun()
        return

    render_fn = getattr(mod, "render", None)
    if not callable(render_fn):
        st.error(f"Moduł {module_name} nie ma funkcji render().")
        return

    try:
        render_fn()
    except Exception as e:
        st.error(f"Błąd w stronie: {page}.")
        try:
            from core.ui import show_exception
            show_exception(e)
        except Exception:
            pass
