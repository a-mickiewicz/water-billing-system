"""
Migracja: Aktualizacja unique constraint dla electricity_invoice_odczyty.
Zmienia constraint z (invoice_id, typ_energii, strefa) na (invoice_id, typ_energii, strefa, data_odczytu),
aby umożliwić zapisanie wielu okresów dla tej samej kombinacji typ_energii i strefa.

Prosta wersja używająca bezpośrednio sqlite3.
"""

import sqlite3
from pathlib import Path


def upgrade():
    """Aktualizuje unique constraint dla odczytów."""
    
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
        
        # Sprawdź czy stary index istnieje i usuń go
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='index' AND name='uq_invoice_energy_type_zone'
        """)
        if cursor.fetchone():
            cursor.execute("DROP INDEX uq_invoice_energy_type_zone")
            print("[INFO] Usunięto stary unique constraint")
        else:
            print("[INFO] Stary unique constraint nie istnieje")
        
        # Sprawdź czy nowy index już istnieje
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='index' AND name='uq_invoice_energy_type_zone_date'
        """)
        if cursor.fetchone():
            print("[INFO] Nowy unique constraint już istnieje")
        else:
            # Dodaj nowy unique constraint z data_odczytu
            cursor.execute("""
                CREATE UNIQUE INDEX uq_invoice_energy_type_zone_date 
                ON electricity_invoice_odczyty(invoice_id, typ_energii, strefa, data_odczytu)
            """)
            print("[OK] Utworzono nowy unique constraint z data_odczytu")
        
        conn.commit()
        print("[OK] Zaktualizowano unique constraint dla electricity_invoice_odczyty")
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Błąd podczas migracji: {e}")
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

