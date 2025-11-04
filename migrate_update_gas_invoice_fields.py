"""
Migracja: Aktualizacja pól w tabeli gas_invoices.

Dodaje nowe pola:
- distribution_fixed_value_net
- distribution_variable_usage_m3
- distribution_variable_conversion_factor
- distribution_variable_value_net
- fuel_conversion_factor
- fuel_usage_kwh
- vat_amount
- total_net_sum
- late_payment_interest
- amount_to_pay
- payment_due_date

Zmienia:
- distribution_variable_quantity -> distribution_variable_usage_m3 (usunięte)
- distribution_variable_price_net (teraz cena za kWh, nie za miesiąc)
"""

import sqlite3
from pathlib import Path

def migrate():
    db_path = Path("water_billing.db")
    
    if not db_path.exists():
        print(f"[ERROR] Baza danych {db_path} nie istnieje!")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Sprawdź czy tabela istnieje
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='gas_invoices'")
        if not cursor.fetchone():
            print("[ERROR] Tabela gas_invoices nie istnieje. Najpierw utworz ja przez model.")
            return
        
        # Sprawdź które pola już istnieją
        cursor.execute("PRAGMA table_info(gas_invoices)")
        existing_columns = [row[1] for row in cursor.fetchall()]
        
        # Dodaj nowe pola jeśli nie istnieją
        new_columns = [
            ("distribution_fixed_value_net", "REAL NOT NULL DEFAULT 0"),
            ("distribution_variable_usage_m3", "REAL NOT NULL DEFAULT 0"),
            ("distribution_variable_conversion_factor", "REAL NOT NULL DEFAULT 0"),
            ("distribution_variable_value_net", "REAL NOT NULL DEFAULT 0"),
            ("fuel_conversion_factor", "REAL NOT NULL DEFAULT 0"),
            ("fuel_usage_kwh", "REAL NOT NULL DEFAULT 0"),
            ("vat_amount", "REAL NOT NULL DEFAULT 0"),
            ("total_net_sum", "REAL NOT NULL DEFAULT 0"),
            ("late_payment_interest", "REAL NOT NULL DEFAULT 0"),
            ("amount_to_pay", "REAL NOT NULL DEFAULT 0"),
            ("payment_due_date", "DATE"),
        ]
        
        for column_name, column_type in new_columns:
            if column_name not in existing_columns:
                print(f"[+] Dodawanie kolumny: {column_name}")
                cursor.execute(f"ALTER TABLE gas_invoices ADD COLUMN {column_name} {column_type}")
        
        # Sprawdź czy stara kolumna distribution_variable_quantity istnieje
        if "distribution_variable_quantity" in existing_columns:
            print("[!] Kolumna distribution_variable_quantity nadal istnieje.")
            print("   Mozesz ja usunac recznie jesli nie jest juz uzywana.")
            print("   ALTER TABLE gas_invoices DROP COLUMN distribution_variable_quantity;")
        
        conn.commit()
        print("[OK] Migracja zakonczona pomyslnie!")
        
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Blad podczas migracji: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()

