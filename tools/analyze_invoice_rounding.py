"""
Analizuje różnicę między sumą brutto faktury a sumą rachunków.
Sprawdza wpływ zaokrągleń na końcową sumę.
"""

from app.core.database import SessionLocal, init_db
from app.models.water import Invoice, Bill

init_db()
db = SessionLocal()

try:
    invoice_number = "FRP/24/02/008566"
    invoice = db.query(Invoice).filter(Invoice.invoice_number == invoice_number).first()
    
    if not invoice:
        print(f"Nie znaleziono faktury {invoice_number}")
        exit(1)
    
    print("=" * 80)
    print(f"ANALIZA FAKTURY: {invoice_number}")
    print("=" * 80)
    
    print(f"\n1. DANE Z BAZY:")
    print(f"   Zuzycie: {invoice.usage} m3")
    print(f"   Cena wody: {invoice.water_cost_m3} zl/m3")
    print(f"   Cena sciekow: {invoice.sewage_cost_m3} zl/m3")
    print(f"   Abonament wody: {invoice.water_subscr_cost} zl")
    print(f"   Abonament sciekow: {invoice.sewage_subscr_cost} zl")
    print(f"   VAT: {invoice.vat * 100}%")
    print(f"   Suma brutto faktury: {invoice.gross_sum} zl")
    
    # Sprawdz rachunki dla tego okresu
    bills = db.query(Bill).filter(Bill.data == invoice.data).all()
    
    print(f"\n2. RACHUNKI DLA OKRESU {invoice.data}:")
    if not bills:
        print("   BRAK RACHUNKOW - musza zostac wygenerowane!")
    else:
        total_gross = 0.0
        total_net = 0.0
        
        for bill in bills:
            print(f"\n   {bill.local.upper()}:")
            print(f"     Zuzycie: {bill.usage_m3} m3")
            print(f"     Koszt wody: {bill.cost_water} zl")
            print(f"     Koszt sciekow: {bill.cost_sewage} zl")
            print(f"     Koszt zuzycia: {bill.cost_usage_total} zl")
            print(f"     Abonament: {bill.abonament_total} zl")
            print(f"     Suma netto: {bill.net_sum} zl")
            print(f"     Suma brutto: {bill.gross_sum} zl")
            
            # Sprawdz obliczenia
            calculated_net = bill.cost_usage_total + bill.abonament_total
            calculated_gross = calculated_net * (1 + invoice.vat)
            
            print(f"     Weryfikacja:")
            print(f"       Netto (obliczone): {calculated_net:.10f} -> {round(calculated_net, 2):.2f} zl")
            print(f"       Brutto (obliczone): {calculated_gross:.10f} -> {round(calculated_gross, 2):.2f} zl")
            print(f"       Roznica netto: {abs(bill.net_sum - calculated_net):.10f} zl")
            print(f"       Roznica brutto: {abs(bill.gross_sum - calculated_gross):.10f} zl")
            
            total_gross += bill.gross_sum
            total_net += bill.net_sum
        
        print(f"\n3. PODSUMOWANIE:")
        print(f"   Suma brutto z rachunkow: {total_gross:.2f} zl")
        print(f"   Suma brutto z faktury: {invoice.gross_sum:.2f} zl")
        print(f"   Roznica: {abs(total_gross - invoice.gross_sum):.2f} zl")
        
        # Sprawdz czy problem jest z zaokrągleniem
        print(f"\n4. ANALIZA ZAOKRAGLEN:")
        print(f"   Suma netto z rachunkow: {total_net:.2f} zl")
        calculated_total_net = sum(b.cost_usage_total + b.abonament_total for b in bills)
        calculated_total_gross = calculated_total_net * (1 + invoice.vat)
        print(f"   Suma netto (obliczona): {calculated_total_net:.10f} -> {round(calculated_total_net, 2):.2f} zl")
        print(f"   Suma brutto (obliczona): {calculated_total_gross:.10f} -> {round(calculated_total_gross, 2):.2f} zl")
        print(f"   Roznica (obliczona vs faktura): {abs(calculated_total_gross - invoice.gross_sum):.10f} zl")
        
        # Sprawdz czy problem jest z zaokrągleniem każdego rachunku osobno
        print(f"\n5. POROWNANIE ZAOKRAGLEN:")
        print(f"   Metoda 1: Zaokraglenie kazdego rachunku osobno (obecna)")
        print(f"     Suma: {total_gross:.2f} zl")
        print(f"   Metoda 2: Zaokraglenie sumy wszystkich rachunkow")
        total_gross_exact = sum((b.cost_usage_total + b.abonament_total) * (1 + invoice.vat) for b in bills)
        total_gross_rounded_sum = round(total_gross_exact, 2)
        print(f"     Suma: {total_gross_rounded_sum:.2f} zl")
        print(f"   Roznica metod: {abs(total_gross - total_gross_rounded_sum):.2f} zl")

finally:
    db.close()

