"""
Moduł zarządzania licznikami i rozliczaniem rachunków.
Oblicza zużycie wody, różnice pomiarowe i generuje koszty.
"""

from typing import Dict, Optional, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc
from models import Reading, Invoice, Bill, Local


def calculate_local_usage(
    current_reading: Reading,
    previous_reading: Optional[Reading],
    local_name: str
) -> float:
    """
    Oblicza zużycie dla konkretnego lokalu jako różnicę między obecnym a poprzednim odczytem.
    
    Args:
        current_reading: Obecny odczyt liczników
        previous_reading: Poprzedni odczyt liczników (None jeśli to pierwszy odczyt)
        local_name: Nazwa lokalu ('gora', 'gabinet', 'dol')
    
    Returns:
        Zużycie w m³ dla danego lokalu (różnica między odczytami)
    """
    if previous_reading is None:
        # Jeśli to pierwszy odczyt, zużycie = obecny stan
        if local_name == 'gora':
            return float(current_reading.water_meter_5)
        elif local_name == 'gabinet':
            return float(current_reading.water_meter_5b)
        elif local_name == 'dol':
            # dla dol obliczamy: main - (gora + gabinet)
            return current_reading.water_meter_main - (current_reading.water_meter_5 + current_reading.water_meter_5b)
        else:
            raise ValueError(f"Nieznany lokal: {local_name}")
    
    # Oblicz różnicę dla gora
    usage_gora = current_reading.water_meter_5 - previous_reading.water_meter_5
    # Oblicz różnicę dla gabinet  
    usage_gabinet = current_reading.water_meter_5b - previous_reading.water_meter_5b
    # Oblicz różnicę dla main
    usage_main = current_reading.water_meter_main - previous_reading.water_meter_main
    
    if local_name == 'gora':
        return float(usage_gora)
    elif local_name == 'gabinet':
        return float(usage_gabinet)
    elif local_name == 'dol':
        # dol = różnica main - (różnica gora + różnica gabinet)
        return usage_main - (usage_gora + usage_gabinet)
    else:
        raise ValueError(f"Nieznany lokal: {local_name}")


def check_measurement_difference(
    main_reading: float,
    meter_5_reading: int,
    meter_5b_reading: int
) -> Tuple[bool, float]:
    """
    Sprawdza różnicę między sumą podliczników a licznikiem głównym.
    
    Args:
        main_reading: Stan licznika głównego
        meter_5_reading: Stan licznika water_meter_5
        meter_5b_reading: Stan licznika water_meter_5b
    
    Returns:
        Tuple: (czy jest różnica, wielkość różnicy)
    """
    sum_submeters = meter_5_reading + meter_5b_reading
    difference = main_reading - sum_submeters
    
    # Dopuszczamy niewielką tolerancję (0.01 m³)
    has_difference = abs(difference) > 0.01
    
    return has_difference, difference


def calculate_bill_costs(
    usage_m3: float,
    water_cost_m3: float,
    sewage_cost_m3: float,
    water_subscr_cost: float,
    sewage_subscr_cost: float,
    nr_of_subscription: int
) -> Tuple[float, float, float, float, float]:
    """
    Oblicza koszty dla pojedynczego rachunku.
    
    Args:
        usage_m3: Zużycie lokalu w m³
        water_cost_m3: Koszt wody za m³
        sewage_cost_m3: Koszt ścieków za m³
        water_subscr_cost: Koszt abonamentu wody za miesiąc
        sewage_subscr_cost: Koszt abonamentu ścieków za miesiąc
        nr_of_subscription: Liczba miesięcy abonamentu
    
    Returns:
        Tuple: (cost_water, cost_sewage, cost_usage_total, abonament_share, net_sum)
    """
    # Koszty zużycia
    cost_water = usage_m3 * water_cost_m3
    cost_sewage = usage_m3 * sewage_cost_m3
    cost_usage_total = cost_water + cost_sewage
    
    # Abonament - dzielony na 3 lokale
    water_subscr_total = water_subscr_cost * nr_of_subscription
    sewage_subscr_total = sewage_subscr_cost * nr_of_subscription
    
    abonament_water_share = water_subscr_total / 3
    abonament_sewage_share = sewage_subscr_total / 3
    abonament_total = abonament_water_share + abonament_sewage_share
    
    # Suma netto (bez VAT)
    net_sum = cost_usage_total + abonament_total
    
    return cost_water, cost_sewage, cost_usage_total, abonament_total, net_sum


