"""
Migracja bazy danych: Dodanie pól kWh dla dystrybucji zmiennej i dystrybucji zmiennej 2.

Dodaje pola:
- distribution_variable_usage_kwh (dla pierwszej dystrybucji zmiennej)
- distribution_variable_2_usage_kwh (dla drugiej dystrybucji zmiennej, jeśli występuje)
"""

import sqlite3
from pathlib import Path

DB_PATH = "water_billing.db"


def migrate():
    """Dodaje kolumny dla kWh w dystrybucji zmiennej."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Sprawdź czy kolumna już istnieje
        cursor.execute("PRAGMA table_info(gas_invoices)")
        columns = [col[1] for col in cursor.fetchall()]
        
        # Dodaj distribution_variable_usage_kwh jeśli nie istnieje
        if 'distribution_variable_usage_kwh' not in columns:
            print("[INFO] Dodawanie kolumny distribution_variable_usage_kwh...")
            cursor.execute("""
                ALTER TABLE gas_invoices 
                ADD COLUMN distribution_variable_usage_kwh REAL NOT NULL DEFAULT 0.0
            """)
            print("[OK] Kolumna distribution_variable_usage_kwh dodana")
        else:
            print("[INFO] Kolumna distribution_variable_usage_kwh już istnieje")
        
        # Dodaj distribution_variable_2_usage_kwh jeśli nie istnieje
        if 'distribution_variable_2_usage_kwh' not in columns:
            print("[INFO] Dodawanie kolumny distribution_variable_2_usage_kwh...")
            cursor.execute("""
                ALTER TABLE gas_invoices 
                ADD COLUMN distribution_variable_2_usage_kwh REAL
            """)
            print("[OK] Kolumna distribution_variable_2_usage_kwh dodana")
        else:
            print("[INFO] Kolumna distribution_variable_2_usage_kwh już istnieje")
        
        conn.commit()
        print("[OK] Migracja zakończona pomyślnie")
        
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Błąd migracji: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    if not Path(DB_PATH).exists():
        print(f"[ERROR] Baza danych {DB_PATH} nie istnieje")
        exit(1)
    
    print(f"\n[INFO] Rozpoczynam migrację bazy danych: {DB_PATH}")
    migrate()

