"""
Skrypt do szczegółowej analizy obliczeń kosztów dla konkretnej faktury i okresu.
Pokazuje krok po kroku jak są obliczane koszty dla każdego lokalu.
"""

import sys
import os

# Dodaj główny katalog projektu do ścieżki
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.electricity import ElectricityReading, ElectricityBill
from app.models.electricity_invoice import (
    ElectricityInvoice,
    ElectricityInvoiceSprzedazEnergii,
    ElectricityInvoiceOplataDystrybucyjna
)
from app.services.electricity.manager import ElectricityBillingManager
from app.services.electricity.calculator import calculate_all_usage, get_previous_reading
from app.services.electricity.cost_calculator import calculate_kwh_cost


def analyze_bill_calculation(invoice_number: str, period: str):
    """Analizuje obliczenia kosztów dla konkretnej faktury i okresu."""
    db: Session = SessionLocal()
    
    try:
        # Znajdź fakturę
        invoice = db.query(ElectricityInvoice).filter(
            ElectricityInvoice.numer_faktury == invoice_number
        ).first()
        
        if not invoice:
            print(f"[BLAD] Nie znaleziono faktury: {invoice_number}")
            return
        
        print(f"FAKTURA: {invoice.numer_faktury}")
        print(f"   Okres: {invoice.data_poczatku_okresu} - {invoice.data_konca_okresu}")
        print(f"   Typ taryfy: {invoice.typ_taryfy}")
        print(f"   Ogolem sprzedaz energii (brutto): {float(invoice.ogolem_sprzedaz_energii):.2f} zl")
        print(f"   Ogolem usluga dystrybucji (brutto): {float(invoice.ogolem_usluga_dystrybucji):.2f} zl")
        print()
        
        # Znajdź odczyty dla okresu
        reading = db.query(ElectricityReading).filter(
            ElectricityReading.data == period
        ).first()
        
        if not reading:
            print(f"[BLAD] Nie znaleziono odczytow dla okresu: {period}")
            return
        
        print(f"ODCZYTY DLA OKRESU: {period}")
        if reading.licznik_dom_jednotaryfowy:
            print(f"   DOM (jednotaryfowy): {reading.odczyt_dom}")
        else:
            print(f"   DOM (dwutaryfowy): I={reading.odczyt_dom_I}, II={reading.odczyt_dom_II}")
        
        if reading.licznik_dol_jednotaryfowy:
            print(f"   DÓŁ (jednotaryfowy): {reading.odczyt_dol}")
        else:
            print(f"   DÓŁ (dwutaryfowy): I={reading.odczyt_dol_I}, II={reading.odczyt_dol_II}")
        
        print(f"   GABINET: {reading.odczyt_gabinet}")
        print()
        
        # Oblicz zużycie
        previous_reading = get_previous_reading(db, period)
        if previous_reading:
            print(f"ODCZYTY POPRZEDNIE: {previous_reading.data}")
            if previous_reading.licznik_dom_jednotaryfowy:
                print(f"   DOM: {previous_reading.odczyt_dom}")
            else:
                print(f"   DOM: I={previous_reading.odczyt_dom_I}, II={previous_reading.odczyt_dom_II}")
            print()
        
        usage_data = calculate_all_usage(reading, previous_reading)
        
        print(f"ZUZYCIE (kWh):")
        print(f"   DOM łącznie: {usage_data['dom']['zuzycie_dom_lacznie']:.4f}")
        if usage_data['dom'].get('zuzycie_dom_I'):
            print(f"   DOM dzienna (I): {usage_data['dom']['zuzycie_dom_I']:.4f}")
            print(f"   DOM nocna (II): {usage_data['dom']['zuzycie_dom_II']:.4f}")
        print(f"   GÓRA łącznie: {usage_data['gora']['zuzycie_gora_lacznie']:.4f}")
        if usage_data['gora'].get('zuzycie_gora_I'):
            print(f"   GÓRA dzienna (I): {usage_data['gora']['zuzycie_gora_I']:.4f}")
            print(f"   GÓRA nocna (II): {usage_data['gora']['zuzycie_gora_II']:.4f}")
        print(f"   DÓŁ łącznie: {usage_data['dol']['zuzycie_dol_lacznie']:.4f}")
        if usage_data['dol'].get('zuzycie_dol_I'):
            print(f"   DÓŁ dzienna (I): {usage_data['dol']['zuzycie_dol_I']:.4f}")
            print(f"   DÓŁ nocna (II): {usage_data['dol']['zuzycie_dol_II']:.4f}")
        print(f"   GABINET: {usage_data['gabinet']['zuzycie_gabinet']:.4f}")
        print()
        
        # Oblicz koszty dla każdego lokalu
        manager = ElectricityBillingManager()
        
        # Sprawdź typ taryfy
        if invoice.typ_taryfy == "DWUTARYFOWA":
            print("METODA OBLICZENIA: Taryfa DWUTARYFOWA - srednia wazona")
            print()
            
            # Pobierz koszty 1 kWh
            koszty_kwh = calculate_kwh_cost(invoice.id, db)
            
            print("KOSZTY 1 kWh (NETTO):")
            if "DZIENNA" in koszty_kwh:
                dzienna = koszty_kwh["DZIENNA"]
                print(f"   DZIENNA:")
                print(f"      Energia czynna: {dzienna.get('energia_czynna', 0):.4f} zł/kWh")
                print(f"      Opłata jakościowa: {dzienna.get('oplata_jakosciowa', 0):.4f} zł/kWh")
                print(f"      Opłata zmienna sieciowa: {dzienna.get('oplata_zmienna_sieciowa', 0):.4f} zł/kWh")
                print(f"      Opłata OZE: {dzienna.get('oplata_oze', 0):.4f} zł/kWh")
                print(f"      Opłata kogeneracyjna: {dzienna.get('oplata_kogeneracyjna', 0):.4f} zł/kWh")
                print(f"      SUMA: {dzienna.get('suma', 0):.4f} zł/kWh")
            
            if "NOCNA" in koszty_kwh:
                nocna = koszty_kwh["NOCNA"]
                print(f"   NOCNA:")
                print(f"      Energia czynna: {nocna.get('energia_czynna', 0):.4f} zł/kWh")
                print(f"      Opłata jakościowa: {nocna.get('oplata_jakosciowa', 0):.4f} zł/kWh")
                print(f"      Opłata zmienna sieciowa: {nocna.get('oplata_zmienna_sieciowa', 0):.4f} zł/kWh")
                print(f"      Opłata OZE: {nocna.get('oplata_oze', 0):.4f} zł/kWh")
                print(f"      Opłata kogeneracyjna: {nocna.get('oplata_kogeneracyjna', 0):.4f} zł/kWh")
                print(f"      SUMA: {nocna.get('suma', 0):.4f} zł/kWh")
            
            if "DZIENNA" in koszty_kwh and "NOCNA" in koszty_kwh:
                koszt_dzienna = koszty_kwh["DZIENNA"].get("suma", 0)
                koszt_nocna = koszty_kwh["NOCNA"].get("suma", 0)
                koszt_sredni_wazony = round(koszt_dzienna * 0.7 + koszt_nocna * 0.3, 4)
                print(f"   ŚREDNIA WAŻONA (0.7 * dzienna + 0.3 * nocna): {koszt_sredni_wazony:.4f} zł/kWh (NETTO)")
            print()
            
            # Pobierz opłaty dystrybucyjne
            oplaty = db.query(ElectricityInvoiceOplataDystrybucyjna).filter(
                ElectricityInvoiceOplataDystrybucyjna.invoice_id == invoice.id,
                ElectricityInvoiceOplataDystrybucyjna.jednostka == "kWh"
            ).all()
            
            dystrybucja_dzienna = 0.0
            dystrybucja_nocna = 0.0
            for op in oplaty:
                if op.strefa == "DZIENNA":
                    dystrybucja_dzienna += float(op.cena)
                elif op.strefa == "NOCNA":
                    dystrybucja_nocna += float(op.cena)
            
            dystrybucja_srednia_wazona = round(dystrybucja_dzienna * 0.7 + dystrybucja_nocna * 0.3, 4)
            print(f"KOSZTY DYSTRYBUCJI 1 kWh (NETTO):")
            print(f"   DZIENNA: {dystrybucja_dzienna:.4f} zł/kWh")
            print(f"   NOCNA: {dystrybucja_nocna:.4f} zł/kWh")
            print(f"   ŚREDNIA WAŻONA: {dystrybucja_srednia_wazona:.4f} zł/kWh (NETTO)")
            print()
            
        else:
            print("METODA OBLICZENIA: Taryfa CALODOBOWA - proporcja zuzycia")
            print()
            total_usage = usage_data['dom']['zuzycie_dom_lacznie']
            print(f"   Całkowite zużycie DOM: {total_usage:.4f} kWh")
            print(f"   Ogółem sprzedaż energii (brutto): {float(invoice.ogolem_sprzedaz_energii):.2f} zł")
            print(f"   Ogółem usługa dystrybucji (brutto): {float(invoice.ogolem_usluga_dystrybucji):.2f} zł")
            print()
        
        # Oblicz opłaty stałe
        fixed_fees_gross = manager.calculate_fixed_fees_per_local(invoice, db)
        print(f"OPLATY STALE (brutto na lokal): {fixed_fees_gross:.4f} zl")
        print(f"   (Oplaty stale z faktury * 2 miesiace / 3 lokale)")
        print()
        
        # Oblicz koszty dla każdego lokalu
        locals_list = ['gora', 'dol', 'gabinet']
        
        for local_name in locals_list:
            print(f"{'='*60}")
            print(f"LOKAL: {local_name.upper()}")
            print(f"{'='*60}")
            
            costs = manager.calculate_bill_costs(invoice, usage_data, local_name, db)
            
            print(f"   Zużycie: {costs['usage_kwh']:.4f} kWh")
            if costs.get('usage_kwh_dzienna'):
                print(f"   Zużycie dzienna: {costs['usage_kwh_dzienna']:.4f} kWh")
                print(f"   Zużycie nocna: {costs['usage_kwh_nocna']:.4f} kWh")
            print()
            
            if invoice.typ_taryfy == "DWUTARYFOWA":
                print(f"   OBLICZENIA (taryfa dwutaryfowa):")
                print(f"   1. Koszt energii NETTO = średnia ważona * zużycie")
                print(f"      = {koszt_sredni_wazony:.4f} * {costs['usage_kwh']:.4f}")
                energy_cost_net = round(koszt_sredni_wazony * costs['usage_kwh'], 4)
                print(f"      = {energy_cost_net:.4f} zł (NETTO)")
                print()
                print(f"   2. Koszt energii BRUTTO = netto * 1.23")
                energy_cost_gross = round(energy_cost_net * 1.23, 4)
                print(f"      = {energy_cost_net:.4f} * 1.23")
                print(f"      = {energy_cost_gross:.4f} zł (BRUTTO)")
                print()
                print(f"   3. Koszt dystrybucji NETTO = średnia ważona dystrybucji * zużycie")
                print(f"      = {dystrybucja_srednia_wazona:.4f} * {costs['usage_kwh']:.4f}")
                distribution_cost_net = round(dystrybucja_srednia_wazona * costs['usage_kwh'], 4)
                print(f"      = {distribution_cost_net:.4f} zł (NETTO)")
                print()
                print(f"   4. Koszt dystrybucji BRUTTO = netto * 1.23")
                distribution_cost_gross = round(distribution_cost_net * 1.23, 4)
                print(f"      = {distribution_cost_net:.4f} * 1.23")
                print(f"      = {distribution_cost_gross:.4f} zł (BRUTTO)")
            else:
                total_usage = usage_data['dom']['zuzycie_dom_lacznie']
                usage_ratio = costs['usage_kwh'] / total_usage
                print(f"   OBLICZENIA (taryfa całodobowa):")
                print(f"   1. Proporcja zużycia = zużycie lokalu / zużycie DOM")
                print(f"      = {costs['usage_kwh']:.4f} / {total_usage:.4f}")
                print(f"      = {usage_ratio:.4f}")
                print()
                print(f"   2. Koszt energii BRUTTO = ogolem_sprzedaz_energii * proporcja")
                energy_cost_gross = float(invoice.ogolem_sprzedaz_energii) * usage_ratio
                print(f"      = {float(invoice.ogolem_sprzedaz_energii):.2f} * {usage_ratio:.4f}")
                print(f"      = {energy_cost_gross:.4f} zł (BRUTTO)")
                print()
                print(f"   3. Koszt dystrybucji BRUTTO = ogolem_usluga_dystrybucji * proporcja")
                distribution_cost_gross = float(invoice.ogolem_usluga_dystrybucji) * usage_ratio
                print(f"      = {float(invoice.ogolem_usluga_dystrybucji):.2f} * {usage_ratio:.4f}")
                print(f"      = {distribution_cost_gross:.4f} zł (BRUTTO)")
            
            print()
            print(f"   5. Opłaty stałe (brutto): {fixed_fees_gross:.4f} zł")
            print()
            print(f"   PODSUMOWANIE:")
            print(f"      Koszt energii brutto: {costs['energy_cost_gross']:.4f} zł")
            print(f"      Koszt dystrybucji brutto: {costs['distribution_cost_gross']:.4f} zł")
            print(f"      Opłaty stałe brutto: {fixed_fees_gross:.4f} zł")
            print(f"      RAZEM BRUTTO: {costs['total_gross_sum']:.4f} zł")
            print(f"      RAZEM NETTO: {costs['total_net_sum']:.4f} zł")
            print()
        
        # Sprawdź wygenerowane rachunki
        print(f"{'='*60}")
        print(f"WYGENEROWANE RACHUNKI W BAZIE:")
        print(f"{'='*60}")
        
        bills = db.query(ElectricityBill).filter(
            ElectricityBill.data == period,
            ElectricityBill.invoice_id == invoice.id
        ).all()
        
        for bill in bills:
            print(f"   {bill.local.upper()}:")
            print(f"      Zużycie: {bill.usage_kwh:.4f} kWh")
            print(f"      Koszt energii brutto: {bill.energy_cost_gross:.4f} zł")
            print(f"      Koszt dystrybucji brutto: {bill.distribution_cost_gross:.4f} zł")
            print(f"      Razem brutto: {bill.total_gross_sum:.4f} zł")
            print()
        
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Użycie: python tools/analyze_bill_calculation.py <numer_faktury> <okres>")
        print("Przykład: python tools/analyze_bill_calculation.py 'P/23666363/0002/24' '2024-10'")
        sys.exit(1)
    
    invoice_number = sys.argv[1]
    period = sys.argv[2]
    
    analyze_bill_calculation(invoice_number, period)

