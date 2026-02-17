# pages/nadzor.py – Panel nadzoru: wejście po kodzie z Authenticatora, statystyki, lista użytkowników, usuwanie kont
from __future__ import annotations

import io
import random
import time
from collections import Counter
from datetime import datetime, timedelta

import streamlit as st

from core.theme import apply_theme
from core.persistence import _load_users, delete_user, load_contest_participants, load_guest_signups
from core.routing import goto
from core.admin_auth import (
    get_totp_secret,
    set_totp_secret,
    generate_totp_secret,
    get_provisioning_uri,
    verify_totp,
    is_admin_session_valid,
    set_admin_session_valid,
    clear_admin_session,
)

apply_theme()

st.set_page_config(page_title="Panel nadzoru", layout="centered", initial_sidebar_state="collapsed")

# Czytelność tekstu na ciemnym tle – nadpisanie stylów dla Panelu nadzoru
st.markdown("""
<style>
/* Metryki – jasny, czytelny tekst */
[data-testid="stMetric"] label,
[data-testid="stMetric"] div,
[data-testid="stMetricValue"],
[data-testid="stMetricDelta"] {
    color: rgba(255,255,255,.96) !important;
    -webkit-text-fill-color: rgba(255,255,255,.96) !important;
    opacity: 1 !important;
    text-shadow: 0 1px 2px rgba(0,0,0,.4);
}

/* Nagłówki, podpisy, markdown */
.stMarkdown p, .stMarkdown strong, .stCaption,
h1, h2, h3, .stSubheader {
    color: rgba(255,255,255,.96) !important;
    -webkit-text-fill-color: rgba(255,255,255,.96) !important;
    opacity: 1 !important;
    text-shadow: 0 1px 2px rgba(0,0,0,.4);
}

/* Inputy i etykiety */
.stTextInput label, .stTextInput input,
.stButton label {
    color: rgba(255,255,255,.96) !important;
    -webkit-text-fill-color: rgba(255,255,255,.96) !important;
}

/* Expandery (lista kont) */
[data-testid="stExpander"] summary,
[data-testid="stExpander"] p, [data-testid="stExpander"] span {
    color: rgba(255,255,255,.96) !important;
    -webkit-text-fill-color: rgba(255,255,255,.96) !important;
    opacity: 1 !important;
}
</style>
""", unsafe_allow_html=True)

# Sekret TOTP: najpierw konfiguracja (generacja + QR), potem logowanie
def _ensure_totp_secret():
    secret = get_totp_secret()
    if secret:
        return secret
    try:
        secret = generate_totp_secret()
        set_totp_secret(secret)
        return secret
    except Exception as e:
        st.error(f"Błąd generacji sekretu TOTP: {e}. Zainstaluj: pip install pyotp")
        return None


def _show_setup_or_login():
    secret = get_totp_secret()
    if not secret:
        if st.button("Wygeneruj sekret i pokaż QR (jednorazowo)"):
            new_secret = _ensure_totp_secret()
            if new_secret:
                st.session_state["_nadzor_show_qr"] = True
                st.rerun()
        if st.session_state.get("_nadzor_show_qr"):
            new_secret = get_totp_secret()
            if new_secret:
                uri = get_provisioning_uri()
                try:
                    import qrcode
                    img = qrcode.make(uri)
                    buf = io.BytesIO()
                    img.save(buf, format="PNG")
                    buf.seek(0)
                    st.image(buf, caption="Zeskanuj w aplikacji Authenticator (Google Authenticator itp.)")
                except Exception:
                    st.code(new_secret, language="text")
                    st.caption("Dodaj ten sekret ręcznie w Authenticatorze jako TOTP.")
                st.info("Po dodaniu wpisu w Authenticatorze wpisz poniżej 6-cyfrowy kod i zatwierdź.")
        return False

    # Opcjonalnie pokaż QR (np. tuż po pierwszej generacji)
    if st.session_state.get("_nadzor_show_qr") and secret:
        uri = get_provisioning_uri()
        if uri:
            try:
                import qrcode
                img = qrcode.make(uri)
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                buf.seek(0)
                st.image(buf, caption="Zeskanuj w Authenticatorze")
            except Exception:
                pass
        st.session_state.pop("_nadzor_show_qr", None)

    if st.button("← Wstecz", key="nadzor_back_btn"):
        try:
            st.switch_page("pages/start.py")  # powrót na /start bez dolnego menu
        except Exception:
            goto("Start")
        return

    st.subheader("Logowanie do panelu nadzoru")
    code = st.text_input("Kod z Authenticatora (6 cyfr)", max_chars=6, type="default", key="nadzor_totp_code")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Zaloguj"):
            if verify_totp(code):
                set_admin_session_valid()
                st.rerun()
            else:
                st.error("Nieprawidłowy kod. Sprawdź czas w telefonie i spróbuj ponownie.")
    with col2:
        if st.button("Anuluj"):
            st.session_state.pop("nadzor_totp_code", None)
            st.rerun()
    return False


