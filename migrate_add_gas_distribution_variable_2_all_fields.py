"""
Migracja bazy danych: Dodanie wszystkich pól dla dystrybucji zmiennej 2.

Dodaje pola:
- distribution_variable_2_usage_m3
- distribution_variable_2_conversion_factor
- distribution_variable_2_usage_kwh
- distribution_variable_2_price_net
- distribution_variable_2_value_net
"""

import sqlite3
from pathlib import Path

DB_PATH = "water_billing.db"


def migrate():
    """Dodaje wszystkie kolumny dla dystrybucji zmiennej 2."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Sprawdź czy kolumny już istnieją
        cursor.execute("PRAGMA table_info(gas_invoices)")
        columns = [col[1] for col in cursor.fetchall()]
        
        # Lista kolumn do dodania dla dystrybucji zmiennej 2
        columns_to_add = [
            ('distribution_variable_2_usage_m3', 'REAL'),
            ('distribution_variable_2_conversion_factor', 'REAL'),
            ('distribution_variable_2_usage_kwh', 'REAL'),
            ('distribution_variable_2_price_net', 'REAL'),
            ('distribution_variable_2_value_net', 'REAL'),
        ]
        
        for column_name, column_type in columns_to_add:
            if column_name not in columns:
                print(f"[INFO] Dodawanie kolumny {column_name}...")
                cursor.execute(f"""
                    ALTER TABLE gas_invoices 
                    ADD COLUMN {column_name} {column_type}
                """)
                print(f"[OK] Kolumna {column_name} dodana")
            else:
                print(f"[INFO] Kolumna {column_name} już istnieje")
        
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

