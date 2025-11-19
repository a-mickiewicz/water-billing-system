"""
Test nowej logiki rozliczania prądu z uwzględnieniem okresów.
"""

import sys
from pathlib import Path
from datetime import date

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import SessionLocal
from app.services.electricity.manager import ElectricityBillingManager
from app.models.electricity import ElectricityReading, ElectricityBill
from app.models.electricity_invoice import ElectricityInvoice
from sqlalchemy import desc


def test_period_logic():
    """Test nowej logiki z okresami."""
    db = SessionLocal()
    manager = ElectricityBillingManager()
    
    try:
        print("=" * 80)
        print("TEST NOWEJ LOGIKI ROZLICZANIA PRĄDU Z OKRESAMI")
        print("=" * 80)
        
        # 1. Sprawdź czy są faktury w bazie
        invoices = db.query(ElectricityInvoice).order_by(desc(ElectricityInvoice.data_poczatku_okresu)).all()
        
        if not invoices:
            print("\n[ERROR] Brak faktur w bazie danych!")
            return
        
        print(f"\n[OK] Znaleziono {len(invoices)} faktur w bazie")
        
        # 2. Sprawdź czy są odczyty
        readings = db.query(ElectricityReading).order_by(ElectricityReading.data).all()
        
        if not readings:
            print("\n[ERROR] Brak odczytów w bazie danych!")
            return
        
        print(f"[OK] Znaleziono {len(readings)} odczytów w bazie")
        
        # 3. Wybierz fakturę do testowania
        test_invoice = invoices[0]
        print(f"\n[INFO] Testuję fakturę: {test_invoice.numer_faktury}")
        print(f"  Okres: {test_invoice.data_poczatku_okresu} - {test_invoice.data_konca_okresu}")
        print(f"  Typ taryfy: {test_invoice.typ_taryfy}")
        
        # 4. Sprawdź okresy z faktury
        print("\n" + "-" * 80)
        print("TEST: get_distribution_periods()")
        print("-" * 80)
        
        distribution_periods = manager.get_distribution_periods(db, test_invoice)
        
        if distribution_periods:
            print(f"[OK] Wyłoniono {len(distribution_periods)} okresów z faktury:")
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
            print("[INFO] Brak okresów z różnymi cenami (faktura ma jedną cenę)")
        
        # 5. Sprawdź okres najemcy dla pierwszego odczytu
        if readings:
            test_reading = readings[0]
            test_period = test_reading.data
            
            print("\n" + "-" * 80)
            print(f"TEST: get_tenant_period_dates() dla okresu {test_period}")
            print("-" * 80)
            
            tenant_period = manager.get_tenant_period_dates(db, test_period)
            
            if tenant_period:
                start_date, end_date = tenant_period
                print(f"[OK] Okres najemcy:")
                print(f"  Od: {start_date}")
                print(f"  Do: {end_date}")
                days = (end_date - start_date).days + 1
                print(f"  Liczba dni: {days}")
            else:
                print("[ERROR] Nie można określić okresu najemcy")
        
        # 6. Test calculate_bill_for_period_with_overlapping (jeśli są okresy)
        if distribution_periods and len(distribution_periods) > 1 and tenant_period:
            print("\n" + "-" * 80)
            print("TEST: calculate_bill_for_period_with_overlapping()")
            print("-" * 80)
            
            start_date, end_date = tenant_period
            
            # Przykładowe zużycie
            usage_dzienna = 100.0
            usage_nocna = 50.0
            
            result = manager.calculate_bill_for_period_with_overlapping(
                start_date,
                end_date,
                distribution_periods,
                usage_dzienna,
                usage_nocna
            )
            
            print(f"[OK] Obliczono koszty:")
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
        
        # 7. Test calculate_bill_costs dla istniejącego okresu
        if readings:
            test_period = test_reading.data
            print("\n" + "-" * 80)
            print(f"TEST: calculate_bill_costs() dla okresu {test_period}")
            print("-" * 80)
            
            usage_data = manager.get_usage_for_period(db, test_period)
            
            if usage_data:
                # Test dla lokalu "gora"
                costs = manager.calculate_bill_costs(
                    test_invoice,
                    usage_data,
                    'gora',
                    db,
                    test_period
                )
                
                print(f"[OK] Obliczono koszty dla lokalu 'gora':")
                print(f"  Zużycie: {costs['usage_kwh']} kWh")
                if costs.get('usage_kwh_dzienna'):
                    print(f"  Zużycie dzienne: {costs['usage_kwh_dzienna']} kWh")
                if costs.get('usage_kwh_nocna'):
                    print(f"  Zużycie nocne: {costs['usage_kwh_nocna']} kWh")
                print(f"  Koszt energii (brutto): {costs['energy_cost_gross']} zł")
                print(f"  Koszt dystrybucji (brutto): {costs['distribution_cost_gross']} zł")
                print(f"  Suma netto: {costs['total_net_sum']} zł")
                print(f"  Suma brutto: {costs['total_gross_sum']} zł")
            else:
                print("[WARNING] Brak danych zużycia dla tego okresu")
        
        # 8. Podsumowanie
        print("\n" + "=" * 80)
        print("PODSUMOWANIE TESTU")
        print("=" * 80)
        
        if distribution_periods and len(distribution_periods) > 1:
            print("[OK] Nowa logika z okresami jest aktywna")
            print(f"     Faktura ma {len(distribution_periods)} okresów z różnymi cenami")
        else:
            print("[INFO] Faktura ma jedną cenę - używana jest stara logika (fallback)")
        
        print("\n[OK] Test zakończony pomyślnie!")
        
    except Exception as e:
        print(f"\n[ERROR] Błąd podczas testu: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    test_period_logic()

