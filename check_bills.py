"""Skrypt do sprawdzania rachunków dla konkretnego okresu."""

from db import SessionLocal, init_db
from models import Bill

def check_bills(period: str):
    """Sprawdza wszystkie rachunki dla okresu."""
    init_db()
    db = SessionLocal()
    
    try:
        print("=" * 80)
        print(f"RACHUNKI DLA OKRESU: {period}")
        print("=" * 80)
        
        bills = db.query(Bill).filter(Bill.data == period).all()
        
        if not bills:
            print(f"Brak rachunkow dla okresu {period}")
            return
        
        print(f"\nLiczba rachunkow: {len(bills)}")
        print("\n" + "-" * 80)
        
        for bill in bills:
            print(f"\nLokal: {bill.local}")
            print(f"  Zuzycie: {bill.usage_m3:.2f} m3")
            print(f"  Koszt wody: {bill.cost_water:.2f} zl")
            print(f"  Koszt sciekow: {bill.cost_sewage:.2f} zl")
            print(f"  Abonament: {bill.abonament_total:.2f} zl")
            print(f"  Suma netto: {bill.net_sum:.2f} zl")
            print(f"  Suma brutto: {bill.gross_sum:.2f} zl")
            
            if bill.usage_m3 < 0:
                print(f"  [PROBLEM] Ujemne zuzycie!")
            if bill.gross_sum < 0:
                print(f"  [PROBLEM] Ujemna suma brutto!")
        
        total_usage = sum(b.usage_m3 for b in bills)
        total_gross = sum(b.gross_sum for b in bills)
        
        print("\n" + "-" * 80)
        print(f"\nSUMY:")
        print(f"  Calkowite zuzycie: {total_usage:.2f} m3")
        print(f"  Calkowita suma brutto: {total_gross:.2f} zl")
        
    finally:
        db.close()

if __name__ == "__main__":
    import sys
    
    period = sys.argv[1] if len(sys.argv) > 1 else "2022-06"
    check_bills(period)


