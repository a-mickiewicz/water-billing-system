"""
Sprawdza szczegoly faktury i jak zostaly obliczone koszty wody i sciekow.
"""

from app.core.database import SessionLocal, init_db
from app.models.water import Invoice, Bill, Reading
from sqlalchemy import desc

def check_invoice_details(invoice_number: str):
    init_db()
    db = SessionLocal()
    
    try:
        print("=" * 80)
        print(f"ANALIZA FAKTURY: {invoice_number}")
        print("=" * 80)
        
        # Znajdz fakture
        invoice = db.query(Invoice).filter(Invoice.invoice_number == invoice_number).first()
        
        if not invoice:
            print(f"[BLAD] Nie znaleziono faktury {invoice_number}")
            return
        
        print(f"\n1. DANE FAKTURY:")
        print(f"   Numer faktury: {invoice.invoice_number}")
        print(f"   Okres rozliczeniowy (data): {invoice.data}")
        print(f"   Okres faktury: {invoice.period_start} - {invoice.period_stop}")
        print(f"   Zuzycie: {invoice.usage} m3")
        print(f"   Koszt wody za m3: {invoice.water_cost_m3} zl/m3")
        print(f"   Koszt sciekow za m3: {invoice.sewage_cost_m3} zl/m3")
        print(f"   Liczba abonamentow: {invoice.nr_of_subscription}")
        print(f"   Koszt abonamentu wody: {invoice.water_subscr_cost} zl")
        print(f"   Koszt abonamentu sciekow: {invoice.sewage_subscr_cost} zl")
        print(f"   VAT: {invoice.vat * 100:.1f}%")
        print(f"   Suma brutto faktury: {invoice.gross_sum} zl")
        
        # Sprawdz odczyty dla tego okresu
        reading = db.query(Reading).filter(Reading.data == invoice.data).first()
        if reading:
            print(f"\n2. ODCZYTY LICZNIKOW DLA OKRESU {invoice.data}:")
            print(f"   water_meter_main: {reading.water_meter_main} m3")
            print(f"   water_meter_5 (gora): {reading.water_meter_5} m3")
            print(f"   water_meter_5a (gabinet): {reading.water_meter_5a} m3")
            
            # Sprawdz poprzedni odczyt
            previous_reading = db.query(Reading).filter(
                Reading.data < invoice.data
            ).order_by(desc(Reading.data)).first()
            
            if previous_reading:
                print(f"\n   Poprzedni odczyt ({previous_reading.data}):")
                print(f"     water_meter_main: {previous_reading.water_meter_main} m3")
                print(f"     water_meter_5 (gora): {previous_reading.water_meter_5} m3")
                print(f"     water_meter_5a (gabinet): {previous_reading.water_meter_5a} m3")
                
                # Oblicz roznice
                diff_main = reading.water_meter_main - previous_reading.water_meter_main
                diff_gora = reading.water_meter_5 - previous_reading.water_meter_5
                diff_gabinet = reading.water_meter_5a - previous_reading.water_meter_5a
                diff_dol = diff_main - (diff_gora + diff_gabinet)
                
                print(f"\n   ROZNICE (zuzycie z odczytow):")
                print(f"     main: {diff_main:.2f} m3")
                print(f"     gora: {diff_gora:.2f} m3")
                print(f"     gabinet: {diff_gabinet:.2f} m3")
                print(f"     dol: {diff_dol:.2f} m3")
                print(f"     SUMA: {diff_gora + diff_gabinet + diff_dol:.2f} m3")
                
                # Porownaj z faktura
                calculated_total = diff_gora + diff_gabinet + diff_dol
                print(f"\n   POROWNANIE:")
                print(f"     Zuzycie z odczytow: {calculated_total:.2f} m3")
                print(f"     Zuzycie z faktury: {invoice.usage:.2f} m3")
                print(f"     ROZNICA: {invoice.usage - calculated_total:.2f} m3")
        else:
            print(f"\n[BRAK ODCZYTU] dla okresu {invoice.data}")
        
        # Sprawdz rachunki wygenerowane z tej faktury
        bills = db.query(Bill).filter(Bill.invoice_id == invoice.id).all()
        if bills:
            print(f"\n3. RACHUNKI WYGENEROWANE Z TEJ FAKTURY:")
            total_usage = 0
            total_cost_water = 0
            total_cost_sewage = 0
            total_subscr = 0
            
            for bill in bills:
                print(f"\n   Lokal {bill.local}:")
                print(f"     Zuzycie: {bill.usage_m3} m3")
                print(f"     Koszt wody: {bill.cost_water} zl")
                print(f"     Koszt sciekow: {bill.cost_sewage} zl")
                print(f"     Koszt zuzycia (woda + scieki): {bill.cost_usage_total} zl")
                print(f"     Abonament wody: {bill.abonament_water_share} zl")
                print(f"     Abonament sciekow: {bill.abonament_sewage_share} zl")
                print(f"     Abonament razem: {bill.abonament_total} zl")
                print(f"     Suma netto: {bill.net_sum} zl")
                print(f"     Suma brutto: {bill.gross_sum} zl")
                
                total_usage += bill.usage_m3
                total_cost_water += bill.cost_water
                total_cost_sewage += bill.cost_sewage
                total_subscr += bill.abonament_total
            
            print(f"\n   PODSUMOWANIE WSZYSTKICH LOKALI:")
            print(f"     Suma zuzycia: {total_usage:.2f} m3")
            print(f"     Suma kosztow wody: {total_cost_water:.2f} zl")
            print(f"     Suma kosztow sciekow: {total_cost_sewage:.2f} zl")
            print(f"     Suma abonamentow: {total_subscr:.2f} zl")
            print(f"     Suma netto: {sum(b.net_sum for b in bills):.2f} zl")
            print(f"     Suma brutto: {sum(b.gross_sum for b in bills):.2f} zl")
            
            # Sprawdz jak zostaly obliczone koszty
            print(f"\n4. JAK ZOSTALY OBLICZONE KOSZTY:")
            print(f"\n   Dla kazdego lokalu:")
            print(f"     Koszt wody = zuzycie * {invoice.water_cost_m3} zl/m3")
            print(f"     Koszt sciekow = zuzycie * {invoice.sewage_cost_m3} zl/m3")
            print(f"     Abonament wody = {invoice.water_subscr_cost} zl / 3 = {invoice.water_subscr_cost / 3:.2f} zl")
            print(f"     Abonament sciekow = {invoice.sewage_subscr_cost} zl / 3 = {invoice.sewage_subscr_cost / 3:.2f} zl")
            
            # Sprawdz czy sa inne faktury dla tego samego okresu
            other_invoices = db.query(Invoice).filter(
                Invoice.data == invoice.data,
                Invoice.id != invoice.id
            ).all()
            
            if other_invoices:
                print(f"\n5. INNE FAKTURY DLA TEGO SAMEGO OKRESU ({invoice.data}):")
                for other_inv in other_invoices:
                    print(f"   {other_inv.invoice_number}: {other_inv.usage} m3, okres {other_inv.period_start} - {other_inv.period_stop}")
        else:
            print(f"\n[BRAK RACHUNKOW] wygenerowanych z tej faktury")
    
    finally:
        db.close()

if __name__ == "__main__":
    import sys
    invoice_number = sys.argv[1] if len(sys.argv) > 1 else "FRP/25/02/022549"
    check_invoice_details(invoice_number)

