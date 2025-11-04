"""Sprawdza szczegółowo przyczynę ujemnego zużycia dla lokalu gora w okresie 2022-06."""

from app.core.database import SessionLocal, init_db
from app.models.water import Reading, Bill, Invoice
from app.services.water.meter_manager import calculate_local_usage

def analyze_gora_issue():
    """Analizuje problem z lokalem gora w okresie 2022-06."""
    init_db()
    db = SessionLocal()
    
    try:
        period = "2022-06"
        
        # Pobierz odczyty
        current_reading = db.query(Reading).filter(Reading.data == period).first()
        previous_reading = db.query(Reading).filter(Reading.data < period).order_by(Reading.data.desc()).first()
        
        print("=" * 80)
        print("ANALIZA PROBLEMU Z LOKALEM GORA - OKRES 2022-06")
        print("=" * 80)
        
        print(f"\nODCZYTY:")
        if previous_reading:
            print(f"  Poprzedni okres ({previous_reading.data}):")
            print(f"    water_meter_5 (gora): {previous_reading.water_meter_5} m3")
        else:
            print(f"  [UWAGA] Brak poprzedniego odczytu!")
        
        if current_reading:
            print(f"  Obecny okres ({current_reading.data}):")
            print(f"    water_meter_5 (gora): {current_reading.water_meter_5} m3")
        
        # Oblicz zużycie
        usage_gora = calculate_local_usage(current_reading, previous_reading, 'gora')
        print(f"\nOBLICZONE ZUZYCIE GORA: {usage_gora:.2f} m3")
        
        if usage_gora < 0:
            print(f"\n[PROBLEM] Ujemne zuzycie!")
            if previous_reading:
                print(f"\nANALIZA:")
                print(f"  Poprzedni odczyt gora: {previous_reading.water_meter_5} m3")
                print(f"  Obecny odczyt gora: {current_reading.water_meter_5} m3")
                print(f"  Roznica: {current_reading.water_meter_5 - previous_reading.water_meter_5} m3")
                print(f"\n  Przyczyna: Obecny odczyt ({current_reading.water_meter_5}) jest MNIEJSZY niz poprzedni ({previous_reading.water_meter_5})!")
                print(f"  To jest fizycznie niemozliwe - licznik nie moze sie cofac!")
                print(f"  Mozliwe przyczyny:")
                print(f"    1. Bledne odczyty w bazie danych")
                print(f"    2. Licznik zostal wymieniony (ale nie zostal to wykryty)")
                print(f"    3. Odczyty zostaly wprowadzone w zlej kolejnosci")
        
        # Sprawdz faktury
        invoices = db.query(Invoice).filter(Invoice.data == period).all()
        if invoices:
            total_invoice_usage = sum(inv.usage for inv in invoices)
            print(f"\nFAKTURY:")
            print(f"  Liczba faktur: {len(invoices)}")
            print(f"  Suma zuzycia z faktur: {total_invoice_usage:.2f} m3")
            
            # Sprawdz wszystkie zuzycia lokali
            bills = db.query(Bill).filter(Bill.data == period).all()
            calculated_total = sum(b.usage_m3 for b in bills)
            print(f"\n  Obliczone zuzycie (suma rachunkow): {calculated_total:.2f} m3")
            print(f"  Roznica (faktury - obliczenia): {total_invoice_usage - calculated_total:.2f} m3")
        
        # Sprawdz czy byla korekta
        bill_gora = db.query(Bill).filter(Bill.data == period, Bill.local == 'gora').first()
        if bill_gora:
            print(f"\nRACHUNEK GORA:")
            print(f"  Zuzycie w rachunku: {bill_gora.usage_m3:.2f} m3")
            if bill_gora.usage_m3 != usage_gora:
                print(f"  [INFO] Roznica miedzy obliczonym ({usage_gora:.2f}) a zapisanym ({bill_gora.usage_m3:.2f})")
                print(f"         Mozliwe, ze zostala dodana korekta z faktury")
        
    finally:
        db.close()

if __name__ == "__main__":
    analyze_gora_issue()


