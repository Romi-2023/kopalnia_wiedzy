# pages/intro.py
# pyright: reportUndefinedVariable=false

from __future__ import annotations

import os
import json
import base64
import streamlit as st
import time as _time
import streamlit.components.v1 as components

from core.state_init import init_core_state, init_router_state, ensure_default_dataset

from core.ui import safe_rerun
from core.routing import goto
from core.config import ASSETS_DIR


INTRO_ASSETS_DIR = os.path.join(ASSETS_DIR, "intro")   # png, tło, itp.
LOTTIE_DIR = os.path.join(ASSETS_DIR, "lottie")        # wszystkie *.json lottie


# =====================================================
# Helpers
# =====================================================
def load_lottie(path: str) -> dict | None:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _bytes_to_b64(data: bytes) -> str:
    return base64.b64encode(data).decode("utf-8")


def _render_lottie_html(anim: dict | None, height: int, element_id: str) -> None:
    """
    Render Lottie przez lottie-web (transparent).
    Efekt jak w "dobrym" nagraniu: bez białego prostokąta.
    """
    if not anim:
        return

    anim_json = json.dumps(anim)

    html = f"""
    <style>
      html, body {{
        margin: 0;
        padding: 0;
        background: transparent !important;
      }}
      #{element_id} {{
        width: 100%;
        height: {height}px;
        background: transparent !important;
      }}
    </style>

    <div id="{element_id}"></div>

    <script src="https://cdnjs.cloudflare.com/ajax/libs/bodymovin/5.12.2/lottie.min.js"></script>
    <script>
      const animData = {anim_json};

      lottie.loadAnimation({{
        container: document.getElementById("{element_id}"),
        renderer: "svg",
        loop: false,
        autoplay: true,
        animationData: animData,
        rendererSettings: {{
          preserveAspectRatio: "xMidYMid meet",
          clearCanvas: true
        }}
      }});
    </script>
    """
    components.html(html, height=height, scrolling=False)


def _file_exists(path: str) -> bool:
    try:
        return os.path.isfile(path)
    except Exception:
        return False