def generate_bills_for_period(db: Session, period: str) -> list[Bill]:
    """
    Generuje rachunki dla wszystkich lokali na dany okres.
    Obsługuje wiele faktur dla jednego okresu (np. podwyżka kosztów w środku okresu).
    
    Args:
        db: Sesja bazy danych
        period: Okres rozliczeniowy w formacie 'YYYY-MM'
    
    Returns:
        Lista wygenerowanych rachunków
    """
    # Pobierz obecny odczyt dla okresu
    current_reading = db.query(Reading).filter(Reading.data == period).first()
    if not current_reading:
        raise ValueError(f"Brak odczytu dla okresu {period}")
    
    # Pobierz poprzedni odczyt (najnowszy przed obecnym okresem)
    previous_reading = db.query(Reading).filter(Reading.data < period).order_by(desc(Reading.data)).first()
    
    # Pobierz WSZYSTKIE faktury dla okresu (może być wiele przy podwyżce kosztów)
    invoices = db.query(Invoice).filter(Invoice.data == period).order_by(Invoice.period_start).all()
    if not invoices:
        raise ValueError(f"Brak faktur dla okresu {period}")
    
    # Sprawdź czy faktury mają ten sam numer co faktury w następnym okresie
    # (sytuacja gdy jedna faktura jest podzielona na dwa okresy rozliczeniowe)
    if invoices:
        invoice_numbers = set(inv.invoice_number for inv in invoices)
        # Pobierz następny okres (YYYY-MM -> YYYY-MM+1)
        try:
            year, month = map(int, period.split('-'))
            if month == 12:
                next_period = f"{year + 1}-01"
            else:
                next_period = f"{year}-{month + 1:02d}"
            
            # Sprawdź faktury z następnego okresu z tym samym numerem
            next_invoices = db.query(Invoice).filter(
                Invoice.data == next_period,
                Invoice.invoice_number.in_(invoice_numbers)
            ).all()
            
            if next_invoices:
                # Dodaj faktury z następnego okresu do rozliczenia
                invoices.extend(next_invoices)
                invoices.sort(key=lambda inv: inv.period_start)
                print(f"[INFO] Znaleziono faktury z tym samym numerem w okresie {next_period},"
                      f" dolaczono do rozliczenia {period}")
        except (ValueError, IndexError):
            pass  # Jeśli nie można sparsować okresu, kontynuuj bez sprawdzania następnego okresu
    
    # Oblicz zużycie dla każdego lokalu jako różnicę między odczytami
    usage_gora = calculate_local_usage(current_reading, previous_reading, 'gora')
    usage_gabinet = calculate_local_usage(current_reading, previous_reading, 'gabinet')
    usage_dol = calculate_local_usage(current_reading, previous_reading, 'dol')
    
    # Oblicz całkowite zużycie z różnic między odczytami
    calculated_total_usage = usage_gora + usage_gabinet + usage_dol
    
    # Oblicz sumę zużycia z wszystkich faktur
    total_invoice_usage = sum(inv.usage for inv in invoices)
    
    # Oblicz różnicę między fakturą a sumą odczytów
    usage_adjustment = total_invoice_usage - calculated_total_usage
    
    # Ostrzeżenie, jeśli różnica jest bardzo duża (może to oznaczać błąd w danych)
    if abs(usage_adjustment) > 5.0:
        print(f"[OSTRZEZENIE] Duza roznica miedzy odczytami a faktura dla {period}:")
        print(f"  Suma roznic odczytow: {calculated_total_usage:.2f} m3")
        print(f"  Zuzycie z faktury: {total_invoice_usage:.2f} m3")
        print(f"  Roznica: {usage_adjustment:.2f} m3")
        print(f"  Mozliwe przyczyny: bledne odczyty, bledna faktura, lub niepokrywajace sie okresy rozliczeniowe")
    
    # Jeśli są różnice, rozdziel korektę proporcjonalnie do zużycia każdego lokalu
    # aby uniknąć ujemnych wartości (np. gdy cała korekta idzie tylko na jeden lokal)
    if abs(usage_adjustment) > 0.01:
        # Jeśli obliczone zużycie jest bardzo małe lub zerowe, rozdziel równomiernie
        if abs(calculated_total_usage) < 0.01:
            # Równomierny podział na 3 lokale
            usage_gora += usage_adjustment / 3
            usage_gabinet += usage_adjustment / 3
            usage_dol += usage_adjustment / 3
        else:
            # Rozdziel proporcjonalnie według udziału każdego lokalu w zużyciu
            # Używamy wartości bezwzględnych, aby obsłużyć przypadki z ujemnym zużyciem
            abs_usage_gora = abs(usage_gora)
            abs_usage_gabinet = abs(usage_gabinet)
            abs_usage_dol = abs(usage_dol)
            abs_total = abs_usage_gora + abs_usage_gabinet + abs_usage_dol
            
            if abs_total > 0.01:
                # Proporcjonalny podział
                usage_gora += usage_adjustment * (abs_usage_gora / abs_total)
                usage_gabinet += usage_adjustment * (abs_usage_gabinet / abs_total)
                usage_dol += usage_adjustment * (abs_usage_dol / abs_total)
            else:
                # Fallback: równomierny podział
                usage_gora += usage_adjustment / 3
                usage_gabinet += usage_adjustment / 3
                usage_dol += usage_adjustment / 3
    
    # Oblicz średnie koszty z wszystkich faktur (ważone zużyciem)
    # Lub użyj najwyższych kosztów - zdecydujemy się na średnią ważoną
    total_usage = sum(inv.usage for inv in invoices)
    weighted_water_cost = sum(inv.water_cost_m3 * inv.usage for inv in invoices) / total_usage if total_usage > 0 else 0
    weighted_sewage_cost = sum(inv.sewage_cost_m3 * inv.usage for inv in invoices) / total_usage if total_usage > 0 else 0
    
    # Zsumuj abonamenty z wszystkich faktur
    total_water_subscr = sum(inv.water_subscr_cost * inv.nr_of_subscription for inv in invoices)
    total_sewage_subscr = sum(inv.sewage_subscr_cost * inv.nr_of_subscription for inv in invoices)
    
    # Użyj średniego VAT z faktur
    avg_vat = sum(inv.vat for inv in invoices) / len(invoices)
    
    # Generuj rachunki dla wszystkich lokali
    locals_list = ['gora', 'gabinet', 'dol']
    bills = []
    
    for local_name in locals_list:
        # Przypisz odpowiednie zużycie
        if local_name == 'gora':
            usage_m3 = usage_gora
        elif local_name == 'gabinet':
            usage_m3 = usage_gabinet
        else:  # dol
            usage_m3 = usage_dol
        
        # Oblicz koszty używając średnich ważonych kosztów z wszystkich faktur
        cost_water = usage_m3 * weighted_water_cost
        cost_sewage = usage_m3 * weighted_sewage_cost
        cost_usage_total = cost_water + cost_sewage
        
        # Abonament dzielony na 3 lokale
        abonament_water_share = total_water_subscr / 3
        abonament_sewage_share = total_sewage_subscr / 3
        abonament_total = abonament_water_share + abonament_sewage_share
        
        # Suma netto
        net_sum = cost_usage_total + abonament_total
        
        # VAT
        gross_sum = net_sum * (1 + avg_vat)
        
        # Znajdź lokal w bazie
        local_obj = db.query(Local).filter(Local.local == local_name).first()
        
        if not local_obj:
            raise ValueError(f"Brak lokalizacji '{local_name}' w bazie")
        
        # Pobierz wartość obecnego odczytu licznika
        if local_name == 'gora':
            current_reading_value = current_reading.water_meter_5
            previous_reading_value = previous_reading.water_meter_5 if previous_reading else 0
        elif local_name == 'gabinet':
            current_reading_value = current_reading.water_meter_5b
            previous_reading_value = previous_reading.water_meter_5b if previous_reading else 0
        else:  # dol
            # dla dol, wartość odczytu to obliczona różnica
            current_reading_value = current_reading.water_meter_main - (current_reading.water_meter_5 + current_reading.water_meter_5b)
            if previous_reading:
                previous_main = previous_reading.water_meter_main - (previous_reading.water_meter_5 + previous_reading.water_meter_5b)
                previous_reading_value = previous_main
            else:
                previous_reading_value = 0
        
        # Pobierz wartość odczytu dla wyświetlenia (obecny stan)
        reading_value = current_reading_value
        
        # Stwórz rachunek (używamy ID pierwszej faktury)
        bill = Bill(
            data=period,
            local=local_name,
            reading_id=period,
            invoice_id=invoices[0].id,  # Pierwsza faktura z okresu
            local_id=local_obj.id,
            reading_value=reading_value,
            usage_m3=usage_m3,
            cost_water=cost_water,
            cost_sewage=cost_sewage,
            cost_usage_total=cost_usage_total,
            abonament_water_share=abonament_water_share,
            abonament_sewage_share=abonament_sewage_share,
            abonament_total=abonament_total,
            net_sum=net_sum,
            gross_sum=gross_sum
        )
        
        db.add(bill)
        bills.append(bill)
    
    db.commit()
    
    return bills

