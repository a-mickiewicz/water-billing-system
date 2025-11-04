"""
Skrypt do generowania przykładowego rachunku za gaz.
Sprawdza faktury w bazie i generuje rachunki PDF.
"""

import sys
from pathlib import Path

# Dodaj główny katalog projektu do ścieżki
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import SessionLocal
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.models.gas import GasInvoice, GasBill
from app.services.gas.manager import GasBillingManager
from app.services.gas.bill_generator import generate_bill_pdf, generate_all_bills_for_period


def main():
    db = SessionLocal()
    try:
        print("=" * 60)
        print("GENEROWANIE RACHUNKÓW ZA GAZ")
        print("=" * 60)
        
        # Sprawdź czy są faktury gazu w bazie
        invoices = db.query(GasInvoice).order_by(desc(GasInvoice.data)).all()
        
        if not invoices:
            print("\n[ERROR] Brak faktur gazu w bazie danych!")
            print("Najpierw zaimportuj faktury gazu przez API lub bezpośrednio.")
            return
        
        print(f"\n[OK] Znaleziono {len(invoices)} faktur gazu w bazie")
        
        # Pokaż dostępne faktury
        print("\nDostępne faktury:")
        for inv in invoices[:5]:  # Pokaż pierwsze 5
            print(f"  - {inv.invoice_number} ({inv.data}): {inv.total_gross_sum:.2f} zł brutto")
        
        # Znajdź fakturę z poprawnymi danymi (suma brutto > 0)
        valid_invoice = None
        for inv in invoices:
            if inv.total_gross_sum > 0:
                valid_invoice = inv
                break
        
        if not valid_invoice:
            print("\n[ERROR] Nie znaleziono faktury z poprawnymi danymi (suma brutto > 0)")
            print("Sprawdź czy faktury zostały prawidłowo zaimportowane.")
            return
        
        period = valid_invoice.data
        print(f"\n[INFO] Używam okresu: {period} (faktura: {valid_invoice.invoice_number})")
        
        # Sprawdź czy rachunki już istnieją dla tego okresu
        existing_bills = db.query(GasBill).filter(GasBill.data == period).all()
        
        if existing_bills:
            print(f"[INFO] Znaleziono {len(existing_bills)} istniejących rachunków dla okresu {period}")
            # Sprawdź czy suma brutto jest poprawna
            if any(b.total_gross_sum > 0 for b in existing_bills):
                print("[INFO] Używam istniejących rachunków")
            else:
                print("[WARNING] Istniejące rachunki mają sumę brutto = 0, usuwam i regeneruję...")
                for bill in existing_bills:
                    db.delete(bill)
                db.commit()
                existing_bills = []
        
        if not existing_bills:
            print(f"[INFO] Generowanie rachunków dla okresu {period}...")
            manager = GasBillingManager()
            bills = manager.generate_bills_for_period(db, period)
            print(f"[OK] Wygenerowano {len(bills)} rachunków")
            existing_bills = bills
        
        # Wygeneruj PDF dla wszystkich rachunków
        print(f"\n[INFO] Generowanie plików PDF...")
        pdf_files = generate_all_bills_for_period(db, period)
        
        if pdf_files:
            print(f"\n[OK] Wygenerowano {len(pdf_files)} plików PDF:")
            for pdf_file in pdf_files:
                print(f"  - {pdf_file}")
        else:
            print("\n[WARNING] Nie wygenerowano żadnych plików PDF")
        
        # Podsumowanie
        print("\n" + "=" * 60)
        print("PODSUMOWANIE:")
        print("=" * 60)
        print(f"Okres: {period}")
        print(f"Faktura: {valid_invoice.invoice_number}")
        print(f"Rachunki: {len(existing_bills)}")
        print(f"Pliki PDF: {len(pdf_files)}")
        
        if existing_bills:
            print("\nSzczegóły rachunków:")
            for bill in existing_bills:
                print(f"  - Lokal: {bill.local}, Udział: {bill.cost_share*100:.0f}%, "
                      f"Suma brutto: {bill.total_gross_sum:.2f} zł")
        
    except Exception as e:
        print(f"\n[ERROR] Błąd: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    main()

