"""
Migracja: Dodanie kolumn is_flagged do tabel electricity_readings i electricity_invoices.
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
else:
    # Sprawdź czy kolumna już istnieje
    cursor.execute("PRAGMA table_info(electricity_readings)")
    columns = [col[1] for col in cursor.fetchall()]
    
    # Dodaj kolumnę is_flagged jeśli nie istnieje
    if 'is_flagged' not in columns:
        print("[INFO] Dodawanie kolumny is_flagged do tabeli electricity_readings...")
        try:
            cursor.execute("ALTER TABLE electricity_readings ADD COLUMN is_flagged BOOLEAN NOT NULL DEFAULT 0")
            conn.commit()
            print("[OK] Kolumna is_flagged została dodana do electricity_readings pomyślnie!")
        except sqlite3.OperationalError as e:
            print(f"[ERROR] Błąd podczas dodawania kolumny is_flagged do electricity_readings: {e}")
            conn.rollback()
            conn.close()
            exit(1)
    else:
        print("[INFO] Kolumna is_flagged już istnieje w electricity_readings - pomijam.")

# Sprawdź czy tabela electricity_invoices istnieje
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='electricity_invoices'")
if not cursor.fetchone():
    print("[INFO] Tabela electricity_invoices nie istnieje - zostanie utworzona automatycznie przy następnym uruchomieniu aplikacji.")
else:
    # Sprawdź czy kolumna już istnieje
    cursor.execute("PRAGMA table_info(electricity_invoices)")
    columns = [col[1] for col in cursor.fetchall()]
    
    # Dodaj kolumnę is_flagged jeśli nie istnieje
    if 'is_flagged' not in columns:
        print("[INFO] Dodawanie kolumny is_flagged do tabeli electricity_invoices...")
        try:
            cursor.execute("ALTER TABLE electricity_invoices ADD COLUMN is_flagged BOOLEAN NOT NULL DEFAULT 0")
            conn.commit()
            print("[OK] Kolumna is_flagged została dodana do electricity_invoices pomyślnie!")
        except sqlite3.OperationalError as e:
            print(f"[ERROR] Błąd podczas dodawania kolumny is_flagged do electricity_invoices: {e}")
            conn.rollback()
            conn.close()
            exit(1)
    else:
        print("[INFO] Kolumna is_flagged już istnieje w electricity_invoices - pomijam.")

conn.close()
print("[OK] Migracja zakończona pomyślnie!")


def upgrade():
    """Dodaje kolumny is_flagged do tabel electricity_readings i electricity_invoices."""
    # Funkcja upgrade jest już zaimplementowana powyżej w głównym kodzie
    pass


def downgrade():
    """Usuwa kolumny is_flagged z tabel electricity_readings i electricity_invoices."""
    # SQLite nie obsługuje bezpośredniego usuwania kolumn
    # Wymaga to utworzenia nowej tabeli bez kolumny i skopiowania danych
    print("[INFO] Funkcja downgrade nie jest zaimplementowana dla tej migracji.")
    print("[INFO] SQLite nie obsługuje bezpośredniego usuwania kolumn.")


if __name__ == "__main__":
    upgrade()

