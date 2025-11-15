"""Znajduje wartości brutto w fakturze gazu"""

from app.services.gas.invoice_reader import extract_text_from_pdf
import re

pdf_path = 'invoices_raw/p_43562821_0001_25.pdf'
text = extract_text_from_pdf(pdf_path)

# Szukaj pełnej linii z paliwem gazowym
fuel_pattern = r'Paliwo\s+gazowe[^\n]+'
fuel_matches = re.findall(fuel_pattern, text, re.IGNORECASE)

print("Linie z paliwem gazowym:")
for i, match in enumerate(fuel_matches[:3], 1):
    # Zamień znaki specjalne na ASCII
    safe_match = match.encode('ascii', 'ignore').decode('ascii')
    print(f"{i}: {safe_match}")

# Sprawdź format - może być: ... netto VAT brutto
# Format może być: "Paliwo gazowe ... 805 m3 11,450 9217 kWh 0,23965 23 2 208,85 [może być brutto]"
# Spróbuj znaleźć wzorzec z wartością brutto
fuel_with_gross = re.search(r'Paliwo\s+gazowe[^\n]*?(\d+)\s+m[^\s]*\s+(\d+[.,]\d+)\s+(\d+)\s+kWh\s+(\d+[.,]\d+)\s+(\d+)\s+([\d\s,]+)(?:\s+([\d\s,]+))?', text, re.IGNORECASE)
if fuel_with_gross:
    print("\nZnalezione wartości:")
    print(f"  Zuzycie m3: {fuel_with_gross.group(1)}")
    print(f"  Wsp. konw: {fuel_with_gross.group(2)}")
    print(f"  Zuzycie kWh: {fuel_with_gross.group(3)}")
    print(f"  Cena netto: {fuel_with_gross.group(4)}")
    print(f"  VAT%: {fuel_with_gross.group(5)}")
    print(f"  Wartosc netto: {fuel_with_gross.group(6)}")
    if fuel_with_gross.group(7):
        print(f"  Wartosc brutto: {fuel_with_gross.group(7)}")
    else:
        print("  Wartosc brutto: BRAK (oblicz z netto + VAT)")

