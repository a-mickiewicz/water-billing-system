"""
Skrypt do debugowania danych faktur w bazie.

Użycie:
    python tools/debug_invoice_data.py [NUMER_FAKTURY]

Przykład:
    python tools/debug_invoice_data.py "P/23666363/0002/24"
"""

import sys
import argparse
from pathlib import Path

# Dodaj ścieżkę do projektu
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import SessionLocal
from app.models.electricity_invoice import (
    ElectricityInvoice,
    ElectricityInvoiceOdczyt,
    ElectricityInvoiceSprzedazEnergii,
    ElectricityInvoiceOplataDystrybucyjna
)

def main():
    parser = argparse.ArgumentParser(
        description="Debugowanie danych faktur w bazie",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Przykłady użycia:
  python tools/debug_invoice_data.py "P/23666363/0002/24"
        """
    )
    parser.add_argument(
        "invoice_number",
        nargs="?",
        help="Numer faktury do debugowania (np. 'P/23666363/0002/24')"
    )
    
    args = parser.parse_args()
    
    if not args.invoice_number:
        parser.print_help()
        print("\n❌ Błąd: Musisz podać numer faktury jako argument!")
        print("Przykład: python tools/debug_invoice_data.py 'P/23666363/0002/24'")
        sys.exit(1)
    
    invoice_number = args.invoice_number
    
    db = SessionLocal()
    
    try:
        invoice = db.query(ElectricityInvoice).filter(
            ElectricityInvoice.numer_faktury == invoice_number
        ).first()
        
        if not invoice:
            print(f"❌ Nie znaleziono faktury: {invoice_number}")
            return
        
        print(f"Faktura: {invoice.numer_faktury}")
        print(f"Okres: {invoice.data_poczatku_okresu} - {invoice.data_konca_okresu}")
        print(f"Typ taryfy: {invoice.typ_taryfy}")
        print()
        
        # Odczyty
        print("=== ODCZYTY ===")
        odczyty = db.query(ElectricityInvoiceOdczyt).filter(
            ElectricityInvoiceOdczyt.invoice_id == invoice.id
        ).all()
        for o in odczyty:
            print(f"  {o.typ_energii} {o.strefa or 'CAŁODOBOWA'}: {o.data_odczytu}, {o.ilosc_kwh} kWh")
        print()
        
        # Sprzedaż energii
        print("=== SPRZEDAŻ ENERGII ===")
        sprzedaz = db.query(ElectricityInvoiceSprzedazEnergii).filter(
            ElectricityInvoiceSprzedazEnergii.invoice_id == invoice.id
        ).all()
        for s in sprzedaz:
            print(f"  Data: {s.data}, Strefa: {s.strefa or 'CAŁODOBOWA'}, kWh: {s.ilosc_kwh}, Cena: {s.cena_za_kwh}")
        print()
        
        # Opłaty dystrybucyjne
        print("=== OPŁATY DYSTRYBUCYJNE ===")
        oplaty = db.query(ElectricityInvoiceOplataDystrybucyjna).filter(
            ElectricityInvoiceOplataDystrybucyjna.invoice_id == invoice.id
        ).all()
        for o in oplaty:
            print(f"  Typ: {o.typ_oplaty}, Strefa: {o.strefa or 'N/A'}, Data: {o.data}, Jednostka: {o.jednostka}, Cena: {o.cena}, kWh: {o.ilosc_kwh}, Miesiące: {o.ilosc_miesiecy}")
        print()
        
    finally:
        db.close()

if __name__ == "__main__":
    main()

