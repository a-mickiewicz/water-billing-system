"""Analizuje format faktury gazu, aby znaleźć wartości brutto"""

from app.services.gas.invoice_reader import extract_text_from_pdf
import re

pdf_path = 'invoices_raw/p_43562821_0001_25.pdf'
text = extract_text_from_pdf(pdf_path)

print("=" * 80)
print("ANALIZA FORMATU FAKTURY GAZU")
print("=" * 80)

# Szukaj sekcji z paliwem gazowym
print("\n1. SEKCJA PALIWA GAZOWEGO:")
fuel_section = re.search(r'Paliwo\s+gazowe.*?(?=\n\n|\n[A-Z]|$)', text, re.IGNORECASE | re.DOTALL)
if fuel_section:
    print(fuel_section.group(0)[:500])

# Szukaj sekcji z abonamentem
print("\n2. SEKCJA ABONAMENTU:")
subscription_section = re.search(r'Opłata\s+abonamentowa.*?(?=\n\n|\n[A-Z]|$)', text, re.IGNORECASE | re.DOTALL)
if subscription_section:
    print(subscription_section.group(0)[:500])

# Szukaj sekcji z dystrybucją stałą
print("\n3. SEKCJA DYSTRYBUCJI STAŁEJ:")
dist_fixed_section = re.search(r'Dystrybucyjna\s+stała.*?(?=\n\n|\n[A-Z]|$)', text, re.IGNORECASE | re.DOTALL)
if dist_fixed_section:
    print(dist_fixed_section.group(0)[:500])

# Szukaj sekcji z dystrybucją zmienną
print("\n4. SEKCJA DYSTRYBUCJI ZMIENNEJ:")
dist_var_section = re.search(r'Dystrybucyjna\s+zmienna.*?(?=\n\n|\n[A-Z]|$)', text, re.IGNORECASE | re.DOTALL)
if dist_var_section:
    print(dist_var_section.group(0)[:1000])

# Szukaj tabeli z wartościami netto i brutto
print("\n5. TABELA Z WARTOŚCIAMI:")
# Szukaj linii z "netto" i "brutto"
table_lines = [line for line in text.split('\n') if 'netto' in line.lower() or 'brutto' in line.lower() or 'vat' in line.lower()]
for i, line in enumerate(table_lines[:20]):
    print(f"{i}: {line}")

# Sprawdź format paliwa gazowego - może mieć wartości brutto
print("\n6. SZUKANIE WARTOŚCI BRUTTO W LINIACH Z PALIWEM:")
fuel_lines = [line for line in text.split('\n') if 'paliwo' in line.lower() and ('brutto' in line.lower() or any(c.isdigit() for c in line))]
for line in fuel_lines[:10]:
    print(line)

