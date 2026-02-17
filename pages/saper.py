from __future__ import annotations

import random
import streamlit as st

from core.state_init import init_core_state, init_router_state, ensure_default_dataset
from core.routing import goto_hard
from core.app_helpers import is_game_unlocked


def _new_board(size: int, mines: int):
    total = size * size
    mines = max(1, min(int(mines), total - 1))
    mine_positions = set(random.sample(range(total), mines))

    board = [[0 for _ in range(size)] for _ in range(size)]
    for idx in mine_positions:
        r = idx // size
        c = idx % size
        board[r][c] = -1

    for r in range(size):
        for c in range(size):
            if board[r][c] == -1:
                continue
            cnt = 0
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    if dr == 0 and dc == 0:
                        continue
                    rr, cc = r + dr, c + dc
                    if 0 <= rr < size and 0 <= cc < size and board[rr][cc] == -1:
                        cnt += 1
            board[r][c] = cnt
    return board


def _reveal_zeroes(board, revealed, start_r, start_c):
    size = len(board)
    stack = [(start_r, start_c)]
    while stack:
        r, c = stack.pop()
        if (r, c) in revealed:
            continue
        revealed.add((r, c))
        if board[r][c] != 0:
            continue
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                rr, cc = r + dr, c + dc
                if 0 <= rr < size and 0 <= cc < size:
                    if (rr, cc) not in revealed:
                        stack.append((rr, cc))


