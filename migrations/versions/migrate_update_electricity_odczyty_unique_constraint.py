"""
Migracja: Aktualizacja unique constraint dla electricity_invoice_odczyty.
Zmienia constraint z (invoice_id, typ_energii, strefa) na (invoice_id, typ_energii, strefa, data_odczytu),
aby umożliwić zapisanie wielu okresów dla tej samej kombinacji typ_energii i strefa.
"""

import sys
from pathlib import Path

# Dodaj główny katalog projektu do ścieżki
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from app.core.database import engine


def upgrade():
    """Aktualizuje unique constraint dla odczytów."""
    
    with engine.begin() as conn:
        # Sprawdź czy tabela istnieje
        result = conn.execute(text("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='electricity_invoice_odczyty'
        """))
        if not result.fetchone():
            print("[INFO] Tabela electricity_invoice_odczyty nie istnieje, pomijam migrację")
            return
        
        # Sprawdź czy stary index istnieje i usuń go
        result = conn.execute(text("""
            SELECT name FROM sqlite_master 
            WHERE type='index' AND name='uq_invoice_energy_type_zone'
        """))
        if result.fetchone():
            conn.execute(text("DROP INDEX uq_invoice_energy_type_zone"))
            print("[INFO] Usunięto stary unique constraint")
        
        # Sprawdź czy nowy index już istnieje
        result = conn.execute(text("""
            SELECT name FROM sqlite_master 
            WHERE type='index' AND name='uq_invoice_energy_type_zone_date'
        """))
        if result.fetchone():
            print("[INFO] Nowy unique constraint już istnieje")
        else:
            # Dodaj nowy unique constraint z data_odczytu
            conn.execute(text("""
                CREATE UNIQUE INDEX uq_invoice_energy_type_zone_date 
                ON electricity_invoice_odczyty(invoice_id, typ_energii, strefa, data_odczytu)
            """))
            print("[OK] Utworzono nowy unique constraint z data_odczytu")
        
        print("[OK] Zaktualizowano unique constraint dla electricity_invoice_odczyty")


def downgrade():
    """Przywraca stary unique constraint."""
    
    with engine.begin() as conn:
        # Sprawdź czy tabela istnieje
        result = conn.execute(text("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='electricity_invoice_odczyty'
        """))
        if not result.fetchone():
            print("[INFO] Tabela electricity_invoice_odczyty nie istnieje, pomijam migrację")
            return
        
        # Usuń nowy constraint
        result = conn.execute(text("""
            SELECT name FROM sqlite_master 
            WHERE type='index' AND name='uq_invoice_energy_type_zone_date'
        """))
        if result.fetchone():
            conn.execute(text("DROP INDEX uq_invoice_energy_type_zone_date"))
            print("[INFO] Usunięto nowy unique constraint")
        
        # Przywróć stary constraint
        result = conn.execute(text("""
            SELECT name FROM sqlite_master 
            WHERE type='index' AND name='uq_invoice_energy_type_zone'
        """))
        if not result.fetchone():
            conn.execute(text("""
                CREATE UNIQUE INDEX uq_invoice_energy_type_zone 
                ON electricity_invoice_odczyty(invoice_id, typ_energii, strefa)
            """))
            print("[OK] Przywrócono stary unique constraint")
        
        print("[OK] Przywrócono stary unique constraint dla electricity_invoice_odczyty")


if __name__ == "__main__":
    db_path = Path("water_billing.db")
    
    if not db_path.exists():
        print(f"[ERROR] Baza danych {db_path} nie istnieje!")
        exit(1)
    
    print(f"\n[INFO] Rozpoczynam migrację bazy danych: {db_path}")
    upgrade()
    print("\n[INFO] Migracja zakończona")

