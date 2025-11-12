"""
Migracja: Dodanie kolumny data_odczytu_licznika do tabeli electricity_readings.
Uruchom ten skrypt raz, aby zaktualizować istniejącą bazę danych.
"""

import sqlite3
from pathlib import Path

db_path = Path("water_billing.db")

if not db_path.exists():
    print(f"[INFO] Baza danych {db_path} nie istnieje - zostanie utworzona automatycznie przy następnym uruchomieniu aplikacji.")
    exit(0)

print(f"[INFO] Łączenie z bazą danych: {db_path}")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Sprawdź czy tabela electricity_readings istnieje
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='electricity_readings'")
if not cursor.fetchone():
    print("[INFO] Tabela electricity_readings nie istnieje - zostanie utworzona automatycznie przy następnym uruchomieniu aplikacji.")
    conn.close()
    exit(0)

# Sprawdź czy kolumna już istnieje
cursor.execute("PRAGMA table_info(electricity_readings)")
columns = [col[1] for col in cursor.fetchall()]

# Dodaj kolumnę data_odczytu_licznika jeśli nie istnieje
if 'data_odczytu_licznika' not in columns:
    print("[INFO] Dodawanie kolumny data_odczytu_licznika do tabeli electricity_readings...")
    try:
        cursor.execute("ALTER TABLE electricity_readings ADD COLUMN data_odczytu_licznika DATE")
        conn.commit()
        print("[OK] Kolumna data_odczytu_licznika została dodana pomyślnie!")
    except sqlite3.OperationalError as e:
        print(f"[ERROR] Błąd podczas dodawania kolumny data_odczytu_licznika: {e}")
        conn.rollback()
        conn.close()
        exit(1)
else:
    print("[INFO] Kolumna data_odczytu_licznika już istnieje - pomijam.")

conn.close()
print("[OK] Migracja zakończona pomyślnie!")


def upgrade():
    """Dodaje kolumnę data_odczytu_licznika do tabeli electricity_readings."""
    # Funkcja upgrade jest już zaimplementowana powyżej w głównym kodzie
    pass


def downgrade():
    """Usuwa kolumnę data_odczytu_licznika z tabeli electricity_readings."""
    # SQLite nie obsługuje bezpośredniego usuwania kolumn
    # Wymaga to utworzenia nowej tabeli bez kolumny i skopiowania danych
    print("[INFO] Funkcja downgrade nie jest zaimplementowana dla tej migracji.")
    print("[INFO] SQLite nie obsługuje bezpośredniego usuwania kolumn.")


if __name__ == "__main__":
    upgrade()

