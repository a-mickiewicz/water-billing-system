"""
Szczegółowe obliczenia rachunków za prąd za okres rozliczeniowy 2024-02 do 2024-04
dla wszystkich trzech lokali (gora, dol, gabinet).
"""

import sys
import os
from datetime import datetime, date
from decimal import Decimal

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from sqlalchemy.orm import Session
from app.core.database import SessionLocal, init_db
from app.models.electricity import ElectricityReading, ElectricityBill
from app.models.electricity_invoice import (
    ElectricityInvoice,
    ElectricityInvoiceBlankiet,
    ElectricityInvoiceOplataDystrybucyjna,
    ElectricityInvoiceSprzedazEnergii
)
from app.services.electricity.manager import ElectricityBillingManager
from app.services.electricity.calculator import (
    calculate_all_usage, 
    get_previous_reading,
    calculate_dom_usage,
    calculate_dol_usage,
    calculate_gabinet_usage
)
from app.services.electricity.cost_calculator import calculate_kwh_cost


def format_currency(value: float) -> str:
    """Formatuje wartość jako waluta."""
    return f"{value:,.2f} zł".replace(",", " ")


def format_kwh(value: float) -> str:
    """Formatuje wartość jako kWh."""
    return f"{value:,.4f} kWh".replace(",", " ")


def print_section(title: str):
    """Drukuje nagłówek sekcji."""
    print("\n" + "=" * 100)
    print(f"  {title}")
    print("=" * 100)


def print_subsection(title: str):
    """Drukuje nagłówek podsekcji."""
    print("\n" + "-" * 100)
    print(f"  {title}")
    print("-" * 100)


def get_invoice_for_period(db: Session, period: str) -> ElectricityInvoice:
    """Znajduje fakturę dla danego okresu."""
    try:
        period_date = datetime.strptime(period, '%Y-%m').date()
    except ValueError:
        raise ValueError(f"Nieprawidłowy format okresu: {period}")
    
    invoices = db.query(ElectricityInvoice).all()
    invoice = None
    
    for inv in invoices:
        invoice_start_month = inv.data_poczatku_okresu.replace(day=1)
        if invoice_start_month <= period_date <= inv.data_konca_okresu:
            invoice = inv
            break
    
    if not invoice:
        raise ValueError(f"Brak faktury dla okresu {period}")
    
    return invoice


def calculate_detailed_costs(
    db: Session,
    invoice: ElectricityInvoice,
    usage_data: dict,
    local_name: str,
    manager: ElectricityBillingManager,
    period: str  # 'YYYY-MM' - okres rachunku
) -> dict:
    """Oblicza szczegółowe koszty dla lokalu."""
    costs = manager.calculate_bill_costs(invoice, usage_data, local_name, db, period)
    
    # Pobierz szczegóły faktury
    oplaty = db.query(ElectricityInvoiceOplataDystrybucyjna).filter(
        ElectricityInvoiceOplataDystrybucyjna.invoice_id == invoice.id
    ).all()
    
    # Opłaty stałe
    fixed_fees = []
    fixed_fees_total = 0.0
    target_fee_names = [
        'Opłata stała sieciowa - układ 3-fazowy',
        'Opłata przejściowa > 1200 kWh',
        'Opłata mocowa ( > 2800 kWh)',
        'Opłata abonamentowa'
    ]
    
    for oplata in oplaty:
        if oplata.typ_oplaty in target_fee_names:
            naleznosc = float(oplata.naleznosc) if oplata.naleznosc else 0.0
            fee_per_local = naleznosc / 3.0  # Dzielone na 3 lokale
            fixed_fees.append({
                'nazwa': oplata.typ_oplaty,
                'kwota_brutto': fee_per_local,
                'kwota_netto': fee_per_local / 1.23
            })
            fixed_fees_total += fee_per_local
    
    # Koszty energii i dystrybucji
    vat_rate = 0.23
    energy_cost_net = costs['energy_cost_gross'] / (1 + vat_rate)
    distribution_cost_net = costs['distribution_cost_gross'] / (1 + vat_rate)
    
    return {
        'usage_kwh': costs['usage_kwh'],
        'usage_kwh_dzienna': costs.get('usage_kwh_dzienna'),
        'usage_kwh_nocna': costs.get('usage_kwh_nocna'),
        'energy_cost_gross': costs['energy_cost_gross'],
        'energy_cost_net': energy_cost_net,
        'distribution_cost_gross': costs['distribution_cost_gross'],
        'distribution_cost_net': distribution_cost_net,
        'fixed_fees': fixed_fees,
        'fixed_fees_total_gross': fixed_fees_total,
        'fixed_fees_total_net': fixed_fees_total / (1 + vat_rate),
        'total_net_sum': costs['total_net_sum'],
        'total_gross_sum': costs['total_gross_sum']
    }


