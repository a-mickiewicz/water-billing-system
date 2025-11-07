"""
Analiza danych liczbowych z faktur za prąd.
Wyciąga wszystkie wartości liczbowe z tabel i innych miejsc.
"""

import re
from pathlib import Path


def extract_all_numbers(text: str) -> list:
    """Wyciąga wszystkie liczby z tekstu, zachowując kontekst."""
    numbers = []
    
    # Wzorce do znajdowania różnych typów liczb
    patterns = [
        # Kwoty w złotych (np. 1.304,87 zł, 4.765,71)
        (r'(\d{1,3}(?:[.\s]\d{3})*(?:,\d{2})?)\s*z[łl]', 'kwota'),
        # Liczby z przecinkiem (np. 0,3640, 0,80)
        (r'(\d+(?:,\d+)?)', 'liczba'),
        # Daty (np. 31/10/2021, 01/11/2020)
        (r'(\d{1,2}/\d{1,2}/\d{4})', 'data'),
        # Procenty (np. 23%, 5%)
        (r'(\d+)\s*%', 'procent'),
        # kWh (np. 7461 kWh, 1098 kWh)
        (r'(\d{1,4}(?:\s?\d{3})*(?:,\d+)?)\s*kWh', 'kwh'),
        # kW (np. 4,03 kW)
        (r'(\d+(?:,\d+)?)\s*kW', 'kw'),
        # Numery faktur (np. P/23666363/0001/21)
        (r'([A-Z]/\d+/\d+/\d+)', 'numer_faktury'),
        # Numery kont (np. 83 1240 6960 0160 2366 6363 0087)
        (r'(\d{2}\s+\d{4}\s+\d{4}\s+\d{4}\s+\d{4}\s+\d{4}\s+\d{4})', 'numer_konta'),
        # Numery liczników (np. 72832207, 81540583)
        (r'nr\s+(\d{8})', 'numer_licznika'),
        # Kody PPE (np. 590310600012165843)
        (r'PPE:\s*(\d{18})', 'kod_ppe'),
    ]
    
    lines = text.split('\n')
    
    for line_num, line in enumerate(lines, 1):
        # Pomiń puste linie i nagłówki
        if not line.strip() or len(line.strip()) < 3:
            continue
        
        # Szukaj wszystkich wzorców
        for pattern, typ in patterns:
            matches = re.finditer(pattern, line, re.IGNORECASE)
            for match in matches:
                value = match.group(1) if match.lastindex else match.group(0)
                # Zapisz z kontekstem
                context = line.strip()[:100]  # Pierwsze 100 znaków linii
                numbers.append({
                    'wartosc': value,
                    'typ': typ,
                    'linia': line_num,
                    'kontekst': context
                })
    
    return numbers


