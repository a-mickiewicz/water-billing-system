"""
Sprawdza rachunki i faktury dla okresow 2025-02, 2025-03, 2025-04
"""

from app.core.database import SessionLocal, init_db
from app.models.water import Reading, Invoice, Bill
from sqlalchemy import desc

def check_periods():
    init_db()
    db = SessionLocal()
    
    try:
        periods = ["2025-02", "2025-03", "2025-04"]
        
        for period in periods:
            print("=" * 80)
            print(f"OKRES: {period}")
            print("=" * 80)
            
            # Sprawdz odczyty
            reading = db.query(Reading).filter(Reading.data == period).first()
            if reading:
                print(f"\nODCZYT:")
                print(f"  water_meter_main: {reading.water_meter_main} m3")
                print(f"  water_meter_5 (gora): {reading.water_meter_5} m3")
                print(f"  water_meter_5a (gabinet): {reading.water_meter_5a} m3")
            else:
                print(f"\n[BRAK ODCZYTU]")
            
            # Sprawdz faktury
            invoices = db.query(Invoice).filter(Invoice.data == period).all()
            if invoices:
                print(f"\nFAKTURY:")
                for inv in invoices:
                    print(f"  {inv.invoice_number}:")
                    print(f"    Zuzycie: {inv.usage} m3")
                    print(f"    Okres faktury: {inv.period_start} - {inv.period_stop}")
                    print(f"    Przypisana do okresu: {inv.data}")
            else:
                print(f"\n[BRAK FAKTUR]")
            
            # Sprawdz rachunki
            bills = db.query(Bill).filter(Bill.data == period).all()
            if bills:
                print(f"\nRACHUNKI:")
                for bill in bills:
                    print(f"  {bill.local}: zuzycie {bill.usage_m3} m3")
            else:
                print(f"\n[BRAK RACHUNKOW]")
            
            print()
    
    finally:
        db.close()

if __name__ == "__main__":
    check_periods()

