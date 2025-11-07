"""
Migracja: Dodanie szczegółowych tabel dla faktur prądu.
Tworzy tabele zgodnie ze schematem z propozycja_tabel_prąd.md:
- electricity_invoices (nowa struktura)
- electricity_invoice_blankiety
- electricity_invoice_odczyty
- electricity_invoice_sprzedaz_energii
- electricity_invoice_oplaty_dystrybucyjne
- electricity_invoice_rozliczenie_okresy
"""

from sqlalchemy import text
from app.core.database import engine


def upgrade():
    """Tworzy szczegółowe tabele dla faktur prądu."""
    
    with engine.begin() as conn:
        # Usuń starą tabelę electricity_invoices jeśli istnieje (będzie zastąpiona nową)
        # UWAGA: To usunie dane! W produkcji należy najpierw zrobić backup lub migrację danych
        conn.execute(text("DROP TABLE IF EXISTS electricity_bills"))  # Najpierw usuń tabele zależne
        conn.execute(text("DROP TABLE IF EXISTS electricity_invoices"))
        
        # Tabela electricity_invoices (nowa struktura)
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS electricity_invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rok INTEGER NOT NULL,
                numer_faktury VARCHAR(100) NOT NULL,
                data_wystawienia DATE NOT NULL,
                data_poczatku_okresu DATE NOT NULL,
                data_konca_okresu DATE NOT NULL,
                naleznosc_za_okres NUMERIC(10, 2) NOT NULL,
                wartosc_prognozy NUMERIC(10, 2) NOT NULL,
                faktury_korygujace NUMERIC(10, 2) NOT NULL,
                odsetki NUMERIC(10, 2) NOT NULL,
                wynik_rozliczenia NUMERIC(10, 2) NOT NULL,
                kwota_nadplacona NUMERIC(10, 2) NOT NULL,
                saldo_z_rozliczenia NUMERIC(10, 2) NOT NULL,
                niedoplata_nadplata NUMERIC(10, 2) NOT NULL,
                energia_do_akcyzy_kwh INTEGER NOT NULL,
                akcyza NUMERIC(10, 2) NOT NULL,
                do_zaplaty NUMERIC(10, 2) NOT NULL,
                zuzycie_kwh INTEGER NOT NULL,
                ogolem_sprzedaz_energii NUMERIC(10, 2) NOT NULL,
                ogolem_usluga_dystrybucji NUMERIC(10, 2) NOT NULL,
                grupa_taryfowa VARCHAR(10) NOT NULL,
                typ_taryfy VARCHAR(20) NOT NULL,
                energia_lacznie_zuzyta_w_roku_kwh INTEGER NOT NULL
            )
        """))
        
        # Indeksy dla electricity_invoices
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_rok ON electricity_invoices(rok)"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_invoice_number_year ON electricity_invoices(numer_faktury, rok)"))
        
        # Tabela electricity_invoice_blankiety
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS electricity_invoice_blankiety (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id INTEGER NOT NULL,
                rok INTEGER NOT NULL,
                numer_blankietu VARCHAR(100) NOT NULL,
                poczatek_podokresu DATE,
                koniec_podokresu DATE,
                ilosc_dzienna_kwh INTEGER,
                ilosc_nocna_kwh INTEGER,
                ilosc_calodobowa_kwh INTEGER,
                kwota_brutto NUMERIC(10, 2) NOT NULL,
                akcyza NUMERIC(10, 2) NOT NULL,
                energia_do_akcyzy_kwh INTEGER NOT NULL,
                nadplata_niedoplata NUMERIC(10, 2) NOT NULL,
                odsetki NUMERIC(10, 2) NOT NULL,
                termin_platnosci DATE NOT NULL,
                do_zaplaty NUMERIC(10, 2) NOT NULL,
                FOREIGN KEY (invoice_id) REFERENCES electricity_invoices(id) ON DELETE CASCADE
            )
        """))
        
        # Indeksy dla blankietów
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_invoice_id_blankiety ON electricity_invoice_blankiety(invoice_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_rok_blankiety ON electricity_invoice_blankiety(rok)"))
        
        # Tabela electricity_invoice_odczyty
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS electricity_invoice_odczyty (
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
                FOREIGN KEY (invoice_id) REFERENCES electricity_invoices(id) ON DELETE CASCADE
            )
        """))
        
        # Indeksy dla odczytów
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_invoice_id_odczyty ON electricity_invoice_odczyty(invoice_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_rok_odczyty ON electricity_invoice_odczyty(rok)"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_invoice_energy_type_zone ON electricity_invoice_odczyty(invoice_id, typ_energii, strefa)"))
        
        # Tabela electricity_invoice_sprzedaz_energii
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS electricity_invoice_sprzedaz_energii (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id INTEGER NOT NULL,
                rok INTEGER NOT NULL,
                data DATE,
                strefa VARCHAR(10),
                ilosc_kwh INTEGER NOT NULL,
                cena_za_kwh NUMERIC(10, 4) NOT NULL,
                naleznosc NUMERIC(10, 2) NOT NULL,
                vat_procent NUMERIC(5, 2) NOT NULL,
                FOREIGN KEY (invoice_id) REFERENCES electricity_invoices(id) ON DELETE CASCADE
            )
        """))
        
        # Indeksy dla sprzedaży energii
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_invoice_id_sprzedaz ON electricity_invoice_sprzedaz_energii(invoice_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_rok_sprzedaz ON electricity_invoice_sprzedaz_energii(rok)"))
        
        # Tabela electricity_invoice_oplaty_dystrybucyjne
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS electricity_invoice_oplaty_dystrybucyjne (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id INTEGER NOT NULL,
                rok INTEGER NOT NULL,
                typ_oplaty VARCHAR(50) NOT NULL,
                strefa VARCHAR(10),
                jednostka VARCHAR(20) NOT NULL,
                data DATE NOT NULL,
                ilosc_kwh INTEGER,
                ilosc_miesiecy INTEGER,
                wspolczynnik NUMERIC(10, 4),
                cena NUMERIC(10, 4) NOT NULL,
                naleznosc NUMERIC(10, 2) NOT NULL,
                vat_procent NUMERIC(5, 2) NOT NULL,
                FOREIGN KEY (invoice_id) REFERENCES electricity_invoices(id) ON DELETE CASCADE
            )
        """))
        
        # Indeksy dla opłat dystrybucyjnych
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_invoice_id_oplaty ON electricity_invoice_oplaty_dystrybucyjne(invoice_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_rok_oplaty ON electricity_invoice_oplaty_dystrybucyjne(rok)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_typ_oplaty ON electricity_invoice_oplaty_dystrybucyjne(typ_oplaty)"))
        
        # Tabela electricity_invoice_rozliczenie_okresy
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS electricity_invoice_rozliczenie_okresy (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id INTEGER NOT NULL,
                rok INTEGER NOT NULL,
                data_okresu DATE NOT NULL,
                numer_okresu INTEGER NOT NULL,
                FOREIGN KEY (invoice_id) REFERENCES electricity_invoices(id) ON DELETE CASCADE
            )
        """))
        
        # Indeksy dla rozliczenia okresów
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_invoice_id_okresy ON electricity_invoice_rozliczenie_okresy(invoice_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_rok_okresy ON electricity_invoice_rozliczenie_okresy(rok)"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_invoice_period_number ON electricity_invoice_rozliczenie_okresy(invoice_id, numer_okresu)"))
        
        # Przywróć tabelę electricity_bills (jeśli była używana)
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS electricity_bills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data VARCHAR(7) NOT NULL,
                local VARCHAR(50) NOT NULL,
                reading_id INTEGER,
                invoice_id INTEGER,
                local_id INTEGER,
                usage_kwh REAL NOT NULL,
                energy_cost_gross REAL NOT NULL,
                distribution_cost_gross REAL NOT NULL,
                total_net_sum REAL NOT NULL,
                total_gross_sum REAL NOT NULL,
                pdf_path VARCHAR(200),
                FOREIGN KEY (reading_id) REFERENCES electricity_readings(id),
                FOREIGN KEY (invoice_id) REFERENCES electricity_invoices(id),
                FOREIGN KEY (local_id) REFERENCES locals(id)
            )
        """))
    
    print("[OK] Szczegółowe tabele dla faktur prądu utworzone")


def downgrade():
    """Usuwa szczegółowe tabele dla faktur prądu."""
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS electricity_bills"))
        conn.execute(text("DROP TABLE IF EXISTS electricity_invoice_rozliczenie_okresy"))
        conn.execute(text("DROP TABLE IF EXISTS electricity_invoice_oplaty_dystrybucyjne"))
        conn.execute(text("DROP TABLE IF EXISTS electricity_invoice_sprzedaz_energii"))
        conn.execute(text("DROP TABLE IF EXISTS electricity_invoice_odczyty"))
        conn.execute(text("DROP TABLE IF EXISTS electricity_invoice_blankiety"))
        conn.execute(text("DROP TABLE IF EXISTS electricity_invoices"))
    
    print("[OK] Szczegółowe tabele dla faktur prądu usunięte")


if __name__ == "__main__":
    upgrade()
