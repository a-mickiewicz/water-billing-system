"""Szczegółowa analiza parsowania faktury FRP/24/02/008566"""

from app.services.water.invoice_reader import extract_text_from_pdf, parse_invoice_data
import re

pdf_path = 'invoices_raw/FVSP_FRP_24_02_008566.pdf'
text = extract_text_from_pdf(pdf_path)
data = parse_invoice_data(text)

print("=" * 80)
print("ANALIZA PARSOWANIA FAKTURY FRP/24/02/008566")
print("=" * 80)

print("\n1. WYNIKI PARSOWANIA:")
print(f"   Zuzycie: {data.get('usage')} m3")
print(f"   Cena wody: {data.get('water_cost_m3')} zl/m3")
print(f"   Cena sciekow: {data.get('sewage_cost_m3')} zl/m3")
print(f"   Suma brutto: {data.get('gross_sum')} zl")

# Sprawdz pozycje wody w PDF
print("\n2. POZYCJE WODY W PDF:")
water_pattern = r'Woda\s+m3\s+(\d+[.,]\d+)\s+(\d+[.,]\d+)\s+(\d+[.,]\d+)'
water_matches = re.findall(water_pattern, text, re.IGNORECASE)

if water_matches:
    print(f"   Znaleziono {len(water_matches)} pozycji:")
    unique_items = {}
    for i, match in enumerate(water_matches, 1):
        usage = float(match[0].replace(',', '.'))
        price = float(match[1].replace(',', '.'))
        value = float(match[2].replace(',', '.'))
        key = (usage, price, value)
        if key not in unique_items:
            unique_items[key] = (usage, price, value)
            print(f"   Pozycja {i}: {usage} m3 × {price} zl = {value} zl")
    
    print(f"\n   Unikalne pozycje: {len(unique_items)}")
    total_usage = sum(u[0] for u in unique_items.values())
    total_value = sum(u[2] for u in unique_items.values())
    avg_price = total_value / total_usage if total_usage > 0 else 0
    print(f"   Suma zuzycia: {total_usage} m3")
    print(f"   Suma wartosci: {total_value} zl")
    print(f"   Srednia wazona cena: {avg_price:.4f} zl/m3")
    print(f"   W parserze: {data.get('usage')} m3, {data.get('water_cost_m3'):.4f} zl/m3")

# Sprawdz pozycje sciekow
print("\n3. POZYCJE SCIEKOW W PDF:")
sewage_pattern = r'[ŚS]cieki\s+m3\s+(\d+[.,]\d+)\s+(\d+[.,]\d+)\s+(\d+[.,]\d+)'
sewage_matches = re.findall(sewage_pattern, text, re.IGNORECASE)

if sewage_matches:
    print(f"   Znaleziono {len(sewage_matches)} pozycji:")
    unique_items = {}
    for i, match in enumerate(sewage_matches, 1):
        usage = float(match[0].replace(',', '.'))
        price = float(match[1].replace(',', '.'))
        value = float(match[2].replace(',', '.'))
        key = (usage, price, value)
        if key not in unique_items:
            unique_items[key] = (usage, price, value)
            print(f"   Pozycja {i}: {usage} m3 × {price} zl = {value} zl")
    
    print(f"\n   Unikalne pozycje: {len(unique_items)}")
    total_usage = sum(u[0] for u in unique_items.values())
    total_value = sum(u[2] for u in unique_items.values())
    avg_price = total_value / total_usage if total_usage > 0 else 0
    print(f"   Suma zuzycia: {total_usage} m3")
    print(f"   Suma wartosci: {total_value} zl")
    print(f"   Srednia wazona cena: {avg_price:.4f} zl/m3")
    print(f"   W parserze: {data.get('usage')} m3, {data.get('sewage_cost_m3'):.4f} zl/m3")