def _parse_created(created: str | None) -> datetime | None:
    """Parsuje created_at (ISO string) do datetime (naive UTC), zwraca None przy błędzie."""
    if not created:
        return None
    try:
        s = str(created).strip().replace("Z", "").replace("+00:00", "")[:19]
        return datetime.fromisoformat(s)
    except Exception:
        return None


def _compute_stats(users: list) -> dict:
    """Oblicza statystyki z listy (login, profile)."""
    total_xp = 0
    total_gems = 0
    age_counts: Counter = Counter()
    subject_counts: Counter = Counter()
    badge_counts: Counter = Counter()
    sticker_counts: Counter = Counter()
    total_tasks = 0
    users_with_tasks = 0
    users_with_streak = 0
    max_streak = 0
    users_with_class = 0

    now_utc = datetime.utcnow()
    week_ago = now_utc - timedelta(days=7)
    month_ago = now_utc - timedelta(days=30)
    year_ago = now_utc - timedelta(days=365)
    registrations_week = 0
    registrations_month = 0
    registrations_year = 0

    for login, profile in users:
        p = profile or {}
        total_xp += int(p.get("xp") or 0)
        total_gems += int(p.get("gems") or 0)

        ag = p.get("age_group") or p.get("age")
        if ag:
            ag_str = str(ag) if ag in ("7-9", "10-12", "13-14") else str(ag)
            age_counts[ag_str] += 1

        badges = p.get("badges") or []
        stickers = p.get("stickers") or []
        if isinstance(badges, list):
            for b in badges:
                badge_counts[str(b)] += 1
        elif isinstance(badges, set):
            for b in badges:
                badge_counts[str(b)] += 1
        if isinstance(stickers, list):
            for s in stickers:
                sticker_counts[str(s)] += 1
        elif isinstance(stickers, set):
            for s in stickers:
                sticker_counts[str(s)] += 1

        st_data = p.get("school_tasks") or {}
        user_tasks = 0
        for day_data in st_data.values():
            if isinstance(day_data, dict):
                for subj, ids in day_data.items():
                    subject_counts[subj] += len(ids) if isinstance(ids, list) else 1
                    user_tasks += len(ids) if isinstance(ids, list) else 1
        total_tasks += user_tasks
        if user_tasks > 0:
            users_with_tasks += 1

        streak = int(p.get("streak") or p.get("retention", {}).get("streak", 0) or 0)
        if streak > 0:
            users_with_streak += 1
            max_streak = max(max_streak, streak)

        if p.get("class_code"):
            users_with_class += 1

        created_dt = _parse_created(p.get("created_at"))
        if created_dt:
            if created_dt >= week_ago:
                registrations_week += 1
            if created_dt >= month_ago:
                registrations_month += 1
            if created_dt >= year_ago:
                registrations_year += 1

    # Uwzględnij gości (Gosc-*) w statystykach „nowe konta” – są kasowani codziennie, liczba jest w guest_signups
    try:
        guest_signups = load_guest_signups() or {}
        week_ago_d = week_ago.date() if hasattr(week_ago, "date") else week_ago
        month_ago_d = month_ago.date() if hasattr(month_ago, "date") else month_ago
        year_ago_d = year_ago.date() if hasattr(year_ago, "date") else year_ago
        for date_str, count in guest_signups.items():
            if not date_str or not isinstance(count, (int, float)):
                continue
            try:
                dt = datetime.strptime(str(date_str)[:10], "%Y-%m-%d")
                d = dt.date() if hasattr(dt, "date") else dt
                c = int(count)
                if d >= week_ago_d:
                    registrations_week += c
                if d >= month_ago_d:
                    registrations_month += c
                if d >= year_ago_d:
                    registrations_year += c
            except Exception:
                pass
    except Exception:
        pass

    n = len(users)
    return {
        "users": n,
        "total_xp": total_xp,
        "total_gems": total_gems,
        "avg_xp": total_xp // n if n else 0,
        "avg_gems": total_gems // n if n else 0,
        "age_counts": dict(age_counts),
        "subject_counts": dict(subject_counts.most_common(10)),
        "badge_counts": dict(badge_counts.most_common(10)),
        "sticker_counts": dict(sticker_counts.most_common(10)),
        "total_badges": sum(badge_counts.values()),
        "total_stickers": sum(sticker_counts.values()),
        "total_tasks": total_tasks,
        "users_with_tasks": users_with_tasks,
        "users_with_streak": users_with_streak,
        "max_streak": max_streak,
        "users_with_class": users_with_class,
        "registrations_week": registrations_week,
        "registrations_month": registrations_month,
        "registrations_year": registrations_year,
    }


