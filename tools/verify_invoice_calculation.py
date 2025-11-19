"""
Skrypt do weryfikacji obliczeń faktury zgodnie z poprawioną logiką.
Przelicza fakturę P/23666363/0002/24 dla okresów 2024-02 i 2024-04.
"""

import sys
from pathlib import Path
from datetime import date, datetime
from sqlalchemy.orm import Session

# Dodaj ścieżkę do projektu
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import SessionLocal
from app.models.electricity_invoice import ElectricityInvoice
from app.models.electricity import ElectricityReading
from app.services.electricity.manager import ElectricityBillingManager
from app.services.electricity.calculator import calculate_all_usage, get_previous_reading


def format_currency(value: float) -> str:
    """Formatuje wartość jako walutę."""
    return f"{value:,.2f} zł"


def print_section(title: str):
    """Drukuje nagłówek sekcji."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def print_subsection(title: str):
    """Drukuje nagłówek podsekcji."""
    print("\n" + "-" * 80)
    print(f"  {title}")
    print("-" * 80)


def verify_invoice_calculation(invoice_number: str, periods: list[str]):
    """
    Weryfikuje obliczenia faktury dla podanych okresów.
    
    Args:
        invoice_number: Numer faktury (np. "P/23666363/0002/24")
        periods: Lista okresów do weryfikacji (np. ["2024-02", "2024-04"])
    """
    db = SessionLocal()
    manager = ElectricityBillingManager()
    
    try:
        # 1. Znajdź fakturę
        print_section("WERYFIKACJA FAKTURY")
        invoice = db.query(ElectricityInvoice).filter(
            ElectricityInvoice.numer_faktury == invoice_number
        ).first()
        
        if not invoice:
            print(f"[BLAD] Nie znaleziono faktury: {invoice_number}")
            return
        
        print(f"Numer faktury: {invoice.numer_faktury}")
        print(f"Okres faktury: {invoice.data_poczatku_okresu} - {invoice.data_konca_okresu}")
        print(f"Typ taryfy: {invoice.typ_taryfy}")
        print(f"Grupa taryfowa: {invoice.grupa_taryfowa}")
        print(f"Zużycie całkowite (DOM): {invoice.zuzycie_kwh} kWh")
        print(f"Ogółem sprzedaż energii (brutto): {format_currency(float(invoice.ogolem_sprzedaz_energii))}")
        print(f"Ogółem usługa dystrybucji (brutto): {format_currency(float(invoice.ogolem_usluga_dystrybucji))}")
        
        # 2. Sprawdź okresy z faktury
        print_section("OKRESY Z FAKTURY")
        distribution_periods = manager.get_distribution_periods(db, invoice)
        
        if not distribution_periods:
            print("[UWAGA] Brak okresow dystrybucyjnych - faktura ma tylko jeden okres")
        else:
            print(f"Znaleziono {len(distribution_periods)} okres(ów) dystrybucyjnych:")
            for i, period in enumerate(distribution_periods, 1):
                print(f"\n  Okres {i}: {period['od']} - {period['do']}")
                print(f"    Cena 1 kWh dzienna (netto): {period.get('cena_1kwh_dzienna', 0):.4f} zł/kWh")
                print(f"    Cena 1 kWh nocna (netto): {period.get('cena_1kwh_nocna', 0):.4f} zł/kWh")
                print(f"    Suma opłat stałych (netto): {format_currency(period.get('suma_oplat_stalych', 0))}")
        
        # 3. Dla każdego okresu najemcy
        for period_data in periods:
            print_section(f"OKRES NAJEMCY: {period_data}")
            
            # Pobierz odczyty
            current_reading = db.query(ElectricityReading).filter(
                ElectricityReading.data == period_data
            ).first()
            
            if not current_reading:
                print(f"[UWAGA] Brak odczytow dla okresu {period_data}")
                continue
            
            previous_reading = get_previous_reading(db, period_data)
            
            if not previous_reading:
                print(f"[UWAGA] Brak poprzedniego odczytu dla okresu {period_data}")
                continue
            
            # Oblicz zużycie
            usage_data = calculate_all_usage(current_reading, previous_reading)
            
            print_subsection("ODCZYTY I ZUŻYCIE")
            print(f"Data odczytu obecnego: {current_reading.data_odczytu_licznika}")
            if previous_reading:
                print(f"Data odczytu poprzedniego: {previous_reading.data_odczytu_licznika}")
            
            print(f"\nDOM łącznie: {usage_data['dom']['zuzycie_dom_lacznie']:.4f} kWh")
            if usage_data['dom'].get('zuzycie_dom_I'):
                print(f"  - Taryfa I (dzienna): {usage_data['dom']['zuzycie_dom_I']:.4f} kWh")
            if usage_data['dom'].get('zuzycie_dom_II'):
                print(f"  - Taryfa II (nocna): {usage_data['dom']['zuzycie_dom_II']:.4f} kWh")
            
            print(f"\nDÓŁ łącznie: {usage_data['dol']['zuzycie_dol_lacznie']:.4f} kWh")
            if usage_data['dol'].get('zuzycie_dol_I'):
                print(f"  - Taryfa I (dzienna): {usage_data['dol']['zuzycie_dol_I']:.4f} kWh")
            if usage_data['dol'].get('zuzycie_dol_II'):
                print(f"  - Taryfa II (nocna): {usage_data['dol']['zuzycie_dol_II']:.4f} kWh")
            
            print(f"\nGABINET: {usage_data['gabinet']['zuzycie_gabinet']:.4f} kWh")
            
            print(f"\nGÓRA łącznie: {usage_data['gora']['zuzycie_gora_lacznie']:.4f} kWh")
            if usage_data['gora'].get('zuzycie_gora_I') is not None:
                print(f"  - Taryfa I (dzienna): {usage_data['gora']['zuzycie_gora_I']:.4f} kWh")
            if usage_data['gora'].get('zuzycie_gora_II') is not None:
                print(f"  - Taryfa II (nocna): {usage_data['gora']['zuzycie_gora_II']:.4f} kWh")
            
            print(f"\nDOL (Mikołaj) łącznie: {usage_data['dol']['zuzycie_dol_lacznie']:.4f} kWh")
            if usage_data['dol'].get('zuzycie_dol_I'):
                print(f"  - Taryfa I (dzienna): {usage_data['dol']['zuzycie_dol_I']:.4f} kWh")
            if usage_data['dol'].get('zuzycie_dol_II'):
                print(f"  - Taryfa II (nocna): {usage_data['dol']['zuzycie_dol_II']:.4f} kWh")
            
            # Określ daty okresu najemcy
            tenant_period_dates = manager.get_tenant_period_dates(db, period_data)
            
            if not tenant_period_dates:
                print(f"[UWAGA] Nie mozna okreslic dat okresu najemcy dla {period_data}")
                continue
            
            tenant_period_start, tenant_period_end = tenant_period_dates
            print_subsection("OKRES NAJEMCY")
            print(f"Data początku: {tenant_period_start}")
            print(f"Data końca: {tenant_period_end}")
            
            # Oblicz koszty dla każdego lokalu
            locals_to_check = ['gora', 'dol', 'gabinet']
            
            for local_name in locals_to_check:
                print_subsection(f"OBLICZENIA DLA LOKALU: {local_name.upper()}")
                
                # Pobierz zużycie
                if local_name == 'gora':
                    local_usage = usage_data['gora']['zuzycie_gora_lacznie']
                    local_usage_dzienna = usage_data['gora'].get('zuzycie_gora_I')
                    local_usage_nocna = usage_data['gora'].get('zuzycie_gora_II')
                elif local_name == 'dol':
                    local_usage = usage_data['dol']['zuzycie_dol_lacznie']
                    local_usage_dzienna = usage_data['dol'].get('zuzycie_dol_I')
                    local_usage_nocna = usage_data['dol'].get('zuzycie_dol_II')
                else:  # gabinet
                    local_usage = usage_data['gabinet']['zuzycie_gabinet']
                    local_usage_dzienna = None
                    local_usage_nocna = None
                
                print(f"Zużycie łącznie: {local_usage:.4f} kWh")
                if local_usage_dzienna is not None:
                    print(f"  - Taryfa I (dzienna): {local_usage_dzienna:.4f} kWh")
                if local_usage_nocna is not None:
                    print(f"  - Taryfa II (nocna): {local_usage_nocna:.4f} kWh")
                
                # Oblicz koszty używając poprawionej logiki
                if distribution_periods and len(distribution_periods) > 1:
                    print("\n[POPRAWIONA LOGIKA] Uzywam overlapping periods")
                    
                    usage_kwh_calodobowa = local_usage if local_name == 'gabinet' else None
                    
                    result = manager.calculate_bill_for_period_with_overlapping(
                        tenant_period_start,
                        tenant_period_end,
                        distribution_periods,
                        local_usage_dzienna or 0.0,
                        local_usage_nocna or 0.0,
                        usage_kwh_calodobowa
                    )
                    
                    print(f"\nKoszty energii (netto): {format_currency(result['energy_cost_net'])}")
                    print(f"Koszty energii (brutto): {format_currency(result['energy_cost_gross'])}")
                    print(f"Koszty dystrybucji (netto): {format_currency(result['distribution_cost_net'])}")
                    print(f"Koszty dystrybucji (brutto): {format_currency(result['distribution_cost_gross'])}")
                    print(f"Opłaty stałe (netto): {format_currency(result['fixed_fees_net'])}")
                    print(f"Opłaty stałe (brutto): {format_currency(result['fixed_fees_gross'])}")
                    print(f"\nRAZEM NETTO: {format_currency(result['total_net_sum'])}")
                    print(f"RAZEM BRUTTO: {format_currency(result['total_gross_sum'])}")
                    
                    if result.get('details'):
                        print("\nSzczegóły overlapping periods:")
                        for detail in result['details']:
                            print(f"  {detail['period']}: {detail['days']} dni, proporcja: {detail['proportion']:.4f}")
                            print(f"    Koszt energii (netto): {format_currency(detail['energy_cost_net'])}")
                            print(f"    Opłaty stałe (netto): {format_currency(detail['fixed_cost_net'])}")
                else:
                    print("\n[STARA LOGIKA] Fallback - jeden okres")
                    
                    # Użyj calculate_bill_costs (która używa starej logiki gdy jest jeden okres)
                    costs = manager.calculate_bill_costs(
                        invoice,
                        usage_data,
                        local_name,
                        db,
                        period_data
                    )
                    
                    print(f"\nKoszty energii (brutto): {format_currency(costs['energy_cost_gross'])}")
                    print(f"Koszty dystrybucji (brutto): {format_currency(costs['distribution_cost_gross'])}")
                    print(f"\nRAZEM NETTO: {format_currency(costs['total_net_sum'])}")
                    print(f"RAZEM BRUTTO: {format_currency(costs['total_gross_sum'])}")
        
        print_section("PODSUMOWANIE")
        if distribution_periods and len(distribution_periods) > 1:
            print("[OK] Faktura ma wiele okresow - uzyto POPRAWIONEJ LOGIKI")
        else:
            print("[UWAGA] Faktura ma jeden okres - uzyto STAREJ LOGIKI (fallback)")
        
    except Exception as e:
        print(f"[BLAD] Blad podczas weryfikacji: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    invoice_number = "P/23666363/0002/24"
    periods = ["2024-02", "2024-04"]
    
    verify_invoice_calculation(invoice_number, periods)

