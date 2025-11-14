"""
Sprawdza faktury dla okresu 2023-12 i czy są dodawane faktury z następnego okresu.
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import SessionLocal
from app.models.water import Invoice, Reading
from sqlalchemy import desc

def check_invoices():
    db = SessionLocal()
    try:
        period = "2023-12"
        
        print(f"=== SPRAWDZENIE FAKTUR DLA {period} ===\n")
        
        # Pobierz faktury dla 2023-12
        invoices_2023_12 = db.query(Invoice).filter(Invoice.data == period).order_by(Invoice.period_start).all()
        print(f"Faktury dla {period}:")
        for inv in invoices_2023_12:
            print(f"  Faktura {inv.invoice_number}:")
            print(f"    Zuzycie: {inv.usage} m3")
            print(f"    Okres: {inv.period_start} - {inv.period_stop}")
            print(f"    Suma brutto: {inv.gross_sum} zl")
        
        total_usage_2023_12 = sum(inv.usage for inv in invoices_2023_12)
        print(f"\nSuma zuzycia z faktur {period}: {total_usage_2023_12} m3")
        
        # Sprawdź faktury z następnego okresu (2024-01) z tymi samymi numerami
        invoice_numbers = set(inv.invoice_number for inv in invoices_2023_12)
        print(f"\nNumery faktur z {period}: {invoice_numbers}")
        
        invoices_2024_01 = db.query(Invoice).filter(
            Invoice.data == "2024-01",
            Invoice.invoice_number.in_(invoice_numbers)
        ).all()
        
        if invoices_2024_01:
            print(f"\n[UWAGA] Znaleziono faktury z 2024-01 z tymi samymi numerami:")
            for inv in invoices_2024_01:
                print(f"  Faktura {inv.invoice_number}:")
                print(f"    Zuzycie: {inv.usage} m3")
                print(f"    Okres: {inv.period_start} - {inv.period_stop}")
                print(f"    Suma brutto: {inv.gross_sum} zl")
            
            total_usage_2024_01 = sum(inv.usage for inv in invoices_2024_01)
            print(f"\nSuma zuzycia z faktur 2024-01: {total_usage_2024_01} m3")
            print(f"Laczna suma (2023-12 + 2024-01): {total_usage_2023_12 + total_usage_2024_01} m3")
            print(f"\n[PROBLEM] System dodaje faktury z 2024-01 do rozliczenia 2023-12!")
            print(f"  To powoduje roznice: {total_usage_2024_01} m3")
            print(f"  Ta roznica jest dodawana do 'gora'!")
        else:
            print(f"\nBrak faktur z 2024-01 z tymi samymi numerami")
        
        # Sprawdź odczyty
        current_reading = db.query(Reading).filter(Reading.data == period).first()
        previous_reading = db.query(Reading).filter(Reading.data < period).order_by(desc(Reading.data)).first()
        
        if current_reading and previous_reading:
            diff_main = current_reading.water_meter_main - previous_reading.water_meter_main
            diff_gora = current_reading.water_meter_5 - previous_reading.water_meter_5
            diff_gabinet = current_reading.water_meter_5a - previous_reading.water_meter_5a
            diff_dol = diff_main - (diff_gora + diff_gabinet)
            
            print(f"\n=== OBLICZENIA Z ODCZYTOW ===")
            print(f"Gora: {diff_gora} m3")
            print(f"Gabinet: {diff_gabinet} m3")
            print(f"Dol: {diff_dol} m3")
            print(f"Glowny: {diff_main} m3")
            print(f"Suma: {diff_gora + diff_gabinet + diff_dol} m3")
            
            if invoices_2024_01:
                total_invoice_usage = total_usage_2023_12 + total_usage_2024_01
                calculated_total = diff_gora + diff_gabinet + diff_dol
                adjustment = total_invoice_usage - calculated_total
                print(f"\n=== KOREKTA ===")
                print(f"Obliczone z odczytow: {calculated_total} m3")
                print(f"Zuzycie z faktur (2023-12 + 2024-01): {total_invoice_usage} m3")
                print(f"Roznica (korekta): {adjustment} m3")
                print(f"Ta roznica jest dodawana do 'gora': {diff_gora} + {adjustment} = {diff_gora + adjustment} m3")
            
    finally:
        db.close()

if __name__ == "__main__":
    check_invoices()

