"""
Skrypt migracyjny - dodaje kolumny:
- email do tabeli locals
- email_sent_date do tabeli combined_bills
Uruchom ten skrypt raz, aby zaktualizować istniejącą bazę danych.
"""

import sqlite3
from pathlib import Path
import os

# Ścieżka do bazy danych
BASE_DIR = Path(__file__).parent.parent.parent
DATABASE_URL = BASE_DIR / "water_billing.db"

if not DATABASE_URL.exists():
    print(f"[INFO] Baza danych {DATABASE_URL} nie istnieje - zostanie utworzona automatycznie przy następnym uruchomieniu aplikacji.")
    exit(0)

print(f"[INFO] Łączenie z bazą danych: {DATABASE_URL}")

conn = sqlite3.connect(str(DATABASE_URL))
cursor = conn.cursor()

try:
    # 1. Dodaj kolumnę email do tabeli locals (jeśli nie istnieje)
    cursor.execute("PRAGMA table_info(locals)")
    locals_columns = [col[1] for col in cursor.fetchall()]
    
    if 'email' not in locals_columns:
        print("[INFO] Dodawanie kolumny 'email' do tabeli locals...")
        cursor.execute("ALTER TABLE locals ADD COLUMN email VARCHAR(200)")
        print("[OK] Kolumna 'email' została dodana do tabeli locals.")
    else:
        print("[INFO] Kolumna 'email' już istnieje w tabeli locals.")
    
    # 2. Dodaj kolumnę email_sent_date do tabeli combined_bills (jeśli tabela istnieje)
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='combined_bills'")
    if cursor.fetchone():
        cursor.execute("PRAGMA table_info(combined_bills)")
        combined_bills_columns = [col[1] for col in cursor.fetchall()]
        
        if 'email_sent_date' not in combined_bills_columns:
            print("[INFO] Dodawanie kolumny 'email_sent_date' do tabeli combined_bills...")
            cursor.execute("ALTER TABLE combined_bills ADD COLUMN email_sent_date DATE")
            print("[OK] Kolumna 'email_sent_date' została dodana do tabeli combined_bills.")
        else:
            print("[INFO] Kolumna 'email_sent_date' już istnieje w tabeli combined_bills.")
    else:
        print("[INFO] Tabela combined_bills nie istnieje - zostanie utworzona automatycznie przy następnym uruchomieniu aplikacji.")
    
    conn.commit()
    print("[OK] Migracja zakończona pomyślnie!")
    
except sqlite3.Error as e:
    print(f"[ERROR] Błąd podczas migracji: {e}")
    conn.rollback()
    exit(1)
finally:
    conn.close()

