# core/ui.py
from __future__ import annotations

import time
import streamlit as st
from pathlib import Path

try:
    from streamlit_lottie import st_lottie as _st_lottie
except Exception:
    _st_lottie = None

import base64


def show_exception(e: Exception) -> None:
    """Bezpieczne wyświetlenie wyjątku niezależnie od wersji Streamlit."""
    if hasattr(st, "exception"):
        try:
            st.exception(e)
            return
        except Exception:
            pass
    # fallback (starsze wersje / dziwne środowiska)
    import traceback

    st.error(str(e))
    st.code(traceback.format_exc())

def _bytes_to_b64(data: bytes) -> str:
    return base64.b64encode(data).decode("utf-8")

def load_minecraft_css():
    """Ładuje CSS jeśli plik istnieje. Bez crasha i bez importów w kółko."""
    css_path = Path("ui/minecraft.css")
    if css_path.exists():
        st.markdown(
            f"<style>{css_path.read_text(encoding='utf-8')}</style>",
            unsafe_allow_html=True
        )

def st_lottie(anim=None, speed: float = 1.0, loop: bool = True, height: int = 200, key=None, **kwargs):
    """
    Kompatybilne st_lottie():
    - jeśli masz streamlit-lottie -> użyje go
    - jeśli nie masz -> fallback przez lottie-web (HTML), bez crasha

    Przyjmuje typowe argumenty: anim(dict), speed, loop, height, key
    """
    if anim is None:
        # pozwala na stare wywołania typu st_lottie(*args, **kwargs) — ale bez animacji nic nie zrobimy
        return None

    # 1) Prefer: streamlit-lottie, jeśli dostępne
    if _st_lottie is not None:
        try:
            return _st_lottie(anim, speed=speed, loop=loop, height=height, key=key, **kwargs)
        except Exception:
            # jakby coś poszło bokiem, to i tak mamy fallback
            pass

    # 2) Fallback: lottie-web przez components.html
    try:
        import json
        import uuid
        import streamlit.components.v1 as components

        element_id = f"lottie-{key or uuid.uuid4().hex}"
        anim_json = json.dumps(anim)

        html = f"""
        <style>
          html, body {{
            margin: 0; padding: 0;
            background: transparent !important;
          }}
          #{element_id} {{
            width: 100%;
            height: {int(height)}px;
            background: transparent !important;
          }}
        </style>

        <div id="{element_id}"></div>

        <script src="https://cdnjs.cloudflare.com/ajax/libs/bodymovin/5.12.2/lottie.min.js"></script>
        <script>
          const animData = {anim_json};
          const anim = lottie.loadAnimation({{
            container: document.getElementById("{element_id}"),
            renderer: "svg",
            loop: {str(bool(loop)).lower()},
            autoplay: true,
            animationData: animData,
            rendererSettings: {{
              preserveAspectRatio: "xMidYMid meet"
            }}
          }});
          anim.setSpeed({float(speed)});
        </script>
        """
        components.html(html, height=int(height), scrolling=False)
        return None
    except Exception:
        # absolutnie ostatnia deska ratunku: nie wywalaj apki
        st.warning("Nie udało się wyrenderować animacji Lottie (brak streamlit-lottie i fallback się nie udał).")
        return None


# =========================
# Small utilities
# =========================
def safe_rerun() -> None:
    """Never crash the page when rerun is blocked."""
    try:
        st.rerun()
    except Exception:
        try:
            st.experimental_rerun()
        except Exception:
            pass


def toast(msg: str) -> None:
    msg = (msg or "").strip()
    if not msg:
        return
    try:
        st.toast(msg)
    except Exception:
        st.info(msg)


# =========================
# Legacy helpers (compat)
# =========================
def confetti_reward() -> None:
    """Legacy: celebratory effect. Falls back safely."""
    try:
        st.balloons()
    except Exception:
        pass


