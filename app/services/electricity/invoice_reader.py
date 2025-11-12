"""
Parsowanie faktur PDF za prąd (ENEA).
Wyciąga dane z faktur i zapisuje do bazy danych.
"""

import re
from typing import Optional, Dict, Any, List
from pathlib import Path
from sqlalchemy.orm import Session
from datetime import datetime
import pdfplumber
from app.models.electricity_invoice import ElectricityInvoice

# Import funkcji z tools/extract_electricity_structured.py
import sys
from pathlib import Path as PathLib
tools_path = PathLib(__file__).parent.parent.parent.parent / "tools"
sys.path.insert(0, str(tools_path))
from extract_electricity_structured import (
    extract_invoice_number,
    extract_period,
    extract_financial_summary,
    extract_prognosis_blankets,
    extract_meter_readings,
    extract_energy_sales,
    extract_distribution_fees,
    extract_summaries
)


def parse_price_value(value_str: str) -> float:
    """
    Parsuje wartość ceny z formatu polskiego.
    Dla cen za kWh (małe wartości < 10), przecinek jest zawsze separatorem dziesiętnym.
    Dla większych wartości, kropki są separatorami tysięcy, przecinek jest separatorem dziesiętnym.
    
    Args:
        value_str: Wartość jako string (np. "0,3640" lub "1.234,56")
    
    Returns:
        Wartość jako float
    """
    if not value_str:
        return 0.0
    
    value_str = str(value_str).strip()
    
    # Jeśli wartość zawiera kropki, to są to separatory tysięcy
    if '.' in value_str:
        # Format: "1.234,56" -> usuń kropki -> "1234,56" -> zamień przecinek -> "1234.56"
        return float(value_str.replace('.', '').replace(',', '.'))
    else:
        # Jeśli nie ma kropek, przecinek jest separatorem dziesiętnym
        # Format: "0,3640" -> zamień przecinek -> "0.3640"
        return float(value_str.replace(',', '.'))


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Wyciąga tekst z pliku PDF.
    
    Args:
        pdf_path: Ścieżka do pliku PDF
    
    Returns:
        Tekst z pliku PDF
    """
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                
                # Spróbuj też wyciągnąć tabele
                try:
                    tables = page.extract_tables()
                    if tables:
                        for table in tables:
                            for row in table:
                                if row:
                                    row_text = " ".join([str(cell) if cell else "" for cell in row])
                                    page_text += " " + row_text
                except Exception:
                    pass
                
                text += page_text + "\n"
    except Exception as e:
        print(f"Błąd przy wczytywaniu PDF {pdf_path}: {e}")
    return text


def parse_invoice_data(text: str) -> Optional[Dict[str, Any]]:
    """
    Parsuje dane z tekstu faktury ENEA - wszystkie 6 tabel.
    
    Args:
        text: Tekst wyciągnięty z PDF
    
    Returns:
        Słownik z danymi faktury dla wszystkich tabel lub None
    """
    # Wyciągnij podstawowe dane
    invoice_number = extract_invoice_number(text)
    period = extract_period(text)
    financial = extract_financial_summary(text)
    summaries = extract_summaries(text)
    
    # Wyciągnij dane dla wszystkich tabel szczegółowych
    blankets = extract_prognosis_blankets(text)
    readings = extract_meter_readings(text)
    sales = extract_energy_sales(text)
    fees = extract_distribution_fees(text)
    
    if not invoice_number or not period:
        return None
    
    # Parsuj daty okresu
    try:
        period_start_str = period['od']
        period_stop_str = period['do']
        period_start = datetime.strptime(period_start_str, "%d/%m/%Y").date()
        period_stop = datetime.strptime(period_stop_str, "%d/%m/%Y").date()
    except (ValueError, KeyError):
        return None
    
    # Generuj data (YYYY-MM) z okresu
    data = period_start.strftime("%Y-%m")
    
    # Oblicz zużycie (kWh) - z podsumowania lub z sales
    usage_kwh = 0.0
    if 'zuzycie_po_bilansowaniu_kwh' in financial:
        usage_kwh = float(financial['zuzycie_po_bilansowaniu_kwh'].replace('.', '').replace(',', '.'))
    elif sales:
        # Suma z sales
        for sale in sales:
            if 'ilosc_kwh' in sale:
                usage_kwh += float(sale['ilosc_kwh'].replace('.', '').replace(',', '.'))
    
    # Oblicz koszty energii
    energy_value_net = 0.0
    energy_value_gross = 0.0
    energy_vat_amount = 0.0
    energy_price_net = 0.0
    
    if sales:
        for sale in sales:
            if sale.get('typ') == 'upust':
                continue  # Pomiń upusty
            naleznosc = float(sale.get('naleznosc', '0').replace('.', '').replace(',', '.'))
            vat_rate = float(sale.get('vat', '23')) / 100.0
            netto = naleznosc / (1 + vat_rate)
            vat = naleznosc - netto
            
            energy_value_net += netto
            energy_value_gross += naleznosc
            energy_vat_amount += vat
            
            # Cena netto - średnia z wszystkich pozycji
            if 'ilosc_kwh' in sale:
                ilosc = float(sale['ilosc_kwh'].replace('.', '').replace(',', '.'))
                if ilosc > 0:
                    cena = parse_price_value(sale.get('cena', '0'))
                    energy_price_net = cena  # Użyj ostatniej ceny
    
    # Oblicz opłaty dystrybucyjne
    distribution_fees_net = 0.0
    distribution_fees_gross = 0.0
    distribution_fees_vat = 0.0
    
    if fees:
        for fee in fees:
            naleznosc = float(fee.get('naleznosc', '0').replace('.', '').replace(',', '.'))
            vat_rate = float(fee.get('vat', '23')) / 100.0
            netto = naleznosc / (1 + vat_rate)
            vat = naleznosc - netto
            
            distribution_fees_net += netto
            distribution_fees_gross += naleznosc
            distribution_fees_vat += vat
    
    # VAT
    vat_rate = 0.23  # Domyślnie 23%
    vat_amount = energy_vat_amount + distribution_fees_vat
    
    # Sumy
    total_net_sum = energy_value_net + distribution_fees_net
    total_gross_sum = energy_value_gross + distribution_fees_gross
    
    # Kwota do zapłaty - z podsumowania finansowego
    amount_to_pay = total_gross_sum
    if 'saldo_z_rozliczenia' in financial:
        try:
            amount_to_pay = float(financial['saldo_z_rozliczenia'].replace('.', '').replace(',', '.'))
        except (ValueError, AttributeError):
            pass
    
    # Termin płatności - z okresu (domyślnie koniec okresu + 14 dni)
    from datetime import timedelta
    payment_due_date = period_stop + timedelta(days=14)
    
    # Wyciągnij rok z okresu
    rok = period_start.year
    
    # Wyciągnij wszystkie dane z podsumowania finansowego
    def parse_financial_value(key, default=0.0):
        """Pomocnicza funkcja do parsowania wartości finansowych."""
        if key in financial:
            try:
                value_str = financial[key].replace('.', '').replace(',', '.')
                return float(value_str)
            except (ValueError, AttributeError):
                pass
        return default
    
    def parse_financial_int(key, default=0):
        """Pomocnicza funkcja do parsowania wartości całkowitych."""
        if key in financial:
            try:
                value_str = financial[key].replace('.', '').replace(',', '.')
                return int(float(value_str))
            except (ValueError, AttributeError):
                pass
        return default
    
    # Wyciągnij dane z summaries
    grupa_taryfowa = summaries.get('grupa_taryfowa', 'G12')
    energia_zuzyta_w_roku = summaries.get('energia_zuzyta_w_roku', '0')
    # Parsuj "9542 kWh" lub "9.542 kWh" -> 9542
    energia_zuzyta_w_roku_kwh = 0
    if energia_zuzyta_w_roku:
        try:
            # Usuń "kWh" i spacje, zamień kropki na nic (separatory tysięcy)
            energia_str = energia_zuzyta_w_roku.replace('kWh', '').replace(' ', '').replace('.', '').replace(',', '.')
            energia_zuzyta_w_roku_kwh = int(float(energia_str))
        except (ValueError, AttributeError):
            pass
    
    # Jeśli nie ma w summaries, spróbuj z financial
    if energia_zuzyta_w_roku_kwh == 0 and 'energia_lacznie_zuzyta_w_roku_kwh' in financial:
        energia_zuzyta_w_roku_kwh = parse_financial_int('energia_lacznie_zuzyta_w_roku_kwh', 0)
    
    # Określ typ taryfy - sprawdź czy są dane dla stref dziennej i nocnej
    typ_taryfy = "DWUTARYFOWA"  # Domyślnie dwutaryfowa
    
    # Sprawdź odczyty - jeśli są tylko odczyty "całodobowa", to taryfa całodobowa
    if readings:
        strefy_odczytow = [r.get('strefa', '').upper() if r.get('strefa') else 'CALODOBOWA' for r in readings]
        if all('CALODOBOWA' in s or s == '' for s in strefy_odczytow):
            typ_taryfy = "CAŁODOBOWA"
    
    # Sprawdź sprzedaż - jeśli są tylko pozycje bez strefy (None), to taryfa całodobowa
    if sales:
        strefy_sprzedazy = [s.get('strefa', '').upper() if s.get('strefa') else 'CALODOBOWA' for s in sales if s.get('typ') != 'upust']
        if all('CALODOBOWA' in s or s == '' for s in strefy_sprzedazy):
            typ_taryfy = "CAŁODOBOWA"
        elif any('DZIENNA' in s or 'NOCNA' in s for s in strefy_sprzedazy):
            typ_taryfy = "DWUTARYFOWA"
    
    # Data wystawienia - użyj daty początku okresu jako domyślnej
    data_wystawienia = period_start
    
    # Ogółem sprzedaż energii - z summaries lub obliczona
    if 'ogolem_sprzedaz_energii' in summaries:
        try:
            ogolem_sprzedaz = float(summaries['ogolem_sprzedaz_energii'].replace('.', '').replace(',', '.'))
        except (ValueError, AttributeError):
            ogolem_sprzedaz = energy_value_gross
    else:
        ogolem_sprzedaz = energy_value_gross
    
    # Ogółem usługa dystrybucji - z summaries lub obliczona
    if 'ogolem_usluga_dystrybucji' in summaries:
        try:
            ogolem_dystrybucja = float(summaries['ogolem_usluga_dystrybucji'].replace('.', '').replace(',', '.'))
        except (ValueError, AttributeError):
            ogolem_dystrybucja = distribution_fees_gross
    else:
        ogolem_dystrybucja = distribution_fees_gross
    
    return {
        # Podstawowe dane
        'data': data,
        'rok': rok,
        'invoice_number': invoice_number,
        'numer_faktury': invoice_number,  # Dla kompatybilności
        'data_wystawienia': data_wystawienia,
        'period_start': period_start,
        'data_poczatku_okresu': period_start,  # Dla kompatybilności
        'period_stop': period_stop,
        'data_konca_okresu': period_stop,  # Dla kompatybilności
        
        # Podsumowanie finansowe
        'naleznosc_za_okres': parse_financial_value('naleznosc_za_okres', total_gross_sum),
        'wartosc_prognozy': parse_financial_value('wartosc_prognozy', 0.0),
        'faktury_korygujace': parse_financial_value('faktury_korygujace', 0.0),
        'odsetki': parse_financial_value('odsetki', 0.0),
        'wynik_rozliczenia': parse_financial_value('wynik_rozliczenia', 0.0),
        'kwota_nadplacona': parse_financial_value('kwota_nadplacona', 0.0),
        'saldo_z_rozliczenia': parse_financial_value('saldo_z_rozliczenia', amount_to_pay),
        'niedoplata_nadplata': parse_financial_value('niedoplata_nadplata', 0.0),
        
        # Akcyza
        'energia_do_akcyzy_kwh': parse_financial_int('energia_do_akcyzy_kwh', 0),
        'akcyza': parse_financial_value('akcyza', 0.0),
        
        # Zużycie i koszty
        'usage_kwh': usage_kwh,
        'zuzycie_kwh': int(usage_kwh),  # Dla kompatybilności
        'do_zaplaty': amount_to_pay,
        'ogolem_sprzedaz_energii': ogolem_sprzedaz,
        'ogolem_usluga_dystrybucji': ogolem_dystrybucja,
        
        # Taryfa
        'grupa_taryfowa': grupa_taryfowa,
        'typ_taryfy': typ_taryfy,
        'energia_lacznie_zuzyta_w_roku_kwh': energia_zuzyta_w_roku_kwh,
        
        # Stare pola (dla kompatybilności)
        'energy_price_net': energy_price_net,
        'energy_value_net': energy_value_net,
        'energy_vat_amount': energy_vat_amount,
        'energy_value_gross': energy_value_gross,
        'distribution_fees_net': distribution_fees_net,
        'distribution_fees_vat': distribution_fees_vat,
        'distribution_fees_gross': distribution_fees_gross,
        'vat_rate': vat_rate,
        'vat_amount': vat_amount,
        'total_net_sum': total_net_sum,
        'total_gross_sum': total_gross_sum,
        'amount_to_pay': amount_to_pay,
        'payment_due_date': payment_due_date,
        
        # Dane dla tabel szczegółowych
        'blankiety': blankets,
        'odczyty': readings,
        'sprzedaz_energii': sales,
        'oplaty_dystrybucyjne': fees,
        
        # Surowe dane (dla debugowania)
        '_raw_data': {
            'financial': financial,
            'sales': sales,
            'fees': fees,
            'summaries': summaries,
            'blankets': blankets,
            'readings': readings
        }
    }


def load_invoice_from_pdf(
    pdf_path: str,
    db: Session
) -> Optional[Dict[str, Any]]:
    """
    Parsuje fakturę PDF i zwraca dane do weryfikacji.
    NIE zapisuje do bazy danych - zwraca dane do weryfikacji przez użytkownika.
    
    Args:
        pdf_path: Ścieżka do pliku PDF
        db: Sesja bazy danych
    
    Returns:
        Słownik z danymi faktury lub None w przypadku błędu
    """
    # Wyciągnij tekst z PDF
    text = extract_text_from_pdf(pdf_path)
    if not text:
        return None
    
    # Parsuj dane
    invoice_data = parse_invoice_data(text)
    if not invoice_data:
        return None
    
    # Dodaj informacje o pliku
    invoice_data['_file_path'] = pdf_path
    invoice_data['_file_name'] = Path(pdf_path).name
    
    return invoice_data


def save_invoice_after_verification(
    db: Session,
    invoice_data: Dict[str, Any]
) -> Optional[ElectricityInvoice]:
    """
    Zapisuje fakturę do bazy danych po weryfikacji przez użytkownika.
    
    Args:
        db: Sesja bazy danych
        invoice_data: Zweryfikowane dane faktury
    
    Returns:
        Utworzona faktura lub None
    """
    # Sprawdź czy faktura już istnieje
    existing = db.query(ElectricityInvoice).filter(
        ElectricityInvoice.data == invoice_data['data'],
        ElectricityInvoice.invoice_number == invoice_data['invoice_number']
    ).first()
    
    if existing:
        raise ValueError(f"Faktura {invoice_data['invoice_number']} dla okresu {invoice_data['data']} już istnieje")
    
    # Utwórz fakturę
    invoice = ElectricityInvoice(
        data=invoice_data['data'],
        invoice_number=invoice_data['invoice_number'],
        period_start=invoice_data['period_start'],
        period_stop=invoice_data['period_stop'],
        usage_kwh=round(invoice_data['usage_kwh'], 4),
        energy_price_net=round(invoice_data['energy_price_net'], 4),
        energy_value_net=round(invoice_data['energy_value_net'], 4),
        energy_vat_amount=round(invoice_data['energy_vat_amount'], 4),
        energy_value_gross=round(invoice_data['energy_value_gross'], 4),
        distribution_fees_net=round(invoice_data['distribution_fees_net'], 4),
        distribution_fees_vat=round(invoice_data['distribution_fees_vat'], 4),
        distribution_fees_gross=round(invoice_data['distribution_fees_gross'], 4),
        vat_rate=invoice_data['vat_rate'],
        vat_amount=round(invoice_data['vat_amount'], 4),
        total_net_sum=round(invoice_data['total_net_sum'], 4),
        total_gross_sum=round(invoice_data['total_gross_sum'], 4),
        amount_to_pay=round(invoice_data['amount_to_pay'], 4),
        payment_due_date=invoice_data['payment_due_date']
    )
    
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    
    return invoice

