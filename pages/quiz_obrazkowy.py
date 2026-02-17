from __future__ import annotations

import os
import hashlib
import streamlit as st

from core.state_init import init_core_state, init_router_state, ensure_default_dataset


def _deps() -> dict:
    """Zbiera zależności bez importu app.py (żeby uniknąć kółek)."""
    import core.app_helpers as ah
    deps = {k: getattr(ah, k) for k in dir(ah) if not k.startswith("__")}
    return deps


def render() -> None:
    # ✅ multipage-safe bootstrap
    init_core_state()
    init_router_state(initial_page="Quiz obrazkowy")
    st.session_state["page"] = "Quiz obrazkowy"
    ensure_default_dataset()

    try:
        globals().update(_deps())
    except Exception as e:
        st.error(
            "❌ Nie udało się załadować zależności quizu obrazkowego.\n\n"
            f"Szczegóły: {e}"
        )
        st.stop()

    kid_emoji = globals().get("KID_EMOJI", "🧒")
    data_dir = globals().get("DATA_DIR", "data")

    top_nav_row(f"🖼️ {kid_emoji} Quiz obrazkowy", back_default="Start", show_start=True)

    quiz_path = os.path.join(data_dir, "quiz_images", "image_quiz.json")
    raw = safe_load_json(quiz_path, default={"items": []})
    items = raw.get("items", []) if isinstance(raw, dict) else []

    if not items:
        st.warning("Brak pytań obrazkowych. Uzupełnij data/quiz_images/image_quiz.json 🙂")
        return

    age_group = get_age_group() if "get_age_group" in globals() else "10-12"
    age_group = str(age_group or "10-12")

    age_cats = {
        "7-9": {"shapes", "emotions", "objects"},
        "10-12": {"shapes", "objects", "plots"},
        "13-14": {"plots", "objects", "emotions"},
    }

    allowed = age_cats.get(age_group, None)
    if allowed:
        pool = [it for it in items if str(it.get("category", "")).strip() in allowed]
    else:
        pool = list(items)

    if not pool:
        pool = list(items)

    day_idx = days_since_epoch() if "days_since_epoch" in globals() else 0
    k = min(10, len(pool))
    salt = f"image_quiz::{age_group}"
    if callable(globals().get("pick_daily_chunk")):
        selected = pick_daily_chunk(pool, k, day_idx, salt)
    else:
        selected = pool[:k]

    done_key = f"img_quiz_done_{day_idx}_{age_group}"
    done_set = st.session_state.setdefault(done_key, set())
    if not isinstance(done_set, set):
        done_set = set(done_set or [])
        st.session_state[done_key] = done_set

    rewarded_key = f"img_quiz_rewarded_{day_idx}_{age_group}"

    st.caption(f"Zestaw dzienny: **{k} pytań** • grupa: **{age_group}**")
    st.progress(min(1.0, len(done_set) / max(1, k)))

    base_dir = os.path.join(data_dir, "quiz_images")

    for idx, it in enumerate(selected, start=1):
        img_name = str(it.get("image") or "").strip()
        q = str(it.get("q") or "").strip()
        options = it.get("options") or []
        correct_idx = int(it.get("correct", 0) or 0)

        try:
            qid_base = f"{img_name}::{q}"
            qid = hashlib.sha256(qid_base.encode("utf-8")).hexdigest()[:10]
        except Exception:
            qid = f"{idx}"

        st.markdown(f"### {idx}/{k}")
        if img_name:
            img_path = os.path.join(base_dir, img_name)
            if os.path.exists(img_path):
                st.image(img_path, use_container_width=True)
            else:
                st.warning(f"Brak pliku obrazka: {img_name}")
        if q:
            st.write(q)

        if qid in done_set:
            st.success("✅ Zaliczone")
            st.divider()
            continue

        radio_key = f"img_q_{day_idx}_{age_group}_{qid}"
        choice = st.radio(
            "Wybierz:",
            options,
            key=radio_key,
            label_visibility="collapsed",
            index=None,
        )
        if st.button("Sprawdź ✅", key=f"{radio_key}_check"):
            if choice is None:
                st.warning("Wybierz odpowiedź.")
            else:
                try:
                    correct = options[correct_idx]
                except Exception:
                    correct = None
                ok = (choice == correct)
                if ok:
                    st.success("✅ Dobrze!")
                    done_set.add(qid)
                    st.session_state[done_key] = done_set
                else:
                    st.error(f"❌ Nie. Poprawna: **{correct}**")
        st.divider()

    # nagroda za komplet
    if len(done_set) >= k and k > 0 and not st.session_state.get(rewarded_key):
        add_xp(10, reason="image_quiz_complete")
        st.session_state[rewarded_key] = True
        st.toast("🎁 Ukończony zestaw: +10 XP", icon="🎁")


# Multipage (st.switch_page): uruchom render() także przy wejściu bez routera
try:
    render()
except Exception:
    pass
