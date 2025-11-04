"""
Skrypt migracyjny - usuwa tabelę gas_readings i kolumnę reading_id z gas_bills.
Wszystkie dane są teraz w fakturze - nie ma potrzeby osobnych odczytów.
"""

import sqlite3
import os

# Ścieżka do bazy danych
DATABASE_PATH = os.path.join(os.path.dirname(__file__), "water_billing.db")

def migrate():
    """Usuwa tabelę gas_readings i kolumnę reading_id z gas_bills."""
    if not os.path.exists(DATABASE_PATH):
        print(f"[BŁĄD] Baza danych nie istnieje: {DATABASE_PATH}")
        return False
    
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    try:
        print("[INFO] Sprawdzanie struktury bazy danych...")
        
        # Sprawdź czy tabela gas_readings istnieje
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='gas_readings'")
        has_readings_table = cursor.fetchone() is not None
        
        # Sprawdź czy kolumna reading_id istnieje w gas_bills
        cursor.execute("PRAGMA table_info(gas_bills)")
        gas_bills_columns = [col[1] for col in cursor.fetchall()]
        has_reading_id_column = 'reading_id' in gas_bills_columns
        
        if not has_readings_table and not has_reading_id_column:
            print("[INFO] Tabela gas_readings i kolumna reading_id już nie istnieją - migracja nie jest potrzebna.")
            return True
        
        print("[INFO] Rozpoczynam migrację...")
        
        # 1. Usuń tabelę gas_readings (jeśli istnieje)
        if has_readings_table:
            print("[INFO] Usuwanie tabeli gas_readings...")
            cursor.execute("DROP TABLE IF EXISTS gas_readings")
            print("[OK] Tabela gas_readings usunięta.")
        else:
            print("[INFO] Tabela gas_readings nie istnieje - pomijam.")
        
        # 2. Usuń kolumnę reading_id z gas_bills (jeśli istnieje)
        if has_reading_id_column:
            print("[INFO] Usuwanie kolumny reading_id z tabeli gas_bills...")
            print("[UWAGA] SQLite nie obsługuje bezpośredniego usuwania kolumn.")
            print("[INFO] Wykonuję migrację przez utworzenie nowej tabeli...")
            
            # Pobierz strukturę obecnej tabeli
            cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='gas_bills'")
            create_sql = cursor.fetchone()
            if not create_sql:
                print("[BŁĄD] Nie można znaleźć tabeli gas_bills")
                return False
            
            # Utwórz nową tabelę bez kolumny reading_id
            cursor.execute("""
                CREATE TABLE gas_bills_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    data VARCHAR(7) NOT NULL,
                    local VARCHAR(50) NOT NULL,
                    invoice_id INTEGER,
                    local_id INTEGER,
                    cost_share FLOAT NOT NULL,
                    fuel_cost_gross FLOAT NOT NULL,
                    subscription_cost_gross FLOAT NOT NULL,
                    distribution_fixed_cost_gross FLOAT NOT NULL,
                    distribution_variable_cost_gross FLOAT NOT NULL,
                    total_net_sum FLOAT NOT NULL,
                    total_gross_sum FLOAT NOT NULL,
                    pdf_path VARCHAR(200),
                    FOREIGN KEY(invoice_id) REFERENCES gas_invoices(id),
                    FOREIGN KEY(local_id) REFERENCES locals(id)
                )
            """)
            
            # Skopiuj dane (bez kolumny reading_id)
            cursor.execute("""
                INSERT INTO gas_bills_new (
                    id, data, local, invoice_id, local_id, cost_share,
                    fuel_cost_gross, subscription_cost_gross,
                    distribution_fixed_cost_gross, distribution_variable_cost_gross,
                    total_net_sum, total_gross_sum, pdf_path
                )
                SELECT 
                    id, data, local, invoice_id, local_id, cost_share,
                    fuel_cost_gross, subscription_cost_gross,
                    distribution_fixed_cost_gross, distribution_variable_cost_gross,
                    total_net_sum, total_gross_sum, pdf_path
                FROM gas_bills
            """)
            
            # Usuń starą tabelę
            cursor.execute("DROP TABLE gas_bills")
            
            # Zmień nazwę nowej tabeli
            cursor.execute("ALTER TABLE gas_bills_new RENAME TO gas_bills")
            
            print("[OK] Kolumna reading_id została usunięta z tabeli gas_bills!")
        else:
            print("[INFO] Kolumna reading_id nie istnieje w gas_bills - pomijam.")
        
        conn.commit()
        print("\n[OK] Migracja zakończona pomyślnie!")
        return True
        
    except sqlite3.Error as e:
        print(f"[BŁĄD] Wystąpił błąd podczas migracji: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    print("=" * 60)
    print("MIGRACJA: Usunięcie tabeli gas_readings i kolumny reading_id")
    print("=" * 60)
    print("\nZmiany:")
    print("  - Usunięcie tabeli gas_readings")
    print("  - Usunięcie kolumny reading_id z gas_bills")
    print("  - Wszystkie dane są teraz w fakturze")
    print()
    
    if migrate():
        print("\n[OK] Migracja zakończona pomyślnie!")
    else:
        print("\n[BŁĄD] Migracja nie powiodła się!")

