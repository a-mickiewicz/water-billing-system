"""
Moduł zarządzania odczytami i rozliczaniem rachunków za prąd.
Oblicza koszty na podstawie faktur i dzieli proporcjonalnie między lokale.
"""

from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import datetime, date, timedelta
from app.models.electricity import ElectricityReading, ElectricityBill
from app.models.electricity_invoice import (
    ElectricityInvoice, 
    ElectricityInvoiceBlankiet, 
    ElectricityInvoiceOplataDystrybucyjna,
    ElectricityInvoiceSprzedazEnergii,
    ElectricityInvoiceRozliczenieOkres
)
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
        podzieloną na 3 lokale.
        
        UWAGA: Opłaty stałe w fakturze są już za cały okres faktury (np. 12 miesięcy),
        więc NIE mnożymy ich przez liczbę miesięcy - tylko dzielimy na lokale.
        
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
                # Należność jest już w formacie brutto i za cały okres faktury
                naleznosc = float(oplata.naleznosc) if oplata.naleznosc else 0.0
                total_fees += naleznosc
        
        # Podziel na 3 lokale (opłaty są już za cały okres faktury, nie mnożymy przez liczbę miesięcy)
        fee_per_local = total_fees / 3.0
        
        return round(fee_per_local, 4)
    
    def calculate_bill_costs(
        self,
        invoice: ElectricityInvoice,
        usage_data: Dict[str, Any],
        local_name: str,
        db: Session,
        data: str  # 'YYYY-MM' - okres rachunku
    ) -> Dict[str, float]:
        """
        Oblicza koszty dla pojedynczego rachunku prądu.
        
        Używa nowej logiki z uwzględnieniem okresów z faktury (gdzie mogą być różne ceny).
        Jeśli faktura ma okresy z różnymi cenami, oblicza overlapping periods i proporcjonalnie
        dzieli zużycie. W przeciwnym razie używa starej logiki (fallback).
        
        Args:
            invoice: Faktura prądu
            usage_data: Dane zużycia (ze calculate_all_usage)
            local_name: Nazwa lokalu ('gora', 'dol', 'gabinet')
            db: Sesja bazy danych
            data: Okres rachunku w formacie 'YYYY-MM'
        
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
        
        # NOWA LOGIKA: Sprawdź czy faktura ma okresy z różnymi cenami
        distribution_periods = self.get_distribution_periods(db, invoice)
        
        if distribution_periods and len(distribution_periods) > 1:
            # Faktura ma wiele okresów - użyj nowej logiki z overlapping periods
            tenant_period_dates = self.get_tenant_period_dates(db, data)
            
            if tenant_period_dates:
                tenant_period_start, tenant_period_end = tenant_period_dates
                
                # Użyj usage_kwh_calodobowa dla gabinetu
                usage_kwh_calodobowa = local_usage if local_name == 'gabinet' else None
                
                # Oblicz koszty z uwzględnieniem overlapping periods
                result = self.calculate_bill_for_period_with_overlapping(
                    tenant_period_start,
                    tenant_period_end,
                    distribution_periods,
                    local_usage_dzienna or 0.0,
                    local_usage_nocna or 0.0,
                    usage_kwh_calodobowa
                )
                
                return {
                    'usage_kwh': round(local_usage, 4),
                    'usage_kwh_dzienna': round(local_usage_dzienna, 4) if local_usage_dzienna is not None else None,
                    'usage_kwh_nocna': round(local_usage_nocna, 4) if local_usage_nocna is not None else None,
                    'energy_cost_gross': result['energy_cost_gross'],
                    'distribution_cost_gross': result['distribution_cost_gross'],
                    'total_net_sum': result['total_net_sum'],
                    'total_gross_sum': result['total_gross_sum']
                }
        
        # FALLBACK: Stara logika (gdy nie ma okresów lub jest tylko jeden okres)
        
        # Jeśli faktura jest dwutaryfowa, użyj średniej ważonej dla wszystkich lokali
        if invoice.typ_taryfy == "DWUTARYFOWA":
            from app.services.electricity.cost_calculator import calculate_kwh_cost
            koszty_kwh = calculate_kwh_cost(invoice.id, db)
            
            # Sprawdź czy faktura ma dwie taryfy (DZIENNA i NOCNA)
            if "DZIENNA" in koszty_kwh and "NOCNA" in koszty_kwh:
                koszt_dzienna = koszty_kwh["DZIENNA"].get("suma", 0)
                koszt_nocna = koszty_kwh["NOCNA"].get("suma", 0)
                # Oblicz średnią ważoną: dzienna * 0.7 + nocna * 0.3
                # Uwaga: koszt_sredni_wazony to koszt NETTO za 1 kWh (suma energii + opłat dystrybucyjnych zmiennych)
                koszt_sredni_wazony = round(koszt_dzienna * 0.7 + koszt_nocna * 0.3, 4)
                
                # Oblicz koszt netto energii: średnia ważona kosztu netto 1 kWh * zużycie lokalu
                energy_cost_net = round(koszt_sredni_wazony * local_usage, 4)
                
                # Dla dystrybucji również użyj średniej ważonej
                # Pobierz opłaty dystrybucyjne z faktury
                from app.models.electricity_invoice import ElectricityInvoiceOplataDystrybucyjna
                oplaty = db.query(ElectricityInvoiceOplataDystrybucyjna).filter(
                    ElectricityInvoiceOplataDystrybucyjna.invoice_id == invoice.id
                ).all()
                
                # Oblicz średnią ważoną kosztu dystrybucji na kWh (netto)
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
                
                # Koszt dystrybucji netto = średnia ważona * zużycie
                distribution_cost_net = round(dystrybucja_srednia_wazona * local_usage, 4)
                
                # Oblicz brutto (zakładając VAT 23%)
                vat_rate = 0.23
                energy_cost_gross = round(energy_cost_net * (1 + vat_rate), 4)
                distribution_cost_gross = round(distribution_cost_net * (1 + vat_rate), 4)
                
                # Dodaj opłaty stałe (stała sieciowa, przejściowa, abonamentowa, mocowa)
                # Podzielone na 3 lokale (opłaty są już za cały okres faktury)
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
        # Podzielone na 3 lokale (opłaty są już za cały okres faktury)
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
    
    def get_tenant_period_dates(
        self,
        db: Session,
        data: str
    ) -> Optional[tuple[date, date]]:
        """
        Określa daty początku i końca okresu najemcy na podstawie odczytów.
        
        Args:
            db: Sesja bazy danych
            data: Data w formacie 'YYYY-MM'
        
        Returns:
            Tuple (start_date, end_date) lub None jeśli brak odczytów
        """
        current = db.query(ElectricityReading).filter(
            ElectricityReading.data == data
        ).first()
        
        if not current:
            return None
        
        previous = get_previous_reading(db, data)
        
        # Okres najemcy kończy się w dacie odczytu obecnego
        if current.data_odczytu_licznika:
            end_date = current.data_odczytu_licznika
        else:
            # Fallback: parsujemy datę z formatu 'YYYY-MM'
            year, month = map(int, data.split('-'))
            # Zakładamy, że odczyty są około 10. dnia miesiąca
            end_date = date(year, month, 10)
        
        # Okres najemcy zaczyna się dzień po dacie odczytu poprzedniego
        if previous and previous.data_odczytu_licznika:
            start_date = previous.data_odczytu_licznika + timedelta(days=1)
        elif previous:
            # Fallback: parsujemy datę z formatu 'YYYY-MM'
            year, month = map(int, previous.data.split('-'))
            start_date = date(year, month, 10) + timedelta(days=1)
        else:
            # Pierwszy odczyt - okres zaczyna się pierwszego dnia miesiąca
            year, month = map(int, data.split('-'))
            start_date = date(year, month, 1)
        
        return (start_date, end_date)
    
    def get_distribution_periods(
        self,
        db: Session,
        invoice: ElectricityInvoice
    ) -> List[Dict[str, Any]]:
        """
        Wyłania okresy z faktury, gdzie mogą być różne ceny.
        
        Pobiera dane z:
        1. electricity_invoice_rozliczenie_okresy (jeśli są dostępne)
        2. electricity_invoice_oplaty_dystrybucyjne (grupowane po data)
        3. electricity_invoice_sprzedaz_energii (grupowane po kolejności)
        
        Args:
            db: Sesja bazy danych
            invoice: Faktura prądu
        
        Returns:
            Lista słowników z okresami, każdy zawiera:
            - od, do: daty okresu
            - cena_1kwh_dzienna, cena_1kwh_nocna, cena_1kwh_calodobowa: ceny netto za 1 kWh
            - suma_oplat_stalych: suma opłat stałych (netto)
        """
        periods = []
        
        # Najpierw sprawdź czy są rozliczenie_okresy
        rozliczenie_okresy = db.query(ElectricityInvoiceRozliczenieOkres).filter(
            ElectricityInvoiceRozliczenieOkres.invoice_id == invoice.id
        ).order_by(ElectricityInvoiceRozliczenieOkres.numer_okresu).all()
        
        if rozliczenie_okresy:
            # Użyj rozliczenie_okresy do wyłaniania okresów
            # Ale nadal musimy pobrać opłaty i sprzedaż dla każdego okresu
            # Przejdź do logiki z opłatami dystrybucyjnymi, ale użyj dat z rozliczenie_okresy
            # (pominięte - przejdź do dalszej logiki)
            pass
        
        # Jeśli nie ma rozliczenie_okresy, użyj opłat dystrybucyjnych
        oplaty = db.query(ElectricityInvoiceOplataDystrybucyjna).filter(
            ElectricityInvoiceOplataDystrybucyjna.invoice_id == invoice.id
        ).order_by(ElectricityInvoiceOplataDystrybucyjna.data).all()
        
        if not oplaty:
            return periods
        
        # Pobierz sprzedaż energii
        sprzedaz = db.query(ElectricityInvoiceSprzedazEnergii).filter(
            ElectricityInvoiceSprzedazEnergii.invoice_id == invoice.id
        ).order_by(ElectricityInvoiceSprzedazEnergii.data).all()
        
        # Okres rozliczeniowy faktury
        period_start_year = invoice.data_poczatku_okresu.year
        period_start = date(period_start_year, 11, 1)
        period_end = date(period_start_year + 1, 10, 31)
        
        # Grupujemy opłaty po datach (okresach)
        unique_dates = sorted(set(o.data for o in oplaty if o.data))
        
        if not unique_dates:
            return periods
        
        # Grupujemy sprzedaż po kolejności
        sprzedaz_grouped = []
        if invoice.typ_taryfy == "DWUTARYFOWA":
            i = 0
            while i < len(sprzedaz):
                dzienna = None
                nocna = None
                if i < len(sprzedaz) and sprzedaz[i].strefa == "DZIENNA":
                    dzienna = sprzedaz[i]
                    i += 1
                if i < len(sprzedaz) and sprzedaz[i].strefa == "NOCNA":
                    nocna = sprzedaz[i]
                    i += 1
                if dzienna or nocna:
                    sprzedaz_grouped.append({"dzienna": dzienna, "nocna": nocna})
        else:
            for s in sprzedaz:
                sprzedaz_grouped.append({"calodobowa": s})
        
        current_start = period_start
        MAX_REASONABLE_PRICE_PER_KWH = 5.0
        
        for i, dist_date in enumerate(unique_dates):
            dist_period_end = dist_date
            sprzedaz_period = sprzedaz_grouped[i] if i < len(sprzedaz_grouped) else {}
            oplaty_period = [o for o in oplaty if o.data == dist_date]
            
            # Ceny z sprzedaży energii
            cena_dzienna = None
            cena_nocna = None
            cena_calodobowa = None
            
            if sprzedaz_period.get("dzienna") and sprzedaz_period["dzienna"].ilosc_kwh > 0:
                cena_raw = float(sprzedaz_period["dzienna"].cena_za_kwh)
                if cena_raw > MAX_REASONABLE_PRICE_PER_KWH:
                    naleznosc = float(sprzedaz_period["dzienna"].naleznosc)
                    ilosc = float(sprzedaz_period["dzienna"].ilosc_kwh)
                    if ilosc > 0:
                        cena_z_naleznosci = naleznosc / ilosc
                        cena_dzienna = cena_z_naleznosci if cena_z_naleznosci <= MAX_REASONABLE_PRICE_PER_KWH else cena_raw
                    else:
                        cena_dzienna = cena_raw
                else:
                    cena_dzienna = cena_raw
            
            if sprzedaz_period.get("nocna") and sprzedaz_period["nocna"].ilosc_kwh > 0:
                cena_raw = float(sprzedaz_period["nocna"].cena_za_kwh)
                if cena_raw > MAX_REASONABLE_PRICE_PER_KWH:
                    naleznosc = float(sprzedaz_period["nocna"].naleznosc)
                    ilosc = float(sprzedaz_period["nocna"].ilosc_kwh)
                    if ilosc > 0:
                        cena_z_naleznosci = naleznosc / ilosc
                        cena_nocna = cena_z_naleznosci if cena_z_naleznosci <= MAX_REASONABLE_PRICE_PER_KWH else cena_raw
                    else:
                        cena_nocna = cena_raw
                else:
                    cena_nocna = cena_raw
            
            if sprzedaz_period.get("calodobowa") and sprzedaz_period["calodobowa"].ilosc_kwh > 0:
                cena_raw = float(sprzedaz_period["calodobowa"].cena_za_kwh)
                if cena_raw > MAX_REASONABLE_PRICE_PER_KWH:
                    naleznosc = float(sprzedaz_period["calodobowa"].naleznosc)
                    ilosc = float(sprzedaz_period["calodobowa"].ilosc_kwh)
                    if ilosc > 0:
                        cena_z_naleznosci = naleznosc / ilosc
                        cena_calodobowa = cena_z_naleznosci if cena_z_naleznosci <= MAX_REASONABLE_PRICE_PER_KWH else cena_raw
                    else:
                        cena_calodobowa = cena_raw
                else:
                    cena_calodobowa = cena_raw
            
            # Opłaty dystrybucyjne zmienne (za kWh)
            oplata_jakosciowa_dzienna = None
            oplata_jakosciowa_nocna = None
            oplata_zmienna_sieciowa_dzienna = None
            oplata_zmienna_sieciowa_nocna = None
            oplata_oze_dzienna = None
            oplata_oze_nocna = None
            oplata_kogeneracyjna_dzienna = None
            oplata_kogeneracyjna_nocna = None
            
            # Opłaty stałe (za miesiąc)
            oplata_stala_sieciowa = None
            oplata_przejściowa = None
            oplata_abonamentowa = None
            oplata_mocowa = None
            
            for o in oplaty_period:
                typ_oplaty_upper = o.typ_oplaty.upper()
                if o.jednostka == "kWh":
                    if "JAKOŚCIOWA" in typ_oplaty_upper or "JAKOSCIOWA" in typ_oplaty_upper:
                        if o.strefa == "DZIENNA":
                            oplata_jakosciowa_dzienna = float(o.cena)
                        elif o.strefa == "NOCNA":
                            oplata_jakosciowa_nocna = float(o.cena)
                    elif "ZMIENNA SIECIOWA" in typ_oplaty_upper:
                        if o.strefa == "DZIENNA":
                            oplata_zmienna_sieciowa_dzienna = float(o.cena)
                        elif o.strefa == "NOCNA":
                            oplata_zmienna_sieciowa_nocna = float(o.cena)
                    elif "OZE" in typ_oplaty_upper:
                        if o.strefa == "DZIENNA":
                            oplata_oze_dzienna = float(o.cena)
                        elif o.strefa == "NOCNA":
                            oplata_oze_nocna = float(o.cena)
                    elif "KOGENERACYJNA" in typ_oplaty_upper:
                        if o.strefa == "DZIENNA":
                            oplata_kogeneracyjna_dzienna = float(o.cena)
                        elif o.strefa == "NOCNA":
                            oplata_kogeneracyjna_nocna = float(o.cena)
                elif o.jednostka == "zł/mc":
                    if "STAŁA SIECIOWA" in typ_oplaty_upper or "STALA SIECIOWA" in typ_oplaty_upper:
                        oplata_stala_sieciowa = float(o.cena)
                    elif "PRZEJŚCIOWA" in typ_oplaty_upper or "PRZEJSCIOWA" in typ_oplaty_upper:
                        oplata_przejściowa = float(o.cena)
                    elif "ABONAMENTOWA" in typ_oplaty_upper:
                        oplata_abonamentowa = float(o.cena)
                    elif "MOCOWA" in typ_oplaty_upper:
                        oplata_mocowa = float(o.cena)
            
            # Obliczamy cenę za 1kWh dla okresu (netto)
            cena_1kwh_dzienna = None
            cena_1kwh_nocna = None
            cena_1kwh_calodobowa = None
            
            if cena_dzienna is not None:
                cena_1kwh_dzienna = cena_dzienna
                if oplata_jakosciowa_dzienna is not None:
                    cena_1kwh_dzienna += oplata_jakosciowa_dzienna
                if oplata_zmienna_sieciowa_dzienna is not None:
                    cena_1kwh_dzienna += oplata_zmienna_sieciowa_dzienna
                if oplata_oze_dzienna is not None:
                    cena_1kwh_dzienna += oplata_oze_dzienna
                if oplata_kogeneracyjna_dzienna is not None:
                    cena_1kwh_dzienna += oplata_kogeneracyjna_dzienna
                cena_1kwh_dzienna = round(cena_1kwh_dzienna, 4)
            
            if cena_nocna is not None:
                cena_1kwh_nocna = cena_nocna
                if oplata_jakosciowa_nocna is not None:
                    cena_1kwh_nocna += oplata_jakosciowa_nocna
                if oplata_zmienna_sieciowa_nocna is not None:
                    cena_1kwh_nocna += oplata_zmienna_sieciowa_nocna
                if oplata_oze_nocna is not None:
                    cena_1kwh_nocna += oplata_oze_nocna
                if oplata_kogeneracyjna_nocna is not None:
                    cena_1kwh_nocna += oplata_kogeneracyjna_nocna
                cena_1kwh_nocna = round(cena_1kwh_nocna, 4)
            
            if cena_calodobowa is not None:
                cena_1kwh_calodobowa = cena_calodobowa
                for o in oplaty_period:
                    if o.jednostka == "kWh" and (o.strefa is None or o.strefa == "CAŁODOBOWA"):
                        if "JAKOŚCIOWA" in o.typ_oplaty.upper() or "ZMIENNA SIECIOWA" in o.typ_oplaty.upper() or \
                           "OZE" in o.typ_oplaty.upper() or "KOGENERACYJNA" in o.typ_oplaty.upper():
                            cena_1kwh_calodobowa += float(o.cena)
                cena_1kwh_calodobowa = round(cena_1kwh_calodobowa, 4)
            
            # Suma opłat stałych (netto)
            suma_oplat_stalych = 0
            if oplata_stala_sieciowa is not None:
                suma_oplat_stalych += oplata_stala_sieciowa
            if oplata_przejściowa is not None:
                suma_oplat_stalych += oplata_przejściowa
            if oplata_abonamentowa is not None:
                suma_oplat_stalych += oplata_abonamentowa
            if oplata_mocowa is not None:
                suma_oplat_stalych += oplata_mocowa
            
            periods.append({
                "okres": f"OKRES_DYSTRYBUCYJNY_{i+1}",
                "od": current_start,
                "do": dist_period_end,
                "cena_1kwh_dzienna": cena_1kwh_dzienna,
                "cena_1kwh_nocna": cena_1kwh_nocna,
                "cena_1kwh_calodobowa": cena_1kwh_calodobowa,
                "suma_oplat_stalych": round(suma_oplat_stalych, 4)
            })
            
            current_start = dist_period_end + timedelta(days=1)
        
        return periods
    
    def calculate_days_between(self, start_date: date, end_date: date) -> int:
        """Oblicza liczbę dni między datami (włącznie z końcową)."""
        return (end_date - start_date).days + 1
    
    def calculate_bill_for_period_with_overlapping(
        self,
        tenant_period_start: date,
        tenant_period_end: date,
        distribution_periods: List[Dict[str, Any]],
        usage_kwh_dzienna: float,
        usage_kwh_nocna: float,
        usage_kwh_calodobowa: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Oblicza rachunek dla okresu najemcy, uwzględniając różne okresy dystrybucyjne.
        
        Args:
            tenant_period_start: Data początku okresu najemcy
            tenant_period_end: Data końca okresu najemcy
            distribution_periods: Lista okresów z faktury z różnymi cenami
            usage_kwh_dzienna: Zużycie dzienne (kWh)
            usage_kwh_nocna: Zużycie nocne (kWh)
            usage_kwh_calodobowa: Zużycie całodobowe (kWh) - opcjonalne
        
        Returns:
            Słownik z obliczonymi kosztami (netto i brutto)
        """
        # Znajdujemy, które okresy dystrybucyjne pokrywają się z okresem najemcy
        overlapping_periods = []
        
        for dist_period in distribution_periods:
            # Sprawdzamy przecięcie okresów
            period_start = max(tenant_period_start, dist_period["od"])
            period_end = min(tenant_period_end, dist_period["do"])
            
            if period_start <= period_end:
                days = self.calculate_days_between(period_start, period_end)
                overlapping_periods.append({
                    "period": dist_period,
                    "days": days,
                    "start": period_start,
                    "end": period_end
                })
        
        if not overlapping_periods:
            return {
                "energy_cost_net": 0.0,
                "energy_cost_gross": 0.0,
                "distribution_cost_net": 0.0,
                "distribution_cost_gross": 0.0,
                "fixed_fees_net": 0.0,
                "fixed_fees_gross": 0.0,
                "total_net_sum": 0.0,
                "total_gross_sum": 0.0,
                "details": []
            }
        
        total_days = sum(op["days"] for op in overlapping_periods)
        
        total_energy_cost_net = 0.0
        total_fixed_fees_net = 0.0
        details = []
        vat_rate = 0.23  # VAT 23%
        
        for op in overlapping_periods:
            period = op["period"]
            days = op["days"]
            proportion = days / total_days if total_days > 0 else 0
            
            # Obliczamy zużycie dla tej części okresu
            if usage_kwh_calodobowa is not None:
                # Taryfa całodobowa
                usage_part = usage_kwh_calodobowa * proportion
                cena_1kwh = period.get("cena_1kwh_calodobowa", 0) or 0
                energy_cost_net = usage_part * cena_1kwh
            else:
                # Taryfa dwutaryfowa
                usage_dzienna_part = usage_kwh_dzienna * proportion
                usage_nocna_part = usage_kwh_nocna * proportion
                
                cena_dzienna = period.get("cena_1kwh_dzienna", 0) or 0
                cena_nocna = period.get("cena_1kwh_nocna", 0) or 0
                
                energy_cost_net = (usage_dzienna_part * cena_dzienna) + (usage_nocna_part * cena_nocna)
            
            # Opłaty stałe proporcjonalnie (netto)
            suma_oplat_stalych = period.get("suma_oplat_stalych", 0) or 0
            fixed_cost_net = suma_oplat_stalych * proportion
            
            total_energy_cost_net += energy_cost_net
            total_fixed_fees_net += fixed_cost_net
            
            details.append({
                "period": period["okres"],
                "days": days,
                "proportion": proportion,
                "energy_cost_net": round(energy_cost_net, 4),
                "fixed_cost_net": round(fixed_cost_net, 4)
            })
        
        # Oblicz brutto
        total_energy_cost_gross = round(total_energy_cost_net * (1 + vat_rate), 4)
        total_fixed_fees_gross = round(total_fixed_fees_net * (1 + vat_rate), 4)
        
        # Dla dystrybucji: w obecnej implementacji dystrybucja jest już wliczona w cenę za kWh
        # (cena_1kwh_dzienna/nocna zawiera już opłaty dystrybucyjne zmienne)
        # Więc distribution_cost = 0 (już wliczone w energy_cost)
        distribution_cost_net = 0.0
        distribution_cost_gross = 0.0
        
        total_net_sum = round(total_energy_cost_net + distribution_cost_net + total_fixed_fees_net, 4)
        total_gross_sum = round(total_energy_cost_gross + distribution_cost_gross + total_fixed_fees_gross, 4)
        
        return {
            "energy_cost_net": round(total_energy_cost_net, 4),
            "energy_cost_gross": total_energy_cost_gross,
            "distribution_cost_net": distribution_cost_net,
            "distribution_cost_gross": distribution_cost_gross,
            "fixed_fees_net": round(total_fixed_fees_net, 4),
            "fixed_fees_gross": total_fixed_fees_gross,
            "total_net_sum": total_net_sum,
            "total_gross_sum": total_gross_sum,
            "details": details
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
            costs = self.calculate_bill_costs(invoice, usage_data, local.local, db, data)
            
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
            
            # Dodaj opłaty stałe dla całego domu (suma dla wszystkich 3 lokali)
            # Opłaty stałe dla DOM = opłaty dla jednego lokalu * 3
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

