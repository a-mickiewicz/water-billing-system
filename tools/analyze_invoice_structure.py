"""
Analizuje strukturę faktury PDF, aby zobaczyć jak wyglądają pozycje wody, ścieków i abonamentu.
"""

from app.services.water.invoice_reader import extract_text_from_pdf
import re

def analyze_invoice(pdf_path: str):
    print("=" * 80)
    print(f"ANALIZA STRUKTURY FAKTURY: {pdf_path}")
    print("=" * 80)
    
    text = extract_text_from_pdf(pdf_path)
    
    # Znajdz sekcje z pozycjami
    print("\n1. POZYCJE WODY:")
    print("-" * 80)
    
    # Szukaj wszystkich pozycji wody
    water_pattern = r'Woda\s+m3\s+(\d+[.,]\d+)\s+(\d+[.,]\d+)\s+(\d+[.,]\d+)\s+\d+%?'
    water_matches = re.findall(water_pattern, text, re.IGNORECASE)
    
    if water_matches:
        print(f"Znaleziono {len(water_matches)} pozycji wody:")
        total_usage = 0.0
        total_value = 0.0
        for i, match in enumerate(water_matches, 1):
            usage = float(match[0].replace(',', '.'))
            price = float(match[1].replace(',', '.'))
            value = float(match[2].replace(',', '.'))
            total_usage += usage
            total_value += value
            print(f"  Pozycja {i}: {usage} m3 × {price} zl/m3 = {value} zl")
        print(f"\n  SUMA: {total_usage} m3, wartosc: {total_value} zl")
        print(f"  Srednia wazona cena: {total_value / total_usage:.4f} zl/m3")
    else:
        print("Nie znaleziono pozycji wody w standardowym formacie")
        # Szukaj alternatywnych formatow
        alt_patterns = [
            r'Usługa.*?woda.*?m3.*?(\d+[.,]\d+).*?(\d+[.,]\d+).*?(\d+[.,]\d+)',
            r'woda.*?(\d+[.,]\d+).*?(\d+[.,]\d+).*?(\d+[.,]\d+)',
        ]
        for pattern in alt_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                print(f"Znaleziono w alternatywnym formacie: {matches}")
                break
    
    print("\n2. POZYCJE SCIEKOW:")
    print("-" * 80)
    
    sewage_pattern = r'Ścieki\s+m3\s+(\d+[.,]\d+)\s+(\d+[.,]\d+)\s+(\d+[.,]\d+)\s+\d+%?'
    sewage_matches = re.findall(sewage_pattern, text, re.IGNORECASE)
    
    if sewage_matches:
        print(f"Znaleziono {len(sewage_matches)} pozycji sciekow:")
        total_usage = 0.0
        total_value = 0.0
        for i, match in enumerate(sewage_matches, 1):
            usage = float(match[0].replace(',', '.'))
            price = float(match[1].replace(',', '.'))
            value = float(match[2].replace(',', '.'))
            total_usage += usage
            total_value += value
            print(f"  Pozycja {i}: {usage} m3 × {price} zl/m3 = {value} zl")
        print(f"\n  SUMA: {total_usage} m3, wartosc: {total_value} zl")
        print(f"  Srednia wazona cena: {total_value / total_usage:.4f} zl/m3")
    else:
        print("Nie znaleziono pozycji sciekow w standardowym formacie")
    
    print("\n3. ABONAMENT:")
    print("-" * 80)
    
    # Szukaj abonamentu w roznych formatach
    abonament_patterns = [
        (r'Abonament\s+Woda\s+szt\.\s+(\d+[.,]\d+)\s+(\d+[.,]\d+)\s+(\d+[.,]\d+)', "Abonament Woda szt."),
        (r'Abonament\s+(?:za\s+)?wod[ęy]\s+(\d+)\s+(\d+[.,]\d+)\s+(\d+[.,]\d+)', "Abonament za wodę"),
        (r'wod[ęy].*?[x×]\s*(\d+)[,\s]+(\d+[.,]\d+)', "woda x ilość, cena"),
        (r'wod[ęy].*?(\d+)[,\s]+(\d+[.,]\d+)', "woda ilość, cena"),
    ]
    
    found_water_abonament = False
    for pattern, desc in abonament_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            print(f"Znaleziono abonament wody (format: {desc}):")
            for match in matches:
                if len(match) == 3:
                    qty, price, value = match
                    print(f"  Ilość: {qty}, Cena: {price}, Wartość: {value}")
                elif len(match) == 2:
                    qty, price = match
                    qty_val = int(qty)
                    price_val = float(price.replace(',', '.'))
                    print(f"  Ilość: {qty_val}, Cena: {price_val} zl, Wartość: {qty_val * price_val:.2f} zl")
            found_water_abonament = True
            break
    
    if not found_water_abonament:
        print("Nie znaleziono abonamentu wody")
    
    # Szukaj abonamentu sciekow
    abonament_sewage_patterns = [
        (r'Abonament\s+[ŚS]cieki\s+szt\.\s+(\d+[.,]\d+)\s+(\d+[.,]\d+)\s+(\d+[.,]\d+)', "Abonament Ścieki szt."),
        (r'Abonament\s+(?:za\s+)?ścieki\s+(\d+)\s+(\d+[.,]\d+)\s+(\d+[.,]\d+)', "Abonament za ścieki"),
        (r'ścieki.*?[x×]\s*(\d+)[,\s]+(\d+[.,]\d+)', "ścieki x ilość, cena"),
        (r'ścieki.*?(\d+)[,\s]+(\d+[.,]\d+)', "ścieki ilość, cena"),
    ]
    
    found_sewage_abonament = False
    for pattern, desc in abonament_sewage_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            print(f"\nZnaleziono abonament sciekow (format: {desc}):")
            for match in matches:
                if len(match) == 3:
                    qty, price, value = match
                    print(f"  Ilość: {qty}, Cena: {price}, Wartość: {value}")
                elif len(match) == 2:
                    qty, price = match
                    qty_val = int(qty)
                    price_val = float(price.replace(',', '.'))
                    print(f"  Ilość: {qty_val}, Cena: {price_val} zl, Wartość: {qty_val * price_val:.2f} zl")
            found_sewage_abonament = True
            break
    
    if not found_sewage_abonament:
        print("\nNie znaleziono abonamentu sciekow")
    
    # Wyswietl fragment tekstu z pozycjami
    print("\n4. FRAGMENT TEKSTU Z POZYCJAMI:")
    print("-" * 80)
    
    # Znajdz sekcje z pozycjami
    items_section = re.search(r'(?:Pozycje|Pozycja|Usługa|Woda|Ścieki).*?(?:Wartość\s+Netto|Razem|Suma|VAT)', text, re.IGNORECASE | re.DOTALL)
    if items_section:
        section_text = items_section.group(0)
        # Wyswietl pierwsze 2000 znakow
        print(section_text[:2000])
    else:
        print("Nie znaleziono sekcji z pozycjami")
        # Wyswietl fragment tekstu zawierajacy "woda" lub "ścieki"
        water_section = re.search(r'.{0,500}woda.{0,500}', text, re.IGNORECASE | re.DOTALL)
        if water_section:
            print(water_section.group(0)[:1000])

if __name__ == "__main__":
    import sys
    pdf_path = sys.argv[1] if len(sys.argv) > 1 else "invoices_raw/FVSP_FRP_25_02_022549.pdf"
    analyze_invoice(pdf_path)

