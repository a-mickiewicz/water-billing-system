"""
Test sprawdzający czy abonament jest dzielony przez 3 dla każdego lokalu.
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import SessionLocal
from app.models.water import Invoice, Bill
from app.services.water.meter_manager import generate_bills_for_period

def test_subscription_division():
    db = SessionLocal()
    try:
        # Wybierz okres z fakturą
        period = "2023-12"
        
        # Pobierz fakturę
        invoice = db.query(Invoice).filter(Invoice.data == period).first()
        if not invoice:
            print(f"Brak faktury dla okresu {period}")
            return
        
        print(f"=== TEST DZIELENIA ABONAMENTU DLA {period} ===\n")
        print(f"Faktura: {invoice.invoice_number}")
        print(f"Abonament woda (za miesiac): {invoice.water_subscr_cost} zl")
        print(f"Abonament scieki (za miesiac): {invoice.sewage_subscr_cost} zl")
        print(f"Liczba miesiecy: {invoice.nr_of_subscription}")
        
        total_water_subscr = invoice.water_subscr_cost * invoice.nr_of_subscription
        total_sewage_subscr = invoice.sewage_subscr_cost * invoice.nr_of_subscription
        
        print(f"\nCalkowity abonament woda: {total_water_subscr} zl")
        print(f"Calkowity abonament scieki: {total_sewage_subscr} zl")
        print(f"Suma abonamentow: {total_water_subscr + total_sewage_subscr} zl")
        
        # Oblicz oczekiwany udział dla każdego lokalu (1/3)
        expected_water_share = total_water_subscr / 3
        expected_sewage_share = total_sewage_subscr / 3
        expected_total_share = expected_water_share + expected_sewage_share
        
        print(f"\n=== OCZEKIWANE UDZIALY (1/3 dla kazdego lokalu) ===")
        print(f"Abonament woda na lokal: {expected_water_share:.2f} zl")
        print(f"Abonament scieki na lokal: {expected_sewage_share:.2f} zl")
        print(f"Suma abonamentu na lokal: {expected_total_share:.2f} zl")
        
        # Pobierz rachunki
        bills = db.query(Bill).filter(Bill.data == period).all()
        
        if not bills:
            print(f"\nBrak rachunkow dla okresu {period}. Generowanie...")
            bills = generate_bills_for_period(db, period)
            db.commit()
        
        print(f"\n=== RZECZYWISTE UDZIALY W RACHUNKACH ===")
        total_water_share_sum = 0
        total_sewage_share_sum = 0
        total_share_sum = 0
        
        for bill in bills:
            print(f"\nLokal {bill.local}:")
            print(f"  Abonament woda: {bill.abonament_water_share:.2f} zl")
            print(f"  Abonament scieki: {bill.abonament_sewage_share:.2f} zl")
            print(f"  Suma abonamentu: {bill.abonament_total:.2f} zl")
            
            # Sprawdź czy jest równe 1/3
            water_diff = abs(bill.abonament_water_share - expected_water_share)
            sewage_diff = abs(bill.abonament_sewage_share - expected_sewage_share)
            total_diff = abs(bill.abonament_total - expected_total_share)
            
            if water_diff > 0.01:
                print(f"  [BLAD] Abonament woda rozni sie o {water_diff:.2f} zl!")
            else:
                print(f"  [OK] Abonament woda jest poprawny (1/3)")
            
            if sewage_diff > 0.01:
                print(f"  [BLAD] Abonament scieki rozni sie o {sewage_diff:.2f} zl!")
            else:
                print(f"  [OK] Abonament scieki jest poprawny (1/3)")
            
            if total_diff > 0.01:
                print(f"  [BLAD] Suma abonamentu rozni sie o {total_diff:.2f} zl!")
            else:
                print(f"  [OK] Suma abonamentu jest poprawna (1/3)")
            
            total_water_share_sum += bill.abonament_water_share
            total_sewage_share_sum += bill.abonament_sewage_share
            total_share_sum += bill.abonament_total
        
        print(f"\n=== PODSUMOWANIE ===")
        print(f"Suma abonamentow woda we wszystkich rachunkach: {total_water_share_sum:.2f} zl")
        print(f"Oczekiwana suma (3 lokale * 1/3): {total_water_subscr:.2f} zl")
        print(f"Roznica: {abs(total_water_share_sum - total_water_subscr):.2f} zl")
        
        print(f"\nSuma abonamentow scieki we wszystkich rachunkach: {total_sewage_share_sum:.2f} zl")
        print(f"Oczekiwana suma (3 lokale * 1/3): {total_sewage_subscr:.2f} zl")
        print(f"Roznica: {abs(total_sewage_share_sum - total_sewage_subscr):.2f} zl")
        
        print(f"\nSuma wszystkich abonamentow we wszystkich rachunkach: {total_share_sum:.2f} zl")
        print(f"Oczekiwana suma: {total_water_subscr + total_sewage_subscr:.2f} zl")
        print(f"Roznica: {abs(total_share_sum - (total_water_subscr + total_sewage_subscr)):.2f} zl")
        
        # Sprawdź czy suma się zgadza
        if abs(total_water_share_sum - total_water_subscr) < 0.01 and \
           abs(total_sewage_share_sum - total_sewage_subscr) < 0.01:
            print(f"\n[OK] Abonament jest poprawnie dzielony przez 3 dla wszystkich lokali!")
        else:
            print(f"\n[BLAD] Abonament NIE jest poprawnie dzielony!")
            
    finally:
        db.close()

if __name__ == "__main__":
    test_subscription_division()

