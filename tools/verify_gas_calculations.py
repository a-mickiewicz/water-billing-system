"""
Weryfikuje poprawność obliczeń rachunków gazu.
Sprawdza:
- Sumy rachunków vs sumy faktur
- Podział kosztów (58%, 25%, 17%)
- Obliczenia szczegółowe (paliwo, abonament, dystrybucja)
- Odsetki dla "gora"
"""

from app.core.database import SessionLocal, init_db
from app.models.gas import GasInvoice, GasBill

init_db()
db = SessionLocal()

print("=" * 80)
print("WERYFIKACJA OBLICZEN RACHUNKOW GAZU")
print("=" * 80)

# Pobierz wszystkie faktury z rachunkami
invoices = db.query(GasInvoice).order_by(GasInvoice.data.desc()).all()

for invoice in invoices:
    print(f"\n{'='*80}")
    print(f"FAKTURA: {invoice.invoice_number} ({invoice.data})")
    print(f"{'='*80}")
    
    print(f"\n1. DANE Z FAKTURY:")
    print(f"   Okres: {invoice.period_start} - {invoice.period_stop}")
    print(f"   Zuzycie: {invoice.fuel_usage_m3} m3 ({invoice.fuel_usage_kwh} kWh)")
    print(f"   VAT: {invoice.vat_rate * 100}%")
    print(f"   Suma netto: {invoice.total_net_sum:.2f} zl")
    print(f"   VAT kwota: {invoice.vat_amount:.2f} zl")
    print(f"   Suma brutto: {invoice.total_gross_sum:.2f} zl")
    print(f"   Odsetki: {invoice.late_payment_interest:.2f} zl")
    print(f"   Do zaplaty: {invoice.amount_to_pay:.2f} zl")
    
    # Pobierz rachunki dla tego okresu
    bills = db.query(GasBill).filter(GasBill.data == invoice.data).all()
    
    if not bills:
        print(f"\n   [BRAK] Brak rachunkow dla tego okresu!")
        continue
    
    print(f"\n2. RACHUNKI DLA LOKALI:")
    total_bills_gross = 0.0
    total_bills_net = 0.0
    
    for bill in bills:
        print(f"\n   {bill.local.upper()} (udzial: {bill.cost_share * 100:.0f}%):")
        print(f"     Paliwo: {bill.fuel_cost_gross:.2f} zl")
        print(f"     Abonament: {bill.subscription_cost_gross:.2f} zl")
        print(f"     Dystrybucja stala: {bill.distribution_fixed_cost_gross:.2f} zl")
        print(f"     Dystrybucja zmienna: {bill.distribution_variable_cost_gross:.2f} zl")
        print(f"     Suma netto: {bill.total_net_sum:.2f} zl")
        print(f"     Suma brutto: {bill.total_gross_sum:.2f} zl")
        
        # Weryfikacja obliczen
        calculated_gross = (bill.fuel_cost_gross + bill.subscription_cost_gross + 
                          bill.distribution_fixed_cost_gross + bill.distribution_variable_cost_gross)
        
        # Dla "gora" dodajemy odsetki
        if bill.local == 'gora' and invoice.late_payment_interest > 0:
            interest_net = invoice.late_payment_interest / (1 + invoice.vat_rate)
            interest_gross = invoice.late_payment_interest
            calculated_gross_with_interest = calculated_gross + interest_gross
            print(f"     Obliczone (bez odsetek): {calculated_gross:.2f} zl")
            print(f"     Odsetki: {interest_gross:.2f} zl")
            print(f"     Obliczone (z odsetkami): {calculated_gross_with_interest:.2f} zl")
            print(f"     Roznica: {abs(bill.total_gross_sum - calculated_gross_with_interest):.2f} zl")
        else:
            print(f"     Obliczone: {calculated_gross:.2f} zl")
            print(f"     Roznica: {abs(bill.total_gross_sum - calculated_gross):.2f} zl")
        
        total_bills_gross += bill.total_gross_sum
        total_bills_net += bill.total_net_sum
    
    print(f"\n3. PODSUMOWANIE:")
    print(f"   Suma rachunkow brutto: {total_bills_gross:.2f} zl")
    print(f"   Suma faktury brutto: {invoice.total_gross_sum:.2f} zl")
    print(f"   Roznica: {abs(total_bills_gross - invoice.total_gross_sum):.2f} zl")
    
    # Sprawdz podzial kosztow
    print(f"\n4. WERYFIKACJA PODZIALU KOSZTOW:")
    house_gross_without_interest = invoice.total_gross_sum - invoice.late_payment_interest
    
    expected_shares = {
        'gora': 0.58,
        'dol': 0.25,
        'gabinet': 0.17
    }
    
    for local_name, expected_share in expected_shares.items():
        bill = next((b for b in bills if b.local == local_name), None)
        if bill:
            expected_gross = house_gross_without_interest * expected_share
            if local_name == 'gora' and invoice.late_payment_interest > 0:
                expected_gross += invoice.late_payment_interest
            
            print(f"   {local_name.upper()}:")
            print(f"     Oczekiwane ({expected_share * 100:.0f}%): {expected_gross:.2f} zl")
            print(f"     W rachunku: {bill.total_gross_sum:.2f} zl")
            print(f"     Roznica: {abs(bill.total_gross_sum - expected_gross):.2f} zl")
    
    # Sprawdz szczegolowe koszty
    print(f"\n5. WERYFIKACJA SZCZEGOLOWYCH KOSZTOW:")
    
    # Sprawdz czy faktura ma szczegolowe wartosci
    has_details = (invoice.fuel_value_gross > 0 or invoice.subscription_value_gross > 0 or
                   invoice.distribution_fixed_value_gross > 0 or invoice.distribution_variable_value_gross > 0)
    
    if has_details:
        print(f"   Faktura ma szczegolowe wartosci brutto:")
        print(f"     Paliwo: {invoice.fuel_value_gross:.2f} zl")
        print(f"     Abonament: {invoice.subscription_value_gross:.2f} zl")
        print(f"     Dystrybucja stala: {invoice.distribution_fixed_value_gross:.2f} zl")
        print(f"     Dystrybucja zmienna: {invoice.distribution_variable_value_gross:.2f} zl")
        
        # Sprawdz czy rachunki uzywaja szczegolowych wartosci
        for bill in bills:
            print(f"\n   {bill.local.upper()}:")
            if bill.local == 'gora':
                share = 0.58
            elif bill.local == 'dol':
                share = 0.25
            else:
                share = 0.17
            
            expected_fuel = invoice.fuel_value_gross * share
            expected_subscr = invoice.subscription_value_gross * share
            expected_fixed = invoice.distribution_fixed_value_gross * share
            expected_var = invoice.distribution_variable_value_gross * share
            
            print(f"     Paliwo: oczekiwane {expected_fuel:.2f}, w rachunku {bill.fuel_cost_gross:.2f}, roznica {abs(bill.fuel_cost_gross - expected_fuel):.2f}")
            print(f"     Abonament: oczekiwane {expected_subscr:.2f}, w rachunku {bill.subscription_cost_gross:.2f}, roznica {abs(bill.subscription_cost_gross - expected_subscr):.2f}")
            print(f"     Dystrybucja stala: oczekiwane {expected_fixed:.2f}, w rachunku {bill.distribution_fixed_cost_gross:.2f}, roznica {abs(bill.distribution_fixed_cost_gross - expected_fixed):.2f}")
            print(f"     Dystrybucja zmienna: oczekiwane {expected_var:.2f}, w rachunku {bill.distribution_variable_cost_gross:.2f}, roznica {abs(bill.distribution_variable_cost_gross - expected_var):.2f}")
    else:
        print(f"   Faktura NIE ma szczegolowych wartosci brutto (wszystkie = 0)")
        print(f"   Rachunki uzywaja proporcjonalnego podzialu z total_gross_sum")

db.close()

print(f"\n{'='*80}")
print("KONIEC WERYFIKACJI")
print(f"{'='*80}")