def show_loot_popup(title: str, msg: str, emoji: str = "🎁") -> None:
    """Legacy: simple 'loot' overlay popup. Safe fallback (no dependencies)."""
    title = (title or "").strip() or "Nagroda!"
    msg = (msg or "").strip()
    # Minimal overlay (works everywhere)
    st.markdown(
        f"""
        <style>
          @keyframes d4k-loot-fade {{
            0%   {{ opacity: 0; }}
            10%  {{ opacity: 1; }}
            85%  {{ opacity: 1; }}
            100% {{ opacity: 0; }}
          }}
        </style>
        <div style="
          position: fixed; inset: 0; z-index: 999999;
          background: rgba(0,0,0,.55);
          display:flex; align-items:center; justify-content:center;
          padding: 18px;
          pointer-events: none;
          animation: d4k-loot-fade 2.8s ease forwards;
        ">
          <div style="
            max-width: 520px; width: 100%;
            border-radius: 18px;
            border: 3px solid rgba(15,23,42,.9);
            box-shadow: 0 14px 40px rgba(0,0,0,.35);
            background: rgba(255,255,255,.92);
            padding: 16px 16px 14px;
            color: #111827;
          ">
            <div style="font-size: 22px; font-weight: 800; margin-bottom: 6px;">{emoji} {title}</div>
            <div style="font-size: 18px; opacity: .9; line-height: 1.3;">{msg}</div>
            <div style="font-size: 14px; opacity: .7; margin-top: 10px;">(zamyka się po chwili)</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def load_lottie(path: str):
    """Legacy: load Lottie JSON from a file path. Returns dict or None. Never raises."""
    import json, os

    try:
        if not path:
            return None
        # allow relative paths
        p = path
        if not os.path.isabs(p):
            base = os.getcwd()
            p = os.path.join(base, p)
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


# =========================
# Navigation (legacy)
# =========================
def top_nav_row(title: str, back_default: str = "Start", show_start: bool = True, show_back: bool = True):
    """Legacy: pasek nawigacji (Wstecz / tytuł / Start). Nie używaj na ekranie Start."""
    import re as _re
    from core.routing import go_back_hard, goto_hard, push_history, set_url_page

    page = str(st.session_state.get("page", ""))
    safe_title = _re.sub(r"[^a-zA-Z0-9_]+", "_", str(title)).strip("_")
    key_base = f"nav_{page}_{safe_title}" if safe_title else f"nav_{page}"

    c1, c2, c3 = st.columns([1.2, 3.6, 1.2])

    with c1:
        if show_back:
            if st.button("⬅️ Wstecz", use_container_width=True, key=f"{key_base}_back"):
                go_back_hard(back_default)

    with c2:
        if title:
            st.markdown(f"<div class='big-title'>{title}</div>", unsafe_allow_html=True)

    with c3:
        if show_start:
            if st.button("🏠 Start", use_container_width=True, key=f"{key_base}_home"):
                goto_hard("Start")
                st.stop()


# =========================
# Design system (new)
# =========================
def notice(text: str, kind: str = "info") -> None:
    """Minecraft-ish notice box (info/warn/ok/danger)."""
    kind = (kind or "info").lower().strip()
    if kind not in {"info", "warn", "ok", "danger"}:
        kind = "info"
    st.markdown(f'<div class="d4k-notice {kind}">{text}</div>', unsafe_allow_html=True)


def pill(text: str) -> None:
    st.markdown(f'<span class="d4k-pill">{text}</span>', unsafe_allow_html=True)


def primary_button(label: str, key: str, *, disabled: bool = False, use_container_width: bool = True) -> bool:
    st.markdown('<div class="d4k-primary">', unsafe_allow_html=True)
    clicked = st.button(label, key=key, disabled=disabled, use_container_width=use_container_width)
    st.markdown("</div>", unsafe_allow_html=True)
    return bool(clicked)


def secondary_button(label: str, key: str, *, disabled: bool = False, use_container_width: bool = True) -> bool:
    st.markdown('<div class="d4k-secondary">', unsafe_allow_html=True)
    clicked = st.button(label, key=key, disabled=disabled, use_container_width=use_container_width)
    st.markdown("</div>", unsafe_allow_html=True)
    return bool(clicked)

def card(
    title: str,
    subtitle: str,
    emoji: str,
    target: str | None,
    *,
    locked: bool = False,
    key: str | None = None,
    color: str | None = None,   # ✅ kompat: start.py używa color=
    on_locked_msg: str = "🔒 Ta opcja jest dostępna po zalogowaniu (zakładka „Dla rodzica”).",
    **_legacy_kwargs,           # ✅ po modulacji: łyka stare argumenty bez crasha
) -> None:
    """Consistent card with guest-lock (click -> toast, no tracebacks)."""

    from core.routing import goto_hard, push_history, set_url_page

    # color na razie nie jest wymagany — trzymamy dla kompatybilności
    _ = color

    st.markdown(
        f"""<div class="d4k-card">
          <div class="d4k-card__title">{emoji} {title}</div>
          <div class="d4k-card__sub">{subtitle}</div>
        </div>""",
        unsafe_allow_html=True,
    )

    label = "🔒 Zablokowane" if locked else "Otwórz ▶"
    clicked = secondary_button(label, key=key or f"card_{target}_{title}")

    if not clicked:
        return

    # Specjalny przypadek: karta typu "Więcej" (target=None)
    if target is None:
        return

    if locked:
        toast(on_locked_msg)
        return

    try:
        push_history(st.session_state.get("page", "Start"))
    except Exception:
        pass
    try:
        set_url_page(target)
    except Exception:
        pass

    goto_hard(target)

