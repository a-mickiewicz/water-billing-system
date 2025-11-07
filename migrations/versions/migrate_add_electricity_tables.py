"""
Migracja: Dodanie tabel dla prądu.
Tworzy tabele: electricity_readings, electricity_invoices, electricity_bills.
"""

from sqlalchemy import text
from app.core.database import engine


def upgrade():
    """Tworzy tabele dla prądu."""
    
    # Tabela electricity_readings
    engine.execute(text("""
        CREATE TABLE IF NOT EXISTS electricity_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data VARCHAR(7) NOT NULL UNIQUE,
            
            -- LICZNIK GŁÓWNY DOM
            licznik_dom_jednotaryfowy BOOLEAN NOT NULL DEFAULT 0,
            odczyt_dom REAL,
            odczyt_dom_I REAL,
            odczyt_dom_II REAL,
            
            -- PODLICZNIK DÓŁ
            licznik_dol_jednotaryfowy BOOLEAN NOT NULL DEFAULT 0,
            odczyt_dol REAL,
            odczyt_dol_I REAL,
            odczyt_dol_II REAL,
            
            -- PODLICZNIK GABINET
            odczyt_gabinet REAL NOT NULL,
            
            CHECK (
                (licznik_dom_jednotaryfowy = 1 AND odczyt_dom IS NOT NULL AND odczyt_dom_I IS NULL AND odczyt_dom_II IS NULL) OR
                (licznik_dom_jednotaryfowy = 0 AND odczyt_dom IS NULL AND odczyt_dom_I IS NOT NULL AND odczyt_dom_II IS NOT NULL)
            ),
            CHECK (
                (licznik_dol_jednotaryfowy = 1 AND odczyt_dol IS NOT NULL AND odczyt_dol_I IS NULL AND odczyt_dol_II IS NULL) OR
                (licznik_dol_jednotaryfowy = 0 AND odczyt_dol IS NULL AND odczyt_dol_I IS NOT NULL AND odczyt_dol_II IS NOT NULL)
            )
        )
    """))
    
    # Tabela electricity_invoices
    engine.execute(text("""
        CREATE TABLE IF NOT EXISTS electricity_invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data VARCHAR(7) NOT NULL,
            invoice_number VARCHAR(100) NOT NULL,
            period_start DATE NOT NULL,
            period_stop DATE NOT NULL,
            usage_kwh REAL NOT NULL,
            energy_price_net REAL NOT NULL,
            energy_value_net REAL NOT NULL,
            energy_vat_amount REAL NOT NULL,
            energy_value_gross REAL NOT NULL,
            distribution_fees_net REAL NOT NULL DEFAULT 0.0,
            distribution_fees_vat REAL NOT NULL DEFAULT 0.0,
            distribution_fees_gross REAL NOT NULL DEFAULT 0.0,
            vat_rate REAL NOT NULL,
            vat_amount REAL NOT NULL,
            total_net_sum REAL NOT NULL,
            total_gross_sum REAL NOT NULL,
            amount_to_pay REAL NOT NULL,
            payment_due_date DATE NOT NULL
        )
    """))
    
    # Tabela electricity_bills
    engine.execute(text("""
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
    
    print("[OK] Tabele dla prądu utworzone")


def downgrade():
    """Usuwa tabele dla prądu."""
    engine.execute(text("DROP TABLE IF EXISTS electricity_bills"))
    engine.execute(text("DROP TABLE IF EXISTS electricity_invoices"))
    engine.execute(text("DROP TABLE IF EXISTS electricity_readings"))
    print("[OK] Tabele dla prądu usunięte")


if __name__ == "__main__":
    upgrade()

