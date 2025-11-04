"""
Narzędzie do debugowania parsowania faktur.
Pomaga znaleźć błędy w parsowaniu danych z faktury.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.water.invoice_reader import extract_text_from_pdf, parse_invoice_data
import re

def debug_invoice(pdf_path: str):
    """Analizuje fakturę i pokazuje co jest parsowane."""
    print(f"\n{'='*80}")
    print(f"Analiza faktury: {os.path.basename(pdf_path)}")
    print(f"{'='*80}\n")
    
    # Wczytaj tekst
    text = extract_text_from_pdf(pdf_path)
    if not text:
        print("❌ Nie udało się wczytać tekstu z PDF")
        return
    
    print("📄 Fragment tekstu faktury (pierwsze 2000 znaków):")
    print("-" * 80)
    print(text[:2000])
    print("-" * 80)
    print("\n")
    
    # Szukaj wzorców wody
    print("🔍 Wyszukiwanie wzorców WODY:")
    print("-" * 80)
    water_pattern = r'Woda\s+m3\s+(\d+[.,]\d+)\s+(\d+[.,]\d+)\s+(\d+[.,]\d+)\s+\d+%?'
    water_matches = re.findall(water_pattern, text, re.IGNORECASE)
    print(f"Znalezione dopasowania: {len(water_matches)}")
    for i, match in enumerate(water_matches, 1):
        print(f"  {i}. Zużycie: {match[0]}, Cena: {match[1]}, Wartość: {match[2]}")
    
    # Szukaj wzorców ścieków
    print("\n🔍 Wyszukiwanie wzorców ŚCIEKÓW:")
    print("-" * 80)
    sewage_pattern = r'Ścieki\s+m3\s+(\d+[.,]\d+)\s+(\d+[.,]\d+)\s+(\d+[.,]\d+)\s+\d+%?'
    sewage_matches = re.findall(sewage_pattern, text, re.IGNORECASE)
    print(f"Znalezione dopasowania: {len(sewage_matches)}")
    for i, match in enumerate(sewage_matches, 1):
        print(f"  {i}. Zużycie: {match[0]}, Cena: {match[1]}, Wartość: {match[2]}")
    
    # Szukaj abonamentów
    print("\n🔍 Wyszukiwanie ABONAMENTÓW:")
    print("-" * 80)
    abonament_water_patterns = [
        r'abonament.*?woda.*?(\d+[.,]\d+)',
        r'woda.*?abonament.*?(\d+[.,]\d+)',
        r'abonament.*?wodny.*?(\d+[.,]\d+)',
    ]
    for pattern in abonament_water_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            print(f"Wzorzec '{pattern}': {matches}")
    
    abonament_sewage_patterns = [
        r'abonament.*?ścieki.*?(\d+[.,]\d+)',
        r'ścieki.*?abonament.*?(\d+[.,]\d+)',
    ]
    for pattern in abonament_sewage_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            print(f"Wzorzec '{pattern}': {matches}")
    
    # Szukaj w tabeli z pozycjami
    print("\n🔍 Wyszukiwanie w tabeli faktury:")
    print("-" * 80)
    # Szukaj sekcji z pozycjami faktury
    table_section = re.search(r'(Woda|Ścieki|Abonament).*?(?:Wartość\s+Netto|Razem|Suma)', text, re.IGNORECASE | re.DOTALL)
    if table_section:
        print("Znaleziona sekcja tabeli:")
        print(table_section.group(0)[:500])
    
    # Parsuj fakturę
    print("\n📊 Wynik parsowania:")
    print("-" * 80)
    parsed_data = parse_invoice_data(text)
    if parsed_data:
        for key, value in parsed_data.items():
            if key not in ['period_start', 'period_stop', 'meter_readings', '_extracted_period']:
                print(f"  {key}: {value}")
    else:
        print("❌ Nie udało się sparsować faktury")
    
    print("\n" + "="*80)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
    else:
        # Domyślnie testuj fakturę FRP/25/10/032668
        pdf_path = "invoices_raw/FVSP_FRP_25_10_032668.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"❌ Plik nie istnieje: {pdf_path}")
        sys.exit(1)
    
    debug_invoice(pdf_path)

