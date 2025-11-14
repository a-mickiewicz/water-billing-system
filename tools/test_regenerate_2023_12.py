"""
Test regeneracji rachunków dla okresu 2023-12.
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import SessionLocal
from app.models.water import Reading, Bill, Invoice
from app.services.water.meter_manager import generate_bills_for_period
from sqlalchemy import desc

def test_regenerate():
    db = SessionLocal()
    try:
        period = "2023-12"
        
        print(f"=== TEST REGENERACJI RACHUNKOW DLA {period} ===\n")
        
        # Sprawdź obecne rachunki
        bills_before = db.query(Bill).filter(Bill.data == period).all()
        print(f"Rachunki przed regeneracja:")
        for bill in bills_before:
            print(f"  Lokal {bill.local}: zuzycie = {bill.usage_m3} m3")
        
        # Usuń stare rachunki
        print(f"\nUsuwanie starych rachunkow...")
        for bill in bills_before:
            db.delete(bill)
        db.commit()
        print(f"Usunieto {len(bills_before)} rachunkow")
        
        # Wygeneruj nowe rachunki
        print(f"\nGenerowanie nowych rachunkow...")
        new_bills = generate_bills_for_period(db, period)
        db.commit()
        
        print(f"\nWygenerowano {len(new_bills)} nowych rachunkow:")
        for bill in new_bills:
            print(f"  Lokal {bill.local}: zuzycie = {bill.usage_m3} m3")
            if bill.local == 'gora':
                # Sprawdź odczyty
                current_reading = db.query(Reading).filter(Reading.data == period).first()
                previous_reading = db.query(Reading).filter(Reading.data < period).order_by(desc(Reading.data)).first()
                if current_reading and previous_reading:
                    diff = current_reading.water_meter_5 - previous_reading.water_meter_5
                    print(f"    Roznica odczytow: {diff} m3")
                    print(f"    Roznica w zuzyciu: {bill.usage_m3 - diff} m3")
        
        # Sprawdź czy są zapisane w bazie
        bills_after = db.query(Bill).filter(Bill.data == period).all()
        print(f"\nRachunki w bazie po regeneracji:")
        for bill in bills_after:
            print(f"  Lokal {bill.local}: zuzycie = {bill.usage_m3} m3")
            
    finally:
        db.close()

if __name__ == "__main__":
    test_regenerate()

