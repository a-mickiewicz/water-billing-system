"""
Sprawdza obecny stan obsługi gazu w systemie.
"""

from pathlib import Path
from app.core.database import SessionLocal, init_db
from app.models.gas import GasInvoice, GasBill
from app.services.gas.invoice_reader import extract_text_from_pdf, parse_invoice_data
import json

init_db()
db = SessionLocal()

print("=" * 80)
print("ANALIZA STANU OBSŁUGI GAZU")
print("=" * 80)

# 1. Sprawdź faktury w bazie
print("\n1. FAKTURY W BAZIE DANYCH:")
invoices = db.query(GasInvoice).order_by(GasInvoice.data.desc()).all()
print(f"   Liczba faktur: {len(invoices)}")
for inv in invoices:
    print(f"   - {inv.invoice_number} ({inv.data}): {inv.total_gross_sum:.2f} zł")
    print(f"     Okres: {inv.period_start} - {inv.period_stop}")
    print(f"     Zuzycie: {inv.fuel_usage_m3} m3 ({inv.fuel_usage_kwh} kWh)")

# 2. Sprawdź rachunki w bazie
print("\n2. RACHUNKI W BAZIE DANYCH:")
bills = db.query(GasBill).order_by(GasBill.data.desc()).all()
print(f"   Liczba rachunków: {len(bills)}")
periods_with_bills = {}
for bill in bills:
    period = bill.data
    if period not in periods_with_bills:
        periods_with_bills[period] = []
    periods_with_bills[period].append(bill)

for period, period_bills in sorted(periods_with_bills.items(), reverse=True):
    print(f"\n   Okres {period}:")
    total = 0.0
    for bill in period_bills:
        print(f"     {bill.local}: {bill.total_gross_sum:.2f} zł")
        total += bill.total_gross_sum
    print(f"     SUMA: {total:.2f} zł")

# 3. Sprawdź dostępne faktury PDF
print("\n3. DOSTĘPNE FAKTURY PDF:")
gas_folder = Path("invoices_raw/gas")
main_folder = Path("invoices_raw")

pdf_files = []
if gas_folder.exists():
    pdf_files.extend(list(gas_folder.glob("p_*.pdf")))
if main_folder.exists():
    pdf_files.extend([f for f in main_folder.glob("p_*.pdf") if f.name.startswith("p_43562821")])

print(f"   Znaleziono {len(pdf_files)} plików PDF")
for pdf_file in sorted(pdf_files)[:10]:  # Pokaż pierwsze 10
    print(f"   - {pdf_file.name}")

# 4. Przetestuj parsowanie przykładowych faktur
print("\n4. TEST PARSOWANIA FAKTUR:")
test_files = sorted(pdf_files)[:3]  # Testuj pierwsze 3
for pdf_file in test_files:
    print(f"\n   Test: {pdf_file.name}")
    try:
        text = extract_text_from_pdf(str(pdf_file))
        data = parse_invoice_data(text)
        
        if data:
            print(f"     [OK] Parsowanie udane")
            print(f"       Numer: {data.get('invoice_number', 'BRAK')}")
            print(f"       Okres: {data.get('period_start', 'BRAK')} - {data.get('period_stop', 'BRAK')}")
            print(f"       Zuzycie: {data.get('fuel_usage_m3', 'BRAK')} m3")
            print(f"       Suma brutto: {data.get('total_gross_sum', 'BRAK')} zl")
            
            # Sprawdź brakujące pola
            required_fields = [
                'invoice_number', 'period_start', 'period_stop',
                'previous_reading', 'current_reading',
                'fuel_usage_m3', 'fuel_price_net', 'fuel_value_net',
                'subscription_quantity', 'subscription_price_net', 'subscription_value_net',
                'distribution_fixed_quantity', 'distribution_fixed_price_net', 'distribution_fixed_value_net',
                'distribution_variable_usage_m3', 'distribution_variable_price_net', 'distribution_variable_value_net',
                'total_net_sum', 'vat_rate', 'vat_amount', 'total_gross_sum',
                'amount_to_pay', 'payment_due_date'
            ]
            missing = [f for f in required_fields if f not in data or data[f] is None]
            if missing:
                print(f"       [WARNING] Brakujace pola: {', '.join(missing)}")
        else:
            print(f"     [ERROR] Parsowanie nieudane")
    except Exception as e:
        print(f"     [ERROR] Blad: {e}")

# 5. Sprawdź czy faktury PDF są już w bazie
print("\n5. PORÓWNANIE PDF Z BAZĄ:")
for pdf_file in sorted(pdf_files)[:5]:
    try:
        text = extract_text_from_pdf(str(pdf_file))
        data = parse_invoice_data(text)
        if data and 'invoice_number' in data:
            invoice_num = data['invoice_number']
            existing = db.query(GasInvoice).filter(
                GasInvoice.invoice_number == invoice_num
            ).first()
            if existing:
                print(f"   [OK] {pdf_file.name} -> {invoice_num} (w bazie)")
            else:
                print(f"   [BRAK] {pdf_file.name} -> {invoice_num} (BRAK w bazie)")
    except:
        pass

db.close()

print("\n" + "=" * 80)
print("KONIEC ANALIZY")
print("=" * 80)

