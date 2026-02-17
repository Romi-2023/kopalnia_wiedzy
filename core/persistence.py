# core/persistence.py
from __future__ import annotations

import json
import os
import tempfile
import contextlib

from typing import Optional, Any

try:
    import fcntl  # type: ignore
except Exception:  # pragma: no cover
    fcntl = None


# --- module config (ustawiane przez init_persistence) ---
DATA_DIR: str | None = None
DATABASE_URL: str | None = None
psycopg2 = None

USERS_FILE: str | None = None
TASKS_FILE: str | None = None
DONORS_FILE: str | None = None
DRAWS_FILE: str | None = None
CONTEST_PARTICIPANTS_FILE: str | None = None
GUEST_SIGNUPS_FILE: str | None = None


def init_persistence(
    *,
    data_dir: str,
    database_url: Optional[str] = None,
    psycopg2_module=None,
) -> None:
    """
    Inicjalizacja konfiguracji persistencji.
    Dzięki temu core/persistence.py nie musi znać BASE_DIR ani Twoich soft-importów.
    """
    global DATA_DIR, DATABASE_URL, psycopg2
    global USERS_FILE, TASKS_FILE, DONORS_FILE, DRAWS_FILE, CONTEST_PARTICIPANTS_FILE, GUEST_SIGNUPS_FILE

    DATA_DIR = data_dir
    DATABASE_URL = database_url
    psycopg2 = psycopg2_module

    # pliki fallback (dev)
    USERS_FILE = os.path.join(DATA_DIR, "users.json")
    TASKS_FILE = os.path.join(DATA_DIR, "tasks.json")
    DONORS_FILE = os.path.join(DATA_DIR, "donors.json")
    DRAWS_FILE = os.path.join(DATA_DIR, "draws.json")
    CONTEST_PARTICIPANTS_FILE = os.path.join(DATA_DIR, "contest_participants.json")
    GUEST_SIGNUPS_FILE = os.path.join(DATA_DIR, "guest_signups.json")

    try:
        os.makedirs(DATA_DIR, exist_ok=True)
    except Exception:
        pass


def get_db_connection():
    """
    Zwraca połączenie z bazą lub None.
    SAFE: timeout + łagodna degradacja.
    """
    if not DATABASE_URL:
        return None
    if psycopg2 is None:
        return None

    try:
        return psycopg2.connect(DATABASE_URL, connect_timeout=5)
    except Exception:
        return None


def ensure_kv_table():
    """Tworzy tabelę kv_store, jeśli jeszcze nie istnieje."""
    if not DATABASE_URL:
        return
    conn = get_db_connection()
    if conn is None:
        return
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS kv_store (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL
                    );
                    """
                )
    finally:
        try:
            conn.close()
        except Exception:
            pass


def kv_get_json(key: str, default: Any):
    """Odczyt JSON-a spod klucza z bazy; jeśli brak/błąd – zwraca default."""
    if not DATABASE_URL:
        return default
    conn = get_db_connection()
    if conn is None:
        return default
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT value FROM kv_store WHERE key = %s", (key,))
                row = cur.fetchone()
        if not row:
            return default
        try:
            return json.loads(row[0])
        except Exception:
            return default
    except Exception:
        return default
    finally:
        try:
            conn.close()
        except Exception:
            pass


def kv_set_json(key: str, value) -> None:
    """Zapis JSON-a pod kluczem w bazie (UPSERT)."""
    if not DATABASE_URL:
        return
    payload = json.dumps(value, ensure_ascii=False)
    conn = get_db_connection()
    if conn is None:
        return
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO kv_store (key, value)
                    VALUES (%s, %s)
                    ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;
                    """,
                    (key, payload),
                )
    finally:
        try:
            conn.close()
        except Exception:
            pass

def _load_classes() -> dict:
    return kv_get_json("classes", {}) or {}

def _save_classes(data: dict) -> None:
    kv_set_json("classes", data)
    


# -------------------
# Safe file IO helpers
# -------------------
def read_json_file(path: str, default: Any):
    """Bezpieczny odczyt JSON z pliku. Nigdy nie rzuca wyjątku."""
    try:
        if not path or (not os.path.exists(path)):
            return default
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

@contextlib.contextmanager
def _file_lock(lock_path: str):
    """Prosty lock plikowy (Unix: fcntl). Na innych OS działa jako no-op."""
    fh = None
    try:
        os.makedirs(os.path.dirname(lock_path) or ".", exist_ok=True)
        fh = open(lock_path, "a+", encoding="utf-8")
        if fcntl is not None:
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            except Exception:
                pass
        yield
    finally:
        try:
            if fh and fcntl is not None:
                try:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
                except Exception:
                    pass
            if fh:
                fh.close()
        except Exception:
            pass

