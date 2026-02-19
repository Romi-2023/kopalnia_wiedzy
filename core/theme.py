# core/theme.py
from __future__ import annotations
import streamlit as st


def apply_theme(page: str = "") -> None:
    """Inject global Minecraft-ish theme (tokens + components). Call at top of every page."""
    st.markdown(
        """
        <style>
          @import url('https://fonts.googleapis.com/css2?family=Press+Start+2P&family=Inter:wght@400;600;700&display=swap');

          :root{
            --mc: 'Press Start 2P', system-ui, sans-serif;
            --ui: 'Inter', system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
            /* Paleta marki (spójna z minecraft.css – do ewentualnego użycia w komponentach) */
            --brand-green: #6aa84f;
            --brand-green-dark: #3d6b2f;

            --bg0: #070914;
            --bg1: #0b1020;

            --surface: rgba(255,255,255,.06);
            --surface2: rgba(255,255,255,.10);

            --border: rgba(148,163,184,.28);
            --border2: rgba(148,163,184,.42);

            --text: rgba(255,255,255,.94);
            --muted: rgba(226,232,240,.78);

            --primary1: rgba(168,85,247,.92);
            --primary2: rgba(59,130,246,.78);

            --ok: rgba(34,197,94,.85);
            --warn: rgba(250,204,21,.9);
            --danger: rgba(239,68,68,.85);
          }

          html, body, .stApp{
            background:
              radial-gradient(1200px 700px at 20% 10%, rgba(59,130,246,0.32), transparent 60%),
              radial-gradient(900px 600px at 80% 20%, rgba(168,85,247,0.20), transparent 60%),
              linear-gradient(180deg, #101a33, var(--bg0)) !important;
            color: var(--text);
            font-family: var(--ui);
          }

          /* Usuń górny header + menu */
          header[data-testid="stHeader"]{ visibility: hidden; height: 0; }
          div[data-testid="stToolbar"]{ visibility: hidden; height: 0; }
          #MainMenu { visibility: hidden; }
          footer { visibility: hidden; }

          .block-container{
            padding-top: .65rem !important;
            padding-bottom: 1.2rem !important;
            max-width: 560px !important;
            margin-left: auto !important;
            margin-right: auto !important;
            padding-left: max(1rem, env(safe-area-inset-left)) !important;
            padding-right: max(1rem, env(safe-area-inset-right)) !important;
          }

          /* =====================================================
             Responsywność: telefon, tablet, komputer
          ===================================================== */
          @media (min-width: 640px){
            .block-container{ max-width: 600px !important; }
          }
          @media (min-width: 768px){
            .block-container{ max-width: 720px !important; padding-top: 1rem !important; }
          }
          @media (min-width: 1024px){
            .block-container{ max-width: 800px !important; }
          }
          /* Większe cele dotykowe na urządzeniach dotykowych */
          @media (hover: none) and (pointer: coarse){
            div[data-testid="stButton"] > button{
              min-height: 44px !important;
              padding-top: 10px !important;
              padding-bottom: 10px !important;
            }
            input, select, [role="combobox"]{
              min-height: 44px !important;
            }
          }

          /* =====================================================
             ✅ READABILITY FIX (jasne panele = ciemny tekst)
          ===================================================== */
          .d4k-panel-light,
          .d4k-panel-light *{
            color: #0f172a !important;
            -webkit-text-fill-color: #0f172a !important;
            text-shadow: none !important;
            opacity: 1 !important;
          }
          .d4k-panel-light a{ color: rgba(37,99,235,.95) !important; }

          /* =====================================================
             Buttons (minecraft label + wygląd)
          ===================================================== */
          div[data-testid="stButton"] > button{
            border-radius: 16px !important;
            border: 3px solid rgba(15,23,42,.95) !important;
            box-shadow: 0 10px 0 rgba(15,23,42,.60), 0 18px 40px rgba(0,0,0,.28) !important;
            background: rgba(255,255,255,.92) !important;
          }
          div[data-testid="stButton"] > button,
          div[data-testid="stButton"] > button *{
            font-family: var(--mc) !important;
            letter-spacing: 1.1px !important;
            text-transform: uppercase !important;
            -webkit-font-smoothing: none !important;
            text-rendering: geometricPrecision !important;

            color: #0f172a !important;
            -webkit-text-fill-color: #0f172a !important;
            text-shadow: none !important;
            opacity: 1 !important;
          }

          /* Primary button (gradient) + jasny tekst */
          .d4k-primary div[data-testid="stButton"] > button{
            background: linear-gradient(180deg, var(--primary1), var(--primary2)) !important;
          }
          .d4k-primary div[data-testid="stButton"] > button,
          .d4k-primary div[data-testid="stButton"] > button *{
            color: rgba(255,255,255,.96) !important;
            -webkit-text-fill-color: rgba(255,255,255,.96) !important;
          }

          /* Secondary (jasny) */
          .d4k-secondary div[data-testid="stButton"] > button{
            background: linear-gradient(180deg, rgba(255,255,255,.92), rgba(243,244,246,.92)) !important;
          }

          /* =====================================================
             Avatar / skin (większy)
          ===================================================== */
          .d4k-skin-slot{
            display:flex;
            align-items:center;
            justify-content:center;
            width:220px;   /* jeśli masz inaczej, zostaw swoje */
            height:220px;
            background:
              radial-gradient(circle at 30% 30%, rgba(255,255,255,.10), transparent 45%),
              linear-gradient(180deg, rgba(0,0,0,.08), rgba(0,0,0,.18));
          }

          .d4k-skin-slot img{
            width: 100%;
            height: 100%;
            object-fit: cover;   /* nie ucina, nie rozciąga */
            image-rendering: pixelated;
          }

          /* HERO layout */
          .d4k-hero-row{
            display:flex;
            align-items:center;
            justify-content:space-between;
            gap: 14px;
          }
          .d4k-avatar-wrap{
            width: 100%;
            display:flex;
            justify-content:center;
          }

          /* Avatar frame (rama) — GRUBA i widoczna (mobile-safe) */
          .avatar-frame{
            position: relative;
            padding: 12px;               /* <<< grubość ramki (zamiast border) */
            border-radius: 28px;
            background: rgba(0,0,0,.10);
            box-shadow:
              0 10px 0 rgba(15,23,42,.35),
              0 18px 40px rgba(0,0,0,.20);
            box-sizing: border-box;
            image-rendering: pixelated;
          }

          /* “ring” + separacja od środka */
          .avatar-frame::after{
            content:"";
            position:absolute;
            inset: 6px;                  /* <<< robi wewnętrzny ring */
            border-radius: 22px;
            pointer-events:none;
            box-shadow:
              inset 0 0 0 3px rgba(255,255,255,.14),
              inset 0 -8px 14px rgba(0,0,0,.30);
          }

          /* Avatar core (środek) – stały wygląd niezależnie od levelu */
          .avatar-core{
            border-radius: 18px;
            padding: 8px;
            background: rgba(148,163,184,.18); /* "stone" */
            box-shadow:
              inset 0 0 0 2px rgba(255,255,255,.10),
              inset 0 -8px 12px rgba(0,0,0,.22);
            display:flex;
            align-items:center;
            justify-content:center;
          }

          /* Ramki jakości — tło ramy + wyraźny glow (działa z padding) */
          .frame-wood{
            background: linear-gradient(145deg, #7a5230, #5a3a1e);
            box-shadow:
              0 10px 0 rgba(15,23,42,.35),
              0 0 18px rgba(245,158,11,.22),
              0 18px 40px rgba(0,0,0,.20);
          }

          .frame-stone{
            background: linear-gradient(145deg, #7d7d7d, #4f4f4f);
            box-shadow:
              0 10px 0 rgba(15,23,42,.35),
              0 0 14px rgba(156,163,175,.18),
              0 18px 40px rgba(0,0,0,.20);
          }

          .frame-copper{
            background: linear-gradient(145deg, #c06a2b, #7a3b14);
            box-shadow:
              0 10px 0 rgba(15,23,42,.35),
              0 0 16px rgba(249,115,22,.22),
              0 18px 40px rgba(0,0,0,.20);
          }

          .frame-iron{
            background: linear-gradient(145deg, #d7dbe0, #8b8f94);
            box-shadow:
              0 10px 0 rgba(15,23,42,.35),
              0 0 14px rgba(229,231,235,.20),
              0 18px 40px rgba(0,0,0,.20);
          }

          .frame-gold{
            background: linear-gradient(145deg, #ffd34a, #b68100);
            box-shadow:
              0 10px 0 rgba(15,23,42,.35),
              0 0 18px rgba(250,204,21,.26),
              0 18px 40px rgba(0,0,0,.20);
          }

          .frame-diamond{
            background: linear-gradient(145deg, #4fd1ff, #1b7fa8);
            box-shadow:
              0 10px 0 rgba(15,23,42,.35),
              0 0 22px rgba(34,211,238,.35),
              0 0 36px rgba(34,211,238,.22),
              0 18px 40px rgba(0,0,0,.20);
          }

          .frame-netherite{
            background: linear-gradient(145deg, #2b2b33, #0f0f14);
            box-shadow:
              0 10px 0 rgba(15,23,42,.35),
              0 0 22px rgba(167,139,250,.30),
              0 0 44px rgba(80,0,160,.35),
              0 18px 40px rgba(0,0,0,.25);
          }

          /* =====================================================
             Tabs readability (Dla gracza / Dla rodzica)
          ===================================================== */
          div[data-testid="stTabs"] button{
            color: rgba(226,232,240,.72) !important;
            font-family: var(--mc) !important;
            font-size: 12px !important;
            letter-spacing: .8px !important;
            opacity: 1 !important;
          }
          div[data-testid="stTabs"] button[aria-selected="true"]{
            color: rgba(255,255,255,.96) !important;
          }
          div[data-testid="stTabs"] [data-baseweb="tab-highlight"]{
            background-color: rgba(59,130,246,.85) !important;
            height: 3px !important;
          }

          /* =====================================================
            FORMS READABILITY (Login/Hasło/Tryb + opisy)
          ===================================================== */

          /* Labelki nad inputami (Login, Hasło, Tryb, itp.) */
          .stTextInput label,
          .stTextArea label,
          .stNumberInput label,
          .stSelectbox label,
          .stRadio label,
          .stCheckbox label,
          .stToggle label,
          div[data-testid="stForm"] label{
            color: rgba(241,245,249,.96) !important;   /* prawie biały */
            -webkit-text-fill-color: rgba(241,245,249,.96) !important;
            font-weight: 700 !important;
            opacity: 1 !important;
            text-shadow: 0 1px 0 rgba(0,0,0,.25);
          }

          /* Tekst pomocniczy / opisy pod polami */
          .stTextInput div[data-testid="stMarkdownContainer"] p,
          .stRadio div[data-testid="stMarkdownContainer"] p,
          div[data-testid="stForm"] div[data-testid="stMarkdownContainer"] p{
            color: rgba(226,232,240,.88) !important;
            -webkit-text-fill-color: rgba(226,232,240,.88) !important;
            opacity: 1 !important;
          }

          /* =====================================================
             Pills + notices
          ===================================================== */
          .d4k-pill{
            display:inline-flex;
            align-items:center;
            gap: 8px;
            padding: 8px 12px;
            border-radius: 999px;
            border: 2px solid rgba(15,23,42,.55);
            background: rgba(255,255,255,.92);
            color: #111827;
            box-shadow: 0 6px 0 rgba(15,23,42,.25);
            font-family: var(--ui);
            font-weight: 600;
          }

          .d4k-notice{
            border-radius: 18px;
            padding: 12px 14px;
            border: 2px solid rgba(148,163,184,.28);
            background: rgba(255,255,255,.06);
          }
          .d4k-notice *{ color: var(--text); }
          .d4k-notice.info{ border-color: rgba(59,130,246,.35); }
          .d4k-notice.warn{ border-color: rgba(250,204,21,.45); }
          .d4k-notice.ok{ border-color: rgba(34,197,94,.40); }
          .d4k-notice.danger{ border-color: rgba(239,68,68,.40); }

          /* =====================================================
             Popover body – ogólny kontrast (tło/teksty)
          ===================================================== */
          div[data-testid="stPopoverBody"],
          div[data-testid="stPopoverBody"] *{
            color: rgba(255,255,255,.92) !important;
            -webkit-text-fill-color: rgba(255,255,255,.92) !important;
          }

          /* Alert/info w popoverze: jasny box -> ciemny tekst */
          div[data-testid="stPopoverBody"] div[data-testid="stAlert"]{
            background: rgba(219, 234, 254, .92) !important;
            border: 2px solid rgba(37, 99, 235, .35) !important;
            border-radius: 16px !important;
          }
          div[data-testid="stPopoverBody"] div[data-testid="stAlert"],
          div[data-testid="stPopoverBody"] div[data-testid="stAlert"] *{
            color: #0f172a !important;
            -webkit-text-fill-color: #0f172a !important;
            opacity: 1 !important;
          }

          /* =====================================================
            HARD FIX: Popover trigger button (np. "Ustaw Avatar")
            Streamlit renderuje różnie (BaseWeb), więc łapiemy szerzej.
          ===================================================== */

          /* Tekst ma być czytelny niezależnie od wrapperów */
          div[data-testid="stPopover"] button,
          div[data-testid="stPopover"] button *,
          div[data-testid="stPopover"] [data-baseweb="button"] button,
          div[data-testid="stPopover"] [data-baseweb="button"] button *,
          div[data-testid="stPopover"] [role="button"],
          div[data-testid="stPopover"] [role="button"] *{
            color: #0f172a !important;
            -webkit-text-fill-color: #0f172a !important;
            opacity: 1 !important;
            text-shadow: none !important;
          }

          /* Wygląd triggera */
          div[data-testid="stPopover"] button,
          div[data-testid="stPopover"] [data-baseweb="button"] button,
          div[data-testid="stPopover"] [role="button"]{
            background: rgba(255,255,255,.92) !important;
            border: 3px solid rgba(15,23,42,.95) !important;
            border-radius: 16px !important;
            box-shadow: 0 10px 0 rgba(15,23,42,.60), 0 18px 40px rgba(0,0,0,.28) !important;
            font-family: var(--mc) !important;
            letter-spacing: 1.1px !important;
            text-transform: uppercase !important;
          }

          /* Stan po kliknięciu */
          div[data-testid="stPopover"] button:focus,
          div[data-testid="stPopover"] button:active,
          div[data-testid="stPopover"] [data-baseweb="button"] button:focus,
          div[data-testid="stPopover"] [data-baseweb="button"] button:active,
          div[data-testid="stPopover"] [role="button"]:focus,
          div[data-testid="stPopover"] [role="button"]:active{
            outline: none !important;
            filter: brightness(0.98) !important;
          }

          /* =====================================================
             Card typo + delikatny hover (bez zmiany layoutu)
          ===================================================== */
          .d4k-card{ margin: 8px 0 6px; transition: transform .15s ease, box-shadow .15s ease; }
          .d4k-card:hover{ transform: translateY(-2px); }
          .d4k-card__title{ font-family: var(--mc); font-size: 13px; letter-spacing: .8px; }
          .d4k-card__sub{ font-family: var(--ui); font-size: 14px; opacity: .85; margin-top: 6px; }

          @media (max-width: 520px){
            .d4k-hero-row{
              flex-direction: column;
              justify-content:flex-start;
              text-align: center;
            }
          }

          @media (max-width: 480px){
            .avatar-frame{
              padding: 14px;           /* jeszcze grubsza rama na telefonie */
              border-radius: 30px;
            }
            .avatar-frame::after{
              inset: 7px;
              border-radius: 23px;
            }
            .avatar-core{
              padding: 8px;
            }
          }

          /* Fallback: BaseWeb button w ogóle (żeby nie robić białe-na-białym) */
          button[data-baseweb="button"],
          button[data-baseweb="button"] *{
            -webkit-text-fill-color: inherit;
          }
          /* =====================================================
            Minecraftowy styl: POPover trigger "USTAW AVATAR"
            (ten sam look co CTA)
          ===================================================== */

          /* Sam przycisk */
          div[data-testid="stPopover"] button,
          div[data-testid="stPopover"] [role="button"],
          div[data-testid="stPopover"] [data-baseweb="button"] button{
            font-family: var(--mc) !important;
            font-size: 13px !important;
            letter-spacing: 1.2px !important;
            text-transform: uppercase !important;

            background: rgba(255,255,255,.96) !important;
            color: #0f172a !important;
            -webkit-text-fill-color: #0f172a !important;

            border: 3px solid rgba(15,23,42,.95) !important;
            border-radius: 18px !important;

            box-shadow:
              0 10px 0 rgba(15,23,42,.60),
              0 18px 40px rgba(0,0,0,.28) !important;

            padding: 10px 14px !important;
          }

          /* Tekst + emoji w środku */
          div[data-testid="stPopover"] button *,
          div[data-testid="stPopover"] [role="button"] *,
          div[data-testid="stPopover"] [data-baseweb="button"] button *{
            font-family: var(--mc) !important;
            font-size: 13px !important;
            letter-spacing: 1.2px !important;
            text-transform: uppercase !important;

            color: #0f172a !important;
            -webkit-text-fill-color: #0f172a !important;
            opacity: 1 !important;
          }

          /* Input text + placeholder (czytelność) */
          .stTextInput input,
          .stTextArea textarea,
          .stNumberInput input{
            color: rgba(15,23,42,.96) !important;              /* wpisywany tekst */
            -webkit-text-fill-color: rgba(15,23,42,.96) !important;
          }

          .stTextInput input::placeholder,
          .stTextArea textarea::placeholder,
          .stNumberInput input::placeholder{
            color: rgba(100,116,139,.88) !important;           /* placeholder */
            -webkit-text-fill-color: rgba(100,116,139,.88) !important;
            opacity: 1 !important;
          }

          /* Hover / active – jak w Minecrafcie */
          div[data-testid="stPopover"] button:hover{
            transform: translateY(1px);
            box-shadow:
              0 8px 0 rgba(15,23,42,.60),
              0 14px 30px rgba(0,0,0,.28) !important;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )
