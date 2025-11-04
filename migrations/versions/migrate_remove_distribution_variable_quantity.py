"""
Migracja: Usunięcie starej kolumny distribution_variable_quantity z tabeli gas_invoices.

Kolumna została zastąpiona przez distribution_variable_usage_m3.
"""

import sqlite3
from pathlib import Path

DB_PATH = "water_billing.db"


def migrate():
    """Usuwa starą kolumnę distribution_variable_quantity."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Sprawdź czy kolumna istnieje
        cursor.execute("PRAGMA table_info(gas_invoices)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'distribution_variable_quantity' in columns:
            print("[INFO] Usuwanie starej kolumny distribution_variable_quantity...")
            
            # SQLite nie obsługuje bezpośredniego DROP COLUMN, więc musimy:
            # 1. Utworzyć nową tabelę bez tej kolumny
            # 2. Skopiować dane
            # 3. Usunąć starą tabelę
            # 4. Zmienić nazwę nowej tabeli
            
            # Pobierz definicję wszystkich kolumn oprócz distribution_variable_quantity
            cursor.execute("PRAGMA table_info(gas_invoices)")
            all_columns = cursor.fetchall()
            
            # Filtruj kolumny (pomijamy distribution_variable_quantity)
            columns_to_keep = [col for col in all_columns if col[1] != 'distribution_variable_quantity']
            
            # Pobierz wszystkie dane
            cursor.execute("SELECT * FROM gas_invoices")
            rows = cursor.fetchall()
            
            # Pobierz nazwy wszystkich kolumn (z distribution_variable_quantity)
            cursor.execute("SELECT * FROM gas_invoices LIMIT 1")
            all_column_names = [description[0] for description in cursor.description]
            quantity_index = all_column_names.index('distribution_variable_quantity')
            
            # Utwórz nową tabelę bez distribution_variable_quantity
            # Najprostsze rozwiązanie: użyjemy ALTER TABLE DROP COLUMN (działa w SQLite 3.35.0+)
            # Jeśli nie działa, użyjemy metody z kopiowaniem tabeli
            
            # Spróbuj prostego DROP COLUMN (dla SQLite 3.35.0+)
            try:
                cursor.execute("ALTER TABLE gas_invoices DROP COLUMN distribution_variable_quantity")
                print("[OK] Kolumna distribution_variable_quantity usunięta")
            except sqlite3.OperationalError:
                # Jeśli nie działa, użyj metody z kopiowaniem
                print("[INFO] SQLite nie obsługuje DROP COLUMN, używam metody z kopiowaniem tabeli...")
                
                # Utwórz nową tabelę
                new_columns_def = []
                for col in columns_to_keep:
                    col_name = col[1]
                    col_type = col[2]
                    col_notnull = "NOT NULL" if col[3] else ""
                    col_default = f"DEFAULT {col[4]}" if col[4] is not None else ""
                    new_columns_def.append(f"{col_name} {col_type} {col_notnull} {col_default}".strip())
                
                # Pobierz definicję kluczy i innych ograniczeń
                cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='gas_invoices'")
                old_table_sql = cursor.fetchone()[0]
                
                # Utwórz nową tabelę
                cursor.execute(f"""
                    CREATE TABLE gas_invoices_new (
                        {', '.join(new_columns_def)}
                    )
                """)
                
                # Skopiuj dane (pomiń kolumnę distribution_variable_quantity)
                column_names_to_keep = [col[1] for col in columns_to_keep]
                placeholders = ','.join(['?' for _ in column_names_to_keep])
                
                for row in rows:
                    # Usuń wartość z indeksu quantity_index
                    new_row = list(row)
                    del new_row[quantity_index]
                    cursor.execute(f"INSERT INTO gas_invoices_new ({','.join(column_names_to_keep)}) VALUES ({placeholders})", new_row)
                
                # Usuń starą tabelę i zmień nazwę nowej
                cursor.execute("DROP TABLE gas_invoices")
                cursor.execute("ALTER TABLE gas_invoices_new RENAME TO gas_invoices")
                
                # Odtwórz indeksy jeśli były
                print("[OK] Kolumna distribution_variable_quantity usunięta (metodą kopiowania)")
        else:
            print("[INFO] Kolumna distribution_variable_quantity już nie istnieje")
        
        conn.commit()
        print("[OK] Migracja zakończona pomyślnie")
        
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Błąd migracji: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    if not Path(DB_PATH).exists():
        print(f"[ERROR] Baza danych {DB_PATH} nie istnieje")
        exit(1)
    
    print(f"\n[INFO] Rozpoczynam migrację bazy danych: {DB_PATH}")
    migrate()