def write_json_file_atomic(path: str, data: Any) -> None:
    """Atomowy zapis JSON: tmp -> fsync -> replace. Z lockiem."""
    if not path:
        return
    lock_path = path + ".lock"
    with _file_lock(lock_path):
        try:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        except Exception:
            pass
        dir_name = os.path.dirname(path) or "."
        fd, tmp_path = tempfile.mkstemp(prefix=".tmp_", suffix=".json", dir=dir_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                try:
                    f.flush()
                    os.fsync(f.fileno())
                except Exception:
                    pass
            try:
                os.replace(tmp_path, path)
            except Exception:
                try:
                    os.rename(tmp_path, path)
                except Exception:
                    pass
        finally:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass

# -------------------
# File fallbacks
# -------------------

def _load_users() -> dict:
    # 1) DB
    db = kv_get_json("users", None)
    if db is not None:
        return db

    # 2) File fallback
    if not USERS_FILE:
        return {}
    return read_json_file(USERS_FILE, {}) or {}



def _save_users(db: dict) -> None:
    # 1) DB
    kv_set_json("users", db)

    # 2) File fallback (dev)
    if not USERS_FILE:
        return
    write_json_file_atomic(USERS_FILE, db)



def _user_db_get(user: str) -> dict | None:
    """Zwraca profil użytkownika (lub None jeśli brak)."""
    db = _load_users() or {}
    return db.get(user)


def _user_db_set(user: str, profile: dict) -> None:
    """Zapisuje profil użytkownika."""
    db = _load_users() or {}
    db[user] = profile
    _save_users(db)


def delete_user(login: str) -> bool:
    """Usuwa konto użytkownika (tylko zwykłe loginy, nie klucze wewnętrzne _*). Zwraca True jeśli usunięto."""
    if not login or str(login).startswith("_"):
        return False
    db = _load_users() or {}
    if login not in db:
        return False
    del db[login]
    _save_users(db)
    return True


def clear_all_users() -> int:
    """Usuwa wszystkich użytkowników (zachowuje klucze wewnętrzne _*). Zwraca liczbę usuniętych kont."""
    db = _load_users() or {}
    to_remove = [k for k in db if not k.startswith("_")]
    for k in to_remove:
        del db[k]
    if to_remove:
        _save_users(db)
    return len(to_remove)


def _load_donors() -> list:
    recs = kv_get_json("donors", None)
    if recs is not None:
        return recs

    if not DONORS_FILE:
        return []
    return read_json_file(DONORS_FILE, []) or []



def _save_donors(records: list) -> None:
    kv_set_json("donors", records)

    if not DONORS_FILE:
        return
    write_json_file_atomic(DONORS_FILE, records)



def _load_draws() -> list:
    recs = kv_get_json("draws", None)
    if recs is not None:
        return recs

    if not DRAWS_FILE:
        return []
    return read_json_file(DRAWS_FILE, []) or []



def _save_draws(records: list) -> None:
    kv_set_json("draws", records)

    if not DRAWS_FILE:
        return
    write_json_file_atomic(DRAWS_FILE, records)


def load_contest_participants() -> list:
    """Lista zgłoszeń do konkursu: [{login, kid_name, parent_name, email, registered_at}, ...]."""
    recs = kv_get_json("contest_participants", None)
    if recs is not None:
        return recs if isinstance(recs, list) else []
    if not CONTEST_PARTICIPANTS_FILE:
        return []
    val = read_json_file(CONTEST_PARTICIPANTS_FILE, [])
    return val if isinstance(val, list) else []


def save_contest_participants(records: list) -> None:
    kv_set_json("contest_participants", records)
    if not CONTEST_PARTICIPANTS_FILE:
        return
    write_json_file_atomic(CONTEST_PARTICIPANTS_FILE, records)


# --- Goście: rejestracje do statystyk + codzienne kasowanie kont Gosc-* ---

def load_guest_signups() -> dict:
    """Słownik data (YYYY-MM-DD) -> liczba gości. Do statystyk admina po skasowaniu kont gości."""
    data = kv_get_json("guest_signups", None)
    if data is not None and isinstance(data, dict):
        return data
    if not GUEST_SIGNUPS_FILE:
        return {}
    val = read_json_file(GUEST_SIGNUPS_FILE, {})
    return val if isinstance(val, dict) else {}


def save_guest_signups(data: dict) -> None:
    kv_set_json("guest_signups", data)
    if not GUEST_SIGNUPS_FILE:
        return
    write_json_file_atomic(GUEST_SIGNUPS_FILE, data)


def record_guest_signup() -> None:
    """Zapisuje +1 gościa na dziś (do statystyk „nowe konta”)."""
    from datetime import datetime
    today = datetime.utcnow().strftime("%Y-%m-%d")
    data = load_guest_signups()
    data[today] = data.get(today, 0) + 1
    save_guest_signups(data)


def delete_guest_accounts_from_db() -> int:
    """Usuwa z bazy użytkowników wszystkie konta Gosc-*. Zwraca liczbę usuniętych."""
    db = _load_users() or {}
    to_remove = [k for k in db if isinstance(k, str) and k.startswith("Gosc-")]
    for k in to_remove:
        del db[k]
    if to_remove:
        _save_users(db)
    return len(to_remove)


def _get_last_guest_cleanup_date() -> str | None:
    last = kv_get_json("last_guest_cleanup_date", None)
    if last:
        return last
    if DATA_DIR:
        path = os.path.join(DATA_DIR, "last_guest_cleanup_date.txt")
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    return f.read().strip() or None
        except Exception:
            pass
    return None


def _set_last_guest_cleanup_date(date: str) -> None:
    kv_set_json("last_guest_cleanup_date", date)
    if DATA_DIR:
        path = os.path.join(DATA_DIR, "last_guest_cleanup_date.txt")
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(date)
        except Exception:
            pass


def run_daily_guest_cleanup_if_needed() -> None:
    """Jeśli minął nowy dzień (UTC), kasuje konta gości i zapisuje datę ostatniego czyszczenia."""
    from datetime import datetime
    today = datetime.utcnow().strftime("%Y-%m-%d")
    if _get_last_guest_cleanup_date() == today:
        return
    delete_guest_accounts_from_db()
    _set_last_guest_cleanup_date(today)


def _load_tasks() -> dict:
    db = kv_get_json("tasks", None)
    if isinstance(db, dict):
        return db

    if not TASKS_FILE:
        return {}
    val = read_json_file(TASKS_FILE, {}) or {}
    return val if isinstance(val, dict) else {}

def _save_tasks(tasks: dict) -> None:
    kv_set_json("tasks", tasks)

    if not TASKS_FILE:
        return
    write_json_file_atomic(TASKS_FILE, tasks)
