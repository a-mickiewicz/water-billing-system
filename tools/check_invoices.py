"""Sprawdza jakie faktury są w bazie danych."""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import SessionLocal
from app.models.electricity_invoice import ElectricityInvoice

db = SessionLocal()
try:
    invoices = db.query(ElectricityInvoice).order_by(ElectricityInvoice.numer_faktury).all()
    print(f"Znaleziono {len(invoices)} faktur:")
    for inv in invoices:
        print(f"  - {inv.numer_faktury} (rok: {inv.rok}, okres: {inv.data_poczatku_okresu} - {inv.data_konca_okresu})")
finally:
    db.close()

