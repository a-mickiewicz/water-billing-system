"""
Ręczna poprawka dla faktury 2023-12 - ustawia nr_of_subscription = 1
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import SessionLocal
from app.models.water import Invoice

def fix_2023_12():
    db = SessionLocal()
    try:
        period = "2023-12"
        
        invoice = db.query(Invoice).filter(Invoice.data == period).first()
        if not invoice:
            print(f"Brak faktury dla okresu {period}")
            return
        
        print(f"=== POPRAWKA DLA FAKTURY {period} ===\n")
        print(f"Faktura: {invoice.invoice_number}")
        print(f"Okres: {invoice.period_start} - {invoice.period_stop}")
        print(f"Obecna wartość nr_of_subscription: {invoice.nr_of_subscription}")
        
        if invoice.nr_of_subscription != 1:
            print(f"\nZmiana: nr_of_subscription {invoice.nr_of_subscription} -> 1")
            invoice.nr_of_subscription = 1
            db.commit()
            print(f"[OK] Zaktualizowano fakturę")
        else:
            print(f"\n[INFO] Wartość jest już poprawna (1)")
            
    finally:
        db.close()

if __name__ == "__main__":
    fix_2023_12()

