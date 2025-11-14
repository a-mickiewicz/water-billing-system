"""Test parsowania faktury"""
from app.services.water.invoice_reader import parse_invoice_data, extract_text_from_pdf
import re

text = extract_text_from_pdf('invoices_raw/FVSP_FRP_25_02_022549.pdf')

# Sprawdz co znajduje parser krok po kroku
print("1. Sprawdzanie pozycji wody:")
items_section = re.search(r'(?:Pozycje|Pozycja|Usługa).*?(?:Wartość\s+Netto|Razem|Suma|VAT)', text, re.IGNORECASE | re.DOTALL)
search_text = items_section.group(0) if items_section else text[:3000]
water_matches = re.findall(r'Woda\s+m3\s+(\d+[.,]\d+)\s+(\d+[.,]\d+)\s+(\d+[.,]\d+)\s+\d+%?', search_text, re.IGNORECASE)
print(f"  Znaleziono {len(water_matches)} pozycji wody")

print("\n2. Parsowanie faktury:")
data = parse_invoice_data(text)

if data:
    print("Znalezione pola:")
    for key, value in data.items():
        print(f"  {key}: {value}")
    
    required = ['invoice_number', 'usage', 'water_cost_m3', 'sewage_cost_m3', 
                'nr_of_subscription', 'water_subscr_cost', 'sewage_subscr_cost', 
                'vat', 'period_start', 'period_stop', 'gross_sum']
    
    print("\nBrakujace pola:")
    missing = [f for f in required if f not in data]
    print(missing if missing else "Wszystkie pola sa obecne")
else:
    print("Parser zwrocil None - nie znaleziono wszystkich wymaganych pol")
    print("\nSprawdzam co zostalo znalezione przed sprawdzeniem wymaganych pol:")
    # Wykonaj parsowanie krok po kroku
    from app.services.water.invoice_reader import parse_invoice_data
    import sys
    # Tymczasowo zmien funkcję, aby zwracała dane nawet jeśli brakuje pól
    # (to tylko do debugowania)

