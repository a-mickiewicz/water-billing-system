"""
Migracja: Naprawa unique constraint dla electricity_invoice_odczyty.
Usuwa automatyczny indeks SQLite i zostawia tylko nowy constraint z data_odczytu.

SQLite nie pozwala bezpośrednio usunąć automatycznego indeksu, więc musimy
przekształcić tabelę: utworzyć nową z poprawnym constraintem, skopiować dane,
usunąć starą i zmienić nazwę.
"""

import sqlite3
from pathlib import Path


def upgrade():
    """Naprawia unique constraint dla odczytów."""
    
    db_path = Path("water_billing.db")
    
    if not db_path.exists():
        print(f"[ERROR] Baza danych {db_path} nie istnieje!")
        return False
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Sprawdź czy tabela istnieje
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='electricity_invoice_odczyty'
        """)
        if not cursor.fetchone():
            print("[INFO] Tabela electricity_invoice_odczyty nie istnieje, pomijam migrację")
            return False
        
        # Sprawdź czy automatyczny indeks istnieje
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='index' AND name='sqlite_autoindex_electricity_invoice_odczyty_1'
        """)
        autoindex_exists = cursor.fetchone() is not None
        
        if not autoindex_exists:
            print("[INFO] Automatyczny indeks nie istnieje, constraint jest już poprawny")
            return True
        
        print("[INFO] Znaleziono automatyczny indeks, przekształcam tabelę...")
        
        # Rozpocznij transakcję
        cursor.execute("BEGIN TRANSACTION")
        
        # Utwórz nową tabelę z poprawnym constraintem
        cursor.execute("""
            CREATE TABLE electricity_invoice_odczyty_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id INTEGER NOT NULL,
                rok INTEGER NOT NULL,
                typ_energii VARCHAR(20) NOT NULL,
                strefa VARCHAR(10),
                data_odczytu DATE NOT NULL,
                biezacy_odczyt INTEGER NOT NULL,
                poprzedni_odczyt INTEGER NOT NULL,
                mnozna INTEGER NOT NULL,
                ilosc_kwh INTEGER NOT NULL,
                straty_kwh INTEGER NOT NULL,
                razem_kwh INTEGER NOT NULL,
                FOREIGN KEY (invoice_id) REFERENCES electricity_invoices(id) ON DELETE CASCADE,
                UNIQUE(invoice_id, typ_energii, strefa, data_odczytu)
            )
        """)
        
        # Skopiuj dane
        cursor.execute("""
            INSERT INTO electricity_invoice_odczyty_new 
            SELECT * FROM electricity_invoice_odczyty
        """)
        
        # Usuń starą tabelę
        cursor.execute("DROP TABLE electricity_invoice_odczyty")
        
        # Zmień nazwę nowej tabeli
        cursor.execute("ALTER TABLE electricity_invoice_odczyty_new RENAME TO electricity_invoice_odczyty")
        
        # Utwórz indeksy (jeśli nie istnieją)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_invoice_id 
            ON electricity_invoice_odczyty(invoice_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_rok 
            ON electricity_invoice_odczyty(rok)
        """)
        
        # Zatwierdź transakcję
        conn.commit()
        
        print("[OK] Przekształcono tabelę i naprawiono unique constraint")
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Błąd podczas migracji: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    print(f"\n[INFO] Rozpoczynam migrację bazy danych")
    success = upgrade()
    if success:
        print("\n[INFO] Migracja zakończona pomyślnie")
    else:
        print("\n[ERROR] Migracja zakończona z błędami")
        exit(1)

