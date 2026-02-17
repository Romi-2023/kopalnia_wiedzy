import os
import json
import psycopg2

# --- Paths (single source of truth) ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

# fallback lokalny (dev) – niech katalog istnieje
try:
    os.makedirs(DATA_DIR, exist_ok=True)
except Exception:
    pass

USERS_FILE = os.path.join(DATA_DIR, "users.json")
DONORS_FILE = os.path.join(DATA_DIR, "donors.json")
DRAWS_FILE = os.path.join(DATA_DIR, "draws.json")
CONTEST_PARTICIPANTS_FILE = os.path.join(DATA_DIR, "contest_participants.json")

DATABASE_URL = os.environ.get("DATABASE_URL")


def load_json_if_exists(path, default):
    if not os.path.exists(path):
        print(f"[INFO] Plik nie istnieje, pomijam: {path}")
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"[OK] Wczytano dane z {path}")
        return data
    except Exception as e:
        print(f"[WARN] Nie udało się wczytać {path}: {e}")
        return default


def main():
    print("=== Migracja danych JSON -> PostgreSQL (kv_store) ===")

    if not DATABASE_URL:
        print("❌ Brak zmiennej środowiskowej DATABASE_URL")
        print("   Ustaw ją na connection string bazy z DigitalOcean i spróbuj ponownie.")
        return

    # 1. Upewnij się, że tabela istnieje
    print("[INFO] Tworzę (jeśli potrzeba) tabelę kv_store...")
    ensure_kv_table()
    print("[OK] Tabela kv_store gotowa.")

    # 2. Users
    users = load_json_if_exists(USERS_FILE, {})
    kv_set_json("users", users)
    print(f"[OK] Zapisano 'users' do kv_store (liczba użytkowników: {len(users) if isinstance(users, dict) else 'nie dotyczy'})")

    # 3. Donors
    donors = load_json_if_exists(DONORS_FILE, [])
    kv_set_json("donors", donors)
    print(f"[OK] Zapisano 'donors' do kv_store (rekordów: {len(donors) if isinstance(donors, list) else 'nie dotyczy'})")

    # 4. Draws
    draws = load_json_if_exists(DRAWS_FILE, [])
    kv_set_json("draws", draws)
    print(f"[OK] Zapisano 'draws' do kv_store (rekordów: {len(draws) if isinstance(draws, list) else 'nie dotyczy'})")

    # 5. Uczestnicy konkursu
    contest_participants = load_json_if_exists(CONTEST_PARTICIPANTS_FILE, [])
    kv_set_json("contest_participants", contest_participants)
    print(f"[OK] Zapisano 'contest_participants' do kv_store (rekordów: {len(contest_participants) if isinstance(contest_participants, list) else 'nie dotyczy'})")

    print("=== Migracja zakończona ✅ ===")


if __name__ == "__main__":
    main()
