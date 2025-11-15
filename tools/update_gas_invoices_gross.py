"""Aktualizuje wartości brutto w istniejących fakturach gazu"""

from app.core.database import SessionLocal, init_db
from app.models.gas import GasInvoice

init_db()
db = SessionLocal()

print("=" * 80)
print("AKTUALIZACJA WARTOSCI BRUTTO W FAKTURACH GAZU")
print("=" * 80)

invoices = db.query(GasInvoice).all()
print(f"\nZnaleziono {len(invoices)} faktur")

updated_count = 0
for invoice in invoices:
    # Sprawdź czy wartości brutto są 0
    if (invoice.fuel_value_gross == 0.0 and invoice.fuel_value_net > 0) or \
       (invoice.subscription_value_gross == 0.0 and invoice.subscription_value_net > 0) or \
       (invoice.distribution_fixed_value_gross == 0.0 and invoice.distribution_fixed_value_net > 0) or \
       (invoice.distribution_variable_value_gross == 0.0 and invoice.distribution_variable_value_net > 0):
        
        print(f"\nAktualizacja faktury {invoice.invoice_number} ({invoice.data}):")
        
        # Oblicz wartości brutto z netto + VAT
        vat_rate = invoice.vat_rate
        
        if invoice.fuel_value_gross == 0.0 and invoice.fuel_value_net > 0:
            invoice.fuel_value_gross = round(invoice.fuel_value_net * (1 + vat_rate), 2)
            invoice.fuel_vat_amount = round(invoice.fuel_value_gross - invoice.fuel_value_net, 2)
            print(f"  Paliwo: {invoice.fuel_value_net} -> {invoice.fuel_value_gross} zl")
        
        if invoice.subscription_value_gross == 0.0 and invoice.subscription_value_net > 0:
            invoice.subscription_value_gross = round(invoice.subscription_value_net * (1 + vat_rate), 2)
            invoice.subscription_vat_amount = round(invoice.subscription_value_gross - invoice.subscription_value_net, 2)
            print(f"  Abonament: {invoice.subscription_value_net} -> {invoice.subscription_value_gross} zl")
        
        if invoice.distribution_fixed_value_gross == 0.0 and invoice.distribution_fixed_value_net > 0:
            invoice.distribution_fixed_value_gross = round(invoice.distribution_fixed_value_net * (1 + vat_rate), 2)
            invoice.distribution_fixed_vat_amount = round(invoice.distribution_fixed_value_gross - invoice.distribution_fixed_value_net, 2)
            print(f"  Dystrybucja stala: {invoice.distribution_fixed_value_net} -> {invoice.distribution_fixed_value_gross} zl")
        
        if invoice.distribution_variable_value_gross == 0.0 and invoice.distribution_variable_value_net > 0:
            invoice.distribution_variable_value_gross = round(invoice.distribution_variable_value_net * (1 + vat_rate), 2)
            invoice.distribution_variable_vat_amount = round(invoice.distribution_variable_value_gross - invoice.distribution_variable_value_net, 2)
            print(f"  Dystrybucja zmienna: {invoice.distribution_variable_value_net} -> {invoice.distribution_variable_value_gross} zl")
        
        updated_count += 1

if updated_count > 0:
    db.commit()
    print(f"\n[OK] Zaktualizowano {updated_count} faktur")
else:
    print("\n[INFO] Wszystkie faktury maja juz poprawne wartosci brutto")

db.close()

