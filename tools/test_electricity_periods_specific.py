"""
Test nowej logiki dla konkretnej faktury z wieloma okresami.
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import SessionLocal
from app.services.electricity.manager import ElectricityBillingManager
from app.models.electricity_invoice import ElectricityInvoice
from sqlalchemy import desc


def test_specific_invoice():
    """Test dla faktury P/23666363/0002/24."""
    db = SessionLocal()
    manager = ElectricityBillingManager()
    
    try:
        print("=" * 80)
        print("TEST DLA FAKTURY P/23666363/0002/24")
        print("=" * 80)
        
        # Znajdź fakturę
        invoice = db.query(ElectricityInvoice).filter(
            ElectricityInvoice.numer_faktury == "P/23666363/0002/24"
        ).first()
        
        if not invoice:
            print("[ERROR] Nie znaleziono faktury!")
            return
        
        print(f"\nFaktura: {invoice.numer_faktury}")
        print(f"Okres: {invoice.data_poczatku_okresu} - {invoice.data_konca_okresu}")
        print(f"Typ taryfy: {invoice.typ_taryfy}")
        
        # Wyłonij okresy
        print("\n" + "-" * 80)
        print("WYŁANIANIE OKRESÓW:")
        print("-" * 80)
        
        distribution_periods = manager.get_distribution_periods(db, invoice)
        
        if distribution_periods:
            print(f"[OK] Wyłoniono {len(distribution_periods)} okresów:")
            for i, period in enumerate(distribution_periods, 1):
                print(f"\n  Okres {i}: {period['okres']}")
                print(f"    Od: {period['od']}")
                print(f"    Do: {period['do']}")
                if period.get('cena_1kwh_dzienna'):
                    print(f"    Cena dzienna: {period['cena_1kwh_dzienna']} zł/kWh (netto)")
                if period.get('cena_1kwh_nocna'):
                    print(f"    Cena nocna: {period['cena_1kwh_nocna']} zł/kWh (netto)")
                if period.get('cena_1kwh_calodobowa'):
                    print(f"    Cena całodobowa: {period['cena_1kwh_calodobowa']} zł/kWh (netto)")
                print(f"    Opłaty stałe: {period['suma_oplat_stalych']} zł (netto)")
        else:
            print("[INFO] Brak okresów")
        
        # Test overlapping periods dla przykładowego okresu najemcy
        if distribution_periods and len(distribution_periods) > 1:
            print("\n" + "-" * 80)
            print("TEST OVERLAPPING PERIODS:")
            print("-" * 80)
            
            # Przykładowy okres najemcy (luty 2024)
            from datetime import date
            tenant_start = date(2024, 2, 1)
            tenant_end = date(2024, 2, 29)
            
            print(f"Okres najemcy: {tenant_start} - {tenant_end}")
            
            usage_dzienna = 100.0
            usage_nocna = 50.0
            
            result = manager.calculate_bill_for_period_with_overlapping(
                tenant_start,
                tenant_end,
                distribution_periods,
                usage_dzienna,
                usage_nocna
            )
            
            print(f"\n[OK] Obliczono koszty:")
            print(f"  Koszt energii (netto): {result['energy_cost_net']} zł")
            print(f"  Koszt energii (brutto): {result['energy_cost_gross']} zł")
            print(f"  Opłaty stałe (netto): {result['fixed_fees_net']} zł")
            print(f"  Opłaty stałe (brutto): {result['fixed_fees_gross']} zł")
            print(f"  Suma netto: {result['total_net_sum']} zł")
            print(f"  Suma brutto: {result['total_gross_sum']} zł")
            
            if result.get('details'):
                print(f"\n  Szczegóły ({len(result['details'])} okresów):")
                for detail in result['details']:
                    print(f"    {detail['period']}:")
                    print(f"      Dni: {detail['days']}, Proporcja: {detail['proportion']:.2%}")
                    print(f"      Koszt energii: {detail['energy_cost_net']} zł (netto)")
                    print(f"      Opłaty stałe: {detail['fixed_cost_net']} zł (netto)")
        
        print("\n[OK] Test zakończony!")
        
    except Exception as e:
        print(f"\n[ERROR] Błąd: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    test_specific_invoice()

