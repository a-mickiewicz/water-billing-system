"""
Skrypt do poprawienia nr_of_subscription w bazie danych.
Dla faktur, gdzie okres rozliczeniowy to 1 miesiąc, ustawia nr_of_subscription = 1.
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import SessionLocal
from app.models.water import Invoice
from datetime import datetime

def fix_subscription_quantity():
    db = SessionLocal()
    try:
        # Pobierz wszystkie faktury
        invoices = db.query(Invoice).all()
        
        print(f"=== POPRAWIANIE ILOŚCI ABONAMENTU W BAZIE ===\n")
        print(f"Znaleziono {len(invoices)} faktur\n")
        
        updated_count = 0
        for invoice in invoices:
            # Sprawdź okres rozliczeniowy
            if invoice.period_start and invoice.period_stop:
                delta = invoice.period_stop - invoice.period_start
                days = delta.days
                
                # Jeśli okres to około 1 miesiąc (20-40 dni), ustaw nr_of_subscription = 1
                # Jeśli okres to około 2 miesiące (50-70 dni), ustaw nr_of_subscription = 2
                if 20 <= days <= 40:
                    if invoice.nr_of_subscription != 1:
                        print(f"Faktura {invoice.invoice_number} ({invoice.data}):")
                        print(f"  Okres: {invoice.period_start} - {invoice.period_stop} ({days} dni)")
                        print(f"  Zmiana: nr_of_subscription {invoice.nr_of_subscription} -> 1")
                        invoice.nr_of_subscription = 1
                        updated_count += 1
                elif 50 <= days <= 70:
                    if invoice.nr_of_subscription != 2:
                        print(f"Faktura {invoice.invoice_number} ({invoice.data}):")
                        print(f"  Okres: {invoice.period_start} - {invoice.period_stop} ({days} dni)")
                        print(f"  Zmiana: nr_of_subscription {invoice.nr_of_subscription} -> 2")
                        invoice.nr_of_subscription = 2
                        updated_count += 1
        
        if updated_count > 0:
            db.commit()
            print(f"\n[OK] Zaktualizowano {updated_count} faktur")
        else:
            print(f"\n[INFO] Brak faktur do aktualizacji")
            
    finally:
        db.close()

if __name__ == "__main__":
    fix_subscription_quantity()