def extract_structured_data(text: str) -> list:
    """Wyciąga strukturalne dane liczbowe z faktury."""
    data = []
    
    # Numer faktury
    invoice_match = re.search(r'FAKTURA VAT NR\s+([A-Z0-9/]+)', text, re.IGNORECASE)
    if invoice_match:
        data.append(f"Numer faktury: {invoice_match.group(1)}")
    
    # Data sprzedaży
    date_match = re.search(r'Data sprzeda[źz]y:\s*(\d{1,2}/\d{1,2}/\d{4})', text, re.IGNORECASE)
    if date_match:
        data.append(f"Data sprzedazy: {date_match.group(1)}")
    
    # Okres rozliczeniowy
    period_match = re.search(r'Należność za okres od\s+(\d{1,2}/\d{1,2}/\d{4})\s+do\s+(\d{1,2}/\d{1,2}/\d{4})\s+([\d.,]+)', text)
    if period_match:
        data.append(f"Okres od: {period_match.group(1)} do: {period_match.group(2)}")
        data.append(f"Naleznosc za okres: {period_match.group(3)}")
    
    # Wartości finansowe
    financial_patterns = [
        (r'Wartość netto\s+([\d.,]+)', 'Wartosc netto'),
        (r'Kwota VAT\s+([\d.,]+)', 'Kwota VAT'),
        (r'Wartość brutto\s+([\d.,]+)', 'Wartosc brutto'),
        (r'Saldo z rozliczenia:\s+([\d.,-]+)', 'Saldo z rozliczenia'),
        (r'Wynik rozliczenia.*?([\d.,-]+)', 'Wynik rozliczenia'),
        (r'Wartość prognozy z poprzedniej faktury\s+([\d.,]+)', 'Wartosc prognozy'),
        (r'Odsetki\s+([\d.,]+)', 'Odsetki'),
        (r'Nadpłata[:\s]+([\d.,-]+)', 'Nadplata'),
        (r'Niedopłata[:\s]+([\d.,-]+)', 'Niedoplata'),
    ]
    
    for pattern, label in financial_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            data.append(f"{label}: {match.group(1)}")
    
    # Zużycie energii
    usage_patterns = [
        (r'Ogółem zużycie[:\s]+([\d.,]+)\s*kWh', 'Ogolem zuzycie kWh'),
        (r'Zużycie po bilansowaniu[:\s]+([\d.,]+)\s*kWh', 'Zuzycie po bilansowaniu kWh'),
        (r'Od\s+([\d.,-]+)\s*kWh energii elektrycznej czynnej', 'Energia do akcyzy kWh'),
        (r'naliczono akcyzę w kwocie\s+([\d.,-]+)', 'Akcyza'),
    ]
    
    for pattern, label in usage_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            data.append(f"{label}: {match.group(1)}")
    
    # Odczyty liczników
    meter_pattern = r'(\d{1,2}/\d{1,2}/\d{4})\s+(\d{1,3}(?:[.\s]\d{3})*)\s+(\d{1,3}(?:[.\s]\d{3})*)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)'
    meter_matches = re.finditer(meter_pattern, text)
    for match in meter_matches:
        data.append(f"Odczyt licznika: data {match.group(1)}, biezace {match.group(2)}, poprzednie {match.group(3)}, mnozna {match.group(4)}, ilosc {match.group(5)}, straty {match.group(6)}, razem {match.group(7)}")
    
    # Sprzedaż energii - szczegółowe pozycje
    energy_sales = re.finditer(r'(dzienna|nocna)\s+kWh\s+(\d+)\s+([\d.,]+)\s+([\d.,]+)\s+(\d+)', text, re.IGNORECASE)
    for match in energy_sales:
        data.append(f"Energia {match.group(1)}: ilosc {match.group(2)} kWh, cena {match.group(3)}, naleznosc {match.group(4)}, VAT {match.group(5)}%")
    
    # Opłaty dystrybucyjne
    distribution_fees = re.finditer(r'(Opłata\s+[^:]+):.*?(\d+(?:,\d+)?)\s+([\d.,]+)', text, re.IGNORECASE | re.DOTALL)
    for match in distribution_fees:
        fee_name = match.group(1).strip().replace('\n', ' ')
        data.append(f"{fee_name}: ilosc {match.group(2)}, kwota {match.group(3)}")
    
    # Podsumowania
    summary_patterns = [
        (r'Ogółem wartość - sprzedaż energii:\s+([\d.,]+)', 'Ogolem sprzedaz energii'),
        (r'Ogółem wartość - usługa dystrybucji:\s+([\d.,]+)', 'Ogolem usluga dystrybucji'),
        (r'Ogółem wartość:\s+([\d.,]+)', 'Ogolem wartosc'),
    ]
    
    for pattern, label in summary_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            data.append(f"{label}: {match.group(1)}")
    
    # Stawki VAT
    vat_matches = re.finditer(r'Stawka VAT\s+(\d+)\s*%', text, re.IGNORECASE)
    for match in vat_matches:
        data.append(f"Stawka VAT: {match.group(1)}%")
    
    # Moc mikroinstalacji
    power_match = re.search(r'Moc mikroinstalacji kW:\s+([\d.,]+)', text, re.IGNORECASE)
    if power_match:
        data.append(f"Moc mikroinstalacji: {power_match.group(1)} kW")
    
    # Kod PPE
    ppe_match = re.search(r'Kod PPE:\s+(\d+)', text)
    if ppe_match:
        data.append(f"Kod PPE: {ppe_match.group(1)}")
    
    # Grupa taryfowa
    tariff_match = re.search(r'Grupa taryfowa:\s+([A-Z0-9]+)', text)
    if tariff_match:
        data.append(f"Grupa taryfowa: {tariff_match.group(1)}")
    
    # Energia zużyta w roku
    year_usage_match = re.search(r'Energia zużyta w roku\s+(\d{4}):\s+(\d+)\s*kWh', text)
    if year_usage_match:
        data.append(f"Energia zuzyta w roku {year_usage_match.group(1)}: {year_usage_match.group(2)} kWh")
    
    # Bilansowanie energii (fotowoltaika)
    balance_patterns = [
        (r'pobranej z sieci \(kWh\)\s+(\d+)', 'Energia pobrana z sieci'),
        (r'wprowadzonej do sieci bez opustu\(kWh\)\s+(\d+)', 'Energia wprowadzona do sieci'),
        (r'Współczynnik \(opust\)\s+([\d.,]+)', 'Wspolczynnik opust'),
        (r'wynikającej z bilansowania z opustem \(kWh\)\s+(\d+)', 'Energia po bilansowaniu'),
    ]
    
    for pattern, label in balance_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            data.append(f"{label}: {match.group(1)}")
    
    return data


def analyze_invoice_file(input_file: Path, output_file: Path):
    """Analizuje pojedynczy plik faktury i zapisuje dane liczbowe."""
    print(f"Analizowanie: {input_file.name}")
    
    with open(input_file, 'r', encoding='utf-8') as f:
        text = f.read()
    
    # Wyciągnij strukturalne dane
    structured_data = extract_structured_data(text)
    
    # Zapisz do pliku
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"ANALIZA DANYCH LICZBOWYCH - {input_file.name}\n")
        f.write("=" * 80 + "\n\n")
        
        for item in structured_data:
            f.write(f"{item}\n")
    
    print(f"  Zapisano do: {output_file.name}")
    print(f"  Znaleziono {len(structured_data)} pozycji danych")


def main():
    """Główna funkcja - analizuje wszystkie faktury."""
    parsed_dir = Path("invoices_raw/electricity/parsed")
    output_dir = Path("invoices_raw/electricity/analysis")
    output_dir.mkdir(exist_ok=True)
    
    # Znajdź wszystkie pliki tekstowe (bez plików analysis)
    txt_files = sorted([f for f in parsed_dir.glob("*.txt") if 'analysis' not in f.name])
    
    if not txt_files:
        print(f"Nie znaleziono plikow do analizy w: {parsed_dir}")
        return
    
    print(f"Znaleziono {len(txt_files)} faktur do analizy:")
    for txt_file in txt_files:
        print(f"  - {txt_file.name}")
    
    print(f"\nDane liczbowe zostana zapisane w: {output_dir}")
    print("=" * 80)
    
    # Analizuj każdą fakturę
    for txt_file in txt_files:
        output_filename = txt_file.name.replace('.txt', '_numbers.txt')
        output_path = output_dir / output_filename
        analyze_invoice_file(txt_file, output_path)
    
    print("\n" + "=" * 80)
    print("KONIEC ANALIZY")
    print("=" * 80)


if __name__ == "__main__":
    main()