def render() -> None:
    # ✅ multipage-safe bootstrap
    init_core_state()
    init_router_state(initial_page="Saper")
    st.session_state["page"] = "Saper"
    ensure_default_dataset()

    # Znacznik strony – style siatki są w ui/minecraft.css (body:has(#page-saper) …)
    st.markdown('<div id="page-saper" style="display:none!important" aria-hidden="true"></div>', unsafe_allow_html=True)

    # Jedno okno jak w oryginale
    st.markdown("""
    <style>
    div[data-testid="stAppViewContainer"] section.main .block-container {
        max-width: 420px !important;
        min-width: 320px !important;
        margin-left: auto !important;
        margin-right: auto !important;
        padding: 1.25rem !important;
        border: 3px solid #6b6b6b !important;
        border-radius: 12px !important;
        box-shadow: inset 0 0 0 1px #fff, 0 6px 0 #444 !important;
        background: linear-gradient(180deg, #e8e8e8, #d0d0d0) !important;
    }
    </style>
    """, unsafe_allow_html=True)

    st.title("🧨 Gra Saper")
    st.caption("Dostosowana do telefonów: domyślnie mniejsza plansza.")

    if st.button("⬅️ Wróć", use_container_width=True):
        goto_hard("Start")
        st.stop()

    user = st.session_state.get("user")
    if not user or str(user).startswith("Gosc-"):
        st.info("Saper jest dostępny po zalogowaniu i odblokowaniu w Skrzynce.")
        if st.button("📦 Przejdź do Skrzynki", use_container_width=True):
            goto_hard("Skrzynka")
        return

    if not is_game_unlocked("saper"):
        st.warning("🔒 Gra Saper jest zablokowana. Odblokuj ją w Skrzynce.")
        if st.button("📦 Przejdź do Skrzynki", use_container_width=True):
            goto_hard("Skrzynka")
        return

    sizes = {
        "Telefon (6x6)": (6, 6),
        "Standard (8x8)": (8, 10),
        "Duży (10x10)": (10, 15),
    }
    size_label = st.selectbox("Rozmiar planszy", list(sizes.keys()), index=0)
    size, mines = sizes[size_label]

    # init / reset
    if "saper_size" not in st.session_state:
        st.session_state["saper_size"] = size
        st.session_state["saper_mines"] = mines
        st.session_state["saper_board"] = _new_board(size, mines)
        st.session_state["saper_revealed"] = set()
        st.session_state["saper_flagged"] = set()
        st.session_state["saper_over"] = False
        st.session_state["saper_win"] = False

    if st.session_state.get("saper_size") != size:
        st.session_state["saper_size"] = size
        st.session_state["saper_mines"] = mines
        st.session_state["saper_board"] = _new_board(size, mines)
        st.session_state["saper_revealed"] = set()
        st.session_state["saper_flagged"] = set()
        st.session_state["saper_over"] = False
        st.session_state["saper_win"] = False

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔁 Nowa gra", use_container_width=True):
            st.session_state["saper_board"] = _new_board(size, mines)
            st.session_state["saper_revealed"] = set()
            st.session_state["saper_flagged"] = set()
            st.session_state["saper_over"] = False
            st.session_state["saper_win"] = False
            st.rerun()
    with col2:
        flag_mode = st.toggle("🚩 Tryb flagi", value=False)

    board = st.session_state.get("saper_board") or []
    revealed = st.session_state.get("saper_revealed", set())
    flagged = st.session_state.get("saper_flagged", set())
    game_over = bool(st.session_state.get("saper_over", False))

    mines_left = int(mines) - len(flagged)
    st.caption(f"TNT: **{mines}** • 🚩 Pozostało: **{max(0, mines_left)}**")
    if st.session_state.pop("_saper_show_bomb", False):
        st.error("💥 Trafiłeś na TNT!")

    # Plansza: jeden wiersz size×size przycisków – CSS grid wymusza siatkę
    cell_px = 44
    n_cells = size * size
    st.markdown(f"""
    <style>
    /* Jedyny blok z {n_cells} kolumnami = plansza Sapera */
    body:has(#page-saper) [data-testid="stHorizontalBlock"]:has(> div:nth-child({n_cells})) {{
        display: grid !important;
        grid-template-columns: repeat({size}, {cell_px}px) !important;
        gap: 3px !important;
        width: fit-content !important;
        margin: 0 auto !important;
    }}
    body:has(#page-saper) [data-testid="stHorizontalBlock"]:has(> div:nth-child({n_cells})) [data-testid="column"] {{
        flex: none !important;
        min-width: {cell_px}px !important;
        max-width: {cell_px}px !important;
    }}
    body:has(#page-saper) [data-testid="stHorizontalBlock"]:has(> div:nth-child({n_cells})) button {{
        width: 100% !important;
        height: {cell_px - 4}px !important;
        min-height: {cell_px - 4}px !important;
        padding: 0 !important;
        font-size: 0.9rem !important;
    }}
    </style>
    """, unsafe_allow_html=True)

    cols = st.columns(n_cells)
    for idx in range(n_cells):
        r, c = idx // size, idx % size
        key = f"saper_{r}_{c}"
        label = "⬜"
        if (r, c) in revealed:
            val = board[r][c]
            label = "🧨" if val == -1 else (str(val) if val > 0 else " ")
        elif (r, c) in flagged:
            label = "🚩"
        with cols[idx]:
            if st.button(label, key=key, use_container_width=True):
                if game_over:
                    pass
                elif flag_mode and (r, c) not in revealed:
                    if (r, c) in flagged:
                        flagged.remove((r, c))
                    else:
                        flagged.add((r, c))
                    st.session_state["saper_flagged"] = flagged
                    st.rerun()
                elif (r, c) not in flagged and (r, c) not in revealed:
                    if board[r][c] == -1:
                        st.session_state["saper_over"] = True
                        st.session_state["_saper_show_bomb"] = True
                        for rr in range(size):
                            for cc in range(size):
                                if board[rr][cc] == -1:
                                    revealed.add((rr, cc))
                        st.session_state["saper_revealed"] = revealed
                        st.rerun()
                    _reveal_zeroes(board, revealed, r, c)
                    st.session_state["saper_revealed"] = revealed
                    total_safe = size * size - mines
                    if len(revealed) >= total_safe:
                        st.session_state["saper_over"] = True
                        st.session_state["saper_win"] = True
                    st.rerun()

    if st.session_state.get("saper_win"):
        st.success("✅ Gratulacje! Wszystkie bezpieczne pola odkryte.")


# Multipage (st.switch_page): uruchom render() także przy wejściu bez routera
try:
    render()
except Exception:
    pass