def print_period_calculations(db: Session, period: str):
    """Drukuje szczegółowe obliczenia dla jednego okresu."""
    print_section(f"OKRES ROZLICZENIOWY: {period}")
    
    # Pobierz fakturę
    try:
        invoice = get_invoice_for_period(db, period)
    except ValueError as e:
        print(f"\n[BRAK FAKTURY] {e}")
        return
    
    # Pobierz odczyty
    reading = db.query(ElectricityReading).filter(
        ElectricityReading.data == period
    ).first()
    
    if not reading:
        print(f"\n[BRAK ODCZYTÓW] Brak odczytów dla okresu {period}")
        return
    
    previous_reading = get_previous_reading(db, period)
    
    # Oblicz zużycie
    usage_data = calculate_all_usage(reading, previous_reading)
    
    # Oblicz zużycie DÓŁ z odczytu (zawiera GABINET) - osobno dla wyświetlania
    dol_reading_usage = calculate_dol_usage(reading, previous_reading)
    
    # Informacje o fakturze
    print_subsection("INFORMACJE O FAKTURZE")
    print(f"Numer faktury: {invoice.numer_faktury}")
    print(f"Okres faktury: {invoice.data_poczatku_okresu.strftime('%d.%m.%Y')} - {invoice.data_konca_okresu.strftime('%d.%m.%Y')}")
    print(f"Typ taryfy: {invoice.typ_taryfy}")
    print(f"Grupa taryfowa: {invoice.grupa_taryfowa}")
    print(f"Zużycie całkowite (DOM): {invoice.zuzycie_kwh} kWh")
    print(f"Ogółem sprzedaż energii (brutto): {format_currency(float(invoice.ogolem_sprzedaz_energii))}")
    print(f"Ogółem usługa dystrybucji (brutto): {format_currency(float(invoice.ogolem_usluga_dystrybucji))}")
    
    # Sprawdź okresy z faktury
    manager = ElectricityBillingManager()
    distribution_periods = manager.get_distribution_periods(db, invoice)
    
    if distribution_periods and len(distribution_periods) > 1:
        print(f"\n[INFO] Faktura ma {len(distribution_periods)} okresów z różnymi cenami:")
        for i, dist_period in enumerate(distribution_periods, 1):
            print(f"  Okres {i}: {dist_period['od']} - {dist_period['do']}")
            if dist_period.get('cena_1kwh_dzienna'):
                print(f"    Cena dzienna: {dist_period['cena_1kwh_dzienna']:.4f} zł/kWh (netto)")
            if dist_period.get('cena_1kwh_nocna'):
                print(f"    Cena nocna: {dist_period['cena_1kwh_nocna']:.4f} zł/kWh (netto)")
            if dist_period.get('cena_1kwh_calodobowa'):
                print(f"    Cena całodobowa: {dist_period['cena_1kwh_calodobowa']:.4f} zł/kWh (netto)")
        print(f"  [UWAGA] Używana jest NOWA LOGIKA z uwzględnieniem okresów i zazębiania się okresów!")
    else:
        print(f"\n[INFO] Faktura ma jedną cenę dla całego okresu - używana jest stara logika (fallback)")
    
    # Odczyty liczników
    print_subsection("ODCZYTY LICZNIKÓW")
    if reading.licznik_dom_jednotaryfowy:
        print(f"DOM (jednotaryfowy): {reading.odczyt_dom:.4f} kWh")
    else:
        print(f"DOM (dwutaryfowy): I={reading.odczyt_dom_I:.4f} kWh, II={reading.odczyt_dom_II:.4f} kWh")
    
    if previous_reading:
        if previous_reading.licznik_dom_jednotaryfowy:
            print(f"DOM poprzedni (jednotaryfowy): {previous_reading.odczyt_dom:.4f} kWh")
        else:
            print(f"DOM poprzedni (dwutaryfowy): I={previous_reading.odczyt_dom_I:.4f} kWh, II={previous_reading.odczyt_dom_II:.4f} kWh")
    else:
        print("DOM poprzedni: BRAK (pierwszy odczyt)")
    
    if reading.licznik_dol_jednotaryfowy:
        print(f"DÓŁ (jednotaryfowy): {reading.odczyt_dol:.4f} kWh")
    else:
        print(f"DÓŁ (dwutaryfowy): I={reading.odczyt_dol_I:.4f} kWh, II={reading.odczyt_dol_II:.4f} kWh")
    
    if previous_reading:
        if previous_reading.licznik_dol_jednotaryfowy:
            print(f"DÓŁ poprzedni (jednotaryfowy): {previous_reading.odczyt_dol:.4f} kWh")
        else:
            print(f"DÓŁ poprzedni (dwutaryfowy): I={previous_reading.odczyt_dol_I:.4f} kWh, II={previous_reading.odczyt_dol_II:.4f} kWh")
    else:
        print("DÓŁ poprzedni: BRAK (pierwszy odczyt)")
    
    print(f"GABINET: {reading.odczyt_gabinet:.4f} kWh")
    if previous_reading:
        print(f"GABINET poprzedni: {previous_reading.odczyt_gabinet:.4f} kWh")
    else:
        print("GABINET poprzedni: BRAK (pierwszy odczyt)")
    
    # Zużycie
    print_subsection("OBLICZONE ZUŻYCIE")
    
    # DOM
    print(f"DOM łącznie: {format_kwh(usage_data['dom']['zuzycie_dom_lacznie'])}")
    if usage_data['dom'].get('zuzycie_dom_I') is not None:
        print(f"  - Taryfa I (dzienna): {format_kwh(usage_data['dom']['zuzycie_dom_I'])}")
        print(f"  - Taryfa II (nocna): {format_kwh(usage_data['dom']['zuzycie_dom_II'])}")
        print(f"\n  WZÓR:")
        if not reading.licznik_dom_jednotaryfowy and previous_reading and not previous_reading.licznik_dom_jednotaryfowy:
            print(f"    Zużycie DOM I = odczyt_dom_I_bieżący - odczyt_dom_I_poprzedni")
            print(f"    Zużycie DOM I = {reading.odczyt_dom_I:.4f} - {previous_reading.odczyt_dom_I:.4f} = {usage_data['dom']['zuzycie_dom_I']:.4f} kWh")
            print(f"    Zużycie DOM II = odczyt_dom_II_bieżący - odczyt_dom_II_poprzedni")
            print(f"    Zużycie DOM II = {reading.odczyt_dom_II:.4f} - {previous_reading.odczyt_dom_II:.4f} = {usage_data['dom']['zuzycie_dom_II']:.4f} kWh")
            print(f"    Zużycie DOM łącznie = Zużycie DOM I + Zużycie DOM II")
            print(f"    Zużycie DOM łącznie = {usage_data['dom']['zuzycie_dom_I']:.4f} + {usage_data['dom']['zuzycie_dom_II']:.4f} = {usage_data['dom']['zuzycie_dom_lacznie']:.4f} kWh")
    
    # DÓŁ (z odczytu - zawiera GABINET)
    print(f"\nDÓŁ łącznie (z odczytu, zawiera GABINET): {format_kwh(dol_reading_usage['zuzycie_dol_lacznie'])}")
    if dol_reading_usage.get('zuzycie_dol_I') is not None:
        print(f"  - Taryfa I (dzienna): {format_kwh(dol_reading_usage['zuzycie_dol_I'])}")
        print(f"  - Taryfa II (nocna): {format_kwh(dol_reading_usage['zuzycie_dol_II'])}")
        print(f"\n  WZÓR:")
        if not reading.licznik_dol_jednotaryfowy and previous_reading and not previous_reading.licznik_dol_jednotaryfowy:
            print(f"    Zużycie DÓŁ I = odczyt_dol_I_bieżący - odczyt_dol_I_poprzedni")
            print(f"    Zużycie DÓŁ I = {reading.odczyt_dol_I:.4f} - {previous_reading.odczyt_dol_I:.4f} = {dol_reading_usage['zuzycie_dol_I']:.4f} kWh")
            print(f"    Zużycie DÓŁ II = odczyt_dol_II_bieżący - odczyt_dol_II_poprzedni")
            print(f"    Zużycie DÓŁ II = {reading.odczyt_dol_II:.4f} - {previous_reading.odczyt_dol_II:.4f} = {dol_reading_usage['zuzycie_dol_II']:.4f} kWh")
            print(f"    Zużycie DÓŁ łącznie = Zużycie DÓŁ I + Zużycie DÓŁ II")
            print(f"    Zużycie DÓŁ łącznie = {dol_reading_usage['zuzycie_dol_I']:.4f} + {dol_reading_usage['zuzycie_dol_II']:.4f} = {dol_reading_usage['zuzycie_dol_lacznie']:.4f} kWh")
    
    # GABINET
    print(f"\nGABINET: {format_kwh(usage_data['gabinet']['zuzycie_gabinet'])}")
    if usage_data['gabinet'].get('zuzycie_gabinet_dzienna') is not None:
        print(f"  - Aproksymacja dzienna (70%): {format_kwh(usage_data['gabinet']['zuzycie_gabinet_dzienna'])}")
        print(f"  - Aproksymacja nocna (30%): {format_kwh(usage_data['gabinet']['zuzycie_gabinet_nocna'])}")
        print(f"\n  WZÓR:")
        if previous_reading:
            print(f"    Zużycie GABINET = odczyt_gabinet_bieżący - odczyt_gabinet_poprzedni")
            print(f"    Zużycie GABINET = {reading.odczyt_gabinet:.4f} - {previous_reading.odczyt_gabinet:.4f} = {usage_data['gabinet']['zuzycie_gabinet']:.4f} kWh")
            print(f"    Aproksymacja dzienna = Zużycie GABINET * 0.7 = {usage_data['gabinet']['zuzycie_gabinet']:.4f} * 0.7 = {usage_data['gabinet']['zuzycie_gabinet_dzienna']:.4f} kWh")
            print(f"    Aproksymacja nocna = Zużycie GABINET * 0.3 = {usage_data['gabinet']['zuzycie_gabinet']:.4f} * 0.3 = {usage_data['gabinet']['zuzycie_gabinet_nocna']:.4f} kWh")
    
    # GÓRA
    print(f"\nGÓRA (obliczone: DOM - DÓŁ): {format_kwh(usage_data['gora']['zuzycie_gora_lacznie'])}")
    if usage_data['gora'].get('zuzycie_gora_I') is not None:
        print(f"  - Taryfa I (dzienna): {format_kwh(usage_data['gora']['zuzycie_gora_I'])}")
        print(f"  - Taryfa II (nocna): {format_kwh(usage_data['gora']['zuzycie_gora_II'])}")
        print(f"\n  WZÓR:")
        print(f"    Zużycie GÓRA I = Zużycie DOM I - Zużycie DÓŁ I")
        print(f"    Zużycie GÓRA I = {usage_data['dom']['zuzycie_dom_I']:.4f} - {dol_reading_usage['zuzycie_dol_I']:.4f} = {usage_data['gora']['zuzycie_gora_I']:.4f} kWh")
        print(f"    Zużycie GÓRA II = Zużycie DOM II - Zużycie DÓŁ II")
        print(f"    Zużycie GÓRA II = {usage_data['dom']['zuzycie_dom_II']:.4f} - {dol_reading_usage['zuzycie_dol_II']:.4f} = {usage_data['gora']['zuzycie_gora_II']:.4f} kWh")
        print(f"    Zużycie GÓRA łącznie = Zużycie GÓRA I + Zużycie GÓRA II")
        print(f"    Zużycie GÓRA łącznie = {usage_data['gora']['zuzycie_gora_I']:.4f} + {usage_data['gora']['zuzycie_gora_II']:.4f} = {usage_data['gora']['zuzycie_gora_lacznie']:.4f} kWh")
    
    # DOL (Mikołaj)
    print(f"\nDOL (Mikołaj) = DÓŁ - GABINET: {format_kwh(usage_data['dol']['zuzycie_dol_lacznie'])}")
    if usage_data['dol'].get('zuzycie_dol_I') is not None:
        print(f"  - Taryfa I (dzienna): {format_kwh(usage_data['dol']['zuzycie_dol_I'])}")
        print(f"  - Taryfa II (nocna): {format_kwh(usage_data['dol']['zuzycie_dol_II'])}")
        print(f"\n  WZÓR:")
        print(f"    Zużycie DOL łącznie = Zużycie DÓŁ łącznie - Zużycie GABINET")
        print(f"    Zużycie DOL łącznie = {dol_reading_usage['zuzycie_dol_lacznie']:.4f} - {usage_data['gabinet']['zuzycie_gabinet']:.4f} = {usage_data['dol']['zuzycie_dol_lacznie']:.4f} kWh")
        if usage_data['gabinet'].get('zuzycie_gabinet_dzienna') is not None:
            print(f"    Zużycie DOL I = Zużycie DÓŁ I - Aproksymacja dzienna GABINET")
            print(f"    Zużycie DOL I = {dol_reading_usage['zuzycie_dol_I']:.4f} - {usage_data['gabinet']['zuzycie_gabinet_dzienna']:.4f} = {usage_data['dol']['zuzycie_dol_I']:.4f} kWh")
            print(f"    Zużycie DOL II = Zużycie DÓŁ II - Aproksymacja nocna GABINET")
            print(f"    Zużycie DOL II = {dol_reading_usage['zuzycie_dol_II']:.4f} - {usage_data['gabinet']['zuzycie_gabinet_nocna']:.4f} = {usage_data['dol']['zuzycie_dol_II']:.4f} kWh")
    
    # Obliczenia dla każdego lokalu
    manager = ElectricityBillingManager()
    
    locals_data = [
        ('gora', 'GÓRA'),
        ('dol', 'DOL (Mikołaj)'),
        ('gabinet', 'GABINET')
    ]
    
    for local_name, local_display in locals_data:
        print_subsection(f"OBLICZENIA DLA LOKALU: {local_display}")
        
        detailed_costs = calculate_detailed_costs(db, invoice, usage_data, local_name, manager, period)
        
        # Zużycie
        print(f"\nZUŻYCIE:")
        print(f"  Łącznie: {format_kwh(detailed_costs['usage_kwh'])}")
        if detailed_costs['usage_kwh_dzienna'] is not None:
            print(f"  - Taryfa I (dzienna): {format_kwh(detailed_costs['usage_kwh_dzienna'])}")
            print(f"  - Taryfa II (nocna): {format_kwh(detailed_costs['usage_kwh_nocna'])}")
        
        # Proporcja zużycia
        total_usage = usage_data['dom']['zuzycie_dom_lacznie']
        if total_usage > 0:
            usage_ratio = detailed_costs['usage_kwh'] / total_usage
            print(f"\nPROPORCJA ZUŻYCIA:")
            print(f"  Udział w zużyciu DOM: {usage_ratio * 100:.2f}%")
            print(f"\n  WZÓR:")
            print(f"    Proporcja = Zużycie {local_display} / Zużycie DOM łącznie")
            print(f"    Proporcja = {detailed_costs['usage_kwh']:.4f} / {total_usage:.4f} = {usage_ratio:.4f} ({usage_ratio * 100:.2f}%)")
        
        # Sprawdź czy używana jest nowa logika z okresami
        distribution_periods = manager.get_distribution_periods(db, invoice)
        tenant_period_dates = manager.get_tenant_period_dates(db, period)
        
        # Koszty energii
        print(f"\nKOSZTY ENERGII ELEKTRYCZNEJ:")
        print(f"  Netto: {format_currency(detailed_costs['energy_cost_net'])}")
        print(f"  VAT 23%: {format_currency(detailed_costs['energy_cost_gross'] - detailed_costs['energy_cost_net'])}")
        print(f"  Brutto: {format_currency(detailed_costs['energy_cost_gross'])}")
        print(f"\n  WZÓR:")
        
        # NOWA LOGIKA: Jeśli faktura ma wiele okresów
        if distribution_periods and len(distribution_periods) > 1 and tenant_period_dates:
            tenant_start, tenant_end = tenant_period_dates
            print(f"    [NOWA LOGIKA] Faktura ma wiele okresów z różnymi cenami.")
            print(f"    Okres najemcy: {tenant_start} - {tenant_end}")
            
            # Oblicz overlapping periods dla tego lokalu
            usage_kwh_calodobowa = detailed_costs['usage_kwh'] if local_name == 'gabinet' else None
            result_overlapping = manager.calculate_bill_for_period_with_overlapping(
                tenant_start,
                tenant_end,
                distribution_periods,
                detailed_costs['usage_kwh_dzienna'] or 0.0,
                detailed_costs['usage_kwh_nocna'] or 0.0,
                usage_kwh_calodobowa
            )
            
            if result_overlapping.get('details'):
                print(f"\n    Obliczanie z uwzględnieniem zazębiania się okresów:")
                total_days = sum(d['days'] for d in result_overlapping['details'])
                print(f"    Całkowita liczba dni okresu najemcy: {total_days}")
                
                for detail in result_overlapping['details']:
                    period_name = detail['period']
                    days = detail['days']
                    proportion = detail['proportion']
                    
                    # Znajdź okres w distribution_periods
                    period_info = next((p for p in distribution_periods if p['okres'] == period_name), None)
                    
                    if period_info:
                        print(f"\n    {period_name} ({days} dni, {proportion:.2%} okresu najemcy):")
                        print(f"      Okres faktury: {period_info['od']} - {period_info['do']}")
                        
                        if local_name == 'gabinet':
                            usage_part = detailed_costs['usage_kwh'] * proportion
                            cena = period_info.get('cena_1kwh_calodobowa', 0) or 0
                            print(f"      Zużycie dla tej części: {usage_part:.4f} kWh")
                            print(f"      Cena: {cena:.4f} zł/kWh (netto)")
                            print(f"      Koszt energii (netto) = {usage_part:.4f} * {cena:.4f} = {detail['energy_cost_net']:.4f} zł")
                        else:
                            usage_dzienna_part = (detailed_costs['usage_kwh_dzienna'] or 0) * proportion
                            usage_nocna_part = (detailed_costs['usage_kwh_nocna'] or 0) * proportion
                            cena_dzienna = period_info.get('cena_1kwh_dzienna', 0) or 0
                            cena_nocna = period_info.get('cena_1kwh_nocna', 0) or 0
                            print(f"      Zużycie dzienne dla tej części: {usage_dzienna_part:.4f} kWh")
                            print(f"      Zużycie nocne dla tej części: {usage_nocna_part:.4f} kWh")
                            print(f"      Cena dzienna: {cena_dzienna:.4f} zł/kWh (netto)")
                            print(f"      Cena nocna: {cena_nocna:.4f} zł/kWh (netto)")
                            print(f"      Koszt energii (netto) = ({usage_dzienna_part:.4f} * {cena_dzienna:.4f}) + ({usage_nocna_part:.4f} * {cena_nocna:.4f}) = {detail['energy_cost_net']:.4f} zł")
                        
                        print(f"      Opłaty stałe (netto) = {period_info['suma_oplat_stalych']:.2f} * {proportion:.4f} = {detail['fixed_cost_net']:.4f} zł")
                
                print(f"\n    Suma kosztów energii ze wszystkich okresów:")
                print(f"      Koszt energii (netto) = {result_overlapping['energy_cost_net']:.4f} zł")
                print(f"      Koszt energii (brutto) = {result_overlapping['energy_cost_net']:.4f} * 1.23 = {result_overlapping['energy_cost_gross']:.4f} zł")
        
        # STARA LOGIKA: Fallback
        else:
            koszty_kwh = calculate_kwh_cost(invoice.id, db)
            if invoice.typ_taryfy == "DWUTARYFOWA" and "DZIENNA" in koszty_kwh and "NOCNA" in koszty_kwh:
                # Taryfa dwutaryfowa - średnia ważona
                koszt_dzienna = koszty_kwh["DZIENNA"].get("suma", 0)
                koszt_nocna = koszty_kwh["NOCNA"].get("suma", 0)
                koszt_sredni_wazony = round(koszt_dzienna * 0.7 + koszt_nocna * 0.3, 4)
                print(f"    [STARA LOGIKA] Dla taryfy DWUTARYFOWEJ używamy średniej ważonej kosztu 1 kWh:")
                print(f"    Koszt 1 kWh (dzienna, netto) = {koszt_dzienna:.4f} zł/kWh")
                print(f"    Koszt 1 kWh (nocna, netto) = {koszt_nocna:.4f} zł/kWh")
                print(f"    Średnia ważona = Koszt dzienna * 0.7 + Koszt nocna * 0.3")
                print(f"    Średnia ważona = {koszt_dzienna:.4f} * 0.7 + {koszt_nocna:.4f} * 0.3 = {koszt_sredni_wazony:.4f} zł/kWh")
                print(f"    Koszt energii (netto) = Średnia ważona * Zużycie {local_display}")
                print(f"    Koszt energii (netto) = {koszt_sredni_wazony:.4f} * {detailed_costs['usage_kwh']:.4f} = {detailed_costs['energy_cost_net']:.4f} zł")
                print(f"    Koszt energii (brutto) = Koszt energii (netto) * 1.23")
                print(f"    Koszt energii (brutto) = {detailed_costs['energy_cost_net']:.4f} * 1.23 = {detailed_costs['energy_cost_gross']:.4f} zł")
            else:
                # Taryfa całodobowa - proporcja
                print(f"    [STARA LOGIKA] Dla taryfy CAŁODOBOWEJ używamy proporcji zużycia:")
                print(f"    Koszt energii (brutto) = Ogółem sprzedaż energii (brutto) * Proporcja")
                print(f"    Koszt energii (brutto) = {float(invoice.ogolem_sprzedaz_energii):.2f} * {usage_ratio:.4f} = {detailed_costs['energy_cost_gross']:.4f} zł")
                print(f"    Koszt energii (netto) = Koszt energii (brutto) / 1.23")
                print(f"    Koszt energii (netto) = {detailed_costs['energy_cost_gross']:.4f} / 1.23 = {detailed_costs['energy_cost_net']:.4f} zł")
        
        # Koszty dystrybucji
        print(f"\nKOSZTY DYSTRYBUCJI:")
        print(f"  Netto: {format_currency(detailed_costs['distribution_cost_net'])}")
        print(f"  VAT 23%: {format_currency(detailed_costs['distribution_cost_gross'] - detailed_costs['distribution_cost_net'])}")
        print(f"  Brutto: {format_currency(detailed_costs['distribution_cost_gross'])}")
        print(f"\n  WZÓR:")
        
        # NOWA LOGIKA: W nowej logice dystrybucja jest już wliczona w cenę za kWh
        if distribution_periods and len(distribution_periods) > 1:
            print(f"    [NOWA LOGIKA] Opłaty dystrybucyjne zmienne są już wliczone w cenę za kWh")
            print(f"    (cena_1kwh_dzienna/nocna zawiera już opłaty dystrybucyjne zmienne)")
            print(f"    Więc distribution_cost = 0 (już wliczone w energy_cost)")
            print(f"    Koszt dystrybucji (netto) = 0.00 zł")
            print(f"    Koszt dystrybucji (brutto) = 0.00 zł")
        
        # STARA LOGIKA: Fallback
        else:
            koszty_kwh = calculate_kwh_cost(invoice.id, db)
            if invoice.typ_taryfy == "DWUTARYFOWA" and "DZIENNA" in koszty_kwh and "NOCNA" in koszty_kwh:
                # Taryfa dwutaryfowa - średnia ważona dystrybucji
                from app.models.electricity_invoice import ElectricityInvoiceOplataDystrybucyjna
                oplaty = db.query(ElectricityInvoiceOplataDystrybucyjna).filter(
                    ElectricityInvoiceOplataDystrybucyjna.invoice_id == invoice.id
                ).all()
                
                dystrybucja_dzienna = 0.0
                dystrybucja_nocna = 0.0
                for op in oplaty:
                    if op.jednostka == "kWh":
                        if op.strefa == "DZIENNA":
                            dystrybucja_dzienna += float(op.cena)
                        elif op.strefa == "NOCNA":
                            dystrybucja_nocna += float(op.cena)
                
                dystrybucja_srednia_wazona = round(dystrybucja_dzienna * 0.7 + dystrybucja_nocna * 0.3, 4)
                print(f"    [STARA LOGIKA] Dla taryfy DWUTARYFOWEJ używamy średniej ważonej kosztu dystrybucji 1 kWh:")
                print(f"    Koszt dystrybucji 1 kWh (dzienna, netto) = {dystrybucja_dzienna:.4f} zł/kWh")
                print(f"    Koszt dystrybucji 1 kWh (nocna, netto) = {dystrybucja_nocna:.4f} zł/kWh")
                print(f"    Średnia ważona = Koszt dzienna * 0.7 + Koszt nocna * 0.3")
                print(f"    Średnia ważona = {dystrybucja_dzienna:.4f} * 0.7 + {dystrybucja_nocna:.4f} * 0.3 = {dystrybucja_srednia_wazona:.4f} zł/kWh")
                print(f"    Koszt dystrybucji (netto) = Średnia ważona * Zużycie {local_display}")
                print(f"    Koszt dystrybucji (netto) = {dystrybucja_srednia_wazona:.4f} * {detailed_costs['usage_kwh']:.4f} = {detailed_costs['distribution_cost_net']:.4f} zł")
                print(f"    Koszt dystrybucji (brutto) = Koszt dystrybucji (netto) * 1.23")
                print(f"    Koszt dystrybucji (brutto) = {detailed_costs['distribution_cost_net']:.4f} * 1.23 = {detailed_costs['distribution_cost_gross']:.4f} zł")
            else:
                # Taryfa całodobowa - proporcja
                print(f"    [STARA LOGIKA] Dla taryfy CAŁODOBOWEJ używamy proporcji zużycia:")
                print(f"    Koszt dystrybucji (brutto) = Ogółem usługa dystrybucji (brutto) * Proporcja")
                print(f"    Koszt dystrybucji (brutto) = {float(invoice.ogolem_usluga_dystrybucji):.2f} * {usage_ratio:.4f} = {detailed_costs['distribution_cost_gross']:.4f} zł")
                print(f"    Koszt dystrybucji (netto) = Koszt dystrybucji (brutto) / 1.23")
                print(f"    Koszt dystrybucji (netto) = {detailed_costs['distribution_cost_gross']:.4f} / 1.23 = {detailed_costs['distribution_cost_net']:.4f} zł")
        
        # Opłaty stałe
        print(f"\nOPŁATY STAŁE (podzielone na 3 lokale):")
        total_fees_brutto_all = 0.0
        for fee in detailed_costs['fixed_fees']:
            print(f"  {fee['nazwa']}:")
            print(f"    Netto: {format_currency(fee['kwota_netto'])}")
            print(f"    VAT 23%: {format_currency(fee['kwota_brutto'] - fee['kwota_netto'])}")
            print(f"    Brutto: {format_currency(fee['kwota_brutto'])}")
            total_fees_brutto_all += fee['kwota_brutto']
        
        print(f"\n  SUMA OPŁAT STAŁYCH:")
        print(f"    Netto: {format_currency(detailed_costs['fixed_fees_total_net'])}")
        print(f"    VAT 23%: {format_currency(detailed_costs['fixed_fees_total_gross'] - detailed_costs['fixed_fees_total_net'])}")
        print(f"    Brutto: {format_currency(detailed_costs['fixed_fees_total_gross'])}")
        print(f"\n  WZÓR:")
        print(f"    Opłaty stałe są podzielone równo na 3 lokale (GÓRA, DOL, GABINET)")
        print(f"    Każda opłata stała z faktury jest dzielona przez 3:")
        if detailed_costs['fixed_fees']:
            first_fee = detailed_costs['fixed_fees'][0]
            print(f"    Przykład: {first_fee['nazwa']}")
            print(f"    Opłata dla lokalu (brutto) = Opłata z faktury (brutto) / 3")
            print(f"    Opłata dla lokalu (brutto) = {first_fee['kwota_brutto'] * 3:.2f} / 3 = {first_fee['kwota_brutto']:.2f} zł")
            print(f"    Opłata dla lokalu (netto) = Opłata dla lokalu (brutto) / 1.23")
            print(f"    Opłata dla lokalu (netto) = {first_fee['kwota_brutto']:.2f} / 1.23 = {first_fee['kwota_netto']:.2f} zł")
        print(f"    Suma opłat stałych (brutto) = Suma wszystkich opłat dla lokalu")
        print(f"    Suma opłat stałych (brutto) = {detailed_costs['fixed_fees_total_gross']:.2f} zł")
        print(f"    Suma opłat stałych (netto) = Suma opłat stałych (brutto) / 1.23")
        print(f"    Suma opłat stałych (netto) = {detailed_costs['fixed_fees_total_gross']:.2f} / 1.23 = {detailed_costs['fixed_fees_total_net']:.2f} zł")
        
        # Podsumowanie
        print(f"\nPODSUMOWANIE:")
        print(f"  Koszty energii (netto): {format_currency(detailed_costs['energy_cost_net'])}")
        print(f"  Koszty dystrybucji (netto): {format_currency(detailed_costs['distribution_cost_net'])}")
        print(f"  Opłaty stałe (netto): {format_currency(detailed_costs['fixed_fees_total_net'])}")
        print(f"  RAZEM NETTO: {format_currency(detailed_costs['total_net_sum'])}")
        print(f"  VAT 23%: {format_currency(detailed_costs['total_gross_sum'] - detailed_costs['total_net_sum'])}")
        print(f"  RAZEM BRUTTO: {format_currency(detailed_costs['total_gross_sum'])}")
        print(f"\n  WZÓR:")
        print(f"    RAZEM NETTO = Koszty energii (netto) + Koszty dystrybucji (netto) + Opłaty stałe (netto)")
        print(f"    RAZEM NETTO = {detailed_costs['energy_cost_net']:.2f} + {detailed_costs['distribution_cost_net']:.2f} + {detailed_costs['fixed_fees_total_net']:.2f} = {detailed_costs['total_net_sum']:.2f} zł")
        print(f"    VAT 23% = RAZEM NETTO * 0.23")
        print(f"    VAT 23% = {detailed_costs['total_net_sum']:.2f} * 0.23 = {detailed_costs['total_gross_sum'] - detailed_costs['total_net_sum']:.2f} zł")
        print(f"    RAZEM BRUTTO = RAZEM NETTO + VAT 23%")
        print(f"    RAZEM BRUTTO = {detailed_costs['total_net_sum']:.2f} + {detailed_costs['total_gross_sum'] - detailed_costs['total_net_sum']:.2f} = {detailed_costs['total_gross_sum']:.2f} zł")


