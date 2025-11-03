"""Szczegółowa analiza problemu z okresem 2022-06."""

from db import SessionLocal, init_db
from models import Reading, Bill, Invoice
from meter_manager import calculate_local_usage

def analyze():
    """Szczegółowa analiza okresu 2022-06."""
    init_db()
    db = SessionLocal()
    
    try:
        period = "2022-06"
        
        current_reading = db.query(Reading).filter(Reading.data == period).first()
        previous_reading = db.query(Reading).filter(Reading.data < period).order_by(Reading.data.desc()).first()
        invoices = db.query(Invoice).filter(Invoice.data == period).all()
        bills = db.query(Bill).filter(Bill.data == period).all()
        
        print("=" * 80)
        print("ANALIZA PRZYCZYNY UJEMNEGO ZUZYCLA W OKRESIE 2022-06")
        print("=" * 80)
        
        # Odczyty
        print(f"\n1. ODCZYTY LICZNIKOW:")
        if previous_reading:
            print(f"   Poprzedni okres ({previous_reading.data}):")
            print(f"     water_meter_main: {previous_reading.water_meter_main} m3")
            print(f"     water_meter_5 (gora): {previous_reading.water_meter_5} m3")
            print(f"     water_meter_5b (gabinet): {previous_reading.water_meter_5b} m3")
        
        if current_reading:
            print(f"   Obecny okres ({current_reading.data}):")
            print(f"     water_meter_main: {current_reading.water_meter_main} m3")
            print(f"     water_meter_5 (gora): {current_reading.water_meter_5} m3")
            print(f"     water_meter_5b (gabinet): {current_reading.water_meter_5b} m3")
        
        # Obliczenia
        print(f"\n2. OBLICZENIA ZUZYCLA Z ODCZYTOW:")
        usage_gora = calculate_local_usage(current_reading, previous_reading, 'gora')
        usage_gabinet = calculate_local_usage(current_reading, previous_reading, 'gabinet')
        usage_dol = calculate_local_usage(current_reading, previous_reading, 'dol')
        
        calculated_total = usage_gora + usage_gabinet + usage_dol
        
        print(f"   Gora: {usage_gora:.2f} m3")
        print(f"   Gabinet: {usage_gabinet:.2f} m3")
        print(f"   Dol: {usage_dol:.2f} m3")
        print(f"   RAZEM: {calculated_total:.2f} m3")
        
        # Faktury
        print(f"\n3. FAKTURY:")
        total_invoice_usage = sum(inv.usage for inv in invoices)
        print(f"   Liczba faktur: {len(invoices)}")
        for inv in invoices:
            print(f"     - {inv.invoice_number}:")
            print(f"       Zuzycie: {inv.usage:.2f} m3")
            print(f"       Okres faktury: {inv.period_start} - {inv.period_stop}")
        print(f"   Suma zuzycia z faktur: {total_invoice_usage:.2f} m3")
        
        # Różnica
        print(f"\n4. ANALIZA ROZNICY:")
        difference = total_invoice_usage - calculated_total
        print(f"   Obliczone z odczytow: {calculated_total:.2f} m3")
        print(f"   Zuzycie z faktury: {total_invoice_usage:.2f} m3")
        print(f"   ROZNICA: {difference:.2f} m3")
        
        print(f"\n5. KOREKTA (zgodnie z logika systemu):")
        print(f"   Roznica ({difference:.2f} m3) zostala dodana do lokalu 'gora'")
        print(f"   Zuzycie gora przed korekta: {usage_gora:.2f} m3")
        print(f"   Zuzycie gora po korekcie: {usage_gora + difference:.2f} m3")
        
        # Rachunki
        print(f"\n6. ZAPISANE RACHUNKI:")
        for bill in bills:
            print(f"   {bill.local}: {bill.usage_m3:.2f} m3")
        
        # Wnioski
        print(f"\n7. WNIOSKI:")
        print(f"   PROBLEM: Faktura pokazuje {total_invoice_usage:.2f} m3, ale obliczenia z odczytow")
        print(f"           pokazuja {calculated_total:.2f} m3.")
        print(f"           Roznica wynosi {abs(difference):.2f} m3 ({difference:.2f} m3).")
        print(f"\n   MOZLIWE PRZYCZYNY:")
        print(f"   1. Faktura jest za niepelny okres rozliczeniowy")
        print(f"   2. Odczyty sa bledne lub nieaktualne")
        print(f"   3. Faktura nie pokrywa sie z okresem rozliczeniowym odczytow")
        print(f"   4. Zostal pominiety jeden z miesiecy (np. brak 2022-05)")
        print(f"   5. Faktura obejmuje inny okres niz okres odczytow")
        print(f"\n   DZIALANIE SYSTEMU:")
        print(f"   System automatycznie dodal roznice ({difference:.2f} m3) do lokalu 'gora',")
        print(f"   co spowodowalo ujemne zuzycie: {usage_gora + difference:.2f} m3")
        
    finally:
        db.close()

if __name__ == "__main__":
    analyze()


