"""
Skrypt testowy do weryfikacji odczytu faktur PDF.
Wyświetla szczegółowe informacje o tym, co udało się wyciągnąć z faktury.
"""

import sys
import re
from pathlib import Path
from invoice_reader import extract_text_from_pdf, parse_invoice_data


def print_section(title: str, width: int = 80):
    """Drukuje sekcję z nagłówkiem."""
    print("\n" + "=" * width)
    print(f" {title}")
    print("=" * width)


def test_regex_pattern(pattern: str, text: str, field_name: str) -> dict:
    """Testuje wzorzec regex i zwraca szczegóły."""
    # Dla wzorców z wieloma liniami używamy również re.DOTALL
    if '[\n\r]' in pattern or '\\n' in pattern:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    else:
        match = re.search(pattern, text, re.IGNORECASE)
    result = {
        'found': match is not None,
        'value': match.group(0) if match else None,
        'full_match': match.group(0) if match else None,
        'groups': match.groups() if match else None,
        'position': (match.start(), match.end()) if match else None
    }
    return result


def analyze_invoice(pdf_path: str):
    """
    Analizuje fakturę PDF i wyświetla szczegółowe informacje.
    
    Args:
        pdf_path: Ścieżka do pliku PDF z fakturą
    """
    pdf_path = Path(pdf_path)
    
    if not pdf_path.exists():
        print(f"❌ BŁĄD: Plik nie istnieje: {pdf_path}")
        return
    
    print_section(f"ANALIZA FAKTURY: {pdf_path.name}")
    
    # 1. Wyciągnij tekst z PDF
    print("\n📄 Wczytywanie tekstu z PDF...")
    text = extract_text_from_pdf(str(pdf_path))
    
    if not text:
        print("❌ Nie udało się wczytać tekstu z PDF")
        return
    
    print(f"✅ Wczytano {len(text)} znaków tekstu")
    
    # 2. Wyświetl surowy tekst (pierwsze 2000 znaków)
    print_section("SUROWY TEKST Z PDF (pierwsze 2000 znaków)")
    print(text[:2000])
    if len(text) > 2000:
        print(f"\n... (pozostało {len(text) - 2000} znaków)")
    
    # 3. Testuj wszystkie wzorce regex
    print_section("TESTOWANIE WZORCÓW REGEX")
    
    patterns = {
        'Numer faktury (bezpośredni)': r'(?:FRP|RP|R)/?\d{2}/\d{2}/\d{6}',
        'Pozycje wody (nowy format)': r'Woda\s+m3\s+(\d+[.,]\d+)\s+(\d+[.,]\d+)\s+(\d+[.,]\d+)\s+\d+%?',
        'Pozycje ścieków (nowy format)': r'Ścieki\s+m3\s+(\d+[.,]\d+)\s+(\d+[.,]\d+)\s+(\d+[.,]\d+)\s+\d+%?',
        'VAT (tabela z nagłówkiem)': r'Wartość\s+Netto\s+Stawka\s+VAT.*?[\n\r]+.*?(\d+[.,]\d+)\s+(\d+)%\s+\d+[.,]\d+\s+\d+[.,]\d+',
        'VAT (format tabeli)': r'\d+[.,]\d+\s+(\d+)%\s+\d+[.,]\d+\s+\d+[.,]\d+',
        'Okres rozliczeniowy (od-do)': r'(?:od|from)[\s:]+(\d{1,2})[./-](\d{1,2})[./-](\d{4})\s+(?:do|to)[\s:]+(\d{1,2})[./-](\d{1,2})[./-](\d{4})',
        'Rozliczenie za okres od': r'Rozliczenie\s+za\s+okres\s+od\s+(\d{1,2})[./-](\d{1,2})[./-](\d{4})',
        'Abonament woda': r'abonament.*?woda.*?(\d+[.,]\d+)',
        'Abonament ścieki': r'abonament.*?ścieki.*?(\d+[.,]\d+)',
        'Wartość brutto (tabela z nagłówkiem)': r'Wartość\s+Netto\s+Stawka\s+VAT.*?[\n\r]+.*?(\d+[.,]\d+)\s+\d+%\s+\d+[.,]\d+\s+(\d+[.,]\d+)',
        'Należność bieżąca': r'Należność\s+bieżąca\s*\(zł\)[:\s]+(\d+[.,]\d+)',
        'Wartość brutto (format tabeli)': r'\d+[.,]\d+\s+\d+%\s+\d+[.,]\d+\s+(\d+[.,]\d+)',
        'Suma brutto (stary format)': r'(?:suma|total|razem)\s*(?:brutto|gross)[\s:]+(\d+[.,]\d+)',
    }
    
    regex_results = {}
    for name, pattern in patterns.items():
        result = test_regex_pattern(pattern, text, name)
        regex_results[name] = result
        
        status = "✅" if result['found'] else "❌"
        print(f"\n{status} {name}:")
        print(f"   Wzorzec: {pattern}")
        if result['found']:
            print(f"   Znaleziono: {result['full_match']}")
            if result['groups']:
                print(f"   Grupy: {result['groups']}")
            if result['position']:
                start, end = result['position']
                print(f"   Pozycja: {start}-{end}")
                # Pokaż kontekst (50 znaków przed i po)
                context_start = max(0, start - 50)
                context_end = min(len(text), end + 50)
                context = text[context_start:context_end]
                print(f"   Kontekst: ...{context}...")
        else:
            print(f"   Nie znaleziono")
    
    # 4. Szczegółowa analiza pozycji wody i ścieków
    print_section("ANALIZA POZYCJI WODY I ŚCIEKÓW")
    
    water_pattern = r'Woda\s+m3\s+(\d+[.,]\d+)\s+(\d+[.,]\d+)\s+(\d+[.,]\d+)\s+\d+%?'
    water_matches = re.findall(water_pattern, text, re.IGNORECASE)
    
    if water_matches:
        print(f"\n✅ Znaleziono {len(water_matches)} pozycji wody:")
        total_usage = 0.0
        total_value = 0.0
        for i, match in enumerate(water_matches, 1):
            usage = float(match[0].replace(',', '.'))
            price = float(match[1].replace(',', '.'))
            value = float(match[2].replace(',', '.'))
            total_usage += usage
            total_value += value
            print(f"   Pozycja {i}:")
            print(f"     Zużycie: {usage} m³")
            print(f"     Cena za m³: {price} zł")
            print(f"     Wartość netto: {value} zł")
        print(f"\n   📊 SUMA:")
        print(f"     Całkowite zużycie: {total_usage} m³")
        print(f"     Całkowita wartość: {total_value} zł")
        if total_usage > 0:
            avg_price = total_value / total_usage
            print(f"     Średnia ważona cena: {avg_price:.2f} zł/m³")
    else:
        print("\n❌ Nie znaleziono pozycji wody w formacie 'Woda m3 ...'")
    
    sewage_pattern = r'Ścieki\s+m3\s+(\d+[.,]\d+)\s+(\d+[.,]\d+)\s+(\d+[.,]\d+)\s+\d+%?'
    sewage_matches = re.findall(sewage_pattern, text, re.IGNORECASE)
    
    if sewage_matches:
        print(f"\n✅ Znaleziono {len(sewage_matches)} pozycji ścieków:")
        total_sewage_usage = 0.0
        total_sewage_value = 0.0
        for i, match in enumerate(sewage_matches, 1):
            usage = float(match[0].replace(',', '.'))
            price = float(match[1].replace(',', '.'))
            value = float(match[2].replace(',', '.'))
            total_sewage_usage += usage
            total_sewage_value += value
            print(f"   Pozycja {i}:")
            print(f"     Zużycie: {usage} m³")
            print(f"     Cena za m³: {price} zł")
            print(f"     Wartość netto: {value} zł")
        print(f"\n   📊 SUMA:")
        print(f"     Całkowite zużycie: {total_sewage_usage} m³")
        print(f"     Całkowita wartość: {total_sewage_value} zł")
        if total_sewage_usage > 0:
            avg_sewage_price = total_sewage_value / total_sewage_usage
            print(f"     Średnia ważona cena: {avg_sewage_price:.2f} zł/m³")
    else:
        print("\n❌ Nie znaleziono pozycji ścieków w formacie 'Ścieki m3 ...'")
    
    # 5. Parsuj dane używając funkcji parse_invoice_data
    print_section("WYNIK PARSOWANIA (parse_invoice_data)")
    
    parsed_data = parse_invoice_data(text)
    
    if parsed_data:
        print("✅ Udało się sparsować dane faktury:\n")
        for key, value in parsed_data.items():
            print(f"  {key}: {value}")
    else:
        print("❌ Nie udało się sparsować danych faktury")
    
    # 6. Sprawdź wymagane pola
    print_section("WERYFIKACJA WYMAGANYCH PÓL")
    
    required_fields = [
        'invoice_number', 'usage', 'water_cost_m3', 'sewage_cost_m3',
        'nr_of_subscription', 'water_subscr_cost', 'sewage_subscr_cost',
        'vat', 'period_start', 'period_stop', 'gross_sum'
    ]
    
    if parsed_data:
        missing_fields = []
        for field in required_fields:
            if field in parsed_data:
                value = parsed_data[field]
                status = "✅" if value else "⚠️"
                print(f"{status} {field}: {value}")
            else:
                missing_fields.append(field)
                print(f"❌ {field}: BRAK")
        
        if missing_fields:
            print(f"\n⚠️ Brakuje {len(missing_fields)} wymaganych pól: {', '.join(missing_fields)}")
        else:
            print("\n✅ Wszystkie wymagane pola są obecne!")
    else:
        print("❌ Brak danych do weryfikacji")
    
    # 7. Wyświetl pełny tekst (na żądanie)
    print_section("INFORMACJE O TEKŚCIE")
    print(f"Całkowita długość tekstu: {len(text)} znaków")
    print(f"Liczba linii: {len(text.split(chr(10)))}")
    print(f"Liczba słów: {len(text.split())}")
    
    # Znajdź wszystkie wystąpienia numerów faktur w tekście
    invoice_numbers = re.findall(r'(?:FRP|RP|R)/?\d{2}/\d{2}/\d{6}', text, re.IGNORECASE)
    if invoice_numbers:
        print(f"\n📋 Znalezione numery faktur w tekście ({len(invoice_numbers)}):")
        for i, inv_num in enumerate(set(invoice_numbers), 1):
            print(f"   {i}. {inv_num}")
    
    print("\n" + "=" * 80)


def main():
    """Główna funkcja - pozwala na testowanie faktur."""
    if len(sys.argv) > 1:
        # Podano ścieżkę jako argument
        pdf_path = sys.argv[1]
    else:
        # Interaktywny wybór
        print("🧪 Testowy odczyt faktur PDF\n")
        print("Dostępne opcje:")
        print("1. Wprowadź ścieżkę do pliku PDF")
        print("2. Wprowadź nazwę pliku z folderu invoices_raw/")
        print("3. Naciśnij Enter, aby użyć domyślnego pliku (invoice_2023_12.pdf)\n")
        
        user_input = input("Wprowadź ścieżkę/nazwę lub naciśnij Enter: ").strip()
        
        if not user_input:
            pdf_path = "invoices_raw/invoice_2023_12.pdf"
        elif Path(user_input).exists():
            pdf_path = user_input
        elif Path(f"invoices_raw/{user_input}").exists():
            pdf_path = f"invoices_raw/{user_input}"
        else:
            print(f"❌ Nie znaleziono pliku: {user_input}")
            return
    
    analyze_invoice(pdf_path)


if __name__ == "__main__":
    main()

