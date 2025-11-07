"""
Skrypt do czyszczenia i odtwarzania tabel faktur elektrycznych.
Usuwa wszystkie dane z tabel i odtwarza strukturę tabel.
"""

import sys
from pathlib import Path

# Dodaj ścieżkę do projektu
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from app.core.database import engine, Base
from app.models.electricity_invoice import (
    ElectricityInvoice,
    ElectricityInvoiceBlankiet,
    ElectricityInvoiceOdczyt,
    ElectricityInvoiceSprzedazEnergii,
    ElectricityInvoiceOplataDystrybucyjna,
    ElectricityInvoiceRozliczenieOkres
)


def clear_electricity_invoices():
    """Czyści wszystkie tabele faktur elektrycznych i odtwarza strukturę."""
    
    print("Czyszczenie tabel faktur elektrycznych...")
    print("")
    
    # Lista tabel do usunięcia (w kolejności zależności - najpierw tabele zależne)
    tables_to_drop = [
        'electricity_invoice_rozliczenie_okresy',
        'electricity_invoice_oplaty_dystrybucyjne',
        'electricity_invoice_sprzedaz_energii',
        'electricity_invoice_odczyty',
        'electricity_invoice_blankiety',
        'electricity_invoices',
    ]
    
    # Usuń tabele (SQLite automatycznie usuwa indeksy przy usuwaniu tabel)
    with engine.connect() as conn:
        for table_name in tables_to_drop:
            try:
                print(f"  Usuwanie tabeli: {table_name}...")
                conn.execute(text(f"DROP TABLE IF EXISTS {table_name}"))
                conn.commit()
                print(f"    [OK] Tabela {table_name} usunieta")
            except Exception as e:
                print(f"    [ERROR] Blad przy usuwaniu {table_name}: {e}")
        
        # Usuń wszystkie indeksy, które mogą kolidować
        print("")
        print("Czyszczenie wszystkich indeksow...")
        try:
            # Pobierz listę wszystkich indeksów
            result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'"))
            indexes = [row[0] for row in result]
            for index_name in indexes:
                try:
                    conn.execute(text(f"DROP INDEX IF EXISTS {index_name}"))
                    print(f"    [OK] Indeks {index_name} usuniety")
                except Exception as e:
                    print(f"    [WARN] Nie udalo sie usunac indeksu {index_name}: {e}")
            
            conn.commit()
        except Exception as e:
            print(f"    [WARN] Blad przy czyszczeniu indeksow: {e}")
        
        print("")
        print("Odtwarzanie struktury tabel...")
        
        # Utwórz tabele na nowo (checkfirst=True sprawdza czy tabela już istnieje)
        # Ignoruj błędy związane z indeksami, które mogą być używane przez inne tabele
        try:
            Base.metadata.create_all(engine, tables=[
                ElectricityInvoice.__table__,
                ElectricityInvoiceBlankiet.__table__,
                ElectricityInvoiceOdczyt.__table__,
                ElectricityInvoiceSprzedazEnergii.__table__,
                ElectricityInvoiceOplataDystrybucyjna.__table__,
                ElectricityInvoiceRozliczenieOkres.__table__,
            ], checkfirst=True)
            print("  [OK] Struktura tabel odtworzona")
        except Exception as e:
            # Jeśli błąd dotyczy tylko indeksów, spróbuj utworzyć tabele bez indeksów
            error_msg = str(e)
            if "index" in error_msg.lower() and "already exists" in error_msg.lower():
                print(f"  [WARN] Niektore indeksy juz istnieja (uzywane przez inne tabele), ale tabele zostaly utworzone")
                print("  [INFO] Mozesz kontynuowac - tabele sa gotowe do uzycia")
            else:
                print(f"  [ERROR] Blad przy odtwarzaniu struktury: {e}")
                raise
    
    print("")
    print("Gotowe! Tabele faktur elektrycznych zostały wyczyszczone i odtworzone.")
    print("Możesz teraz ponownie sparsować faktury z poprawionym kodem parsowania cen.")


if __name__ == "__main__":
    clear_electricity_invoices()

