"""Oblicza przewidywaną wartość następnej faktury za wodę i ścieki na podstawie stawek z ostatniej faktury."""
import sys
from pathlib import Path
from datetime import datetime, date
from typing import Optional

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import SessionLocal
from app.models.water import Invoice, Reading
from sqlalchemy import desc

def calculate_bill_costs(
    usage_m3: float,
    water_cost_m3: float,
    sewage_cost_m3: float,
    water_subscr_cost: float,
    sewage_subscr_cost: float,
    nr_of_subscription: int
) -> tuple[float, float, float, float, float]:
    """
    Oblicza koszty rachunku na podstawie zużycia i stawek.
    Zwraca: (cost_water, cost_sewage, cost_usage_total, abonament_total, net_sum)
    """
    # Koszt wody
    cost_water = usage_m3 * water_cost_m3
    
    # Koszt ścieków
    cost_sewage = usage_m3 * sewage_cost_m3
    
    # Suma kosztów zużycia
    cost_usage_total = cost_water + cost_sewage
    
    # Abonament (podzielony przez liczbę lokali)
    # Zakładamy, że jest 3 lokale (gora, gabinet, dol)
    nr_of_locals = 3
    abonament_water_share = (water_subscr_cost * nr_of_subscription) / nr_of_locals
    abonament_sewage_share = (sewage_subscr_cost * nr_of_subscription) / nr_of_locals
    abonament_total = abonament_water_share + abonament_sewage_share
    
    # Suma netto
    net_sum = cost_usage_total + abonament_total
    
    return cost_water, cost_sewage, cost_usage_total, abonament_total, net_sum