def _show_panel():
    now = time.time()
    if not is_admin_session_valid(now):
        return _show_setup_or_login()

    if st.button("← Wstecz", key="nadzor_panel_back_btn"):
        try:
            st.switch_page("pages/start.py")  # powrót na /start bez dolnego menu
        except Exception:
            goto("Start")
        return

    st.subheader("Panel nadzoru")
    if st.button("Wyloguj z panelu"):
        clear_admin_session()
        st.rerun()

    db = _load_users() or {}
    # Tylko zwykłe konta (bez _* i bez Gosc-* – goście są kasowani codziennie i ujmowani w statystykach „nowe konta”)
    users = [(k, v) for k, v in db.items() if not k.startswith("_") and not (isinstance(k, str) and k.startswith("Gosc-"))]
    users.sort(key=lambda x: (x[0].lower(), x[0]))

    if not users:
        st.info("Brak zarejestrowanych użytkowników. Statystyki, losowanie i lista będą dostępne po rejestracji pierwszych kont.")

    stats = _compute_stats(users)

    st.markdown("---")
    st.markdown("### 📊 Statystyki aplikacji")

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.metric("Konta", stats["users"])
        st.metric("Łącznie XP", f"{stats['total_xp']:,}".replace(",", " "))
    with c2:
        st.metric("Łącznie 💎", stats["total_gems"])
        st.metric("Misje ukończone", stats["total_tasks"])
    with c3:
        st.metric("Odznaki", stats["total_badges"])
        st.metric("Naklejki", stats["total_stickers"])
    with c4:
        st.metric("Serie (max)", stats["max_streak"])
        st.metric("W klasach", stats["users_with_class"])
    with c5:
        st.metric("Nowe konta (tydz.)", stats["registrations_week"])
        st.metric("Nowe konta (mies.)", stats["registrations_month"])
        st.metric("Nowe konta (rok)", stats["registrations_year"])

    if stats["age_counts"]:
        st.caption("**Wiek:** " + ", ".join(f"{k}: {v}" for k, v in sorted(stats["age_counts"].items())))

    if stats["subject_counts"]:
        top_subj = ", ".join(f"{k} ({v})" for k, v in list(stats["subject_counts"].items())[:5])
        st.caption("**Popularne przedmioty:** " + top_subj)

    if stats["badge_counts"]:
        top_badges = ", ".join(f"{k} ({v})" for k, v in list(stats["badge_counts"].items())[:5])
        st.caption("**Odznaki:** " + top_badges)

    if stats["sticker_counts"]:
        top_stickers = ", ".join(f"{k} ({v})" for k, v in list(stats["sticker_counts"].items())[:5])
        st.caption("**Naklejki:** " + top_stickers)

    st.markdown("---")
    st.markdown("### 🎲 Losowanie konkursu")
    participants = load_contest_participants()
    if not participants:
        st.caption("Brak zgłoszeń do konkursu. Uczestnicy rejestrują się w zakładce „Wsparcie i konkursy” na Start.")
    else:
        st.caption(f"Liczba zgłoszeń: **{len(participants)}**. Wylosuj 3 pierwsze miejsca spośród uczestników.")
        if st.button("Wylosuj 3 miejsca", key="draw_contest_btn"):
            shuffled = list(participants)
            random.shuffle(shuffled)
            winners = shuffled[:3]
            for i, w in enumerate(winners, 1):
                medal = ["🥇", "🥈", "🥉"][i - 1]
                name = (w.get("kid_name") or w.get("login") or "").strip() or "—"
                parent = (w.get("parent_name") or "").strip() or "—"
                email = (w.get("email") or "").strip() or "—"
                st.success(f"{medal} **{i}. miejsce:** {name} (opiekun: {parent}, {email})")
            st.session_state["_contest_last_draw"] = winners
        if st.session_state.get("_contest_last_draw"):
            st.markdown("**Ostatni wynik losowania:**")
            for i, w in enumerate(st.session_state["_contest_last_draw"], 1):
                medal = ["🥇", "🥈", "🥉"][i - 1]
                name = (w.get("kid_name") or w.get("login") or "").strip() or "—"
                parent = (w.get("parent_name") or "").strip() or "—"
                st.caption(f"{medal} {i}. {name} — {parent}")

    st.markdown("---")
    st.markdown("**Lista kont** (usunięcie jest nieodwracalne)")

    for login, profile in users:
        kid = (profile or {}).get("kid_name") or "—"
        with st.expander(f"**{login}** — {kid}", expanded=False):
            st.caption(f"Login: `{login}`")
            if st.button("Usuń konto", key=f"del_{login}", type="primary"):
                st.session_state[f"_confirm_del_{login}"] = True
            if st.session_state.get(f"_confirm_del_{login}"):
                st.warning(f"Czy na pewno usunąć konto **{login}**?")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Tak, usuń", key=f"yes_del_{login}"):
                        if delete_user(login):
                            st.success(f"Usunięto konto {login}.")
                            st.session_state.pop(f"_confirm_del_{login}", None)
                            st.rerun()
                        else:
                            st.error("Nie udało się usunąć.")
                with c2:
                    if st.button("Anuluj", key=f"no_del_{login}"):
                        st.session_state.pop(f"_confirm_del_{login}", None)
                        st.rerun()


def render():
    """Wymagana przez dispatch() – wyświetla panel nadzoru."""
    _show_panel()
