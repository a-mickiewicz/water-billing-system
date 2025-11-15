"""Sprawdza szczegolowe wartosci brutto w fakturach gazu"""

from app.services.gas.invoice_reader import extract_text_from_pdf, parse_invoice_data
from app.core.database import SessionLocal, init_db
from app.models.gas import GasInvoice
import re

init_db()
db = SessionLocal()

print("=" * 80)
print("SPRAWDZENIE SZCZEGOLOWYCH WARTOSCI BRUTTO W FAKTURACH")
print("=" * 80)

# Test na przykładowej fakturze
pdf_path = 'invoices_raw/p_43562821_0001_25.pdf'
text = extract_text_from_pdf(pdf_path)
data = parse_invoice_data(text)

print("\n1. WARTOSCI Z PARSERA:")
print(f"   fuel_value_net: {data.get('fuel_value_net', 'BRAK')}")
print(f"   fuel_value_gross: {data.get('fuel_value_gross', 'BRAK')}")
print(f"   subscription_value_net: {data.get('subscription_value_net', 'BRAK')}")
print(f"   subscription_value_gross: {data.get('subscription_value_gross', 'BRAK')}")
print(f"   distribution_fixed_value_net: {data.get('distribution_fixed_value_net', 'BRAK')}")
print(f"   distribution_fixed_value_gross: {data.get('distribution_fixed_value_gross', 'BRAK')}")
print(f"   distribution_variable_value_net: {data.get('distribution_variable_value_net', 'BRAK')}")
print(f"   distribution_variable_value_gross: {data.get('distribution_variable_value_gross', 'BRAK')}")

# Sprawdz czy w tekście są wartości brutto
print("\n2. SZUKANIE WARTOSCI BRUTTO W TEKSCIE PDF:")
print("   Szukam wzorców dla wartości brutto...")

# Format faktury - sprawdz czy są wartości brutto dla poszczególnych pozycji
# W fakturach PGNiG wartości brutto są zwykle w podsumowaniu, nie dla każdej pozycji osobno

# Sprawdz czy w fakturze są wartości brutto dla paliwa
fuel_gross_pattern = r'Paliwo\s+gazowe[^\n]*?(\d+[.,]\d+)\s+(\d+[.,]\d+)\s+(\d+[.,]\d+)\s+(\d+[.,]\d+)'
fuel_gross_match = re.search(fuel_gross_pattern, text, re.IGNORECASE)
if fuel_gross_match:
    print(f"   Znaleziono wzorzec dla paliwa: {fuel_gross_match.groups()}")
else:
    print("   Nie znaleziono wartości brutto dla paliwa w tekście")

# Sprawdz faktury w bazie
print("\n3. WARTOSCI W BAZIE DANYCH:")
invoice = db.query(GasInvoice).filter(GasInvoice.invoice_number == 'P/43562821/0001/25').first()
if invoice:
    print(f"   fuel_value_gross: {invoice.fuel_value_gross}")
    print(f"   subscription_value_gross: {invoice.subscription_value_gross}")
    print(f"   distribution_fixed_value_gross: {invoice.distribution_fixed_value_gross}")
    print(f"   distribution_variable_value_gross: {invoice.distribution_variable_value_gross}")
    print(f"   total_gross_sum: {invoice.total_gross_sum}")
    
    # Oblicz sumę szczegółowych wartości brutto
    sum_details = (invoice.fuel_value_gross + invoice.subscription_value_gross + 
                  invoice.distribution_fixed_value_gross + invoice.distribution_variable_value_gross)
    print(f"\n   Suma szczegolowych wartosci brutto: {sum_details:.2f} zl")
    print(f"   Suma brutto faktury: {invoice.total_gross_sum:.2f} zl")
    print(f"   Roznica: {abs(sum_details - invoice.total_gross_sum):.2f} zl")

db.close()

