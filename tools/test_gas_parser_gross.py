"""Testuje parser wartości brutto w fakturach gazu"""

from app.services.gas.invoice_reader import extract_text_from_pdf, parse_invoice_data

pdf_path = 'invoices_raw/p_43562821_0001_25.pdf'
text = extract_text_from_pdf(pdf_path)
data = parse_invoice_data(text)

print("=" * 80)
print("TEST PARSERA WARTOSCI BRUTTO")
print("=" * 80)

print("\nWartosci brutto z parsera:")
print(f"  fuel_value_gross: {data.get('fuel_value_gross', 0)}")
print(f"  subscription_value_gross: {data.get('subscription_value_gross', 0)}")
print(f"  distribution_fixed_value_gross: {data.get('distribution_fixed_value_gross', 0)}")
print(f"  distribution_variable_value_gross: {data.get('distribution_variable_value_gross', 0)}")

print("\nWartosci netto:")
print(f"  fuel_value_net: {data.get('fuel_value_net', 0)}")
print(f"  subscription_value_net: {data.get('subscription_value_net', 0)}")
print(f"  distribution_fixed_value_net: {data.get('distribution_fixed_value_net', 0)}")
print(f"  distribution_variable_value_net: {data.get('distribution_variable_value_net', 0)}")

print("\nVAT rate:")
print(f"  vat_rate: {data.get('vat_rate', 0)}")

print("\nWeryfikacja obliczen:")
fuel_net = data.get('fuel_value_net', 0)
fuel_gross = data.get('fuel_value_gross', 0)
if fuel_net > 0:
    calculated_gross = round(fuel_net * (1 + data.get('vat_rate', 0.23)), 2)
    print(f"  Paliwo: netto {fuel_net} * 1.23 = {calculated_gross}, parser: {fuel_gross}, roznica: {abs(calculated_gross - fuel_gross)}")

subscr_net = data.get('subscription_value_net', 0)
subscr_gross = data.get('subscription_value_gross', 0)
if subscr_net > 0:
    calculated_gross = round(subscr_net * (1 + data.get('vat_rate', 0.23)), 2)
    print(f"  Abonament: netto {subscr_net} * 1.23 = {calculated_gross}, parser: {subscr_gross}, roznica: {abs(calculated_gross - subscr_gross)}")

dist_fixed_net = data.get('distribution_fixed_value_net', 0)
dist_fixed_gross = data.get('distribution_fixed_value_gross', 0)
if dist_fixed_net > 0:
    calculated_gross = round(dist_fixed_net * (1 + data.get('vat_rate', 0.23)), 2)
    print(f"  Dystrybucja stala: netto {dist_fixed_net} * 1.23 = {calculated_gross}, parser: {dist_fixed_gross}, roznica: {abs(calculated_gross - dist_fixed_gross)}")

dist_var_net = data.get('distribution_variable_value_net', 0)
dist_var_gross = data.get('distribution_variable_value_gross', 0)
if dist_var_net > 0:
    calculated_gross = round(dist_var_net * (1 + data.get('vat_rate', 0.23)), 2)
    print(f"  Dystrybucja zmienna: netto {dist_var_net} * 1.23 = {calculated_gross}, parser: {dist_var_gross}, roznica: {abs(calculated_gross - dist_var_gross)}")

