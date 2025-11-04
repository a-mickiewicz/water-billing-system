"""
Skrypt migracyjny - dodaje kolumnę gas_meter_name do tabeli locals.
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

# Sprawdź czy kolumna już istnieje
cursor.execute("PRAGMA table_info(locals)")
columns = [col[1] for col in cursor.fetchall()]

if 'gas_meter_name' in columns:
    print("[INFO] Kolumna gas_meter_name już istnieje - migracja nie jest potrzebna.")
    conn.close()
    exit(0)

# Dodaj kolumnę gas_meter_name
print("[INFO] Dodawanie kolumny gas_meter_name do tabeli locals...")
try:
    cursor.execute("ALTER TABLE locals ADD COLUMN gas_meter_name VARCHAR(50)")
    conn.commit()
    print("[OK] Kolumna gas_meter_name została dodana pomyślnie!")
except sqlite3.OperationalError as e:
    print(f"[ERROR] Błąd podczas dodawania kolumny: {e}")
    conn.rollback()
    conn.close()
    exit(1)

conn.close()
print("[OK] Migracja zakończona pomyślnie!")

