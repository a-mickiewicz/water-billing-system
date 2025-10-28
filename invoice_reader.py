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
    Wyciąga tekst z pliku PDF.
    
    Args:
        pdf_path: Ścieżka do pliku PDF
    
    Returns:
        Wszystki tekst z pliku PDF
    """
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text += page.extract_text() or ""
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
    
    # Wyszukaj numer faktury
    invoice_match = re.search(r'(?:Nr|numer|faktury|invoice):\s*(\w+)', text, re.IGNORECASE)
    if invoice_match:
        data['invoice_number'] = invoice_match.group(1)
    else:
        # Szukaj różnych wzorców
        invoice_match = re.search(r'(?:Faktura|Invoice)\s+(?:nr\s+)?([A-Z0-9/-]+)', text, re.IGNORECASE)
        if invoice_match:
            data['invoice_number'] = invoice_match.group(1)
    
    # Wyszukaj zużycie w m³
    usage_match = re.search(r'(?:zużycie|usage|Zużycie)\s*:?\s*(\d+[.,]\d+)\s*m[³3]', text, re.IGNORECASE)
    if usage_match:
        data['usage'] = float(usage_match.group(1).replace(',', '.'))
    
    # Wyszukaj koszt wody za m³
    water_cost_match = re.search(r'(?:woda|water)[\s:]+(\d+[.,]\d+)\s*[zł]', text, re.IGNORECASE)
    if not water_cost_match:
        water_cost_match = re.search(r'(\d+[.,]\d+)\s*zł\s*/?\s*m[³3].*?woda', text, re.IGNORECASE)
    if water_cost_match:
        data['water_cost_m3'] = float(water_cost_match.group(1).replace(',', '.'))
    
    # Wyszukaj koszt ścieków za m³
    sewage_cost_match = re.search(r'(?:ścieki|sewage)[\s:]+(\d+[.,]\d+)\s*[zł]', text, re.IGNORECASE)
    if not sewage_cost_match:
        sewage_cost_match = re.search(r'(\d+[.,]\d+)\s*zł\s*/?\s*m[³3].*?ścieki', text, re.IGNORECASE)
    if sewage_cost_match:
        data['sewage_cost_m3'] = float(sewage_cost_match.group(1).replace(',', '.'))
    
    # Wyszukaj VAT
    vat_match = re.search(r'VAT[:\s]+(\d+[.,]\d+)%?', text, re.IGNORECASE)
    if vat_match:
        vat_str = vat_match.group(1).replace(',', '.')
        data['vat'] = float(vat_str) / 100 if float(vat_str) > 1 else float(vat_str)
    else:
        data['vat'] = 0.08  # Domyślny VAT 8%
    
    # Wyszukaj daty okresu rozliczeniowego
    period_match = re.search(r'(?:od|from)[\s:]+(\d{1,2})[./-](\d{1,2})[./-](\d{4})\s+(?:do|to)[\s:]+(\d{1,2})[./-](\d{1,2})[./-](\d{4})', text, re.IGNORECASE)
    if period_match:
        start_day, start_month, start_year = period_match.group(1, 2, 3)
        end_day, end_month, end_year = period_match.group(4, 5, 6)
        data['period_start'] = datetime(int(start_year), int(start_month), int(start_day))
        data['period_stop'] = datetime(int(end_year), int(end_month), int(end_day))
    
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
    gross_sum_match = re.search(r'(?:suma|total|razem)\s*(?:brutto|gross)[\s:]+(\d+[.,]\d+)', text, re.IGNORECASE)
    if not gross_sum_match:
        gross_sum_match = re.search(r'(\d+[.,]\d+)\s*zł[\s]*$', text)
    if gross_sum_match:
        data['gross_sum'] = float(gross_sum_match.group(1).replace(',', '.'))
    
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
    
    Args:
        db: Sesja bazy danych
        pdf_path: Ścieżka do pliku PDF
        period: Okres rozliczeniowy (jeśli None, wyciąga z nazwy pliku)
    
    Returns:
        Zapisana faktura lub None w przypadku błędu
    """
    # Wyciągnij okres z nazwy pliku jeśli nie podano
    if not period:
        period = parse_period_from_filename(os.path.basename(pdf_path))
    
    if not period:
        print(f"Nie można wyciągnąć okresu z nazwy pliku: {pdf_path}")
        return None
    
    # Wczytaj tekst z PDF (może być wiele faktur dla tego samego okresu)
    text = extract_text_from_pdf(pdf_path)
    if not text:
        print(f"Nie udało się wczytać tekstu z pliku: {pdf_path}")
        return None
    
    # Parsuj dane
    invoice_data = parse_invoice_data(text)
    
    if not invoice_data:
        print(f"Nie udało się sparsować danych z faktury: {pdf_path}")
        print("Tekst z faktury (pierwsze 500 znaków):")
        print(text[:500])
        return None
    
    # Dodaj okres do danych
    invoice_data['data'] = period
    
    # Stwórz fakturę
    invoice = Invoice(**invoice_data)
    
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    
    print(f"[OK] Wczytano fakturę dla okresu {period}")
    
    return invoice


def load_invoices_from_folder(db: Session, folder_path: str = "invoices_raw") -> list[Invoice]:
    """
    Wczytuje wszystkie faktury PDF z folderu.
    
    Args:
        db: Sesja bazy danych
        folder_path: Ścieżka do folderu z faktrami
    
    Returns:
        Lista wczytanych faktur
    """
    invoices = []
    folder = Path(folder_path)
    
    if not folder.exists():
        print(f"Folder {folder_path} nie istnieje")
        return invoices
    
    # Znajdź wszystkie pliki PDF
    pdf_files = list(folder.glob("*.pdf"))
    
    print(f"Znaleziono {len(pdf_files)} plików PDF")
    
    for pdf_file in pdf_files:
        invoice = load_invoice_from_pdf(db, str(pdf_file))
        if invoice:
            invoices.append(invoice)
    
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