def main():
    """Główna funkcja."""
    import sys
    from io import StringIO
    
    init_db()
    db = SessionLocal()
    
    # Przechwytuj output do stringa
    output_buffer = StringIO()
    original_stdout = sys.stdout
    
    try:
        periods = ['2024-02', '2024-03', '2024-04']
        
        # Przekieruj stdout do bufora
        sys.stdout = output_buffer
        
        print("\n" + "=" * 100)
        print("  SZCZEGÓŁOWE OBLICZENIA RACHUNKÓW ZA PRĄD")
        print("  Okres rozliczeniowy: 2024-02 do 2024-04")
        print("  Lokale: GÓRA, DOL (Mikołaj), GABINET")
        print("=" * 100)
        
        for period in periods:
            try:
                print_period_calculations(db, period)
            except Exception as e:
                print(f"\n[BŁĄD] Błąd podczas przetwarzania okresu {period}: {e}")
                import traceback
                traceback.print_exc()
        
        print("\n" + "=" * 100)
        print("  KONIEC RAPORTU")
        print("=" * 100 + "\n")
        
        # Przywróć stdout i wyświetl na ekran
        sys.stdout = original_stdout
        output_text = output_buffer.getvalue()
        print(output_text)
        
        # Zapisz do pliku
        output_file = os.path.join(project_root, "obliczenia_rachunkow_prad_2024_02_04.txt")
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(output_text)
        
        print(f"\n[RAPORT ZAPISANY] Plik: {output_file}")
        
    finally:
        db.close()
        output_buffer.close()


if __name__ == "__main__":
    main()

