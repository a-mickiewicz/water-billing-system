"""
Narzędzie do debugowania parsowania konkretnej faktury.
Pokazuje co jest parsowane z faktury.
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
        print("[BLAD] Nie udalo sie wczytac tekstu z PDF")
        return
    
    # Znajdź sekcję z pozycjami faktury
    items_section = re.search(r'(?:Pozycje|Pozycja|Woda|Ścieki|Abonament).*?(?:Wartość\s+Netto|Razem|Suma|VAT)', text, re.IGNORECASE | re.DOTALL)
    search_text = items_section.group(0) if items_section else text
    
    print("[SEKCJA] Sekcja z pozycjami faktury:")
    print("-" * 80)
    print(search_text[:1500])
    print("-" * 80)
    print("\n")
    
    # Szukaj wzorców abonamentu wody
    print("[SZUKANIE] Wyszukiwanie ABONAMENTU WODY:")
    print("-" * 80)
    abonament_water_patterns = [
        (r'Abonament\s+Woda\s+szt\.\s+\d+[.,]\d+\s+(\d+[.,]\d+)\s+\d+[.,]\d+', "Wzorzec 1: Abonament Woda szt."),
        (r'Abonament\s+(?:za\s+)?wod[ęy]\s+(?:\d+\s+)?(\d+[.,]\d+)\s+\d+[.,]\d+', "Wzorzec 2: Abonament za wodę"),
        (r'Abonament\s+wodny\s+(?:\d+\s+)?(\d+[.,]\d+)\s+\d+[.,]\d+', "Wzorzec 3: Abonament wodny"),
        (r'abonament.*?woda.*?m[iesiącyec]+.*?(\d+[.,]\d+)\s+\d+[.,]\d+', "Wzorzec 4: abonament woda miesiące"),
        (r'abonament.*?wod[ęy].*?(?:za\s+m[iesiącyec]+)?[:\s]+(\d+[.,]\d+)', "Wzorzec 5: fallback"),
    ]
    
    for pattern, description in abonament_water_patterns:
        matches = re.findall(pattern, search_text, re.IGNORECASE)
        if matches:
            print(f"[OK] {description}: {matches}")
            # Pokaż kontekst dopasowania
            match_obj = re.search(pattern, search_text, re.IGNORECASE)
            if match_obj:
                start = max(0, match_obj.start() - 50)
                end = min(len(search_text), match_obj.end() + 50)
                print(f"   Kontekst: ...{search_text[start:end]}...")
        else:
            print(f"[BRAK] {description}: brak dopasowania")
    
    # Szukaj wzorców abonamentu ścieków
    print("\n[SZUKANIE] Wyszukiwanie ABONAMENTU ŚCIEKÓW:")
    print("-" * 80)
    abonament_sewage_patterns = [
        (r'Abonament\s+[ŚS]cieki\s+szt\.\s+\d+[.,]\d+\s+(\d+[.,]\d+)\s+\d+[.,]\d+', "Wzorzec 1: Abonament Ścieki szt."),
        (r'Abonament\s+(?:za\s+)?ścieki\s+(?:\d+\s+)?(\d+[.,]\d+)\s+\d+[.,]\d+', "Wzorzec 2: Abonament za ścieki"),
        (r'abonament.*?ścieki.*?m[iesiącyec]+.*?(\d+[.,]\d+)\s+\d+[.,]\d+', "Wzorzec 3: abonament ścieki miesiące"),
        (r'abonament.*?ścieki.*?(?:za\s+m[iesiącyec]+)?[:\s]+(\d+[.,]\d+)', "Wzorzec 4: fallback"),
    ]
    
    for pattern, description in abonament_sewage_patterns:
        matches = re.findall(pattern, search_text, re.IGNORECASE)
        if matches:
            print(f"[OK] {description}: {matches}")
            # Pokaż kontekst dopasowania
            match_obj = re.search(pattern, search_text, re.IGNORECASE)
            if match_obj:
                start = max(0, match_obj.start() - 50)
                end = min(len(search_text), match_obj.end() + 50)
                print(f"   Kontekst: ...{search_text[start:end]}...")
        else:
            print(f"[BRAK] {description}: brak dopasowania")
    
    # Szukaj wszystkich wystąpień słowa "abonament" w sekcji
    print("\n[SZUKANIE] Wszystkie wystąpienia słowa 'abonament' w sekcji:")
    print("-" * 80)
    abonament_lines = []
    for line in search_text.split('\n'):
        if 'abonament' in line.lower():
            abonament_lines.append(line.strip())
    
    if abonament_lines:
        for i, line in enumerate(abonament_lines, 1):
            print(f"{i}. {line}")
    else:
        print("Brak linii z 'abonament'")
    
    # Parsuj fakturę
    print("\n[WYNIK] Wynik parsowania:")
    print("-" * 80)
    parsed_data = parse_invoice_data(text)
    if parsed_data:
        print(f"  Zuzycie (m3): {parsed_data.get('usage', 'BRAK')}")
        print(f"  Koszt wody za m3: {parsed_data.get('water_cost_m3', 'BRAK')}")
        print(f"  Koszt sciekow za m3: {parsed_data.get('sewage_cost_m3', 'BRAK')}")
        print(f"  Abonament woda (za miesiac): {parsed_data.get('water_subscr_cost', 'BRAK')}")
        print(f"  Abonament scieki (za miesiac): {parsed_data.get('sewage_subscr_cost', 'BRAK')}")
        print(f"  Liczba miesiecy abonamentu: {parsed_data.get('nr_of_subscription', 'BRAK')}")
        print(f"  VAT: {parsed_data.get('vat', 'BRAK')}")
        print(f"  Suma brutto: {parsed_data.get('gross_sum', 'BRAK')}")
    else:
        print("[BLAD] Nie udalo sie sparsowac faktury")
    
    print("\n" + "="*80)

if __name__ == "__main__":
    pdf_path = "invoices_raw/FVSP_FRP_25_10_032668.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"[BLAD] Plik nie istnieje: {pdf_path}")
        sys.exit(1)
    
    debug_invoice(pdf_path)

