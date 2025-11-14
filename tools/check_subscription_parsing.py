"""
Sprawdza, co jest parsowane z faktury dla abonamentu.
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import SessionLocal
from app.models.water import Invoice

def check_subscription_parsing():
    db = SessionLocal()
    try:
        period = "2023-12"
        
        invoice = db.query(Invoice).filter(Invoice.data == period).first()
        if not invoice:
            print(f"Brak faktury dla okresu {period}")
            return
        
        print(f"=== SPRAWDZENIE PARSOWANIA ABONAMENTU DLA {period} ===\n")
        print(f"Faktura: {invoice.invoice_number}")
        print(f"Okres: {invoice.period_start} - {invoice.period_stop}")
        print(f"\nWartosci w bazie:")
        print(f"  water_subscr_cost: {invoice.water_subscr_cost} zl")
        print(f"  sewage_subscr_cost: {invoice.sewage_subscr_cost} zl")
        print(f"  nr_of_subscription: {invoice.nr_of_subscription}")
        
        print(f"\nObliczenia w kodzie (meter_manager.py linia 311-312):")
        total_water_subscr = invoice.water_subscr_cost * invoice.nr_of_subscription
        total_sewage_subscr = invoice.sewage_subscr_cost * invoice.nr_of_subscription
        print(f"  total_water_subscr = {invoice.water_subscr_cost} * {invoice.nr_of_subscription} = {total_water_subscr} zl")
        print(f"  total_sewage_subscr = {invoice.sewage_subscr_cost} * {invoice.nr_of_subscription} = {total_sewage_subscr} zl")
        
        print(f"\nDzielenie przez 3 (meter_manager.py linia 336-337):")
        subscription_water_share = total_water_subscr / 3
        subscription_sewage_share = total_sewage_subscr / 3
        print(f"  subscription_water_share = {total_water_subscr} / 3 = {subscription_water_share:.2f} zl")
        print(f"  subscription_sewage_share = {total_sewage_subscr} / 3 = {subscription_sewage_share:.2f} zl")
        
        print(f"\n=== ANALIZA ===")
        print(f"Jesli na fakturze jest 1 okres rozliczeniowy:")
        print(f"  - water_subscr_cost powinno byc calkowita wartoscia za okres (nie za miesiac)")
        print(f"  - Wtedy NIE powinno byc mnozone przez nr_of_subscription")
        print(f"  - Powinno byc dzielone przez 3 bezposrednio")
        
        print(f"\nAktualna logika:")
        print(f"  - water_subscr_cost jest traktowane jako cena za miesiac")
        print(f"  - Mnozone przez nr_of_subscription (liczba miesiecy)")
        print(f"  - Potem dzielone przez 3")
        print(f"  - To daje: {invoice.water_subscr_cost} * {invoice.nr_of_subscription} / 3 = {subscription_water_share:.2f} zl na lokal")
        
        print(f"\nPoprawna logika (jesli water_subscr_cost to calkowita wartosc za okres):")
        correct_water_share = invoice.water_subscr_cost / 3
        correct_sewage_share = invoice.sewage_subscr_cost / 3
        print(f"  - water_subscr_cost / 3 = {invoice.water_subscr_cost} / 3 = {correct_water_share:.2f} zl na lokal")
        print(f"  - sewage_subscr_cost / 3 = {invoice.sewage_subscr_cost} / 3 = {correct_sewage_share:.2f} zl na lokal")
        
        print(f"\nRoznica:")
        print(f"  Woda: {subscription_water_share:.2f} vs {correct_water_share:.2f} (roznica: {abs(subscription_water_share - correct_water_share):.2f} zl)")
        print(f"  Scieki: {subscription_sewage_share:.2f} vs {correct_sewage_share:.2f} (roznica: {abs(subscription_sewage_share - correct_sewage_share):.2f} zl)")
        
    finally:
        db.close()

if __name__ == "__main__":
    check_subscription_parsing()