def predict_next_invoice():
    """Oblicza przewidywaną wartość następnej faktury."""
    db = SessionLocal()
    
    try:
        # Pobierz ostatnią fakturę
        last_invoice = db.query(Invoice).order_by(desc(Invoice.data)).first()
        
        if not last_invoice:
            print("Brak faktur w bazie danych.")
            return
        
        print("=== OSTATNIA FAKTURA ===")
        print(f"Okres: {last_invoice.data}")
        print(f"Numer: {last_invoice.invoice_number}")
        print(f"Zuzycie: {last_invoice.usage} m3")
        print(f"Suma brutto: {last_invoice.gross_sum:.2f} zl")
        print()
        
        # Pobierz stawki z ostatniej faktury
        water_cost_m3 = last_invoice.water_cost_m3
        sewage_cost_m3 = last_invoice.sewage_cost_m3
        water_subscr_cost = last_invoice.water_subscr_cost
        sewage_subscr_cost = last_invoice.sewage_subscr_cost
        nr_of_subscription = last_invoice.nr_of_subscription
        vat_rate = last_invoice.vat
        
        print("=== STAWKI Z OSTATNIEJ FAKTURY ===")
        print(f"Woda: {water_cost_m3:.4f} zl/m3")
        print(f"Scieki: {sewage_cost_m3:.4f} zl/m3")
        print(f"Abonament wody: {water_subscr_cost:.2f} zl/miesiac")
        print(f"Abonament sciekow: {sewage_subscr_cost:.2f} zl/miesiac")
        print(f"Liczba miesiecy abonamentu: {nr_of_subscription}")
        print(f"VAT: {vat_rate*100:.1f}%")
        print()
        
        # Znajdź odczyt dla okresu ostatniej faktury
        invoice_period_reading = db.query(Reading).filter(Reading.data == last_invoice.data).first()
        
        # Znajdź najnowszy odczyt (może być dla następnego okresu)
        latest_reading = db.query(Reading).order_by(desc(Reading.data)).first()
        
        if not latest_reading:
            print("UWAGA: Brak odczytow w bazie danych.")
            print("Nie mozna obliczyc zuzycia dla nastepnego okresu.")
            return
        
        # Sprawdź, czy najnowszy odczyt jest dla następnego okresu (po ostatniej fakturze)
        from datetime import datetime, timedelta
        invoice_period = datetime.strptime(last_invoice.data, "%Y-%m")
        next_period = invoice_period + timedelta(days=32)
        next_period_str = next_period.strftime("%Y-%m")
        
        # Sprawdź, czy najnowszy odczyt jest dla następnego okresu lub późniejszego
        if latest_reading.data >= next_period_str:
            # Mamy odczyt dla następnego okresu lub późniejszego - oblicz zużycie
            if invoice_period_reading:
                print("=== ODCZYT DLA OKRESU OSTATNIEJ FAKTURY ===")
                print(f"Okres: {invoice_period_reading.data}")
                print(f"Licznik glowny: {invoice_period_reading.water_meter_main:.2f} m3")
                print(f"Licznik gora: {invoice_period_reading.water_meter_5} m3")
                print(f"Licznik dol: {invoice_period_reading.water_meter_5b} m3")
                print()
                
                print(f"=== ODCZYT DLA OKRESU {latest_reading.data} ===")
                print(f"Licznik glowny: {latest_reading.water_meter_main:.2f} m3")
                print(f"Licznik gora: {latest_reading.water_meter_5} m3")
                print(f"Licznik dol: {latest_reading.water_meter_5b} m3")
                print()
                
                # Oblicz zużycie jako różnicę między odczytami
                meter_main_replaced = latest_reading.water_meter_main < invoice_period_reading.water_meter_main
                
                if meter_main_replaced:
                    print("UWAGA: Wykryto wymiane licznika glownego!")
                    print(f"  Poprzedni stan: {invoice_period_reading.water_meter_main:.2f} m3")
                    print(f"  Nowy stan: {latest_reading.water_meter_main:.2f} m3")
                    print("  Przyjmuje nowy stan jako zuzycie dla okresu")
                    predicted_usage = latest_reading.water_meter_main
                else:
                    # Oblicz zużycie dla każdego lokalu
                    usage_gora = latest_reading.water_meter_5 - invoice_period_reading.water_meter_5
                    usage_gabinet = latest_reading.water_meter_5b - invoice_period_reading.water_meter_5b
                    usage_main = latest_reading.water_meter_main - invoice_period_reading.water_meter_main
                    usage_dol = usage_main - (usage_gora + usage_gabinet)
                    
                    predicted_usage = usage_main
                    
                    print("=== OBLICZONE ZUZYCIE ===")
                    print(f"Gora: {usage_gora:.2f} m3")
                    print(f"Gabinet: {usage_gabinet:.2f} m3")
                    print(f"Dol: {usage_dol:.2f} m3")
                    print(f"*** CALKOWITE ZUZYCIE: {predicted_usage:.2f} m3 ***")
                    if latest_reading.data > next_period_str:
                        print(f"UWAGA: To zuzycie obejmuje okres od {next_period_str} do {latest_reading.data}")
                    print()
            else:
                # Brak odczytu dla okresu ostatniej faktury, ale mamy odczyt dla następnego okresu
                print(f"UWAGA: Brak odczytu dla okresu ostatniej faktury ({last_invoice.data}).")
                print(f"Znaleziono odczyt dla okresu {latest_reading.data}.")
                print("Nie mozna obliczyc dokladnego zuzycia - uzywam alternatywnej metody.")
                print()
                predicted_usage = last_invoice.usage
        else:
            # Najnowszy odczyt nie jest dla następnego okresu
            print(f"=== NAJNOWSZY ODCZYT ===")
            print(f"Okres: {latest_reading.data}")
            print(f"Licznik glowny: {latest_reading.water_meter_main:.2f} m3")
            print()
            print(f"UWAGA: Najnowszy odczyt ({latest_reading.data}) nie jest dla nastepnego okresu ({next_period_str}).")
            print("Nie mozna obliczyc rzeczywistego zuzycia dla nastepnego okresu.")
            print()
            print("=== ALTERNATYWNA PROGNOZA (na podstawie sredniej) ===")
            invoices = db.query(Invoice).order_by(desc(Invoice.data)).limit(6).all()
            if len(invoices) > 1:
                total_usage = sum(inv.usage for inv in invoices)
                avg_usage = total_usage / len(invoices)
                print(f"Ostatnie {len(invoices)} faktur:")
                for inv in invoices:
                    print(f"  {inv.data}: {inv.usage} m3")
                print(f"Srednie zuzycie: {avg_usage:.2f} m3")
                predicted_usage = avg_usage
            else:
                predicted_usage = last_invoice.usage
                print(f"Uzywam zuzycia z ostatniej faktury: {predicted_usage} m3")
        
        print("=== PRZEWIDYWANE ZUZYCIE ===")
        print(f"Przewidywane zuzycie dla nastepnej faktury: {predicted_usage:.2f} m3")
        print()
        
        # Oblicz koszty dla przewidywanego zużycia
        cost_water, cost_sewage, cost_usage_total, abonament_total, net_sum = calculate_bill_costs(
            predicted_usage,
            water_cost_m3,
            sewage_cost_m3,
            water_subscr_cost,
            sewage_subscr_cost,
            nr_of_subscription
        )
        
        # Oblicz VAT i sumę brutto
        vat_amount = net_sum * vat_rate
        gross_sum = net_sum + vat_amount
        
        print("=== PRZEWIDYWANA WARTOSC NASTEPNEJ FAKTURY ===")
        print(f"Zuzycie: {predicted_usage:.2f} m3")
        print(f"Koszt wody: {cost_water:.2f} zl")
        print(f"Koszt sciekow: {cost_sewage:.2f} zl")
        print(f"Suma kosztow zuzycia: {cost_usage_total:.2f} zl")
        print(f"Abonament (lacznie): {(water_subscr_cost + sewage_subscr_cost) * nr_of_subscription:.2f} zl")
        print(f"Suma netto: {net_sum:.2f} zl")
        print(f"VAT ({vat_rate*100:.1f}%): {vat_amount:.2f} zl")
        print(f"*** SUMA BRUTTO: {gross_sum:.2f} zl ***")
        print()
        
        # Porównanie z ostatnią fakturą
        print("=== POROWNANIE Z OSTATNIA FAKTURA ===")
        print(f"Ostatnia faktura: {last_invoice.gross_sum:.2f} zl")
        print(f"Przewidywana: {gross_sum:.2f} zl")
        difference = gross_sum - last_invoice.gross_sum
        if difference > 0:
            print(f"Roznica: +{difference:.2f} zl (wysza o {difference/last_invoice.gross_sum*100:.1f}%)")
        else:
            print(f"Roznica: {difference:.2f} zl (nizsza o {abs(difference)/last_invoice.gross_sum*100:.1f}%)")
        
    finally:
        db.close()

if __name__ == "__main__":
    predict_next_invoice()