# =====================================================
# RENDER
# =====================================================
def render():
    """Intro v2:
    - Kilof pulsuje od razu
    - Przycisk aktywny od razu
    - Po kliknięciu: ożywa portal (tylko wnętrze), 3s “magii”, potem Start
    """

    # ✅ multipage-safe bootstrap (gdy ktoś wejdzie bezpośrednio na /intro)
    init_core_state()
    init_router_state(initial_page="Intro")
    st.session_state["page"] = "Intro"
    ensure_default_dataset()

    # Jeśli intro już było zakończone w tej sesji, przeskocz od razu na Start
    if st.session_state.get("intro_done"):
        try:
            st.switch_page("pages/start.py")
        except Exception:
            goto("Start")
        st.stop()

    # Paths
    PORTAL_IMG = os.path.join(ASSETS_DIR, "portal.png")
    pickaxe_path = os.path.join(INTRO_ASSETS_DIR, "pickaxe.png")
    portal_fx_path = os.path.join(INTRO_ASSETS_DIR, "portal_fx.gif")

    # base64: pickaxe + portal + fx
    pickaxe_b64 = ""
    portal_b64 = ""
    portal_fx_b64 = ""
    try:
        with open(pickaxe_path, "rb") as f:
            pickaxe_b64 = _bytes_to_b64(f.read())
    except Exception:
        pickaxe_b64 = ""

    try:
        with open(PORTAL_IMG, "rb") as f:
            portal_b64 = _bytes_to_b64(f.read())
    except Exception:
        portal_b64 = ""

    try:
        with open(portal_fx_path, "rb") as f:
            portal_fx_b64 = _bytes_to_b64(f.read())
    except Exception:
        portal_fx_b64 = ""

    # State: entering
    st.session_state.setdefault("intro_entering", False)
    st.session_state.setdefault("intro_enter_ts", 0.0)

    entering = bool(st.session_state.get("intro_entering"))
    enter_ts = float(st.session_state.get("intro_enter_ts") or 0.0)
    elapsed = (_time.time() - enter_ts) if entering else 0.0

    ENTER_SEC = 3.0

    # CSS
    st.markdown(
        """
        <style>
          @import url('https://fonts.googleapis.com/css2?family=Press+Start+2P&display=swap');
          :root { --mc: 'Press Start 2P', system-ui, sans-serif; }

          html, body, .stApp {
            height: 100%;
            background:
              radial-gradient(1200px 700px at 20% 10%, rgba(59,130,246,0.25), transparent 60%),
              radial-gradient(900px 600px at 80% 20%, rgba(168,85,247,0.20), transparent 60%),
              linear-gradient(180deg, #0b1020, #050814) !important;
          }

          .block-container {
            padding-top: 0.75rem !important;
            padding-bottom: 1.25rem !important;
            max-width: 520px !important;
          }

          .d4k-title{
            font-family: var(--mc);
            font-size: 46px;
            letter-spacing: 1.6px;
            color: #e5e7eb;
            text-align: center;
            margin-top: 24px;
            margin-bottom: 12px;
            line-height: 1.02;
            text-shadow: 0 3px 0 rgba(0,0,0,.55), 0 0 16px rgba(59,130,246,.18);
          }

          .d4k-sub{
            font-family: var(--mc);
            font-size: 10px;
            color: rgba(203,213,225,.92);
            text-align: center;
            margin-bottom: 14px;
            line-height: 1.55;
          }

          .d4k-hint{
            font-family: var(--mc);
            font-size: 13px;
            color: rgba(229,231,235,.98);
            text-align: center;
            line-height: 1.75;
            margin-top: 14px;   /* odstęp od portalu */
            margin-bottom: 18px;/* odstęp do przycisku */
            text-shadow: 0 2px 0 rgba(0,0,0,.65);
          }

          .d4k-center{
            display:flex;
            flex-direction:column;
            align-items:center;
            gap: 12px;
          }

          /* ⛏️ kilof — pulsuje zawsze (opcja 2) */
          .d4k-pickaxe{
            display:flex;
            justify-content:center;
            align-items:center;
            margin: 4px 0 10px 0;
          }

          .d4k-pickaxe img{
            width: min(160px, 52vw);
            image-rendering: pixelated;
            transform-origin: 50% 55%;
            transform: none;
            animation: d4k-pulse 1.6s ease-in-out infinite;
          }

          @keyframes d4k-pulse{
            0%{ transform: scale(1.00); filter: drop-shadow(0 0 0 rgba(255,255,255,0)); }
            50%{ transform: scale(1.06); filter: drop-shadow(0 10px 18px rgba(0,0,0,.35)); }
            100%{ transform: scale(1.00); filter: drop-shadow(0 0 0 rgba(255,255,255,0)); }
          }

          /* 🌀 PORTAL */
          .portal-wrap{
            width: min(420px, 92vw);
            border-radius: 18px;
            overflow: hidden;
            position: relative;
            box-shadow: 0 18px 40px rgba(0,0,0,.35);
            border: 3px solid rgba(17,24,39,.65);
          }
          .portal-wrap img{
            width: 100%;
            display:block;
          }

          /* To jest “żółty obszar” – maska tylko na wnętrze portalu */
          .portal-core{
            position:absolute;
            left: 30%;
            top: 29%;
            width: 42%;
            height: 53%;
            border-radius: 10px;
            pointer-events:none;
            overflow:hidden;

            /* FIX: twarde przycięcie nawet przy blur */
            clip-path: inset(0 round 10px);
            isolation: isolate;
            transform: translateZ(0);
          }

          
/* warstwa FX (GIF / tekstura) - zawsze przycięta do portal-core */
.portal-fx{
  position:absolute;
  inset:0;
  background-size: 100% 100%;   /* <— dopasowanie do wnętrza */
  background-position: center;
  background-repeat: no-repeat;
  image-rendering: pixelated;  /* <— minecraftowy vibe */
  opacity: 0;
  transform: scale(0.98);
  filter: brightness(1.05) contrast(1.05) saturate(1.25);
  mix-blend-mode: screen;
}

/* delikatna winieta: “głębia” w portalu */
.portal-vignette{
  position:absolute;
  inset:0;
  box-shadow: inset 0 0 26px rgba(0,0,0,.45);
  opacity: 0;
}

/* aktywacja po kliknięciu */
.portal-wrap.entering .portal-fx{
  animation: fx-in 0.35s ease-out forwards, fx-wobble 0.9s ease-in-out infinite;
}
.portal-wrap.entering .portal-vignette{
  animation: vignette-in 0.35s ease-out forwards;
}

@keyframes fx-in{
  from { opacity: 0; transform: scale(0.98); }
  to   { opacity: 1; transform: scale(1.02); }
}
@keyframes fx-wobble{
  0%   { transform: scale(1.02) rotate(0deg); }
  50%  { transform: scale(1.05) rotate(0.6deg); }
  100% { transform: scale(1.02) rotate(0deg); }
}
@keyframes vignette-in{
  from { opacity: 0; }
  to   { opacity: 1; }
}

          
/* przycisk */

.cta-wrap{
  width: 100% !important;
  display: flex !important;
  justify-content: center !important;   /* ⬅️ środek w poziomie */
  align-items: center !important;

  /* ważne przy .d4k-center (flex-column + align-items:center) */
  align-self: stretch !important;

  /* bezpieczniki na różne przeglądarki / streamlit */
  margin-left: auto !important;
  margin-right: auto !important;
  text-align: center !important;
}

.cta-wrap div.stButton{
  width: 100% !important;
  display: flex !important;
  justify-content: center !important;
}

/* przycisk tylko w tym wrapperze */
.cta-wrap div.stButton > button{
            display: block !important;
            margin-left: auto !important;
            margin-right: auto !important;

            width: min(420px, 92%) !important;
            min-height: 52px !important;
            padding: 12px 16px !important;
            border-radius: 16px !important;

            font-family: var(--mc) !important;
            font-size: 13px !important;
            letter-spacing: 0.6px;

            color: rgba(255,255,255,.95) !important;
            background: linear-gradient(
              180deg,
              rgba(168,85,247,.92),
              rgba(59,130,246,.78)
            ) !important;

            border: 3px solid rgba(15,23,42,.95) !important;
            box-shadow:
              0 10px 0 rgba(15,23,42,.65),
              0 18px 40px rgba(0,0,0,.35) !important;
          }

          .cta-wrap div.stButton > button:hover{
            filter: brightness(1.05) saturate(1.1);
          }

          .cta-wrap div.stButton > button:active{
            transform: translateY(5px);
            box-shadow: 0 5px 0 rgba(15,23,42,.65), 0 14px 30px rgba(0,0,0,.30) !important;
          }

          

/* minecraftowy tekst w przyciskach (Streamlit potrafi oddzielić wrapper od buttona) */
div[data-testid="stButton"] > button,
div[data-testid="stButton"] > button *{
  font-family: var(--mc) !important;
  letter-spacing: 1.2px !important;
  text-transform: uppercase !important;
  -webkit-font-smoothing: none !important;
  text-rendering: geometricPrecision !important;
  text-shadow: 0 2px 0 rgba(0,0,0,.65) !important;
}

.enter-note{
            font-family: var(--mc);
            font-size: 10px;
            color: rgba(229,231,235,.92);
            text-align:center;
            margin-top: -4px;
          }


          @media (prefers-reduced-motion: reduce){
            .portal-wrap.entering .portal-fx,
            .d4k-pickaxe img{
              animation: none !important;
            }
          }

          @media (max-width: 420px){
            .d4k-title{ font-size: 34px; letter-spacing: 1px; }
            .d4k-hint{ font-size: 11px; }
          }

          /* komponent HTML (lottie-web) bez tła */
          div[data-testid="stHtml"] { background: transparent !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # UI
    st.markdown('<div class="d4k-center">', unsafe_allow_html=True)

    st.markdown('<div class="d4k-title">KOPALNIA<br/>WIEDZY</div>', unsafe_allow_html=True)

    if pickaxe_b64:
        st.markdown(
            f'<div class="d4k-pickaxe"><img src="data:image/png;base64,{pickaxe_b64}"></div>',
            unsafe_allow_html=True,
        )

    # Portal render (z klasą entering gdy kliknięte)
    portal_class = "portal-wrap entering" if entering else "portal-wrap"

    fx_bg = (
        f"url('data:image/gif;base64,{portal_fx_b64}')" if portal_fx_b64 else
        "radial-gradient(circle at 30% 30%, rgba(255,255,255,.20), transparent 55%),"
        "radial-gradient(circle at 70% 60%, rgba(168,85,247,.35), transparent 60%),"
        "radial-gradient(circle at 50% 80%, rgba(59,130,246,.25), transparent 65%)"
    )

    if portal_b64:
        st.markdown(
            f"""
            <div class="{portal_class}">
              <img src="data:image/png;base64,{portal_b64}" />
              <div class="portal-core">
                <div class="portal-fx" style="background-image: {fx_bg};"></div>
                <div class="portal-vignette"></div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        '<div class="d4k-hint">Portal otwarty, bez Creeperów… chyba.<br/>Wchodzisz? 🙂</div>',
        unsafe_allow_html=True,
    )
    # BUTTON: aktywny od razu, ale blokuje się po kliknięciu
    btn_label = "⛏️ ENTER THE PORTAL" if not entering else "🌀 WCHODZĘ..."

    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        clicked = st.button(
            btn_label,
            key="enter_portal_btn_v2",
            disabled=entering,
            use_container_width=True
        )

    if clicked and (not entering):
        st.session_state["intro_entering"] = True
        st.session_state["intro_enter_ts"] = _time.time()
        safe_rerun()

    # Po kliknięciu: 3 sek magii i przejście
    if entering:
        st.markdown('<div class="enter-note">Nie mrugaj… bo ci UI ucieknie do Netheru.</div>', unsafe_allow_html=True)

        if elapsed >= ENTER_SEC:
            st.session_state["intro_done"] = True
            st.session_state["intro_entering"] = False
            st.session_state["intro_enter_ts"] = 0.0

            try:
                st.switch_page("pages/start.py")
                st.stop()
            except Exception:
                goto("Start")
                st.stop()
        # animacja “w czasie” – odświeżamy płynnie
        _time.sleep(0.12)
        safe_rerun()

    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()



# Multipage (st.switch_page): uruchom render() także przy wejściu bez routera
try:
    render()
except Exception as e:
    try:
        from core.ui import show_exception
        show_exception(e)
    except Exception:
        pass
