"""
Skrypt diagnostyczny do sprawdzania wysokiego zużycia dla lokalu "gora" w okresach 2025-03 i 2025-06.
"""

from app.core.database import SessionLocal, init_db
from app.models.water import Reading, Invoice, Bill
from app.services.water.meter_manager import calculate_local_usage
from sqlalchemy import desc

def check_gora_usage(period: str):
    """Sprawdza odczyty i obliczenia dla lokalu gora w konkretnym okresie."""
    init_db()
    db = SessionLocal()
    
    try:
        print("=" * 80)
        print(f"DIAGNOZA ZUŻYCIA GORA DLA OKRESU: {period}")
        print("=" * 80)
        
        # Pobierz odczyty
        current_reading = db.query(Reading).filter(Reading.data == period).first()
        if not current_reading:
            print(f"[BŁĄD] Brak odczytu dla okresu {period}")
            return
        
        # Pobierz poprzedni odczyt
        previous_reading = db.query(Reading).filter(
            Reading.data < period
        ).order_by(desc(Reading.data)).first()
        
        print(f"\n1. ODCZYTY LICZNIKÓW:")
        print(f"   Obecny okres ({period}):")
        print(f"     water_meter_main: {current_reading.water_meter_main} m3")
        print(f"     water_meter_5 (gora): {current_reading.water_meter_5} m3")
        print(f"     water_meter_5a (gabinet): {current_reading.water_meter_5a} m3")
        
        if previous_reading:
            print(f"\n   Poprzedni okres ({previous_reading.data}):")
            print(f"     water_meter_main: {previous_reading.water_meter_main} m3")
            print(f"     water_meter_5 (gora): {previous_reading.water_meter_5} m3")
            print(f"     water_meter_5a (gabinet): {previous_reading.water_meter_5a} m3")
            
            # Oblicz różnice
            diff_main = current_reading.water_meter_main - previous_reading.water_meter_main
            diff_gora = current_reading.water_meter_5 - previous_reading.water_meter_5
            diff_gabinet = current_reading.water_meter_5a - previous_reading.water_meter_5a
            diff_dol = diff_main - (diff_gora + diff_gabinet)
            
            print(f"\n   ROZNICE (zuzycie z odczytow):")
            print(f"     main: {diff_main:.2f} m3")
            print(f"     gora: {diff_gora:.2f} m3")
            print(f"     gabinet: {diff_gabinet:.2f} m3")
            print(f"     dol (obliczone): {diff_dol:.2f} m3")
            print(f"     SUMA: {diff_gora + diff_gabinet + diff_dol:.2f} m3")
        else:
            print(f"\n   [INFO] Brak poprzedniego odczytu - to pierwszy odczyt")
        
        # Pobierz faktury
        invoices = db.query(Invoice).filter(Invoice.data == period).order_by(Invoice.period_start).all()
        print(f"\n2. FAKTURY DLA OKRESU {period}:")
        if invoices:
            total_invoice_usage = 0
            for inv in invoices:
                print(f"   Faktura {inv.invoice_number}:")
                print(f"     Zuzycie: {inv.usage} m3")
                print(f"     Okres: {inv.period_start} - {inv.period_stop}")
                print(f"     Koszt wody: {inv.water_cost_m3} zl/m3")
                print(f"     Koszt sciekow: {inv.sewage_cost_m3} zl/m3")
                total_invoice_usage += inv.usage
            print(f"\n   SUMA zuzycia z faktur: {total_invoice_usage:.2f} m3")
        else:
            print(f"   [BŁĄD] Brak faktur dla okresu {period}")
        
        # Pobierz rachunki
        bills = db.query(Bill).filter(Bill.data == period).all()
        print(f"\n3. RACHUNKI DLA OKRESU {period}:")
        if bills:
            for bill in bills:
                print(f"   Lokal {bill.local}:")
                print(f"     Zuzycie: {bill.usage_m3} m3")
                print(f"     Wartosc odczytu: {bill.reading_value} m3")
                print(f"     Koszt netto: {bill.net_sum} zl")
                print(f"     Koszt brutto: {bill.gross_sum} zl")
        else:
            print(f"   [INFO] Brak rachunków dla okresu {period}")
        
        # Sprawdź kompensację z poprzedniego okresu
        if previous_reading:
            prev_period = previous_reading.data
            prev_bills = db.query(Bill).filter(
                Bill.data == prev_period,
                Bill.local == 'dol'
            ).all()
            
            print(f"\n4. SPRAWDZENIE KOMPENSACJI Z POPRZEDNIEGO OKRESU ({prev_period}):")
            compensation = 0.0
            for prev_bill in prev_bills:
                if prev_bill.usage_m3 < 0:
                    compensation = abs(prev_bill.usage_m3)
                    print(f"   [ZNALEZIONO] Ujemne zuzycie dol w poprzednim okresie: {prev_bill.usage_m3:.2f} m3")
                    print(f"   Kompensacja dodana do gora: {compensation:.2f} m3")
                else:
                    print(f"   Zuzycie dol w poprzednim okresie: {prev_bill.usage_m3:.2f} m3 (dodatnie)")
        
        # Oblicz korektę z faktury
        if previous_reading and invoices:
            calculated_total = diff_gora + diff_gabinet + diff_dol
            total_invoice_usage = sum(inv.usage for inv in invoices)
            usage_adjustment = total_invoice_usage - calculated_total
            
            print(f"\n5. KOREKTA Z RÓŻNICY FAKTURA vs OBLICZENIA:")
            print(f"   Suma roznic odczytow: {calculated_total:.2f} m3")
            print(f"   Zuzycie z faktury: {total_invoice_usage:.2f} m3")
            print(f"   ROZNICA (korekta): {usage_adjustment:.2f} m3")
            if abs(usage_adjustment) > 0.01:
                print(f"   [INFO] Ta różnica jest dodawana do 'gora'")
        
        # Sprawdź czy był wymieniony licznik główny
        if previous_reading:
            meter_replaced = current_reading.water_meter_main < previous_reading.water_meter_main
            if meter_replaced:
                print(f"\n6. WYMIANA LICZNIKA GŁÓWNEGO:")
                print(f"   [WYKRYTO] Licznik główny został wymieniony")
                print(f"   Poprzedni stan: {previous_reading.water_meter_main} m3")
                print(f"   Nowy stan: {current_reading.water_meter_main} m3")
        
        # Podsumowanie dla gora
        bill_gora = db.query(Bill).filter(
            Bill.data == period,
            Bill.local == 'gora'
        ).first()
        
        if bill_gora:
            print(f"\n7. PODSUMOWANIE DLA GORA:")
            print(f"   Zuzycie w rachunku: {bill_gora.usage_m3} m3")
            if previous_reading:
                base_usage = diff_gora
                print(f"   Bazowe zuzycie (roznica odczytow): {base_usage:.2f} m3")
                
                # Oblicz komponenty
                if previous_reading:
                    prev_bills_dol = db.query(Bill).filter(
                        Bill.data == previous_reading.data,
                        Bill.local == 'dol'
                    ).all()
                    compensation = abs(prev_bills_dol[0].usage_m3) if prev_bills_dol and prev_bills_dol[0].usage_m3 < 0 else 0.0
                    
                    calculated_total = diff_gora + diff_gabinet + diff_dol
                    total_invoice_usage = sum(inv.usage for inv in invoices)
                    usage_adjustment = total_invoice_usage - calculated_total
                    
                    print(f"   Kompensacja z poprzedniego okresu: {compensation:.2f} m3")
                    print(f"   Korekta z faktury: {usage_adjustment:.2f} m3")
                    print(f"   RAZEM: {base_usage + compensation + usage_adjustment:.2f} m3")
        
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
    db = SessionLocal()
    
    # Sprawdz jakie okresy sa dostepne
    print("Dostepne okresy w bazie:")
    readings = db.query(Reading.data).order_by(Reading.data).all()
    for r in readings:
        print(f"  {r.data}")
    db.close()
    
    print("\n" + "="*80)
    print("Sprawdzanie zuzycia gora dla okresow 2025-03 i 2025-06\n")
    
    check_gora_usage("2025-03")
    print("\n\n")
    check_gora_usage("2025-06")

