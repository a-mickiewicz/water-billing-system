"""
Moduł zarządzania odczytami i rozliczaniem rachunków za prąd.
Oblicza koszty na podstawie faktur i dzieli proporcjonalnie między lokale.
"""

from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import datetime
from app.models.electricity import ElectricityReading, ElectricityBill
from app.models.electricity_invoice import ElectricityInvoice, ElectricityInvoiceBlankiet, ElectricityInvoiceOplataDystrybucyjna
from app.models.water import Local
from app.services.electricity.calculator import (
    calculate_all_usage,
    get_previous_reading
)
from app.services.electricity.cost_calculator import calculate_kwh_cost


class ElectricityBillingManager:
    """Zarządzanie odczytami i rozliczaniem rachunków za prąd."""
    
    def get_usage_for_period(
        self,
        db: Session,
        data: str
    ) -> Optional[Dict[str, Any]]:
        """
        Pobiera i oblicza zużycie dla danego okresu.
        
        Args:
            db: Sesja bazy danych
            data: Data w formacie 'YYYY-MM'
        
        Returns:
            Słownik z zużyciem dla wszystkich lokali lub None
        """
        current = db.query(ElectricityReading).filter(
            ElectricityReading.data == data
        ).first()
        
        if not current:
            return None
        
        previous = get_previous_reading(db, data)
        return calculate_all_usage(current, previous)
    
    def get_usage_for_local(
        self,
        db: Session,
        data: str,
        local_name: str
    ) -> Optional[float]:
        """
        Pobiera zużycie dla konkretnego lokalu w danym okresie.
        
        Args:
            db: Sesja bazy danych
            data: Data w formacie 'YYYY-MM'
            local_name: Nazwa lokalu ('gora', 'dol', 'gabinet')
        
        Returns:
            Zużycie w kWh lub None
        """
        usage_data = self.get_usage_for_period(db, data)
        if not usage_data:
            return None
        
        if local_name == 'gora':
            return usage_data['gora']['zuzycie_gora_lacznie']
        elif local_name == 'dol':
            return usage_data['dol']['zuzycie_dol_lacznie']
        elif local_name == 'gabinet':
            return usage_data['gabinet']['zuzycie_gabinet']
        else:
            return None
    
    def calculate_fixed_fees_per_local(
        self,
        invoice: ElectricityInvoice,
        db: Session
    ) -> float:
        """
        Oblicza sumę opłat stałych (stała sieciowa, przejściowa, abonamentowa, mocowa)
        pomnożoną przez 2 (okres rozliczeniowy około 2 miesiące) i podzieloną na 3 lokale.
        
        Args:
            invoice: Faktura prądu
            db: Sesja bazy danych
        
        Returns:
            Kwota opłat stałych przypadająca na jeden lokal (brutto)
        """
        # Lista nazw opłat do zsumowania
        target_fee_names = [
            'Opłata stała sieciowa - układ 3-fazowy',
            'Opłata przejściowa > 1200 kWh',
            'Opłata mocowa ( > 2800 kWh)',
            'Opłata abonamentowa'
        ]
        
        # Pobierz wszystkie opłaty dystrybucyjne dla faktury
        oplaty = db.query(ElectricityInvoiceOplataDystrybucyjna).filter(
            ElectricityInvoiceOplataDystrybucyjna.invoice_id == invoice.id
        ).all()
        
        # Sumuj należności dla opłat z listy
        total_fees = 0.0
        for oplata in oplaty:
            if oplata.typ_oplaty in target_fee_names:
                # Należność jest już w formacie brutto
                naleznosc = float(oplata.naleznosc) if oplata.naleznosc else 0.0
                total_fees += naleznosc
        
        # Pomnóż przez 2 (okres rozliczeniowy około 2 miesiące)
        total_fees *= 2
        
        # Podziel na 3 lokale
        fee_per_local = total_fees / 3.0
        
        return round(fee_per_local, 4)
    
    def calculate_bill_costs(
        self,
        invoice: ElectricityInvoice,
        usage_data: Dict[str, Any],
        local_name: str,
        db: Session
    ) -> Dict[str, float]:
        """
        Oblicza koszty dla pojedynczego rachunku prądu.
        
        Jeśli faktura jest dwutaryfowa, używa średniej ważonej (dzienna * 0.7 + nocna * 0.3)
        dla wszystkich lokali. W przeciwnym razie używa proporcji zużycia.
        
        Args:
            invoice: Faktura prądu
            usage_data: Dane zużycia (ze calculate_all_usage)
            local_name: Nazwa lokalu ('gora', 'dol', 'gabinet')
            db: Sesja bazy danych
        
        Returns:
            Słownik z obliczonymi kosztami dla lokalu
        """
        # Pobierz zużycie dla lokalu z usage_data (łącznie oraz dzienne/nocne)
        if local_name == 'gora':
            local_usage = usage_data['gora']['zuzycie_gora_lacznie']
            local_usage_dzienna = usage_data['gora'].get('zuzycie_gora_I')
            local_usage_nocna = usage_data['gora'].get('zuzycie_gora_II')
        elif local_name == 'dol':
            local_usage = usage_data['dol']['zuzycie_dol_lacznie']
            local_usage_dzienna = usage_data['dol'].get('zuzycie_dol_I')
            local_usage_nocna = usage_data['dol'].get('zuzycie_dol_II')
        elif local_name == 'gabinet':
            local_usage = usage_data['gabinet']['zuzycie_gabinet']
            local_usage_dzienna = None  # GABINET jest zawsze jednotaryfowy
            local_usage_nocna = None
        else:
            local_usage = 0.0
            local_usage_dzienna = None
            local_usage_nocna = None
        
        if local_usage is None or local_usage <= 0:
            return {
                'usage_kwh': 0.0,
                'usage_kwh_dzienna': None,
                'usage_kwh_nocna': None,
                'energy_cost_gross': 0.0,
                'distribution_cost_gross': 0.0,
                'total_net_sum': 0.0,
                'total_gross_sum': 0.0
            }
        
        # Jeśli faktura jest dwutaryfowa, użyj średniej ważonej dla wszystkich lokali
        if invoice.typ_taryfy == "DWUTARYFOWA":
            from app.services.electricity.cost_calculator import calculate_kwh_cost
            koszty_kwh = calculate_kwh_cost(invoice.id, db)
            
            # Sprawdź czy faktura ma dwie taryfy (DZIENNA i NOCNA)
            if "DZIENNA" in koszty_kwh and "NOCNA" in koszty_kwh:
                koszt_dzienna = koszty_kwh["DZIENNA"].get("suma", 0)
                koszt_nocna = koszty_kwh["NOCNA"].get("suma", 0)
                # Oblicz średnią ważoną: dzienna * 0.7 + nocna * 0.3
                koszt_sredni_wazony = round(koszt_dzienna * 0.7 + koszt_nocna * 0.3, 4)
                
                # Użyj średniej ważonej do obliczenia kosztów energii
                # Koszt = średnia ważona kosztu 1 kWh * zużycie lokalu
                energy_cost_gross = round(koszt_sredni_wazony * local_usage, 4)
                
                # Dla dystrybucji również użyj średniej ważonej
                # Pobierz opłaty dystrybucyjne z faktury
                from app.models.electricity_invoice import ElectricityInvoiceOplataDystrybucyjna
                oplaty = db.query(ElectricityInvoiceOplataDystrybucyjna).filter(
                    ElectricityInvoiceOplataDystrybucyjna.invoice_id == invoice.id
                ).all()
                
                # Oblicz średnią ważoną kosztu dystrybucji na kWh
                dystrybucja_dzienna = 0.0
                dystrybucja_nocna = 0.0
                for op in oplaty:
                    if op.jednostka != "kWh":
                        continue
                    if op.strefa == "DZIENNA":
                        dystrybucja_dzienna += float(op.cena)
                    elif op.strefa == "NOCNA":
                        dystrybucja_nocna += float(op.cena)
                
                dystrybucja_srednia_wazona = round(dystrybucja_dzienna * 0.7 + dystrybucja_nocna * 0.3, 4)
                
                # Koszt dystrybucji = średnia ważona * zużycie
                distribution_cost_gross = round(dystrybucja_srednia_wazona * local_usage, 4)
                
                # Oblicz netto (zakładając VAT 23%)
                vat_rate = 0.23
                energy_cost_net = round(energy_cost_gross / (1 + vat_rate), 4)
                distribution_cost_net = round(distribution_cost_gross / (1 + vat_rate), 4)
                
                # Dodaj opłaty stałe (stała sieciowa, przejściowa, abonamentowa, mocowa)
                # Pomnożone przez 2 (okres rozliczeniowy około 2 miesiące) i podzielone na 3 lokale
                fixed_fees_gross = self.calculate_fixed_fees_per_local(invoice, db)
                fixed_fees_net = round(fixed_fees_gross / (1 + vat_rate), 4)
                
                total_net_sum = round(energy_cost_net + distribution_cost_net + fixed_fees_net, 4)
                total_gross_sum = round(energy_cost_gross + distribution_cost_gross + fixed_fees_gross, 4)
                
                # Dla gabinetu nie mamy dziennej/nocnej, dla innych lokali zachowujemy
                return {
                    'usage_kwh': round(local_usage, 4),
                    'usage_kwh_dzienna': round(local_usage_dzienna, 4) if local_usage_dzienna is not None else None,
                    'usage_kwh_nocna': round(local_usage_nocna, 4) if local_usage_nocna is not None else None,
                    'energy_cost_gross': energy_cost_gross,
                    'distribution_cost_gross': distribution_cost_gross,
                    'total_net_sum': total_net_sum,
                    'total_gross_sum': total_gross_sum
                }
        
        # Dla taryfy całodobowej lub gdy nie ma dwóch taryf, użyj proporcji zużycia
        total_usage = usage_data['dom']['zuzycie_dom_lacznie']
        if total_usage <= 0:
            return {
                'usage_kwh': round(local_usage, 4) if local_usage is not None else 0.0,
                'usage_kwh_dzienna': round(local_usage_dzienna, 4) if local_usage_dzienna is not None else None,
                'usage_kwh_nocna': round(local_usage_nocna, 4) if local_usage_nocna is not None else None,
                'energy_cost_gross': 0.0,
                'distribution_cost_gross': 0.0,
                'total_net_sum': 0.0,
                'total_gross_sum': 0.0
            }
        
        usage_ratio = local_usage / total_usage
        
        # Rozdziel koszty proporcjonalnie z nowego modelu faktury
        # Nowy model ma: ogolem_sprzedaz_energii i ogolem_usluga_dystrybucji (brutto)
        energy_cost_gross = float(invoice.ogolem_sprzedaz_energii) * usage_ratio
        distribution_cost_gross = float(invoice.ogolem_usluga_dystrybucji) * usage_ratio
        
        # Oblicz netto (zakładając VAT 23% - standardowy VAT dla energii)
        # Jeśli potrzebujemy dokładnego VAT, możemy obliczyć z naleznosc_za_okres
        vat_rate = 0.23  # Domyślny VAT 23%
        energy_cost_net = energy_cost_gross / (1 + vat_rate)
        distribution_cost_net = distribution_cost_gross / (1 + vat_rate)
        
        # Dodaj opłaty stałe (stała sieciowa, przejściowa, abonamentowa, mocowa)
        # Pomnożone przez 2 (okres rozliczeniowy około 2 miesiące) i podzielone na 3 lokale
        fixed_fees_gross = self.calculate_fixed_fees_per_local(invoice, db)
        fixed_fees_net = round(fixed_fees_gross / (1 + vat_rate), 4)
        
        total_net_sum = energy_cost_net + distribution_cost_net + fixed_fees_net
        total_gross_sum = energy_cost_gross + distribution_cost_gross + fixed_fees_gross
        
        # Zaokrąglij wszystkie wartości do 4 miejsc po przecinku
        return {
            'usage_kwh': round(local_usage, 4) if local_usage is not None else 0.0,
            'usage_kwh_dzienna': round(local_usage_dzienna, 4) if local_usage_dzienna is not None else None,
            'usage_kwh_nocna': round(local_usage_nocna, 4) if local_usage_nocna is not None else None,
            'energy_cost_gross': round(energy_cost_gross, 4),
            'distribution_cost_gross': round(distribution_cost_gross, 4),
            'total_net_sum': round(total_net_sum, 4),
            'total_gross_sum': round(total_gross_sum, 4)
        }
    
    def find_blankiet_for_period(
        self,
        db: Session,
        invoice_id: int,
        period: str  # 'YYYY-MM'
    ) -> Optional[ElectricityInvoiceBlankiet]:
        """
        Znajduje blankiet (podokres) dla danego okresu rozliczeniowego.
        
        Args:
            db: Sesja bazy danych
            invoice_id: ID faktury
            period: Okres w formacie 'YYYY-MM'
        
        Returns:
            Blankiet odpowiadający okresowi lub None
        """
        # Parsuj okres na datę (pierwszy dzień miesiąca)
        try:
            period_date = datetime.strptime(period, '%Y-%m').date()
        except ValueError:
            return None
        
        # Pobierz wszystkie blankiety dla faktury
        blankiety = db.query(ElectricityInvoiceBlankiet).filter(
            ElectricityInvoiceBlankiet.invoice_id == invoice_id
        ).all()
        
        # Znajdź blankiet, którego okres zawiera datę okresu
        for blankiet in blankiety:
            if blankiet.poczatek_podokresu and blankiet.koniec_podokresu:
                # Sprawdź czy okres rachunku mieści się w podokresie blankietu
                if blankiet.poczatek_podokresu <= period_date <= blankiet.koniec_podokresu:
                    return blankiet
            elif blankiet.poczatek_podokresu:
                # Jeśli brak końca, sprawdź tylko początek (miesiąc powinien być >= początek)
                if period_date >= blankiet.poczatek_podokresu:
                    return blankiet
        
        # Jeśli nie znaleziono, zwróć pierwszy blankiet (jako fallback)
        if blankiety:
            return blankiety[0]
        
        return None
    
    def generate_bills_for_period(
        self,
        db: Session,
        data: str
    ) -> list[ElectricityBill]:
        """
        Generuje rachunki dla wszystkich lokali w danym okresie.
        
        Args:
            db: Sesja bazy danych
            data: Data w formacie 'YYYY-MM'
        
        Returns:
            Lista wygenerowanych rachunków
        """
        # Parsuj okres na datę (pierwszy dzień miesiąca)
        try:
            period_date = datetime.strptime(data, '%Y-%m').date()
        except ValueError:
            raise ValueError(f"Nieprawidłowy format okresu: {data}. Oczekiwany format: YYYY-MM")
        
        # Znajdź fakturę, której okres zawiera datę
        # Okres rozliczeniowy dwumiesięczny zaczyna się początkiem okresu (pierwszy dzień miesiąca)
        # Więc sprawdzamy czy okres rachunku (pierwszy dzień miesiąca) jest w zakresie faktury
        invoices = db.query(ElectricityInvoice).all()
        invoice = None
        
        for inv in invoices:
            # Pobierz pierwszy dzień miesiąca z początku okresu faktury
            invoice_start_month = inv.data_poczatku_okresu.replace(day=1)
            
            # Sprawdź czy okres rachunku (pierwszy dzień miesiąca) jest w zakresie faktury
            # period_date to już pierwszy dzień miesiąca (z parsowania 'YYYY-MM')
            if invoice_start_month <= period_date <= inv.data_konca_okresu:
                invoice = inv
                break
        
        if not invoice:
            raise ValueError(f"Brak faktury dla okresu {data}")
        
        # Znajdź blankiet dla okresu
        blankiet = self.find_blankiet_for_period(db, invoice.id, data)
        
        # Oblicz koszt 1 kWh dla faktury
        koszty_kwh = calculate_kwh_cost(invoice.id, db)
        
        # Pobierz dane zużycia
        usage_data = self.get_usage_for_period(db, data)
        if not usage_data:
            raise ValueError(f"Brak odczytów dla okresu {data}")
        
        # Pobierz lokale
        locals = db.query(Local).all()
        bills = []
        
        for local in locals:
            # Oblicz koszty
            costs = self.calculate_bill_costs(invoice, usage_data, local.local, db)
            
            # Sprawdź czy rachunek już istnieje
            existing_bill = db.query(ElectricityBill).filter(
                ElectricityBill.data == data,
                ElectricityBill.local == local.local
            ).first()
            
            if existing_bill:
                # Aktualizuj istniejący (w tym invoice_id, bo mogło się zmienić po poprawce logiki)
                existing_bill.invoice_id = invoice.id
                existing_bill.usage_kwh = costs['usage_kwh']
                existing_bill.usage_kwh_dzienna = costs.get('usage_kwh_dzienna')
                existing_bill.usage_kwh_nocna = costs.get('usage_kwh_nocna')
                existing_bill.energy_cost_gross = costs['energy_cost_gross']
                existing_bill.distribution_cost_gross = costs['distribution_cost_gross']
                existing_bill.total_net_sum = costs['total_net_sum']
                existing_bill.total_gross_sum = costs['total_gross_sum']
                bills.append(existing_bill)
            else:
                # Utwórz nowy
                bill = ElectricityBill(
                    data=data,
                    local=local.local,
                    reading_id=None,  # TODO: powiązać z odczytem
                    invoice_id=invoice.id,
                    local_id=local.id,
                    usage_kwh=costs['usage_kwh'],
                    usage_kwh_dzienna=costs.get('usage_kwh_dzienna'),
                    usage_kwh_nocna=costs.get('usage_kwh_nocna'),
                    energy_cost_gross=costs['energy_cost_gross'],
                    distribution_cost_gross=costs['distribution_cost_gross'],
                    total_net_sum=costs['total_net_sum'],
                    total_gross_sum=costs['total_gross_sum']
                )
                db.add(bill)
                bills.append(bill)
        
        # Dodaj rachunek dla całego domu (DOM) - suma wszystkich lokali
        dom_usage = usage_data['dom']['zuzycie_dom_lacznie']
        dom_usage_dzienna = usage_data['dom'].get('zuzycie_dom_I')
        dom_usage_nocna = usage_data['dom'].get('zuzycie_dom_II')
        
        if dom_usage and dom_usage > 0:
            # Koszty dla całego domu to całkowite koszty z faktury
            dom_energy_cost_gross = float(invoice.ogolem_sprzedaz_energii)
            dom_distribution_cost_gross = float(invoice.ogolem_usluga_dystrybucji)
            
            # Oblicz netto (zakładając VAT 23%) - zaokrąglone do 4 miejsc
            vat_rate = 0.23
            dom_energy_cost_net = round(dom_energy_cost_gross / (1 + vat_rate), 4)
            dom_distribution_cost_net = round(dom_distribution_cost_gross / (1 + vat_rate), 4)
            
            # Dodaj opłaty stałe dla całego domu (pomnożone przez 2, bez dzielenia na lokale)
            # Opłaty stałe dla DOM = suma opłat stałych * 2 (okres rozliczeniowy około 2 miesiące)
            fixed_fees_dom_gross = self.calculate_fixed_fees_per_local(invoice, db) * 3.0
            fixed_fees_dom_net = round(fixed_fees_dom_gross / (1 + vat_rate), 4)
            
            dom_total_net_sum = round(dom_energy_cost_net + dom_distribution_cost_net + fixed_fees_dom_net, 4)
            dom_total_gross_sum = round(dom_energy_cost_gross + dom_distribution_cost_gross + fixed_fees_dom_gross, 4)
            
            # Zaokrąglij również zużycie i koszty brutto do 4 miejsc
            dom_usage = round(dom_usage, 4) if dom_usage else 0.0
            dom_usage_dzienna = round(dom_usage_dzienna, 4) if dom_usage_dzienna is not None else None
            dom_usage_nocna = round(dom_usage_nocna, 4) if dom_usage_nocna is not None else None
            dom_energy_cost_gross = round(dom_energy_cost_gross, 4)
            dom_distribution_cost_gross = round(dom_distribution_cost_gross, 4)
            
            # Sprawdź czy rachunek DOM już istnieje
            existing_dom_bill = db.query(ElectricityBill).filter(
                ElectricityBill.data == data,
                ElectricityBill.local == 'dom'
            ).first()
            
            if existing_dom_bill:
                # Aktualizuj istniejący (w tym invoice_id, bo mogło się zmienić po poprawce logiki)
                existing_dom_bill.invoice_id = invoice.id
                existing_dom_bill.usage_kwh = dom_usage
                existing_dom_bill.usage_kwh_dzienna = dom_usage_dzienna
                existing_dom_bill.usage_kwh_nocna = dom_usage_nocna
                existing_dom_bill.energy_cost_gross = dom_energy_cost_gross
                existing_dom_bill.distribution_cost_gross = dom_distribution_cost_gross
                existing_dom_bill.total_net_sum = dom_total_net_sum
                existing_dom_bill.total_gross_sum = dom_total_gross_sum
                bills.append(existing_dom_bill)
            else:
                # Utwórz nowy rachunek dla DOM
                dom_bill = ElectricityBill(
                    data=data,
                    local='dom',
                    reading_id=None,
                    invoice_id=invoice.id,
                    local_id=None,  # DOM nie ma przypisanego lokalu w tabeli locals
                    usage_kwh=dom_usage,
                    usage_kwh_dzienna=dom_usage_dzienna,
                    usage_kwh_nocna=dom_usage_nocna,
                    energy_cost_gross=dom_energy_cost_gross,
                    distribution_cost_gross=dom_distribution_cost_gross,
                    total_net_sum=dom_total_net_sum,
                    total_gross_sum=dom_total_gross_sum
                )
                db.add(dom_bill)
                bills.append(dom_bill)
        
        db.commit()
        return bills

