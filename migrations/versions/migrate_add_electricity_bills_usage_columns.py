"""
Migracja: Dodanie kolumn usage_kwh_dzienna i usage_kwh_nocna do tabeli electricity_bills.
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

# Sprawdź czy tabela electricity_bills istnieje
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='electricity_bills'")
if not cursor.fetchone():
    print("[INFO] Tabela electricity_bills nie istnieje - zostanie utworzona automatycznie przy następnym uruchomieniu aplikacji.")
    conn.close()
    exit(0)

# Sprawdź czy kolumny już istnieją
cursor.execute("PRAGMA table_info(electricity_bills)")
columns = [col[1] for col in cursor.fetchall()]

# Dodaj kolumnę usage_kwh_dzienna jeśli nie istnieje
if 'usage_kwh_dzienna' not in columns:
    print("[INFO] Dodawanie kolumny usage_kwh_dzienna do tabeli electricity_bills...")
    try:
        cursor.execute("ALTER TABLE electricity_bills ADD COLUMN usage_kwh_dzienna REAL")
        conn.commit()
        print("[OK] Kolumna usage_kwh_dzienna została dodana pomyślnie!")
    except sqlite3.OperationalError as e:
        print(f"[ERROR] Błąd podczas dodawania kolumny usage_kwh_dzienna: {e}")
        conn.rollback()
        conn.close()
        exit(1)
else:
    print("[INFO] Kolumna usage_kwh_dzienna już istnieje - pomijam.")

# Dodaj kolumnę usage_kwh_nocna jeśli nie istnieje
if 'usage_kwh_nocna' not in columns:
    print("[INFO] Dodawanie kolumny usage_kwh_nocna do tabeli electricity_bills...")
    try:
        cursor.execute("ALTER TABLE electricity_bills ADD COLUMN usage_kwh_nocna REAL")
        conn.commit()
        print("[OK] Kolumna usage_kwh_nocna została dodana pomyślnie!")
    except sqlite3.OperationalError as e:
        print(f"[ERROR] Błąd podczas dodawania kolumny usage_kwh_nocna: {e}")
        conn.rollback()
        conn.close()
        exit(1)
else:
    print("[INFO] Kolumna usage_kwh_nocna już istnieje - pomijam.")

conn.close()
print("[OK] Migracja zakończona pomyślnie!")

