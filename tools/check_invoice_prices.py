"""
Sprawdza rzeczywiste ceny w bazie danych dla faktury.
"""

import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.electricity_invoice import (
    ElectricityInvoice,
    ElectricityInvoiceSprzedazEnergii,
    ElectricityInvoiceOplataDystrybucyjna
)


def check_invoice_prices(invoice_number: str):
    """Sprawdza ceny w bazie danych dla faktury."""
    db: Session = SessionLocal()
    
    try:
        invoice = db.query(ElectricityInvoice).filter(
            ElectricityInvoice.numer_faktury == invoice_number
        ).first()
        
        if not invoice:
            print(f"Nie znaleziono faktury: {invoice_number}")
            return
        
        print(f"FAKTURA: {invoice.numer_faktury}")
        print(f"Okres: {invoice.data_poczatku_okresu} - {invoice.data_konca_okresu}")
        print()
        
        # Sprzedaż energii
        sales = db.query(ElectricityInvoiceSprzedazEnergii).filter(
            ElectricityInvoiceSprzedazEnergii.invoice_id == invoice.id
        ).all()
        
        print("SPRZEDAZ ENERGII:")
        for sale in sales:
            print(f"  Strefa: {sale.strefa or 'BRAK'}")
            print(f"  Ilosc kWh: {sale.ilosc_kwh}")
            print(f"  Cena za kWh: {float(sale.cena_za_kwh):.6f} zl/kWh")
            print(f"  Naleznosc: {float(sale.naleznosc):.2f} zl")
            print(f"  VAT: {float(sale.vat_procent):.2f}%")
            # Sprawdź czy cena * ilość = należność
            obliczona = float(sale.cena_za_kwh) * sale.ilosc_kwh
            print(f"  Cena * Ilosc: {obliczona:.2f} zl")
            print(f"  Roznica: {abs(obliczona - float(sale.naleznosc)):.2f} zl")
            print()
        
        # Opłaty dystrybucyjne
        oplaty = db.query(ElectricityInvoiceOplataDystrybucyjna).filter(
            ElectricityInvoiceOplataDystrybucyjna.invoice_id == invoice.id
        ).all()
        
        print("OPLATY DYSTRYBUCYJNE (tylko kWh):")
        for op in oplaty:
            if op.jednostka != "kWh":
                continue
            print(f"  Typ: {op.typ_oplaty}")
            print(f"  Strefa: {op.strefa or 'BRAK'}")
            print(f"  Cena: {float(op.cena):.6f} zl/kWh")
            print(f"  Ilosc kWh: {op.ilosc_kwh}")
            print(f"  Naleznosc: {float(op.naleznosc):.2f} zl")
            print()
        
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uzycie: python tools/check_invoice_prices.py <numer_faktury>")
        print("Przyklad: python tools/check_invoice_prices.py 'P/23666363/0002/24'")
        sys.exit(1)
    
    invoice_number = sys.argv[1]
    check_invoice_prices(invoice_number)

