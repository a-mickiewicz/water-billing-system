"""
Moduł wczytywania i parsowania faktur PDF od dostawcy mediów.
Wczytuje dane z plików PDF w folderze invoices_raw/.
"""

import os
import re
from datetime import datetime
from pathlib import Path
import pdfplumber
from typing import Optional, Dict
from sqlalchemy.orm import Session
from models import Invoice, Reading


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
    Używa dodatkowych opcji, aby wyciągnąć także tekst z tabel i innych elementów.
    
    Args:
        pdf_path: Ścieżka do pliku PDF
    
    Returns:
        Wszystki tekst z pliku PDF
    """
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages, 1):
                # Wyciągnij tekst podstawowy
                page_text = page.extract_text() or ""
                
                # Spróbuj też wyciągnąć tabele (mogą zawierać dane o odczytach liczników)
                try:
                    tables = page.extract_tables()
                    if tables:
                        # Dodaj dane z tabel do tekstu
                        for table in tables:
                            for row in table:
                                if row:
                                    row_text = " ".join([str(cell) if cell else "" for cell in row])
                                    page_text += " " + row_text
                except Exception:
                    pass  # Jeśli nie da się wyciągnąć tabel, kontynuuj
                
                text += page_text + "\n"
        
    except Exception as e:
        print(f"Błąd przy wczytywaniu PDF {pdf_path}: {e}")
    return text


def parse_invoice_data(text: str) -> Optional[Dict]:
    """
    Parsuje dane z faktury na podstawie tekstu PDF.
    To jest przykładowa implementacja - może wymagać dostosowania do konkretnego formatu faktur.
    
    Args:
        text: Tekst z pliku PDF
    
    Returns:
        Słownik z danymi faktury lub None
    """
    data = {}
    
    # Wyszukaj numer faktury (format: R14/08/002163, RP18/07/003594, FRP19/08/028241, FRP/22/04/018327)
    invoice_match = re.search(r'(?:FRP|RP|R)/?\d{2}/\d{2}/\d{6}', text, re.IGNORECASE)
    if invoice_match:
        data['invoice_number'] = invoice_match.group(0)
    else:
        # Szukaj z prefiksem tekstowym (Nr:, numer:, faktury:, etc.)
        invoice_match = re.search(r'(?:FRP|RP|Nr|numer|faktury|invoice)[\s:]*((?:FRP|RP|R)/?\d{2}/\d{2}/\d{6})', text, re.IGNORECASE)
        if invoice_match:
            data['invoice_number'] = invoice_match.group(1)
        else:
            # Szukaj różnych wzorców (fallback)
            invoice_match = re.search(r'(?:Faktura|Invoice)\s+(?:nr\s+)?([A-Z0-9/-]+)', text, re.IGNORECASE)
            if invoice_match:
                data['invoice_number'] = invoice_match.group(1)
    
    # Wyszukaj wszystkie pozycje wody (format: "Woda m3 8,10 4,70 38,07 8%")
    # Format: "Woda m3 [zużycie] [cena_za_m3] [wartość_netto] [vat]"
    water_pattern = r'Woda\s+m3\s+(\d+[.,]\d+)\s+(\d+[.,]\d+)\s+(\d+[.,]\d+)\s+\d+%?'
    water_matches = re.findall(water_pattern, text, re.IGNORECASE)
    
    if water_matches:
        # Sumuj zużycie i oblicz średnią ważoną cenę
        total_usage = 0.0
        total_value = 0.0  # wartość netto (zużycie * cena)
        
        for match in water_matches:
            usage = float(match[0].replace(',', '.'))
            price = float(match[1].replace(',', '.'))
            value = float(match[2].replace(',', '.'))
            total_usage += usage
            total_value += value
        
        # Średnia ważona cena (całkowita wartość / całkowite zużycie)
        avg_price = total_value / total_usage if total_usage > 0 else 0.0
        
        data['usage'] = total_usage
        data['water_cost_m3'] = avg_price
    else:
        # Fallback - stary sposób szukania
        usage_match = re.search(r'(?:zużycie|usage|Zużycie)\s*:?\s*(\d+[.,]\d+)\s*m[³3]', text, re.IGNORECASE)
        if usage_match:
            data['usage'] = float(usage_match.group(1).replace(',', '.'))
        
        water_cost_match = re.search(r'(?:woda|water)[\s:]+(\d+[.,]\d+)\s*[zł]', text, re.IGNORECASE)
        if not water_cost_match:
            water_cost_match = re.search(r'(\d+[.,]\d+)\s*zł\s*/?\s*m[³3].*?woda', text, re.IGNORECASE)
        if water_cost_match:
            data['water_cost_m3'] = float(water_cost_match.group(1).replace(',', '.'))
    
    # Wyszukaj wszystkie pozycje ścieków (format: "Ścieki m3 8,10 4,70 38,07 8%")
    sewage_pattern = r'Ścieki\s+m3\s+(\d+[.,]\d+)\s+(\d+[.,]\d+)\s+(\d+[.,]\d+)\s+\d+%?'
    sewage_matches = re.findall(sewage_pattern, text, re.IGNORECASE)
    
    if sewage_matches:
        # Sumuj zużycie i oblicz średnią ważoną cenę
        total_sewage_usage = 0.0
        total_sewage_value = 0.0
        
        for match in sewage_matches:
            usage = float(match[0].replace(',', '.'))
            price = float(match[1].replace(',', '.'))
            value = float(match[2].replace(',', '.'))
            total_sewage_usage += usage
            total_sewage_value += value
        
        # Średnia ważona cena (całkowita wartość / całkowite zużycie)
        avg_sewage_price = total_sewage_value / total_sewage_usage if total_sewage_usage > 0 else 0.0
        
        data['sewage_cost_m3'] = avg_sewage_price
    else:
        # Fallback - stary sposób szukania
        sewage_cost_match = re.search(r'(?:ścieki|sewage)[\s:]+(\d+[.,]\d+)\s*[zł]', text, re.IGNORECASE)
        if not sewage_cost_match:
            sewage_cost_match = re.search(r'(\d+[.,]\d+)\s*zł\s*/?\s*m[³3].*?ścieki', text, re.IGNORECASE)
        if sewage_cost_match:
            data['sewage_cost_m3'] = float(sewage_cost_match.group(1).replace(',', '.'))
    
    # Wyszukaj VAT
    # Format 1: Tabela z nagłówkiem "Wartość Netto Stawka VAT Kwota VAT Wartość Brutto"
    # Format linii danych: 394,88 8% 31,59 426,47
    # Szukamy linii z formatem: liczba liczba% liczba liczba (gdzie druga liczba to VAT%)
    vat_table_match = re.search(r'Wartość\s+Netto\s+Stawka\s+VAT.*?[\n\r]+.*?(\d+[.,]\d+)\s+(\d+)%\s+\d+[.,]\d+\s+\d+[.,]\d+', text, re.IGNORECASE | re.DOTALL)
    if vat_table_match:
        vat_str = vat_table_match.group(2).replace(',', '.')
        data['vat'] = float(vat_str) / 100 if float(vat_str) > 1 else float(vat_str)
    else:
        # Format 2: Linia z samą wartością VAT w formacie tabeli (bez nagłówka)
        # Format: liczba liczba% liczba liczba
        vat_line_match = re.search(r'\d+[.,]\d+\s+(\d+)%\s+\d+[.,]\d+\s+\d+[.,]\d+', text, re.IGNORECASE)
        if vat_line_match:
            vat_str = vat_line_match.group(1).replace(',', '.')
            data['vat'] = float(vat_str) / 100 if float(vat_str) > 1 else float(vat_str)
        else:
            # Format 3: Stary format "VAT: 8%"
            vat_match = re.search(r'VAT[:\s]+(\d+[.,]?\d*)%?', text, re.IGNORECASE)
            if vat_match:
                vat_str = vat_match.group(1).replace(',', '.')
                if vat_str:
                    vat_val = float(vat_str)
                    data['vat'] = vat_val / 100 if vat_val > 1 else vat_val
                else:
                    data['vat'] = 0.08
            else:
                data['vat'] = 0.08  # Domyślny VAT 8%
    
    # Wyszukaj daty okresu rozliczeniowego
    period_match = re.search(r'(?:od|from)[\s:]+(\d{1,2})[./-](\d{1,2})[./-](\d{4})\s+(?:do|to)[\s:]+(\d{1,2})[./-](\d{1,2})[./-](\d{4})', text, re.IGNORECASE)
    if period_match:
        start_day, start_month, start_year = period_match.group(1, 2, 3)
        end_day, end_month, end_year = period_match.group(4, 5, 6)
        data['period_start'] = datetime(int(start_year), int(start_month), int(start_day))
        data['period_stop'] = datetime(int(end_year), int(end_month), int(end_day))
    
    # Wyszukaj "Rozliczenie za okres od DD-MM-YYYY" i wyciągnij okres YYYY-MM
    # Wzorzec: "Rozliczenie za okres od" + data w formacie DD-MM-YYYY lub DD.MM.YYYY lub DD/MM/YYYY
    rozliczenie_match = re.search(r'Rozliczenie\s+za\s+okres\s+od\s+(\d{1,2})[./-](\d{1,2})[./-](\d{4})', text, re.IGNORECASE)
    extracted_period = None  # Zapisujemy okres do użycia w load_invoice_from_pdf, ale nie dodajemy do data
    if rozliczenie_match:
        day, month, year = rozliczenie_match.group(1, 2, 3)
        # Zapisz okres w formacie YYYY-MM (nie dodajemy do data, bo model używa 'data', nie 'period')
        extracted_period = f"{year}-{int(month):02d}"
        # Jeśli nie mamy period_start, ustaw go na podstawie tej daty
        if 'period_start' not in data:
            data['period_start'] = datetime(int(year), int(month), int(day))
    
    # Zapisz wyciągnięty okres do użycia w load_invoice_from_pdf (ale nie dodawaj do data)
    if extracted_period:
        # Używamy specjalnego klucza który zostanie usunięty przed utworzeniem Invoice
        data['_extracted_period'] = extracted_period
    
    # Wyszukaj abonament
    abonament_match = re.search(r'(\d+)\s*(?:miesięcy|months)', text, re.IGNORECASE)
    if abonament_match:
        data['nr_of_subscription'] = int(abonament_match.group(1))
    else:
        # Próba wyliczenia z dat
        if 'period_start' in data and 'period_stop' in data:
            delta = data['period_stop'] - data['period_start']
            data['nr_of_subscription'] = max(1, int(delta.days / 30))
        else:
            data['nr_of_subscription'] = 2  # Domyślnie 2 miesiące
    
    # Wyszukaj koszty abonamentów
    abonament_water_match = re.search(r'abonament.*?woda.*?(\d+[.,]\d+)', text, re.IGNORECASE)
    if abonament_water_match:
        data['water_subscr_cost'] = float(abonament_water_match.group(1).replace(',', '.'))
    else:
        data['water_subscr_cost'] = 0.0
    
    abonament_sewage_match = re.search(r'abonament.*?ścieki.*?(\d+[.,]\d+)', text, re.IGNORECASE)
    if abonament_sewage_match:
        data['sewage_subscr_cost'] = float(abonament_sewage_match.group(1).replace(',', '.'))
    else:
        data['sewage_subscr_cost'] = 0.0
    
    # Wyszukaj sumę brutto
    # Format 1: Tabela z nagłówkiem "Wartość Netto Stawka VAT Kwota VAT Wartość Brutto"
    # Format linii danych: 394,88 8% 31,59 426,47 (ostatnia wartość to wartość brutto)
    gross_table_match = re.search(r'Wartość\s+Netto\s+Stawka\s+VAT.*?[\n\r]+.*?(\d+[.,]\d+)\s+\d+%\s+\d+[.,]\d+\s+(\d+[.,]\d+)', text, re.IGNORECASE | re.DOTALL)
    if gross_table_match:
        data['gross_sum'] = float(gross_table_match.group(2).replace(',', '.'))
    else:
        # Format 2: "Należność bieżąca (zł): 426,47"
        gross_current_match = re.search(r'Należność\s+bieżąca\s*\(zł\)[:\s]+(\d+[.,]\d+)', text, re.IGNORECASE)
        if gross_current_match:
            data['gross_sum'] = float(gross_current_match.group(1).replace(',', '.'))
        else:
            # Format 3: Linia z formatem tabeli (bez nagłówka)
            # Format: liczba liczba% liczba liczba (ostatnia to wartość brutto)
            gross_line_match = re.search(r'\d+[.,]\d+\s+\d+%\s+\d+[.,]\d+\s+(\d+[.,]\d+)', text, re.IGNORECASE)
            if gross_line_match:
                data['gross_sum'] = float(gross_line_match.group(1).replace(',', '.'))
            else:
                # Format 4: Stary format
                gross_sum_match = re.search(r'(?:suma|total|razem)\s*(?:brutto|gross)[\s:]+(\d+[.,]\d+)', text, re.IGNORECASE)
                if not gross_sum_match:
                    gross_sum_match = re.search(r'(\d+[.,]\d+)\s*zł[\s]*$', text)
                if gross_sum_match:
                    data['gross_sum'] = float(gross_sum_match.group(1).replace(',', '.'))
    
    # Wyszukaj odczyty liczników z tabeli (pod "Adres świadczenia usługi")
    # Format: Tabela z kolumnami: "Poprzed. odczyt", "Bieżący odczyt", "Ilość do rozl."
    # Szukamy wzorców typu: "Poprzed. odczyt" lub "Poprzedni odczyt" + liczba
    meter_readings = {}
    
    # Wzorzec dla tabeli z odczytami - szukamy sekcji po "Adres świadczenia usługi"
    adres_match = re.search(r'Adres\s+świadczenia\s+usługi.*?(?=Wartość\s+Netto|Rozliczenie|Należność|$)', text, re.IGNORECASE | re.DOTALL)
    if adres_match:
        adres_section = adres_match.group(0)
        
        # Szukaj poprzedniego odczytu - różne formaty
        prev_patterns = [
            r'Poprzed\.?\s*odczyt[:\s]*(\d+[.,]?\d*)',
            r'Poprzedni\s+odczyt[:\s]*(\d+[.,]?\d*)',
            r'Poprzed\.\s+odczyt[:\s]*(\d+[.,]?\d*)',
        ]
        for pattern in prev_patterns:
            prev_match = re.search(pattern, adres_section, re.IGNORECASE)
            if prev_match:
                meter_readings['previous_reading'] = float(prev_match.group(1).replace(',', '.'))
                break
        
        # Szukaj bieżącego odczytu
        current_patterns = [
            r'Bieżący\s+odczyt[:\s]*(\d+[.,]?\d*)',
            r'Biezący\s+odczyt[:\s]*(\d+[.,]?\d*)',
        ]
        for pattern in current_patterns:
            current_match = re.search(pattern, adres_section, re.IGNORECASE)
            if current_match:
                meter_readings['current_reading'] = float(current_match.group(1).replace(',', '.'))
                break
        
        # Szukaj ilości do rozliczenia
        quantity_patterns = [
            r'Ilość\s+do\s+rozliczenia[:\s]*(\d+[.,]?\d*)',
            r'Ilość\s+do\s+rozl\.?[:\s]*(\d+[.,]?\d*)',
        ]
        for pattern in quantity_patterns:
            quantity_match = re.search(pattern, adres_section, re.IGNORECASE)
            if quantity_match:
                meter_readings['quantity_to_settle'] = float(quantity_match.group(1).replace(',', '.'))
                break
    
    # Alternatywny wzorzec - szukaj w całym tekście formatu tabeli
    if not meter_readings:
        # Szukaj wzorca: Woda/Poprzed. odczyt/[liczba]/Bieżący odczyt/[liczba]/Ilość do rozl./[liczba]
        meter_table_pattern = r'Woda.*?(?:Poprzed\.?\s*odczyt|Poprzedni\s+odczyt)[:\s]*(\d+[.,]?\d*).*?(?:Bieżący\s+odczyt|Biezący\s+odczyt)[:\s]*(\d+[.,]?\d*).*?(?:Ilość\s+do\s+rozl\.?|Ilość\s+do\s+rozliczenia)[:\s]*(\d+[.,]?\d*)'
        meter_table_match = re.search(meter_table_pattern, text, re.IGNORECASE | re.DOTALL)
        if meter_table_match:
            meter_readings['previous_reading'] = float(meter_table_match.group(1).replace(',', '.'))
            meter_readings['current_reading'] = float(meter_table_match.group(2).replace(',', '.'))
            meter_readings['quantity_to_settle'] = float(meter_table_match.group(3).replace(',', '.'))
    
    # Dodaj odczyty liczników do danych faktury (jeśli znalezione)
    if meter_readings:
        data['meter_readings'] = meter_readings
        print(f"  [INFO] Znaleziono odczyty liczników z faktury:")
        if 'previous_reading' in meter_readings:
            print(f"    Poprzedni odczyt: {meter_readings['previous_reading']} m³")
        if 'current_reading' in meter_readings:
            print(f"    Bieżący odczyt: {meter_readings['current_reading']} m³")
        if 'quantity_to_settle' in meter_readings:
            print(f"    Ilość do rozliczenia: {meter_readings['quantity_to_settle']} m³")
    
    # Sprawdź czy wszystkie wymagane dane są obecne
    required_fields = [
        'invoice_number', 'usage', 'water_cost_m3', 'sewage_cost_m3',
        'nr_of_subscription', 'water_subscr_cost', 'sewage_subscr_cost',
        'vat', 'period_start', 'period_stop', 'gross_sum'
    ]
    
    if all(field in data for field in required_fields):
        return data
    
    return None


def load_invoice_from_pdf(db: Session, pdf_path: str, period: Optional[str] = None) -> Optional[Invoice]:
    """
    Wczytuje fakturę z pliku PDF i zapisuje do bazy danych.
    Obsługuje różne nazwy plików - okres jest wyciągany z nazwy pliku lub z dat faktury.
    
    Args:
        db: Sesja bazy danych
        pdf_path: Ścieżka do pliku PDF
        period: Okres rozliczeniowy (jeśli None, wyciąga z nazwy pliku lub z dat faktury)
    
    Returns:
        Zapisana faktura lub None w przypadku błędu
    """
    print(f"\n📄 Przetwarzanie pliku: {os.path.basename(pdf_path)}")
    
    # Wczytaj tekst z PDF
    text = extract_text_from_pdf(pdf_path)
    if not text:
        print(f"❌ Nie udało się wczytać tekstu z pliku: {pdf_path}")
        return None
    
    # Parsuj dane z faktury
    invoice_data = parse_invoice_data(text)
    
    if not invoice_data:
        print(f"❌ Nie udało się sparsować danych z faktury: {pdf_path}")
        print("   Tekst z faktury (pierwsze 500 znaków):")
        print(f"   {text[:500]}")
        return None
    
    # Określ okres rozliczeniowy
    if not period:
        # Priorytet 1: Wyciągnij z tekstu faktury "Rozliczenie za okres od DD-MM-YYYY"
        if '_extracted_period' in invoice_data:
            period = invoice_data['_extracted_period']
            print(f"📅 Okres wyciągnięty z tekstu faktury 'Rozliczenie za okres od...': {period}")
        else:
            # Priorytet 2: Próbuj wyciągnąć z nazwy pliku
            period = parse_period_from_filename(os.path.basename(pdf_path))
            if period:
                print(f"📅 Okres wyciągnięty z nazwy pliku: {period}")
            else:
                # Priorytet 3: Wyciągnij z daty początku okresu faktury
                if 'period_start' in invoice_data:
                    period_start = invoice_data['period_start']
                    period = f"{period_start.year}-{period_start.month:02d}"
                    print(f"📅 Okres wyciągnięty z daty początku okresu faktury: {period}")
    
    if not period:
        print(f"❌ Nie można określić okresu rozliczeniowego dla: {pdf_path}")
        print("   Okres musi być w tekście faktury ('Rozliczenie za okres od DD-MM-YYYY'),")
        print("   w nazwie pliku (format YYYY-MM) lub w dacie faktury")
        return None
    
    # Dodaj okres do danych
    invoice_data['data'] = period
    
    # Usuń pomocnicze pola które nie są w modelu Invoice
    invoice_data.pop('_extracted_period', None)  # Usuń pomocniczy klucz okresu
    invoice_data.pop('meter_readings', None)  # Usuń odczyty liczników (nie są częścią modelu Invoice)
    
    # Sprawdź czy faktura już istnieje w bazie danych
    # Porównaj kluczowe pola: numer faktury, okres, suma brutto
    existing_invoice = db.query(Invoice).filter(
        Invoice.invoice_number == invoice_data['invoice_number'],
        Invoice.data == invoice_data['data']
    ).first()
    
    if existing_invoice:
        # Faktura już istnieje - sprawdź czy dane się zgadzają
        differences = []
        
        # Porównaj wszystkie kluczowe pola
        fields_to_compare = [
            ('usage', 'Zużycie'),
            ('water_cost_m3', 'Koszt wody za m³'),
            ('sewage_cost_m3', 'Koszt ścieków za m³'),
            ('nr_of_subscription', 'Liczba miesięcy abonamentu'),
            ('water_subscr_cost', 'Koszt abonamentu wody'),
            ('sewage_subscr_cost', 'Koszt abonamentu ścieków'),
            ('vat', 'VAT'),
            ('period_start', 'Początek okresu'),
            ('period_stop', 'Koniec okresu'),
            ('gross_sum', 'Suma brutto'),
        ]
        
        for field, label in fields_to_compare:
            existing_value = getattr(existing_invoice, field)
            new_value = invoice_data[field]
            
            # Dla wartości float porównaj z tolerancją
            if isinstance(existing_value, float) and isinstance(new_value, float):
                if abs(existing_value - new_value) > 0.01:  # Tolerancja 0.01
                    differences.append(f"{label}: istniejące={existing_value}, nowe={new_value}")
            elif existing_value != new_value:
                differences.append(f"{label}: istniejące={existing_value}, nowe={new_value}")
        
        if differences:
            # Dane się różnią - wyświetl ostrzeżenie
            print(f"[⚠️ OSTRZEŻENIE] Faktura {invoice_data['invoice_number']} dla okresu {period} już istnieje w bazie!")
            print("Znalezione różnice:")
            for diff in differences:
                print(f"  - {diff}")
            print(f"[INFO] Zostanie użyta istniejąca faktura (ID: {existing_invoice.id})")
            return existing_invoice
        else:
            # Dane się zgadzają - użyj istniejącej faktury
            print(f"[INFO] Faktura {invoice_data['invoice_number']} dla okresu {period} już istnieje w bazie i dane się zgadzają.")
            print(f"[INFO] Używam istniejącej faktury (ID: {existing_invoice.id})")
            return existing_invoice
    
    # Faktura nie istnieje - stwórz nową
    invoice = Invoice(**invoice_data)
    
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    
    print(f"[OK] Wczytano nową fakturę {invoice_data['invoice_number']} dla okresu {period} (ID: {invoice.id})")
    
    return invoice


def load_invoices_from_folder(db: Session, folder_path: str = "invoices_raw") -> list[Invoice]:
    """
    Wczytuje wszystkie faktury PDF z folderu.
    Obsługuje różne nazwy plików - okres jest wyciągany z nazwy pliku lub z dat faktury.
    
    Args:
        db: Sesja bazy danych
        folder_path: Ścieżka do folderu z faktrami
    
    Returns:
        Lista wczytanych faktur
    """
    invoices = []
    folder = Path(folder_path)
    
    if not folder.exists():
        print(f"❌ Folder {folder_path} nie istnieje")
        return invoices
    
    # Znajdź wszystkie pliki PDF
    pdf_files = sorted(list(folder.glob("*.pdf")))
    
    print("=" * 80)
    print(f"📁 Wczytywanie faktur z folderu: {folder_path}")
    print(f"📄 Znaleziono {len(pdf_files)} plików PDF")
    print("=" * 80)
    
    if not pdf_files:
        print("⚠️ Brak plików PDF do przetworzenia")
        return invoices
    
    loaded_count = 0
    skipped_count = 0
    error_count = 0
    
    for pdf_file in pdf_files:
        try:
            invoice = load_invoice_from_pdf(db, str(pdf_file))
            if invoice:
                invoices.append(invoice)
                loaded_count += 1
            else:
                # Może to być faktura która już istnieje (duplikat) lub błąd parsowania
                skipped_count += 1
        except Exception as e:
            error_count += 1
            print(f"❌ Błąd podczas przetwarzania {pdf_file.name}: {e}")
    
    print("\n" + "=" * 80)
    print("📊 PODSUMOWANIE:")
    print(f"   ✅ Wczytane nowe faktury: {loaded_count}")
    print(f"   ⏭️  Pominięte faktury: {skipped_count}")
    print(f"   ❌ Błędy: {error_count}")
    print(f"   📋 Razem: {len(pdf_files)} plików")
    print("=" * 80)
    
    return invoices


if __name__ == "__main__":
    from db import SessionLocal, init_db
    from models import Invoice
    
    init_db()
    
    db = SessionLocal()
    try:
        invoices = load_invoices_from_folder(db)
        print(f"\n[OK] Wczytano {len(invoices)} faktur")
    finally:
        db.close()

