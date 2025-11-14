"""
Skrypt do sprawdzenia dlaczego zużycie gora w 2023-12 wynosi 37,9 m³ zamiast 19 m³.
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import SessionLocal
from app.models.water import Reading, Bill, Invoice
from sqlalchemy import desc

def check_2023_12():
    db = SessionLocal()
    try:
        period = "2023-12"
        
        # Pobierz odczyt dla 2023-12
        current_reading = db.query(Reading).filter(Reading.data == period).first()
        if not current_reading:
            print(f"❌ Brak odczytu dla okresu {period}")
            return
        
        print(f"=== ODCZYT DLA {period} ===")
        print(f"Licznik główny: {current_reading.water_meter_main}")
        print(f"Licznik 5 (gora): {current_reading.water_meter_5}")
        print(f"Licznik 5a (gabinet): {current_reading.water_meter_5a}")
        
        # Pobierz poprzedni odczyt
        previous_reading = db.query(Reading).filter(Reading.data < period).order_by(desc(Reading.data)).first()
        if not previous_reading:
            print(f"❌ Brak poprzedniego odczytu")
            return
        
        print(f"\n=== POPRZEDNI ODCZYT ({previous_reading.data}) ===")
        print(f"Licznik główny: {previous_reading.water_meter_main}")
        print(f"Licznik 5 (gora): {previous_reading.water_meter_5}")
        print(f"Licznik 5a (gabinet): {previous_reading.water_meter_5a}")
        
        # Oblicz różnice
        diff_gora = current_reading.water_meter_5 - previous_reading.water_meter_5
        diff_gabinet = current_reading.water_meter_5a - previous_reading.water_meter_5a
        diff_main = current_reading.water_meter_main - previous_reading.water_meter_main
        diff_dol = diff_main - (diff_gora + diff_gabinet)
        
        print(f"\n=== ROZNICE ODCZYTOW ===")
        print(f"Gora: {diff_gora} m3")
        print(f"Gabinet: {diff_gabinet} m3")
        print(f"Dol: {diff_dol} m3")
        print(f"Glowny: {diff_main} m3")
        
        # Sprawdź rachunki dla poprzedniego okresu
        prev_period = previous_reading.data
        prev_bills = db.query(Bill).filter(Bill.data == prev_period).all()
        
        print(f"\n=== RACHUNKI DLA {prev_period} ===")
        for bill in prev_bills:
            print(f"Lokal {bill.local}: zuzycie = {bill.usage_m3} m3")
            if bill.local == 'dol' and bill.usage_m3 < 0:
                print(f"  [UWAGA] UJEMNE ZUZYCIE - kompensacja bedzie dodana do gora w nastepnym okresie")
        
        # Sprawdź faktury dla 2023-12
        invoices = db.query(Invoice).filter(Invoice.data == period).all()
        print(f"\n=== FAKTURY DLA {period} ===")
        total_invoice_usage = 0
        for inv in invoices:
            print(f"Faktura {inv.invoice_number}: zuzycie = {inv.usage} m3")
            total_invoice_usage += inv.usage
        
        print(f"Suma zuzycia z faktur: {total_invoice_usage} m3")
        
        # Oblicz korektę
        calculated_total = diff_gora + diff_gabinet + diff_dol
        usage_adjustment = total_invoice_usage - calculated_total
        
        print(f"\n=== KOREKTA Z FAKTURY ===")
        print(f"Obliczone z odczytow: {calculated_total} m3")
        print(f"Zuzycie z faktur: {total_invoice_usage} m3")
        print(f"Roznica (korekta): {usage_adjustment} m3")
        if abs(usage_adjustment) > 0.01:
            print(f"  [UWAGA] Ta roznica jest dodawana do 'gora'!")
        
        # Sprawdź rachunki dla 2023-12
        bills = db.query(Bill).filter(Bill.data == period).all()
        print(f"\n=== RACHUNKI DLA {period} ===")
        for bill in bills:
            print(f"Lokal {bill.local}: zuzycie = {bill.usage_m3} m3")
            if bill.local == 'gora':
                compensation = 0
                for prev_bill in prev_bills:
                    if prev_bill.local == 'dol' and prev_bill.usage_m3 < 0:
                        compensation = abs(prev_bill.usage_m3)
                        break
                print(f"  Roznica odczytow: {diff_gora} m3")
                print(f"  Kompensacja z poprzedniego: {compensation} m3")
                print(f"  Korekta z faktury: {usage_adjustment} m3")
                calculated_sum = diff_gora + compensation + usage_adjustment
                print(f"  OBLICZONA SUMA: {calculated_sum} m3")
                print(f"  ZAPISANA W RACHUNKU: {bill.usage_m3} m3")
                print(f"  ROZNICA: {bill.usage_m3 - calculated_sum} m3")
                
        # Sprawdź czy brakuje okresu 2023-11
        reading_2023_11 = db.query(Reading).filter(Reading.data == "2023-11").first()
        if not reading_2023_11:
            print(f"\n[UWAGA] BRAK ODCZYTU DLA 2023-11!")
            print(f"   System uzywa odczytu z {prev_period} jako poprzedniego")
            print(f"   To oznacza, ze roznica odczytow obejmuje 2 miesiace (listopad + grudzien)")
            print(f"   Ale faktura 2023-12 moze obejmowac tylko grudzien!")
            
            # Sprawdź czy może być problem z tym, że faktura obejmuje tylko grudzień
            # ale odczyty obejmują listopad + grudzień
            if total_invoice_usage > calculated_total:
                print(f"\n  [ANALIZA] Mozliwy problem:")
                print(f"    Roznica odczytow (2 miesiace): {calculated_total} m3")
                print(f"    Zuzycie z faktury (moze tylko grudzien): {total_invoice_usage} m3")
                print(f"    Roznica: {total_invoice_usage - calculated_total} m3")
                print(f"    To moze byc zuzycie z listopada, ktore nie bylo rozliczone!")
            
    finally:
        db.close()

if __name__ == "__main__":
    check_2023_12()

