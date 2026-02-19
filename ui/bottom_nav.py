import streamlit as st
from urllib.parse import quote
from typing import Optional, Set

def bottom_nav(valid_pages: Optional[Set[str]] = None):
    """
    Fixed bottom-nav jako HTML (bez iframe).
    - Active state
    - Safe-area
    - "Więcej" jako overlay (sheet) – app vibe
    - Padding-bottom, żeby nie przykrywało treści
    """
    user = st.session_state.get("user")
    is_guest = isinstance(user, str) and user.startswith("Gosc-")

    guest_q = ""
    if is_guest:
        guest_q = "&g=" + quote(user)

    active = str(st.session_state.get("page", "Start"))

    def href(page: str) -> str:
        return f"?p={quote(page)}{guest_q}"

    # Jeśli podasz valid_pages, to przytnij linki tylko do istniejących stron
    def ok(page: str) -> bool:
        return True if not valid_pages else page in valid_pages

    main_items = [
        ("Start", "home", "Start"),
        ("Misje", "explore", "Misje"),
        ("Quiz danych", "query_stats", "Quiz"),
        ("Skrzynka", "inventory_2", "Skrzynka"),
    ]

    more_items = []

    # odfiltruj wszystko czego nie ma w VALID_PAGES (jeśli podane)
    main_items = [it for it in main_items if ok(it[0])]
    more_items = [it for it in more_items if ok(it[0])]

    def btn(item):
        page, icon, label = item
        is_active = (page == active)
        a = "is-active" if is_active else ""
        return f"""
<a class="d4k-navbtn {a}" href="{href(page)}" target="_top" rel="noopener">
  <span class="material-symbols-outlined d4k-ico">{icon}</span>
  <span class="d4k-lbl">{label}</span>
</a>
"""

    more_grid = "\n".join([
        f"""
<a class="d4k-moreitem" href="{href(p)}" target="_top" rel="noopener">
  <span class="material-symbols-outlined d4k-ico">{ic}</span>
  <span class="d4k-lbl">{lbl}</span>
</a>
""" for (p, ic, lbl) in more_items
    ])

    html = f"""
<style>
.d4k-bottomnav-wrapper {{
  position: fixed;
  left: 0; right: 0; bottom: 0;
  z-index: 200;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  box-sizing: border-box;
}}

.d4k-bottomnav {{
  padding: 10px 10px 6px;
  background: rgba(255,255,255,0.92);
  border-top: 1px solid rgba(17,24,39,0.22);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  display: flex;
  gap: 10px;
  align-items: center;
  justify-content: space-between;
  box-sizing: border-box;
  font-family: 'VT323', monospace;
}}

body.page-memory .d4k-bottomnav {{
  backdrop-filter: none !important;
  -webkit-backdrop-filter: none !important;
}}

/* Zawsze zostaw miejsce pod bottom-nav (różne DOM-y Streamlit) + safe-area na telefonach */
.block-container,
section.main .block-container,
div[data-testid="stAppViewContainer"] .main .block-container{{
  padding-bottom: calc(150px + env(safe-area-inset-bottom)) !important;
  padding-top: max(.65rem, env(safe-area-inset-top)) !important;
}}

.d4k-navbtn {{
  flex: 1;
  text-decoration: none !important;
  color: #111827;
  border-radius: 18px;
  padding: 12px 8px;
  min-height: 48px;
  display: grid;
  place-items: center;
  gap: 2px;
  border: 1px solid rgba(17,24,39,0.10);
  background: rgba(249,250,251,0.75);
  box-shadow: 0 1px 0 rgba(0,0,0,0.05);
  user-select: none;
  -webkit-tap-highlight-color: transparent;
}}

.d4k-navbtn:active {{
  transform: translateY(1px);
}}

.d4k-navbtn.is-active {{
  background: rgba(17,24,39,0.08);
  border-color: rgba(17,24,39,0.22);
}}

.d4k-ico {{
  font-size: 22px;
  line-height: 22px;
}}

.d4k-lbl {{
  font-size: 16px;
  line-height: 16px;
}}

.d4k-more {{
  width: 54px;
  min-width: 54px;
}}

.d4k-morebtn {{
  width: 54px;
  height: 54px;
  border-radius: 18px;
  display: grid;
  place-items: center;
  border: 1px solid rgba(17,24,39,0.10);
  background: rgba(249,250,251,0.75);
  box-shadow: 0 1px 0 rgba(0,0,0,0.05);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}}

.d4k-morebtn:active {{ transform: translateY(1px); }}

.d4k-sheet {{
  position: fixed;
  left: 0; right: 0; bottom: 0;
  transform: translateY(110%);
  transition: transform .18s ease;
  z-index: 199;
  padding: 12px 12px calc(18px + env(safe-area-inset-bottom));
  background: rgba(255,255,255,0.96);
  border-top-left-radius: 22px;
  border-top-right-radius: 22px;
  border: 1px solid rgba(17,24,39,0.18);
  box-shadow: 0 -12px 40px rgba(0,0,0,0.18);
}}

.d4k-sheet.open {{
  transform: translateY(0%);
}}

.d4k-sheet-head {{
  display:flex;
  align-items:center;
  justify-content: space-between;
  margin-bottom: 10px;
}}

.d4k-sheet-title {{
  font-size: 22px;
  color: #111827;
}}

.d4k-sheet-close {{
  border: 0;
  background: transparent;
  font-size: 22px;
  cursor: pointer;
}}

.d4k-grid {{
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}}

.d4k-moreitem {{
  text-decoration: none !important;
  color: #111827;
  border-radius: 16px;
  padding: 12px 10px;
  display: grid;
  place-items: center;
  gap: 4px;
  border: 1px solid rgba(17,24,39,0.10);
  background: rgba(249,250,251,0.75);
}}

.d4k-backdrop {{
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.22);
  opacity: 0;
  pointer-events: none;
  transition: opacity .18s ease;
  z-index: 198;
}}

.d4k-backdrop.open {{
  opacity: 1;
  pointer-events: auto;
}}
</style>

<div class="d4k-backdrop" id="d4kBackdrop"></div>

<div class="d4k-sheet" id="d4kSheet" aria-hidden="true">
  <div class="d4k-sheet-head">
    <div class="d4k-sheet-title">Więcej</div>
    <button class="d4k-sheet-close" id="d4kSheetClose" aria-label="Zamknij">✕</button>
  </div>
  <div class="d4k-grid">
    {more_grid}
  </div>
</div>

<div class="d4k-bottomnav-wrapper">
  <nav class="d4k-bottomnav" role="navigation" aria-label="Nawigacja">
    {btn(main_items[0]) if len(main_items)>0 else ""}
    {btn(main_items[1]) if len(main_items)>1 else ""}
    {btn(main_items[2]) if len(main_items)>2 else ""}
    {btn(main_items[3]) if len(main_items)>3 else ""}

    <div class="d4k-more">
      <button class="d4k-morebtn" id="d4kMoreBtn" aria-label="Więcej">
        <span class="material-symbols-outlined d4k-ico">apps</span>
      </button>
    </div>
  </nav>
</div>

<script>
(function(){{
  const sheet = document.getElementById("d4kSheet");
  const bd = document.getElementById("d4kBackdrop");
  const btn = document.getElementById("d4kMoreBtn");
  const close = document.getElementById("d4kSheetClose");

  function openSheet(){{
    sheet.classList.add("open");
    bd.classList.add("open");
    sheet.setAttribute("aria-hidden", "false");
  }}
  function closeSheet(){{
    sheet.classList.remove("open");
    bd.classList.remove("open");
    sheet.setAttribute("aria-hidden", "true");
  }}

  if(btn) btn.addEventListener("click", (e)=>{{ e.preventDefault(); openSheet(); }});
  if(close) close.addEventListener("click", (e)=>{{ e.preventDefault(); closeSheet(); }});
  if(bd) bd.addEventListener("click", closeSheet);

  document.addEventListener("keydown", (e)=>{{
    if(e.key === "Escape") closeSheet();
  }});
}})();
</script>
"""
    st.markdown(html, unsafe_allow_html=True)
