"""
Skrypt migracyjny - dodaje kolumnę email do tabeli users.
Uruchom ten skrypt raz, aby zaktualizować istniejącą bazę danych.
"""

import sqlite3
import os
from pathlib import Path

# Ścieżka do bazy danych
BASE_DIR = Path(__file__).parent
DATABASE_URL = BASE_DIR / "water_billing.db"

if not DATABASE_URL.exists():
    print(f"[ERROR] Baza danych nie istnieje: {DATABASE_URL}")
    exit(1)

print(f"[INFO] Łączenie z bazą danych: {DATABASE_URL}")

# Połącz z bazą danych
conn = sqlite3.connect(str(DATABASE_URL))
cursor = conn.cursor()

try:
    # Sprawdź czy kolumna email już istnieje
    cursor.execute("PRAGMA table_info(users)")
    columns = [column[1] for column in cursor.fetchall()]
    
    if 'email' in columns:
        print("[INFO] Kolumna 'email' już istnieje w tabeli users. Migracja nie jest potrzebna.")
    else:
        print("[INFO] Dodawanie kolumny 'email' do tabeli users...")
        
        # Dodaj kolumnę email (nullable, ponieważ istniejące rekordy mogą nie mieć email)
        cursor.execute("ALTER TABLE users ADD COLUMN email VARCHAR(255)")
        
        # Dla istniejących użytkowników (oprócz admina), ustaw email = username jeśli username wygląda jak email
        cursor.execute("""
            UPDATE users 
            SET email = username 
            WHERE username != 'admin' 
            AND email IS NULL
            AND username LIKE '%@%'
        """)
        
        # Dla użytkowników, którzy nie mają email i username nie wygląda jak email, ustaw email = NULL
        # (będą mogli ustawić później)
        
        conn.commit()
        print("[OK] Kolumna 'email' została dodana do tabeli users.")
        
        # Pokaż statystyki
        cursor.execute("SELECT COUNT(*) FROM users WHERE email IS NOT NULL")
        users_with_email = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        print(f"[INFO] Użytkownicy z emailem: {users_with_email}/{total_users}")
        
except sqlite3.Error as e:
    print(f"[ERROR] Błąd migracji: {e}")
    conn.rollback()
    exit(1)
finally:
    conn.close()

print("[OK] Migracja zakończona.")

