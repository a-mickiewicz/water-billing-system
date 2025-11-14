"""
Moduł wczytywania i parsowania faktur PDF gazu (PGNiG).
Wczytuje dane z plików PDF w folderze invoices_raw/gas/.
"""

import os
import re
from datetime import datetime
from pathlib import Path
import pdfplumber
from typing import Optional, Dict
from sqlalchemy.orm import Session
from app.models.gas import GasInvoice


def parse_period_from_filename(filename: str) -> Optional[str]:
    """
    Wyciąga okres rozliczeniowy z nazwy pliku.
    Format: invoice__2025_02.pdf -> '2025-02'
    
    Args:
        filename: Nazwa pliku
    
    Returns:
        Okres w formacie 'YYYY-MM' lub None
    """
    match = re.search(r'(\d{4})[_-](\d{2})', filename)
    if match:
        year, month = match.groups()
        return f"{year}-{month}"
    return None


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Wyciąga tekst z pliku PDF - wszystkie strony i wszystkie znaki.
    
    Args:
        pdf_path: Ścieżka do pliku PDF
    
    Returns:
        Wszystki tekst z pliku PDF
    """
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages, 1):
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


def parse_invoice_data(text: str) -> Optional[Dict]:
    """
    Parsuje dane z faktury gazu na podstawie tekstu PDF.
    
    Args:
        text: Tekst z pliku PDF
    
    Returns:
        Słownik z danymi faktury lub None
    """
    data = {}
    
    # 1. Okres YYYY-MM z daty "z dnia" przy numerze faktury
    # Format: "Faktura VAT nr P/43562821/0003/25 z dnia 02.07.2025"
    invoice_date_match = re.search(r'Faktura\s+VAT\s+nr\s+[A-Z0-9/]+\s+z\s+dnia\s+(\d{1,2})\.(\d{1,2})\.(\d{4})', text, re.IGNORECASE)
    if invoice_date_match:
        day, month, year = invoice_date_match.group(1, 2, 3)
        data['_extracted_period'] = f"{year}-{month:0>2}"
    
    # 2. Numer faktury: tylko numer bez "Faktura VAT nr"
    # Format: "Faktura VAT nr P/43562821/0003/25"
    invoice_match = re.search(r'Faktura\s+VAT\s+nr\s+([A-Z0-9/]+)', text, re.IGNORECASE)
    if invoice_match:
        data['invoice_number'] = invoice_match.group(1)  # Tylko numer, bez prefiksu
    else:
        # Alternatywny format
        invoice_match = re.search(r'Faktura\s+VAT\s+([A-Z0-9/]+)', text, re.IGNORECASE)
        if invoice_match:
            data['invoice_number'] = invoice_match.group(1)
    
    # 3. Data początku i końca okresu z "Opłata abonamentowa"
    # Format: "Opłata abonamentowa W-3.6 01.05.202530.06.2025 2,0000 mc 6,40000 23 12,80"
    # Daty są w formacie DD.MM.YYYYDD.MM.YYYY (bez spacji między datami)
    subscription_match = re.search(r'Opłata\s+abonamentowa[^\n]*?\s+(\d{1,2})\.(\d{1,2})\.(\d{4})(\d{1,2})\.(\d{1,2})\.(\d{4})\s+(\d+[.,]\d+)\s+mc', text, re.IGNORECASE)
    if subscription_match:
        # Wyciągnij daty początku i końca okresu
        start_day, start_month, start_year = subscription_match.group(1, 2, 3)
        end_day, end_month, end_year = subscription_match.group(4, 5, 6)
        data['period_start'] = datetime(int(start_year), int(start_month), int(start_day)).date()
        data['period_stop'] = datetime(int(end_year), int(end_month), int(end_day)).date()
        
        # Wyciągnij dane opłaty abonamentowej
        data['subscription_quantity'] = int(float(subscription_match.group(7).replace(',', '.')))
    
    # 4. Opłata abonamentowa - cena i wartość netto
    # Format: "Opłata abonamentowa ... 2,0000 mc 6,40000 23 12,80"
    subscription_values_match = re.search(r'Opłata\s+abonamentowa[^\n]*?\s+\d+[.,]\d+\s+mc\s+(\d+[.,]\d+)\s+(\d+)\s+(\d+[.,]\d+)', text, re.IGNORECASE)
    if subscription_values_match:
        data['subscription_price_net'] = float(subscription_values_match.group(1).replace(',', '.'))
        vat_rate_subscr = float(subscription_values_match.group(2)) / 100  # VAT rate z linii
        data['subscription_value_net'] = float(subscription_values_match.group(3).replace(',', '.'))
        # Oblicz wartość brutto z netto + VAT
        data['subscription_value_gross'] = round(data['subscription_value_net'] * (1 + vat_rate_subscr), 2)
        data['subscription_vat_amount'] = round(data['subscription_value_gross'] - data['subscription_value_net'], 2)
    
    # 5. Odczyty liczników
    # Format: "Paliwo gazowe G1 W-3.6 25.04.202530.06.2025 11571 R 11656 R 85 m³"
    fuel_match = re.search(r'Paliwo\s+gazowe[^\n]*?\s+(\d+)\s+R\s+(\d+)\s+R', text, re.IGNORECASE)
    if fuel_match:
        data['previous_reading'] = float(fuel_match.group(1))
        data['current_reading'] = float(fuel_match.group(2))
    
    # 6. Paliwo gazowe - Zużycie
    # Format: "Paliwo gazowe G1 W-3.6 31.12.202425.02.2025 10213 R 11018 R 805 m³ 11,450 9217 kWh 0,23965 23 2 208,85"
    # Wartości mogą mieć spacje jako separator tysięcy
    fuel_full_match = re.search(r'Paliwo\s+gazowe[^\n]*?\s+(\d+)\s+m³\s+(\d+[.,]\d+)\s+(\d+)\s+kWh\s+(\d+[.,]\d+)\s+(\d+)\s+([\d\s,]+)', text, re.IGNORECASE)
    if fuel_full_match:
        data['fuel_usage_m3'] = float(fuel_full_match.group(1))
        data['fuel_conversion_factor'] = float(fuel_full_match.group(2).replace(',', '.'))  # Wsp. konw.
        data['fuel_usage_kwh'] = float(fuel_full_match.group(3))
        data['fuel_price_net'] = float(fuel_full_match.group(4).replace(',', '.'))
        vat_rate_fuel = float(fuel_full_match.group(5)) / 100  # VAT rate z linii
        # Usuń spacje z wartości netto (separator tysięcy)
        fuel_value_net_str = fuel_full_match.group(6).replace(' ', '').replace(',', '.')
        data['fuel_value_net'] = float(fuel_value_net_str)
        # Oblicz wartość brutto z netto + VAT
        data['fuel_value_gross'] = round(data['fuel_value_net'] * (1 + vat_rate_fuel), 2)
        data['fuel_vat_amount'] = round(data['fuel_value_gross'] - data['fuel_value_net'], 2)
    
    # 7. Dystrybucja stała
    # Format: "Dystrybucyjna stała W-3.6_PO 01.05.202530.06.2025 2,0000 mc 50,83000 23 101,66"
    dist_fixed_match = re.search(r'Dystrybucyjna\s+stała[^\n]*?\s+(\d+[.,]\d+)\s+mc\s+(\d+[.,]\d+)\s+(\d+)\s+(\d+[.,]\d+)', text, re.IGNORECASE)
    if dist_fixed_match:
        data['distribution_fixed_quantity'] = int(float(dist_fixed_match.group(1).replace(',', '.')))
        data['distribution_fixed_price_net'] = float(dist_fixed_match.group(2).replace(',', '.'))
        vat_rate_fixed = float(dist_fixed_match.group(3)) / 100  # VAT rate z linii
        data['distribution_fixed_value_net'] = float(dist_fixed_match.group(4).replace(',', '.'))
        # Oblicz wartość brutto z netto + VAT
        data['distribution_fixed_value_gross'] = round(data['distribution_fixed_value_net'] * (1 + vat_rate_fixed), 2)
        data['distribution_fixed_vat_amount'] = round(data['distribution_fixed_value_gross'] - data['distribution_fixed_value_net'], 2)
    
    # 8. Dystrybucja zmienna (może być kilka)
    # Format: "Dystrybucyjna zmienna G1 W-3.6_PO 31.12.202431.12.2024 10213 R - 14 m³ 11,450 160 kWh 0,04411 23 7,06"
    # Format alternatywny: "Dystrybucyjna zmienna G1 W-3.6_PO 01.01.202525.02.2025 - 11018 R 791 m³ 11,450 9057 kWh 0,05502 23 498,32"
    # Format: "... [zużycie] m³ [wsp. konw.] [kWh] kWh [cena netto] [VAT%] [wartość netto]"
    # Odczyty mogą być w formacie "X R Y R" lub "X R -" lub "- Y R"
    dist_var_matches = re.finditer(r'Dystrybucyjna\s+zmienna[^\n]*?\s+(?:\d+\s+R\s+-\s+|-\s+\d+\s+R\s+|\d+\s+R\s+\d+\s+R\s+)(\d+)\s+m³\s+(\d+[.,]\d+)\s+(\d+)\s+kWh\s+(\d+[.,]\d+)\s+(\d+)\s+([\d\s,]+)', text, re.IGNORECASE)
    dist_var_list = list(dist_var_matches)
    
    if dist_var_list:
        # Pierwsza dystrybucja zmienna
        # Format: "... 791 m³ 11,450 9057 kWh 0,05502 23 498,32"
        # Grupy: (1) m3, (2) wsp. konw., (3) kWh, (4) cena netto, (5) VAT%, (6) wartość netto
        match = dist_var_list[0]
        data['distribution_variable_usage_m3'] = float(match.group(1))
        data['distribution_variable_conversion_factor'] = float(match.group(2).replace(',', '.'))
        data['distribution_variable_usage_kwh'] = float(match.group(3))  # Ilość kWh
        data['distribution_variable_price_net'] = float(match.group(4).replace(',', '.'))
        vat_rate_var = float(match.group(5)) / 100  # VAT rate z linii
        value_net_str = match.group(6).replace(' ', '').replace(',', '.')
        data['distribution_variable_value_net'] = float(value_net_str)
        # Oblicz wartość brutto z netto + VAT
        data['distribution_variable_value_gross'] = round(data['distribution_variable_value_net'] * (1 + vat_rate_var), 2)
        data['distribution_variable_vat_amount'] = round(data['distribution_variable_value_gross'] - data['distribution_variable_value_net'], 2)
        
        # Druga dystrybucja zmienna (jeśli istnieje)
        if len(dist_var_list) > 1:
            match2 = dist_var_list[1]
            data['distribution_variable_2_usage_m3'] = float(match2.group(1))
            data['distribution_variable_2_conversion_factor'] = float(match2.group(2).replace(',', '.'))
            data['distribution_variable_2_usage_kwh'] = float(match2.group(3))  # Ilość kWh dla dystrybucji zmiennej 2
            data['distribution_variable_2_price_net'] = float(match2.group(4).replace(',', '.'))
            vat_rate_var2 = float(match2.group(5)) / 100  # VAT rate z linii
            value_net_str_2 = match2.group(6).replace(' ', '').replace(',', '.')
            data['distribution_variable_2_value_net'] = float(value_net_str_2)
            # Oblicz wartość brutto z netto + VAT
            data['distribution_variable_2_value_gross'] = round(data['distribution_variable_2_value_net'] * (1 + vat_rate_var2), 2)
    
    # 9. Wartość netto ogółem
    # Format: "A. Razem sprzedaż okresie rozliczeniowym od 31.12.2024 do 25.02.2025 2 828,69"
    # Może brakować "w" przed "okresie", wartości mogą mieć spacje
    total_net_match = re.search(r'A\.\s+Razem\s+sprzedaż\s+(?:w\s+)?okresie\s+rozliczeniowym\s+od\s+\d{1,2}\.\d{1,2}\.\d{4}\s+do\s+\d{1,2}\.\d{1,2}\.\d{4}\s+([\d\s,]+)', text, re.IGNORECASE)
    if total_net_match:
        total_net_str = total_net_match.group(1).replace(' ', '').replace(',', '.')
        data['total_net_sum'] = float(total_net_str)
    
    # 10. VAT i Wartość brutto
    # Format: "Sprzedaż VAT 23% 2 828,69 650,60 3 479,29"
    # Kolejność: netto, VAT, brutto (wartości mogą mieć spacje jako separator tysięcy)
    # Użyj bardziej precyzyjnego regex - wartości są oddzielone większymi spacjami
    # Format wartości: cyfry, spacje (separator tysięcy), przecinek, cyfry
    vat_match = re.search(r'Sprzedaż\s+VAT\s+(\d+)%\s+([\d\s]+,\d+)\s+([\d\s]+,\d+)\s+([\d\s]+,\d+)', text, re.IGNORECASE)
    if vat_match:
        data['vat_rate'] = float(vat_match.group(1)) / 100
        # VAT amount to trzecia wartość (po netto)
        vat_str = vat_match.group(3).strip().replace(' ', '').replace(',', '.')
        data['vat_amount'] = float(vat_str)
        # Brutto to czwarta wartość
        gross_str = vat_match.group(4).strip().replace(' ', '').replace(',', '.')
        data['total_gross_sum'] = float(gross_str)
    else:
        # Alternatywny format bez spacji (wartości proste)
        vat_match_alt = re.search(r'Sprzedaż\s+VAT\s+(\d+)%\s+(\d+[.,]\d+)\s+(\d+[.,]\d+)\s+(\d+[.,]\d+)', text, re.IGNORECASE)
        if vat_match_alt:
            data['vat_rate'] = float(vat_match_alt.group(1)) / 100
            vat_str = vat_match_alt.group(3).replace(',', '.')
            data['vat_amount'] = float(vat_str)
            gross_str = vat_match_alt.group(4).replace(',', '.')
            data['total_gross_sum'] = float(gross_str)
        else:
            data['vat_rate'] = 0.23  # Domyślnie 23%
    
    # 12. Odsetki za nieterminowe wpłaty
    # Format: "Odsetki za nieterminowe wpłaty 2,16 zł"
    interest_match = re.search(r'Odsetki\s+za\s+nieterminowe\s+wpłaty\s+(\d+[.,]\d+)\s*zł', text, re.IGNORECASE)
    if interest_match:
        data['late_payment_interest'] = float(interest_match.group(1).replace(',', '.'))
    else:
        data['late_payment_interest'] = 0.0
    
    # 13. Do zapłaty
    # Format: "Do zapłaty: 3 479,29 zł" (wartości mogą mieć spacje)
    amount_match = re.search(r'Do\s+zapłaty[:\s]+([\d\s,]+)\s*zł', text, re.IGNORECASE)
    if amount_match:
        amount_str = amount_match.group(1).replace(' ', '').replace(',', '.')
        data['amount_to_pay'] = float(amount_str)
    
    # 14. Termin płatności
    # Format: "Termin płatności*: 16.07.2025"
    due_date_match = re.search(r'Termin\s+płatności\*?[:\s]+(\d{1,2})\.(\d{1,2})\.(\d{4})', text, re.IGNORECASE)
    if due_date_match:
        day, month, year = due_date_match.group(1, 2, 3)
        data['payment_due_date'] = datetime(int(year), int(month), int(day)).date()
    else:
        # Alternatywny format: "Termin płatności:1" z datą wcześniej w tekście
        due_date_alt = re.search(r'(\d{1,2})\.(\d{1,2})\.(\d{4})\s+Termin\s+płatności', text, re.IGNORECASE)
        if due_date_alt:
            day, month, year = due_date_alt.group(1, 2, 3)
            data['payment_due_date'] = datetime(int(year), int(month), int(day)).date()
    
    # Sprawdź czy wszystkie wymagane pola są wypełnione
    required_fields = [
        'invoice_number', 'period_start', 'period_stop', 
        'previous_reading', 'current_reading',
        'fuel_usage_m3', 'fuel_conversion_factor', 'fuel_usage_kwh', 'fuel_price_net', 'fuel_value_net',
        'subscription_quantity', 'subscription_price_net', 'subscription_value_net',
        'distribution_fixed_quantity', 'distribution_fixed_price_net', 'distribution_fixed_value_net',
        'distribution_variable_usage_m3', 'distribution_variable_conversion_factor', 'distribution_variable_price_net', 'distribution_variable_value_net',
        'total_net_sum', 'vat_rate', 'vat_amount', 'total_gross_sum',
        'late_payment_interest', 'amount_to_pay', 'payment_due_date'
    ]
    
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        print(f"[WARNING] Brakujące pola w fakturze: {', '.join(missing_fields)}")
        # Nie zwracaj None, zwróć co się udało sparsować
    
    return data


def load_invoice_from_pdf(db: Session, pdf_path: str, period: Optional[str] = None) -> Optional[GasInvoice]:
    """
    Wczytuje fakturę gazu z pliku PDF i zwraca sparsowane dane do weryfikacji.
    
    UWAGA: Przed zapisem do bazy danych, należy wyświetlić dane w dashboardzie
    dla użytkownika do weryfikacji i ewentualnej zmiany.
    
    Args:
        db: Sesja bazy danych
        pdf_path: Ścieżka do pliku PDF
        period: Okres rozliczeniowy (jeśli None, próbuje wyciągnąć z nazwy pliku lub dat faktury)
    
    Returns:
        Sparsowane dane (słownik) do weryfikacji lub None w przypadku błędu
    """
    print(f"\n[INFO] Przetwarzanie faktury gazu: {os.path.basename(pdf_path)}")
    
    # Wczytaj tekst z PDF
    text = extract_text_from_pdf(pdf_path)
    if not text:
        print(f"[ERROR] Nie udalo sie wczytac tekstu z pliku: {pdf_path}")
        return None
    
    # Parsuj dane z faktury
    invoice_data = parse_invoice_data(text)
    
    if not invoice_data:
        print(f"[ERROR] Nie udalo sie sparsowac danych z faktury: {pdf_path}")
        print("   TODO: Implementacja pelnego parsowania")
        return None
    
    # Określ okres rozliczeniowy
    if not period:
        # Priorytet 1: okres wyciągnięty z faktury
        if '_extracted_period' in invoice_data:
            period = invoice_data['_extracted_period']
            print(f"[INFO] Okres wyciagniety z faktury: {period}")
        else:
            # Priorytet 2: z daty początku okresu faktury
            if invoice_data.get('period_start'):
                period_start = invoice_data['period_start']
                if isinstance(period_start, datetime):
                    period = f"{period_start.year}-{period_start.month:02d}"
                elif isinstance(period_start, str):
                    try:
                        dt = datetime.strptime(period_start, "%Y-%m-%d")
                        period = f"{dt.year}-{dt.month:02d}"
                    except:
                        pass
                if period:
                    print(f"[INFO] Okres wyciagniety z daty poczatku okresu: {period}")
        
        # Priorytet 3: z nazwy pliku
        if not period:
            period = parse_period_from_filename(os.path.basename(pdf_path))
            if period:
                print(f"[INFO] Okres wyciagniety z nazwy pliku: {period}")
    
    if not period:
        print(f"[ERROR] Nie mozna okreslic okresu rozliczeniowego dla: {pdf_path}")
        return None
    
    # Dodaj okres do danych
    invoice_data['data'] = period
    invoice_data.pop('_extracted_period', None)  # Usuń pomocnicze pole
    
    # Zwróć dane do weryfikacji (NIE zapisuj jeszcze!)
    return invoice_data


def save_invoice_after_verification(db: Session, invoice_data: dict) -> Optional[GasInvoice]:
    """
    Zapisuje fakturę do bazy danych po weryfikacji przez użytkownika.
    Wywoływane z dashboardu po zatwierdzeniu.
    Automatycznie oblicza brakujące wartości netto i VAT z wartości brutto.
    
    Args:
        db: Sesja bazy danych
        invoice_data: Sparsowane dane faktury (może być edytowane przez użytkownika)
    
    Returns:
        Zapisana faktura lub None w przypadku błędu
    """
    from datetime import datetime
    
    # Oblicz wartości netto i VAT z wartości brutto (jeśli nie podane)
    vat_rate = invoice_data.get('vat_rate', 0.23)
    
    def calculate_net_from_gross(gross_value, vat):
        """Oblicza wartość netto z brutto i VAT."""
        if gross_value == 0 or gross_value is None:
            return 0.0, 0.0
        gross_value = float(gross_value)
        net_value = round(gross_value / (1 + vat), 2)
        vat_amount = round(gross_value - net_value, 2)
        return net_value, vat_amount
    
    # Użyj wartości brutto z parsera (jeśli są obliczone), w przeciwnym razie oblicz z netto + VAT
    # Jeśli wartości brutto nie są w invoice_data, oblicz je z netto + VAT
    vat_rate = invoice_data.get('vat_rate', 0.23)
    
    if 'fuel_value_gross' not in invoice_data or invoice_data.get('fuel_value_gross', 0.0) == 0.0:
        fuel_net = invoice_data.get('fuel_value_net', 0.0)
        invoice_data['fuel_value_gross'] = round(fuel_net * (1 + vat_rate), 2) if fuel_net > 0 else 0.0
        invoice_data['fuel_vat_amount'] = round(invoice_data['fuel_value_gross'] - fuel_net, 2) if fuel_net > 0 else 0.0
    
    if 'subscription_value_gross' not in invoice_data or invoice_data.get('subscription_value_gross', 0.0) == 0.0:
        subscr_net = invoice_data.get('subscription_value_net', 0.0)
        invoice_data['subscription_value_gross'] = round(subscr_net * (1 + vat_rate), 2) if subscr_net > 0 else 0.0
        invoice_data['subscription_vat_amount'] = round(invoice_data['subscription_value_gross'] - subscr_net, 2) if subscr_net > 0 else 0.0
    
    if 'distribution_fixed_value_gross' not in invoice_data or invoice_data.get('distribution_fixed_value_gross', 0.0) == 0.0:
        dist_fixed_net = invoice_data.get('distribution_fixed_value_net', 0.0)
        invoice_data['distribution_fixed_value_gross'] = round(dist_fixed_net * (1 + vat_rate), 2) if dist_fixed_net > 0 else 0.0
        invoice_data['distribution_fixed_vat_amount'] = round(invoice_data['distribution_fixed_value_gross'] - dist_fixed_net, 2) if dist_fixed_net > 0 else 0.0
    
    if 'distribution_variable_value_gross' not in invoice_data or invoice_data.get('distribution_variable_value_gross', 0.0) == 0.0:
        dist_var_net = invoice_data.get('distribution_variable_value_net', 0.0)
        invoice_data['distribution_variable_value_gross'] = round(dist_var_net * (1 + vat_rate), 2) if dist_var_net > 0 else 0.0
        invoice_data['distribution_variable_vat_amount'] = round(invoice_data['distribution_variable_value_gross'] - dist_var_net, 2) if dist_var_net > 0 else 0.0
    
    # Ustaw VAT amount na 0 dla poszczególnych pozycji (jeśli nie podano)
    # VAT jest tylko w podsumowaniu (vat_amount)
    invoice_data['fuel_vat_amount'] = invoice_data.get('fuel_vat_amount', 0.0)
    invoice_data['subscription_vat_amount'] = invoice_data.get('subscription_vat_amount', 0.0)
    invoice_data['distribution_fixed_vat_amount'] = invoice_data.get('distribution_fixed_vat_amount', 0.0)
    invoice_data['distribution_variable_vat_amount'] = invoice_data.get('distribution_variable_vat_amount', 0.0)
    
    # Oblicz fuel_usage_m3 jeśli nie podano
    if not invoice_data.get('fuel_usage_m3'):
        previous_reading = invoice_data.get('previous_reading', 0)
        current_reading = invoice_data.get('current_reading', 0)
        invoice_data['fuel_usage_m3'] = round(float(current_reading) - float(previous_reading), 2)
    
    # Ustaw domyślne ilości jeśli nie podano (faktury dwumiesięczne)
    if not invoice_data.get('subscription_quantity'):
        invoice_data['subscription_quantity'] = 2
    if not invoice_data.get('distribution_fixed_quantity'):
        invoice_data['distribution_fixed_quantity'] = 2
    
    # Ustaw domyślne wartości dla wymaganych pól paliwa gazowego
    if not invoice_data.get('fuel_conversion_factor'):
        invoice_data['fuel_conversion_factor'] = 0.0
    if not invoice_data.get('fuel_usage_kwh'):
        invoice_data['fuel_usage_kwh'] = 0.0
    
    # Ustaw domyślne wartości dla wymaganych pól dystrybucji zmiennej
    if not invoice_data.get('distribution_variable_conversion_factor'):
        invoice_data['distribution_variable_conversion_factor'] = 0.0
    if not invoice_data.get('distribution_variable_usage_kwh'):
        invoice_data['distribution_variable_usage_kwh'] = 0.0
    
    # Ustaw domyślne wartości dla opcjonalnych pól dystrybucji zmiennej 2
    # Jeśli pola są puste lub None, po prostu je usuń z invoice_data (SQLAlchemy użyje wartości domyślnej NULL)
    optional_fields_2 = [
        'distribution_variable_2_usage_m3',
        'distribution_variable_2_conversion_factor',
        'distribution_variable_2_usage_kwh',
        'distribution_variable_2_price_net',
        'distribution_variable_2_value_net'
    ]
    
    for field in optional_fields_2:
        value = invoice_data.get(field)
        if value is None or value == '' or (isinstance(value, str) and value.strip() == ''):
            # Usuń pole z invoice_data - SQLAlchemy użyje domyślnej wartości NULL
            invoice_data.pop(field, None)
        else:
            # Upewnij się, że wartość jest liczbą
            try:
                invoice_data[field] = float(value)
            except (ValueError, TypeError):
                invoice_data.pop(field, None)
    
    # Oblicz ceny netto jeśli nie podano
    if not invoice_data.get('subscription_price_net'):
        if invoice_data.get('subscription_quantity', 0) > 0:
            invoice_data['subscription_price_net'] = round(invoice_data.get('subscription_value_net', 0) / invoice_data['subscription_quantity'], 2)
        else:
            invoice_data['subscription_price_net'] = 0.0
    
    if not invoice_data.get('fuel_price_net'):
        if invoice_data.get('fuel_usage_m3', 0) > 0:
            invoice_data['fuel_price_net'] = round(invoice_data.get('fuel_value_net', 0) / invoice_data['fuel_usage_m3'], 2)
        else:
            invoice_data['fuel_price_net'] = 0.0
    
    if not invoice_data.get('distribution_fixed_price_net'):
        if invoice_data.get('distribution_fixed_quantity', 0) > 0:
            distribution_fixed_net_value, _ = calculate_net_from_gross(invoice_data.get('distribution_fixed_value_gross', 0), vat_rate)
            invoice_data['distribution_fixed_price_net'] = round(distribution_fixed_net_value / invoice_data['distribution_fixed_quantity'], 2)
        else:
            invoice_data['distribution_fixed_price_net'] = 0.0
    
    if not invoice_data.get('distribution_variable_price_net'):
        if invoice_data.get('distribution_variable_usage_m3', 0) > 0:
            # Dla dystrybucji zmiennej cena netto jest za kWh, więc potrzebujemy zużycia w kWh
            distribution_variable_net_value = invoice_data.get('distribution_variable_value_net', 0)
            fuel_usage_kwh = invoice_data.get('fuel_usage_kwh', 0)
            if fuel_usage_kwh > 0:
                invoice_data['distribution_variable_price_net'] = round(distribution_variable_net_value / fuel_usage_kwh, 5)
            else:
                invoice_data['distribution_variable_price_net'] = 0.0
        else:
            invoice_data['distribution_variable_price_net'] = 0.0
    
    # Zaokrąglij wszystkie wartości Float do 2 miejsc po przecinku
    float_fields = [
        'previous_reading', 'current_reading',
        'fuel_usage_m3', 'fuel_conversion_factor', 'fuel_usage_kwh', 'fuel_price_net', 'fuel_value_net', 'fuel_vat_amount', 'fuel_value_gross',
        'subscription_quantity', 'subscription_price_net', 'subscription_value_net', 'subscription_vat_amount', 'subscription_value_gross',
        'distribution_fixed_quantity', 'distribution_fixed_price_net', 'distribution_fixed_value_net', 'distribution_fixed_vat_amount', 'distribution_fixed_value_gross',
        'distribution_variable_usage_m3', 'distribution_variable_conversion_factor', 'distribution_variable_usage_kwh', 'distribution_variable_price_net', 'distribution_variable_value_net', 'distribution_variable_vat_amount', 'distribution_variable_value_gross',
        'distribution_variable_2_usage_m3', 'distribution_variable_2_conversion_factor', 'distribution_variable_2_usage_kwh', 'distribution_variable_2_price_net', 'distribution_variable_2_value_net',
        'vat_rate', 'vat_amount', 'total_net_sum', 'total_gross_sum',
        'late_payment_interest', 'amount_to_pay', 'balance_before_settlement'
    ]
    
    for field in float_fields:
        if field in invoice_data and invoice_data[field] is not None:
            # Pomiń pola dystrybucji zmiennej 2 jeśli są None (opcjonalne)
            if field.startswith('distribution_variable_2_') and invoice_data[field] is None:
                continue
            try:
                invoice_data[field] = round(float(invoice_data[field]), 2)
            except (ValueError, TypeError):
                if field.endswith('_quantity'):
                    invoice_data[field] = int(invoice_data.get(field, 0))
                else:
                    # Dla pól dystrybucji zmiennej 2 ustaw None zamiast 0.0
                    if field.startswith('distribution_variable_2_'):
                        invoice_data[field] = None
                    else:
                        invoice_data[field] = 0.0
    
    # Konwertuj daty jeśli są stringami
    if 'period_start' in invoice_data and isinstance(invoice_data['period_start'], str):
        invoice_data['period_start'] = datetime.strptime(invoice_data['period_start'], "%Y-%m-%d").date()
    if 'period_stop' in invoice_data and isinstance(invoice_data['period_stop'], str):
        invoice_data['period_stop'] = datetime.strptime(invoice_data['period_stop'], "%Y-%m-%d").date()
    if 'payment_due_date' in invoice_data and isinstance(invoice_data['payment_due_date'], str):
        invoice_data['payment_due_date'] = datetime.strptime(invoice_data['payment_due_date'], "%Y-%m-%d").date()
    
    # Upewnij się, że wszystkie wymagane pola są ustawione
    required_fields = {
        'data': invoice_data.get('data'),
        'period_start': invoice_data.get('period_start'),
        'period_stop': invoice_data.get('period_stop'),
        'previous_reading': invoice_data.get('previous_reading', 0.0),
        'current_reading': invoice_data.get('current_reading', 0.0),
        'fuel_usage_m3': invoice_data.get('fuel_usage_m3', 0.0),
        'fuel_price_net': invoice_data.get('fuel_price_net', 0.0),
        'fuel_value_net': invoice_data.get('fuel_value_net', 0.0),
        'fuel_vat_amount': invoice_data.get('fuel_vat_amount', 0.0),
        'fuel_value_gross': invoice_data.get('fuel_value_gross', 0.0),
        'fuel_conversion_factor': invoice_data.get('fuel_conversion_factor', 0.0),
        'fuel_usage_kwh': invoice_data.get('fuel_usage_kwh', 0.0),
        'subscription_quantity': invoice_data.get('subscription_quantity', 2),
        'subscription_price_net': invoice_data.get('subscription_price_net', 0.0),
        'subscription_value_net': invoice_data.get('subscription_value_net', 0.0),
        'subscription_vat_amount': invoice_data.get('subscription_vat_amount', 0.0),
        'subscription_value_gross': invoice_data.get('subscription_value_gross', 0.0),
        'distribution_fixed_quantity': invoice_data.get('distribution_fixed_quantity', 2),
        'distribution_fixed_price_net': invoice_data.get('distribution_fixed_price_net', 0.0),
        'distribution_fixed_vat_amount': invoice_data.get('distribution_fixed_vat_amount', 0.0),
        'distribution_fixed_value_gross': invoice_data.get('distribution_fixed_value_gross', 0.0),
        'distribution_fixed_value_net': invoice_data.get('distribution_fixed_value_net', 0.0),
        'distribution_variable_usage_m3': invoice_data.get('distribution_variable_usage_m3', 0.0),
        'distribution_variable_conversion_factor': invoice_data.get('distribution_variable_conversion_factor', 0.0),
        'distribution_variable_usage_kwh': invoice_data.get('distribution_variable_usage_kwh', 0.0),
        'distribution_variable_price_net': invoice_data.get('distribution_variable_price_net', 0.0),
        'distribution_variable_value_net': invoice_data.get('distribution_variable_value_net', 0.0),
        'distribution_variable_vat_amount': invoice_data.get('distribution_variable_vat_amount', 0.0),
        'distribution_variable_value_gross': invoice_data.get('distribution_variable_value_gross', 0.0),
        'vat_rate': invoice_data.get('vat_rate', 0.23),
        'vat_amount': invoice_data.get('vat_amount', 0.0),
        'total_net_sum': invoice_data.get('total_net_sum', 0.0),
        'total_gross_sum': invoice_data.get('total_gross_sum', 0.0),
        'late_payment_interest': invoice_data.get('late_payment_interest', 0.0),
        'amount_to_pay': invoice_data.get('amount_to_pay', 0.0),
        'payment_due_date': invoice_data.get('payment_due_date'),
        'invoice_number': invoice_data.get('invoice_number'),
    }
    
    # Sprawdź czy wszystkie wymagane pola są ustawione
    missing_fields = [k for k, v in required_fields.items() if v is None]
    if missing_fields:
        raise ValueError(f"Brakuje wymaganych pól: {', '.join(missing_fields)}")
    
    # Zaktualizuj invoice_data z wymaganymi polami
    invoice_data.update(required_fields)
    
    # Sprawdź czy faktura już istnieje
    existing_invoice = db.query(GasInvoice).filter(
        GasInvoice.invoice_number == invoice_data['invoice_number'],
        GasInvoice.data == invoice_data['data']
    ).first()
    
    if existing_invoice:
        print(f"[INFO] Faktura {invoice_data['invoice_number']} dla okresu {invoice_data['data']} już istnieje.")
        return existing_invoice
    
    # Utwórz nową fakturę - usuń pola None dla opcjonalnych pól, aby nie były przekazywane do konstruktora
    # SQLAlchemy automatycznie użyje NULL dla pól nullable=True, jeśli nie są przekazane
    invoice_kwargs = {k: v for k, v in invoice_data.items() if v is not None or not k.startswith('distribution_variable_2_')}
    
    try:
        invoice = GasInvoice(**invoice_kwargs)
        db.add(invoice)
        db.commit()
        db.refresh(invoice)
        
        print(f"[OK] Wczytano nową fakturę gazu {invoice_data['invoice_number']} dla okresu {invoice_data['data']} (ID: {invoice.id})")
        
        return invoice
    except Exception as e:
        db.rollback()
        import traceback
        error_details = traceback.format_exc()
        print(f"[ERROR] Błąd tworzenia faktury gazu: {error_details}")
        print(f"[ERROR] Dane faktury: {invoice_kwargs.keys()}")
        raise

