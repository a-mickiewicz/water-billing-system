"""
Skrypt diagnostyczny do sprawdzania problemów z obliczeniami dla konkretnego okresu.
"""

from db import SessionLocal, init_db
from models import Reading, Invoice, Bill
from meter_manager import calculate_local_usage
from sqlalchemy import desc

def check_period(period: str):
    """Sprawdza odczyty i obliczenia dla konkretnego okresu."""
    init_db()
    db = SessionLocal()
    
    try:
        print("=" * 80)
        print(f"DIAGNOZA OKRESU: {period}")
        print("=" * 80)
        
        # Pobierz odczyty
        current_reading = db.query(Reading).filter(Reading.data == period).first()
        if not current_reading:
            print(f"[BLAD] Brak odczytu dla okresu {period}")
            return
        
        # Pobierz poprzedni odczyt
        previous_reading = db.query(Reading).filter(
            Reading.data < period
        ).order_by(desc(Reading.data)).first()
        
        print(f"\nODCZYTY LICZNIKOW:")
        print(f"   Obecny okres ({period}):")
        print(f"     water_meter_main: {current_reading.water_meter_main} m3")
        print(f"     water_meter_5 (gora): {current_reading.water_meter_5} m3")
        print(f"     water_meter_5b (gabinet): {current_reading.water_meter_5b} m3")
        print(f"     water_meter_5a (dol - obliczone): {current_reading.water_meter_main - (current_reading.water_meter_5 + current_reading.water_meter_5b):.2f} m3")
        
        if previous_reading:
            print(f"\n   Poprzedni okres ({previous_reading.data}):")
            print(f"     water_meter_main: {previous_reading.water_meter_main} m3")
            print(f"     water_meter_5 (gora): {previous_reading.water_meter_5} m3")
            print(f"     water_meter_5b (gabinet): {previous_reading.water_meter_5b} m3")
            print(f"     water_meter_5a (dol - obliczone): {previous_reading.water_meter_main - (previous_reading.water_meter_5 + previous_reading.water_meter_5b):.2f} m3")
        else:
            print(f"\n   [UWAGA] Brak poprzedniego odczytu (pierwszy odczyt w systemie)")
        
        # Oblicz zużycie dla każdego lokalu
        print(f"\nOBLICZENIA ZUZYCIA:")
        usage_gora = calculate_local_usage(current_reading, previous_reading, 'gora')
        usage_gabinet = calculate_local_usage(current_reading, previous_reading, 'gabinet')
        usage_dol = calculate_local_usage(current_reading, previous_reading, 'dol')
        
        print(f"   Gora: {usage_gora:.2f} m3")
        print(f"   Gabinet: {usage_gabinet:.2f} m3")
        print(f"   Dol: {usage_dol:.2f} m3")
        print(f"   RAZEM: {usage_gora + usage_gabinet + usage_dol:.2f} m3")
        
        if usage_dol < 0:
            print(f"\n[PROBLEM] Lokal 'dol' ma ujemne zuzycie!")
            print(f"   Analiza:")
            
            if previous_reading:
                diff_main = current_reading.water_meter_main - previous_reading.water_meter_main
                diff_gora = current_reading.water_meter_5 - previous_reading.water_meter_5
                diff_gabinet = current_reading.water_meter_5b - previous_reading.water_meter_5b
                
                print(f"     Roznica main: {diff_main:.2f} m3")
                print(f"     Roznica gora: {diff_gora:.2f} m3")
                print(f"     Roznica gabinet: {diff_gabinet:.2f} m3")
                print(f"     Roznica dol (main - gora - gabinet): {diff_main - (diff_gora + diff_gabinet):.2f} m3")
                
                # Sprawdź czy suma gora + gabinet nie przekracza main
                current_sum_sub = current_reading.water_meter_5 + current_reading.water_meter_5b
                previous_sum_sub = previous_reading.water_meter_5 + previous_reading.water_meter_5b
                
                print(f"\n     Sprawdzenie spójności:")
                print(f"       Obecny main: {current_reading.water_meter_main:.2f} m3")
                print(f"       Obecny gora+gabinet: {current_sum_sub:.2f} m3")
                print(f"       Roznica (main - gora - gabinet): {current_reading.water_meter_main - current_sum_sub:.2f} m3")
                
                if current_sum_sub > current_reading.water_meter_main:
                    print(f"     [BLAD] Suma gora+gabinet ({current_sum_sub:.2f}) > main ({current_reading.water_meter_main:.2f})!")
                    print(f"        To jest fizycznie niemożliwe - podliczniki nie mogą sumować się do więcej niż licznik główny!")
                
                if previous_sum_sub > previous_reading.water_meter_main:
                    print(f"     [BLAD] Poprzednia suma gora+gabinet ({previous_sum_sub:.2f}) > poprzedni main ({previous_reading.water_meter_main:.2f})!")
        
        # Sprawdź faktury
        invoices = db.query(Invoice).filter(Invoice.data == period).all()
        if invoices:
            print(f"\nFAKTURY DLA OKRESU:")
            total_invoice_usage = sum(inv.usage for inv in invoices)
            print(f"   Liczba faktur: {len(invoices)}")
            for inv in invoices:
                print(f"     - {inv.invoice_number}: {inv.usage:.2f} m3")
            print(f"   Suma zuzycia z faktur: {total_invoice_usage:.2f} m3")
            
            calculated_usage = usage_gora + usage_gabinet + usage_dol
            difference = total_invoice_usage - calculated_usage
            print(f"   Roznica (faktury - odczyty): {difference:.2f} m3")
        else:
            print(f"\n[UWAGA] Brak faktur dla okresu {period}")
        
        # Sprawdź wygenerowane rachunki
        bills = db.query(Bill).filter(Bill.data == period).all()
        if bills:
            print(f"\nRACHUNKI:")
            for bill in bills:
                if bill.local == 'dol':
                    print(f"   {bill.local}:")
                    print(f"     Zuzycie: {bill.usage_m3:.2f} m3")
                    print(f"     Suma brutto: {bill.gross_sum:.2f} zł")
                    if bill.usage_m3 < 0 or bill.gross_sum < 0:
                        print(f"     [PROBLEM] Ujemne wartosci!")
        
    finally:
        db.close()

if __name__ == "__main__":
    import sys
    
    period = sys.argv[1] if len(sys.argv) > 1 else "2024-04"
    check_period(period)

