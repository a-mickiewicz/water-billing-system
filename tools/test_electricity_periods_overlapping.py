"""
Test scenariusza, gdzie okres najemcy zazębia się z DWOMA okresami faktury.
"""

import sys
from pathlib import Path
from datetime import date

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import SessionLocal
from app.services.electricity.manager import ElectricityBillingManager
from app.models.electricity_invoice import ElectricityInvoice


def test_overlapping_two_periods():
    """Test gdy okres najemcy zazębia się z dwoma okresami faktury."""
    db = SessionLocal()
    manager = ElectricityBillingManager()
    
    try:
        print("=" * 80)
        print("TEST: OKRES NAJEMCY ZAZĘBIA SIĘ Z DWOMA OKRESAMI FAKTURY")
        print("=" * 80)
        
        # Znajdź fakturę
        invoice = db.query(ElectricityInvoice).filter(
            ElectricityInvoice.numer_faktury == "P/23666363/0002/24"
        ).first()
        
        if not invoice:
            print("[ERROR] Nie znaleziono faktury!")
            return
        
        # Wyłonij okresy
        distribution_periods = manager.get_distribution_periods(db, invoice)
        
        if not distribution_periods or len(distribution_periods) < 2:
            print("[ERROR] Faktura nie ma wystarczającej liczby okresów!")
            return
        
        print(f"\nFaktura ma {len(distribution_periods)} okresów:")
        for i, period in enumerate(distribution_periods, 1):
            print(f"  Okres {i}: {period['od']} - {period['do']}")
        
        # Test: okres najemcy marzec-kwiecień (zazębia się z Okresem 2 i 3)
        # Okres 2: 2024-01-01 - 2024-04-06
        # Okres 3: 2024-04-07 - 2024-06-30
        # Okres najemcy: 2024-03-01 - 2024-04-30
        
        tenant_start = date(2024, 3, 1)
        tenant_end = date(2024, 4, 30)
        
        print(f"\n" + "-" * 80)
        print(f"Okres najemcy: {tenant_start} - {tenant_end}")
        print(f"  (61 dni)")
        print("-" * 80)
        
        usage_dzienna = 175.0  # kWh
        usage_nocna = 75.0      # kWh
        
        print(f"\nZużycie:")
        print(f"  Dzienne: {usage_dzienna} kWh")
        print(f"  Nocne: {usage_nocna} kWh")
        print(f"  Razem: {usage_dzienna + usage_nocna} kWh")
        
        result = manager.calculate_bill_for_period_with_overlapping(
            tenant_start,
            tenant_end,
            distribution_periods,
            usage_dzienna,
            usage_nocna
        )
        
        print(f"\n" + "-" * 80)
        print("WYNIKI:")
        print("-" * 80)
        print(f"  Koszt energii (netto): {result['energy_cost_net']} zł")
        print(f"  Koszt energii (brutto): {result['energy_cost_gross']} zł")
        print(f"  Opłaty stałe (netto): {result['fixed_fees_net']} zł")
        print(f"  Opłaty stałe (brutto): {result['fixed_fees_gross']} zł")
        print(f"  Suma netto: {result['total_net_sum']} zł")
        print(f"  Suma brutto: {result['total_gross_sum']} zł")
        
        if result.get('details'):
            print(f"\n  Szczegóły ({len(result['details'])} okresów):")
            total_days = sum(d['days'] for d in result['details'])
            for detail in result['details']:
                period = detail['period']
                days = detail['days']
                proportion = detail['proportion']
                
                # Znajdź okres w distribution_periods
                period_info = next((p for p in distribution_periods if p['okres'] == period), None)
                
                print(f"\n    {period}:")
                print(f"      Dni: {days} ({proportion:.2%} okresu najemcy)")
                if period_info:
                    print(f"      Cena dzienna: {period_info.get('cena_1kwh_dzienna', 'N/A')} zł/kWh")
                    print(f"      Cena nocna: {period_info.get('cena_1kwh_nocna', 'N/A')} zł/kWh")
                    print(f"      Zużycie dzienne: {usage_dzienna * proportion:.2f} kWh")
                    print(f"      Zużycie nocne: {usage_nocna * proportion:.2f} kWh")
                print(f"      Koszt energii: {detail['energy_cost_net']} zł (netto)")
                print(f"      Opłaty stałe: {detail['fixed_cost_net']} zł (netto)")
            
            print(f"\n  Suma dni: {total_days} (powinno być 61)")
        
        print("\n[OK] Test zakończony!")
        
    except Exception as e:
        print(f"\n[ERROR] Błąd: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    test_overlapping_two_periods()

