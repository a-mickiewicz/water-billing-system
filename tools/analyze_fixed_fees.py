"""
Analiza obliczeń opłat stałych dla faktur prądu.
"""

import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.electricity_invoice import (
    ElectricityInvoice,
    ElectricityInvoiceOplataDystrybucyjna
)
from app.services.electricity.manager import ElectricityBillingManager


def analyze_fixed_fees(invoice_number: str):
    """Analizuje opłaty stałe dla faktury."""
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
        
        # Oblicz liczbę dni w okresie faktury
        from datetime import timedelta
        days_in_period = (invoice.data_konca_okresu - invoice.data_poczatku_okresu).days + 1
        months_in_period = days_in_period / 30.0
        print(f"Liczba dni w okresie: {days_in_period}")
        print(f"Liczba miesięcy (przybliżona): {months_in_period:.2f}")
        print()
        
        # Pobierz opłaty stałe
        target_fee_names = [
            'Opłata stała sieciowa - układ 3-fazowy',
            'Opłata przejściowa > 1200 kWh',
            'Opłata mocowa ( > 2800 kWh)',
            'Opłata abonamentowa'
        ]
        
        oplaty = db.query(ElectricityInvoiceOplataDystrybucyjna).filter(
            ElectricityInvoiceOplataDystrybucyjna.invoice_id == invoice.id
        ).all()
        
        print("OPLATY STALE W FAKTURZE:")
        print("=" * 80)
        
        total_fees = 0.0
        for oplata in oplaty:
            if oplata.typ_oplaty in target_fee_names:
                naleznosc = float(oplata.naleznosc) if oplata.naleznosc else 0.0
                jednostka = oplata.jednostka
                ilosc = oplata.ilosc_kwh if oplata.ilosc_kwh else oplata.ilosc_miesiecy
                cena = float(oplata.cena) if oplata.cena else 0.0
                
                print(f"  {oplata.typ_oplaty}:")
                print(f"    Jednostka: {jednostka}")
                if ilosc:
                    print(f"    Ilosc: {ilosc}")
                if cena:
                    print(f"    Cena: {cena:.4f}")
                print(f"    Naleznosc (brutto): {naleznosc:.2f} zl")
                print()
                
                total_fees += naleznosc
        
        print(f"SUMA OPLAT STALYCH Z FAKTURY (brutto): {total_fees:.2f} zl")
        print()
        
        # Obecne obliczenia (BŁĘDNE - mnoży przez 2)
        print("OBECNE OBLICZENIA (BŁĘDNE):")
        print("=" * 80)
        print(f"1. Suma opłat stałych z faktury: {total_fees:.2f} zl")
        print(f"2. Pomnożone przez 2 (okres rozliczeniowy około 2 miesiące): {total_fees * 2:.2f} zl")
        print(f"3. Podzielone na 3 lokale: {(total_fees * 2) / 3.0:.2f} zl na lokal")
        print()
        
        # Poprawne obliczenia
        print("POPRAWNE OBLICZENIA:")
        print("=" * 80)
        print(f"1. Suma opłat stałych z faktury: {total_fees:.2f} zl")
        print(f"   (To jest już za cały okres faktury: {days_in_period} dni = {months_in_period:.2f} miesięcy)")
        print(f"2. Podzielone na 3 lokale: {total_fees / 3.0:.2f} zl na lokal")
        print()
        
        # Sprawdź jak manager oblicza
        manager = ElectricityBillingManager()
        current_calculation = manager.calculate_fixed_fees_per_local(invoice, db)
        print(f"OBLICZENIA Z MANAGERA (obecne): {current_calculation:.2f} zl na lokal")
        print()
        
        # Różnica
        correct_calculation = total_fees / 3.0
        difference = current_calculation - correct_calculation
        print(f"RÓŻNICA (obecne - poprawne): {difference:.2f} zl na lokal")
        print(f"To jest {difference / correct_calculation * 100:.1f}% więcej niż powinno być!")
        print()
        
        # Dla każdego lokalu
        print("DLA KAŻDEGO LOKALU:")
        print("=" * 80)
        print(f"  Obecne (błędne): {current_calculation:.2f} zl")
        print(f"  Poprawne: {correct_calculation:.2f} zl")
        print(f"  Różnica: {difference:.2f} zl")
        print()
        print(f"  Dla 3 lokali łącznie:")
        print(f"    Obecne: {current_calculation * 3:.2f} zl")
        print(f"    Poprawne: {correct_calculation * 3:.2f} zl")
        print(f"    Różnica: {difference * 3:.2f} zl")
        
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uzycie: python tools/analyze_fixed_fees.py <numer_faktury>")
        print("Przyklad: python tools/analyze_fixed_fees.py 'P/23666363/0002/24'")
        sys.exit(1)
    
    invoice_number = sys.argv[1]
    analyze_fixed_fees(invoice_number)

