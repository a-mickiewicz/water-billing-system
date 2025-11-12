"""Sprawdza faktury prądu w bazie i ich rok."""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import SessionLocal
from app.models.electricity_invoice import ElectricityInvoice

db = SessionLocal()
try:
    invoices = db.query(ElectricityInvoice).all()
    print(f"Znaleziono {len(invoices)} faktur prądu:")
    print()
    for inv in invoices:
        print(f"ID: {inv.id}, Numer: {inv.numer_faktury}, Rok: {inv.rok}")
    
    # Sprawdź unikalne lata
    from sqlalchemy import distinct, func
    years = db.query(distinct(ElectricityInvoice.rok)).order_by(ElectricityInvoice.rok).all()
    print()
    print("Dostępne lata:")
    for year in years:
        print(f"  - {year[0]}")
finally:
    db.close()

