"""
Szczegolowa analiza obliczen kosztow wody i sciekow z faktury.
"""

from app.core.database import SessionLocal, init_db
from app.models.water import Invoice, Bill, Reading
from sqlalchemy import desc

def detailed_calculation(invoice_number: str):
    init_db()
    db = SessionLocal()
    
    try:
        print("=" * 80)
        print(f"SZCZEGOLOWA ANALIZA OBLICZEN KOSZTOW Z FAKTURY: {invoice_number}")
        print("=" * 80)
        
        invoice = db.query(Invoice).filter(Invoice.invoice_number == invoice_number).first()
        if not invoice:
            print(f"[BLAD] Nie znaleziono faktury")
            return
        
        print(f"\nFAKTURA:")
        print(f"  Numer: {invoice.invoice_number}")
        print(f"  Okres rozliczeniowy: {invoice.data}")
        print(f"  Okres faktury: {invoice.period_start} - {invoice.period_stop}")
        print(f"  Zuzycie: {invoice.usage} m3")
        print(f"  Koszt wody za m3: {invoice.water_cost_m3} zl/m3")
        print(f"  Koszt sciekow za m3: {invoice.sewage_cost_m3} zl/m3")
        print(f"  Abonament wody (SUMA): {invoice.water_subscr_cost} zl")
        print(f"  Abonament sciekow (SUMA): {invoice.sewage_subscr_cost} zl")
        print(f"  Liczba abonamentow: {invoice.nr_of_subscription}")
        print(f"  VAT: {invoice.vat * 100:.1f}%")
        print(f"  Suma brutto faktury: {invoice.gross_sum} zl")
        
        bills = db.query(Bill).filter(Bill.invoice_id == invoice.id).all()
        
        print(f"\n" + "=" * 80)
        print("OBLICZENIA DLA KAZDEGO LOKALU:")
        print("=" * 80)
        
        total_net = 0
        total_gross = 0
        
        for bill in bills:
            print(f"\n{bill.local.upper()}:")
            print(f"  Zuzycie: {bill.usage_m3} m3")
            
            # Oblicz koszty zuzycia
            cost_water_calc = bill.usage_m3 * invoice.water_cost_m3
            cost_sewage_calc = bill.usage_m3 * invoice.sewage_cost_m3
            cost_total_calc = cost_water_calc + cost_sewage_calc
            
            print(f"\n  KOSZTY ZUZYCIA:")
            print(f"    Woda: {bill.usage_m3} m3 × {invoice.water_cost_m3} zl/m3 = {cost_water_calc:.2f} zl")
            print(f"      (w rachunku: {bill.cost_water} zl)")
            print(f"    Scieki: {bill.usage_m3} m3 × {invoice.sewage_cost_m3} zl/m3 = {cost_sewage_calc:.2f} zl")
            print(f"      (w rachunku: {bill.cost_sewage} zl)")
            print(f"    Razem zuzycie: {cost_total_calc:.2f} zl")
            print(f"      (w rachunku: {bill.cost_usage_total} zl)")
            
            # Oblicz abonament
            abonament_water_share = invoice.water_subscr_cost / 3
            abonament_sewage_share = invoice.sewage_subscr_cost / 3
            abonament_total_share = abonament_water_share + abonament_sewage_share
            
            print(f"\n  ABONAMENT (podzielony na 3 lokale):")
            print(f"    Woda: {invoice.water_subscr_cost} zl ÷ 3 = {abonament_water_share:.2f} zl")
            print(f"      (w rachunku: {bill.abonament_water_share} zl)")
            print(f"    Scieki: {invoice.sewage_subscr_cost} zl ÷ 3 = {abonament_sewage_share:.2f} zl")
            print(f"      (w rachunku: {bill.abonament_sewage_share} zl)")
            print(f"    Razem abonament: {abonament_total_share:.2f} zl")
            print(f"      (w rachunku: {bill.abonament_total} zl)")
            
            # Suma netto
            net_sum_calc = cost_total_calc + abonament_total_share
            print(f"\n  SUMA NETTO:")
            print(f"    Koszt zuzycia: {cost_total_calc:.2f} zl")
            print(f"    Abonament: {abonament_total_share:.2f} zl")
            print(f"    RAZEM NETTO: {net_sum_calc:.2f} zl")
            print(f"      (w rachunku: {bill.net_sum} zl)")
            
            # Suma brutto
            gross_sum_calc = net_sum_calc * (1 + invoice.vat)
            print(f"\n  SUMA BRUTTO:")
            print(f"    Netto: {net_sum_calc:.2f} zl")
            print(f"    VAT ({invoice.vat * 100:.1f}%): {net_sum_calc * invoice.vat:.2f} zl")
            print(f"    RAZEM BRUTTO: {gross_sum_calc:.2f} zl")
            print(f"      (w rachunku: {bill.gross_sum} zl)")
            
            total_net += net_sum_calc
            total_gross += gross_sum_calc
        
        print(f"\n" + "=" * 80)
        print("PODSUMOWANIE WSZYSTKICH LOKALI:")
        print("=" * 80)
        
        total_usage = sum(b.usage_m3 for b in bills)
        total_cost_water = sum(b.cost_water for b in bills)
        total_cost_sewage = sum(b.cost_sewage for b in bills)
        total_abonament = sum(b.abonament_total for b in bills)
        
        print(f"\n  Suma zuzycia: {total_usage:.2f} m3")
        print(f"  Suma kosztow wody: {total_cost_water:.2f} zl")
        print(f"  Suma kosztow sciekow: {total_cost_sewage:.2f} zl")
        print(f"  Suma abonamentow: {total_abonament:.2f} zl")
        print(f"  Suma netto: {total_net:.2f} zl")
        print(f"  Suma brutto: {total_gross:.2f} zl")
        
        print(f"\n  WERYFIKACJA:")
        print(f"    Abonament wody (3 lokale): {invoice.water_subscr_cost / 3 * 3:.2f} zl (powinno byc {invoice.water_subscr_cost} zl)")
        print(f"    Abonament sciekow (3 lokale): {invoice.sewage_subscr_cost / 3 * 3:.2f} zl (powinno byc {invoice.sewage_subscr_cost} zl)")
        print(f"    Suma abonamentow z rachunkow: {total_abonament:.2f} zl")
        print(f"    Suma abonamentow z faktury: {invoice.water_subscr_cost + invoice.sewage_subscr_cost:.2f} zl")
        
        # Sprawdz czy suma brutto z rachunkow zgadza sie z faktura
        print(f"\n  POROWNANIE Z FAKTURA:")
        print(f"    Suma brutto z rachunkow: {total_gross:.2f} zl")
        print(f"    Suma brutto z faktury: {invoice.gross_sum:.2f} zl")
        print(f"    ROZNICA: {abs(total_gross - invoice.gross_sum):.2f} zl")
        
        if abs(total_gross - invoice.gross_sum) > 0.01:
            print(f"\n  [UWAGA] Roznica miedzy suma rachunkow a faktura!")
            print(f"    Mozliwe przyczyny:")
            print(f"    - Zaokraglenia przy obliczeniach")
            print(f"    - Faktura moze zawierac dodatkowe pozycje")
            print(f"    - Rozne zaokraglenia w fakturze vs rachunkach")
    
    finally:
        db.close()

if __name__ == "__main__":
    import sys
    invoice_number = sys.argv[1] if len(sys.argv) > 1 else "FRP/25/02/022549"
    detailed_calculation(invoice_number)

