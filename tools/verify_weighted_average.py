"""Weryfikuje obliczenie średniej ważonej ceny wody"""

from app.services.water.invoice_reader import extract_text_from_pdf, parse_invoice_data
import re

# Wczytaj fakturę
text = extract_text_from_pdf('invoices_raw/FVSP_FRP_24_02_008566.pdf')
data = parse_invoice_data(text)

# Znajdź pozycje wody
water_pattern = r'Woda\s+m3\s+(\d+[.,]\d+)\s+(\d+[.,]\d+)\s+(\d+[.,]\d+)'
water_matches = re.findall(water_pattern, text, re.IGNORECASE)

# Usuń duplikaty
unique_items = {}
for match in water_matches:
    usage = float(match[0].replace(',', '.'))
    price = float(match[1].replace(',', '.'))
    value = float(match[2].replace(',', '.'))
    key = (usage, price, value)
    if key not in unique_items:
        unique_items[key] = (usage, price, value)

print("=" * 80)
print("WERYFIKACJA OBLICZENIA SRODNIEJ WAZONEJ")
print("=" * 80)

print("\n1. POZYCJE Z FAKTURY:")
total_usage = 0.0
total_value = 0.0
for i, (usage, price, value) in enumerate(unique_items.values(), 1):
    calculated_value = usage * price
    print(f"   Pozycja {i}: {usage} m3 × {price} zl = {value} zl")
    print(f"      Obliczone: {usage} × {price} = {calculated_value:.10f} zl")
    print(f"      Roznica: {abs(value - calculated_value):.10f} zl")
    total_usage += usage
    total_value += value

print(f"\n2. SUMA:")
print(f"   Zuzycie: {total_usage} m3")
print(f"   Wartosc: {total_value} zl")

print(f"\n3. SRODNIA WAZONA:")
avg_price = total_value / total_usage if total_usage > 0 else 0.0
print(f"   {total_value} / {total_usage} = {avg_price:.10f} zl/m3")

print(f"\n4. WERYFIKACJA:")
verification = total_usage * avg_price
print(f"   {total_usage} × {avg_price:.10f} = {verification:.10f} zl")
print(f"   Oczekiwana suma: {total_value} zl")
print(f"   Roznica: {abs(verification - total_value):.10f} zl")

print(f"\n5. W PARSERZE:")
print(f"   Zuzycie: {data.get('usage')} m3")
print(f"   Cena: {data.get('water_cost_m3'):.10f} zl/m3")
parser_verification = data.get('usage') * data.get('water_cost_m3')
print(f"   Weryfikacja: {data.get('usage')} × {data.get('water_cost_m3'):.10f} = {parser_verification:.10f} zl")
print(f"   Roznica z suma z faktury: {abs(parser_verification - total_value):.10f} zl")

print(f"\n6. POROWNANIE METOD:")
print(f"   Metoda 1 (z wartosci z faktury): {total_value} zl")
print(f"   Metoda 2 (usage × price):")
method2_total = sum(usage * price for usage, price, value in unique_items.values())
method2_str = " + ".join([f"{u}×{p}" for u, p, v in unique_items.values()])
print(f"      {method2_str} = {method2_total:.10f} zl")
print(f"   Roznica metod: {abs(total_value - method2_total):.10f} zl")

