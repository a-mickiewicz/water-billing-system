"""
Skrypt do obliczania nowej logiki generowania rachunków z faktur.

Użycie:
    python tools/calculate_bill_logic.py [NUMER_FAKTURY_POPRZEDNIEJ] [NUMER_FAKTURY_OBECNEJ]

Przykład:
    python tools/calculate_bill_logic.py "P/23666363/0001/23" "P/23666363/0002/24"
"""

import sys
import argparse
from pathlib import Path
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Tuple, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

# Dodaj ścieżkę do projektu
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import SessionLocal
from app.models.electricity_invoice import (
    ElectricityInvoice,
    ElectricityInvoiceOdczyt,
    ElectricityInvoiceSprzedazEnergii,
    ElectricityInvoiceOplataDystrybucyjna
)
from app.models.electricity import ElectricityReading
from app.services.electricity.calculator import calculate_all_usage, get_previous_reading


def get_invoice_by_number(db: Session, invoice_number: str) -> Optional[ElectricityInvoice]:
    """Pobiera fakturę po numerze."""
    return db.query(ElectricityInvoice).filter(
        ElectricityInvoice.numer_faktury == invoice_number
    ).first()


def calculate_days_between(start_date: date, end_date: date) -> int:
    """Oblicza liczbę dni między datami (włącznie z końcową)."""
    return (end_date - start_date).days + 1


def get_periods_from_readings(
    db: Session,
    prev_invoice: ElectricityInvoice,
    current_invoice: ElectricityInvoice
) -> List[Dict]:
    """
    I. Wyłaniamy okresy z faktur "Odczyty".
    
    Okres rozliczeniowy faktury zawsze zaczyna się 1.11.YYYY, a kończy w następnym roku 31.10.YYYY
    """
    periods = []
    
    # Pobieramy odczyty z faktury poprzedniej (pierwszy odczyt)
    prev_readings = db.query(ElectricityInvoiceOdczyt).filter(
        ElectricityInvoiceOdczyt.invoice_id == prev_invoice.id
    ).order_by(ElectricityInvoiceOdczyt.data_odczytu).all()
    
    # Pobieramy odczyty z faktury kolejnej
    current_readings = db.query(ElectricityInvoiceOdczyt).filter(
        ElectricityInvoiceOdczyt.invoice_id == current_invoice.id
    ).order_by(ElectricityInvoiceOdczyt.data_odczytu).all()
    
    if not prev_readings or not current_readings:
        return periods
    
    # Okres rozliczeniowy zaczyna się 1.11.YYYY z faktury obecnej
    period_start_year = current_invoice.data_poczatku_okresu.year
    period_start = date(period_start_year, 11, 1)
    
    # Pierwszy odczyt z faktury kolejnej
    first_current_reading_date = min(r.data_odczytu for r in current_readings)
    
    # OKRES I - od 1.11.YYYY do pierwszego odczytu z faktury kolejnej
    period_end = first_current_reading_date
    
    # Pobieramy ilość kWh dla OKRES I
    # Szukamy odczytów z faktury obecnej, które są w tym okresie
    period_readings = [r for r in current_readings 
                      if period_start <= r.data_odczytu <= period_end]
    
    dzienna_kwh = 0
    nocna_kwh = 0
    calodobowa_kwh = 0
    
    for reading in period_readings:
        if reading.typ_energii == "POBRANA":
            if reading.strefa == "DZIENNA":
                dzienna_kwh += reading.ilosc_kwh
            elif reading.strefa == "NOCNA":
                nocna_kwh += reading.ilosc_kwh
            elif reading.strefa is None:  # całodobowa
                calodobowa_kwh += reading.ilosc_kwh
    
    periods.append({
        "okres": "OKRES I",
        "od": period_start,
        "do": period_end,
        "dzienna_kwh": dzienna_kwh,
        "nocna_kwh": nocna_kwh,
        "calodobowa_kwh": calodobowa_kwh
    })
    
    # OKRES II i kolejne - od kolejnego dnia po zakończeniu poprzedniego
    current_period_start = period_end + timedelta(days=1)
    
    # Sortujemy wszystkie odczyty z faktury kolejnej po datach
    all_readings_dates = sorted(set(r.data_odczytu for r in current_readings))
    
    for i, reading_date in enumerate(all_readings_dates):
        if i == 0:
            # Pierwszy okres już obsłużyliśmy
            continue
        
        period_start_date = current_period_start
        period_end_date = reading_date
        
        # Pobieramy odczyty dla tego okresu
        period_readings = [r for r in current_readings 
                          if period_start_date <= r.data_odczytu <= period_end_date]
        
        dzienna_kwh = 0
        nocna_kwh = 0
        calodobowa_kwh = 0
        
        for reading in period_readings:
            if reading.typ_energii == "POBRANA":
                if reading.strefa == "DZIENNA":
                    dzienna_kwh += reading.ilosc_kwh
                elif reading.strefa == "NOCNA":
                    nocna_kwh += reading.ilosc_kwh
                elif reading.strefa is None:
                    calodobowa_kwh += reading.ilosc_kwh
        
        periods.append({
            "okres": f"OKRES {i+1}",
            "od": period_start_date,
            "do": period_end_date,
            "dzienna_kwh": dzienna_kwh,
            "nocna_kwh": nocna_kwh,
            "calodobowa_kwh": calodobowa_kwh
        })
        
        current_period_start = period_end_date + timedelta(days=1)
    
    # Ostatni okres kończy się 31.10.YYYY
    last_period_end = date(period_start_year + 1, 10, 31)
    if current_period_start <= last_period_end:
        # Ostatni okres
        period_readings = [r for r in current_readings 
                          if r.data_odczytu >= current_period_start]
        
        dzienna_kwh = 0
        nocna_kwh = 0
        calodobowa_kwh = 0
        
        for reading in period_readings:
            if reading.typ_energii == "POBRANA":
                if reading.strefa == "DZIENNA":
                    dzienna_kwh += reading.ilosc_kwh
                elif reading.strefa == "NOCNA":
                    nocna_kwh += reading.ilosc_kwh
                elif reading.strefa is None:
                    calodobowa_kwh += reading.ilosc_kwh
        
        periods.append({
            "okres": f"OKRES {len(periods)+1}",
            "od": current_period_start,
            "do": last_period_end,
            "dzienna_kwh": dzienna_kwh,
            "nocna_kwh": nocna_kwh,
            "calodobowa_kwh": calodobowa_kwh
        })
    
    return periods


def get_distribution_periods(
    db: Session,
    invoice: ElectricityInvoice
) -> List[Dict]:
    """
    II. Wyłaniamy okresy z "Rozliczenie usługa dystrybucji".
    
    Pobieramy dane z electricity_invoice_oplaty_dystrybucyjne i electricity_invoice_sprzedaz_energii.
    """
    periods = []
    
    # Pobieramy opłaty dystrybucyjne, sortowane po dacie
    oplaty = db.query(ElectricityInvoiceOplataDystrybucyjna).filter(
        ElectricityInvoiceOplataDystrybucyjna.invoice_id == invoice.id
    ).order_by(ElectricityInvoiceOplataDystrybucyjna.data).all()
    
    # Pobieramy sprzedaż energii, sortowane po dacie
    sprzedaz = db.query(ElectricityInvoiceSprzedazEnergii).filter(
        ElectricityInvoiceSprzedazEnergii.invoice_id == invoice.id
    ).order_by(ElectricityInvoiceSprzedazEnergii.data).all()
    
    if not oplaty:
        return periods
    
    # Okres rozliczeniowy faktury
    period_start_year = invoice.data_poczatku_okresu.year
    period_start = date(period_start_year, 11, 1)
    period_end = date(period_start_year + 1, 10, 31)
    
    # Grupujemy opłaty po datach (okresach)
    unique_dates = sorted(set(o.data for o in oplaty))
    
    # Sprzedaż energii ma data = None, więc dopasowujemy po kolejności
    # Grupujemy sprzedaż po kolejności - para dzienna+nocna lub całodobowa
    sprzedaz_grouped = []
    if invoice.typ_taryfy == "DWUTARYFOWA":
        # Dla dwutaryfowej: pary dzienna+nocna
        i = 0
        while i < len(sprzedaz):
            dzienna = None
            nocna = None
            if i < len(sprzedaz) and sprzedaz[i].strefa == "DZIENNA":
                dzienna = sprzedaz[i]
                i += 1
            if i < len(sprzedaz) and sprzedaz[i].strefa == "NOCNA":
                nocna = sprzedaz[i]
                i += 1
            if dzienna or nocna:
                sprzedaz_grouped.append({"dzienna": dzienna, "nocna": nocna})
    else:
        # Dla całodobowej: pojedyncze pozycje
        for s in sprzedaz:
            sprzedaz_grouped.append({"calodobowa": s})
    
    current_start = period_start
    
    for i, dist_date in enumerate(unique_dates):
        # Okres dystrybucyjny kończy się w dacie z opłat
        dist_period_end = dist_date
        
        # Pobieramy sprzedaż energii dla tego okresu (po kolejności)
        sprzedaz_period = sprzedaz_grouped[i] if i < len(sprzedaz_grouped) else {}
        
        # Pobieramy opłaty dla tego okresu
        oplaty_period = [o for o in oplaty if o.data == dist_date]
        
        # Ilość kWh z sprzedaży energii
        dzienna_sprzedaz = sprzedaz_period.get("dzienna")
        nocna_sprzedaz = sprzedaz_period.get("nocna")
        calodobowa_sprzedaz = sprzedaz_period.get("calodobowa")
        
        ilosc_kwh_dzienna = dzienna_sprzedaz.ilosc_kwh if dzienna_sprzedaz else 0
        ilosc_kwh_nocna = nocna_sprzedaz.ilosc_kwh if nocna_sprzedaz else 0
        ilosc_kwh_calodobowa = calodobowa_sprzedaz.ilosc_kwh if calodobowa_sprzedaz else 0
        
        # Ceny za 1kWh z sprzedaży energii
        cena_dzienna = None
        cena_nocna = None
        cena_calodobowa = None
        
        # Maksymalna rozsądna cena za 1 kWh (w zł) - jeśli większa, to prawdopodobnie błąd w danych
        MAX_REASONABLE_PRICE_PER_KWH = 5.0
        
        if sprzedaz_period.get("dzienna") and sprzedaz_period["dzienna"].ilosc_kwh > 0:
            cena_raw = float(sprzedaz_period["dzienna"].cena_za_kwh)
            # Walidacja: jeśli cena jest zbyt wysoka, może być błąd w danych
            # Sprawdzamy też, czy może być to całkowita kwota zamiast ceny za kWh
            if cena_raw > MAX_REASONABLE_PRICE_PER_KWH:
                # Może być to całkowita kwota - sprawdźmy, czy należność / ilość daje rozsądną cenę
                naleznosc = float(sprzedaz_period["dzienna"].naleznosc)
                ilosc = float(sprzedaz_period["dzienna"].ilosc_kwh)
                if ilosc > 0:
                    cena_z_naleznosci = naleznosc / ilosc
                    if cena_z_naleznosci <= MAX_REASONABLE_PRICE_PER_KWH:
                        # Użyj ceny obliczonej z należności
                        cena_dzienna = cena_z_naleznosci
                        print(f"UWAGA: Cena dzienna {cena_raw} za kWh jest zbyt wysoka. Używam ceny z należności: {cena_z_naleznosci}")
                    else:
                        # Użyj wartości z bazy, ale z ostrzeżeniem
                        cena_dzienna = cena_raw
                        print(f"UWAGA: Cena dzienna {cena_raw} za kWh jest bardzo wysoka - możliwy błąd w danych!")
                else:
                    cena_dzienna = cena_raw
            else:
                cena_dzienna = cena_raw
                
        if sprzedaz_period.get("nocna") and sprzedaz_period["nocna"].ilosc_kwh > 0:
            cena_raw = float(sprzedaz_period["nocna"].cena_za_kwh)
            if cena_raw > MAX_REASONABLE_PRICE_PER_KWH:
                naleznosc = float(sprzedaz_period["nocna"].naleznosc)
                ilosc = float(sprzedaz_period["nocna"].ilosc_kwh)
                if ilosc > 0:
                    cena_z_naleznosci = naleznosc / ilosc
                    if cena_z_naleznosci <= MAX_REASONABLE_PRICE_PER_KWH:
                        cena_nocna = cena_z_naleznosci
                        print(f"UWAGA: Cena nocna {cena_raw} za kWh jest zbyt wysoka. Używam ceny z należności: {cena_z_naleznosci}")
                    else:
                        cena_nocna = cena_raw
                        print(f"UWAGA: Cena nocna {cena_raw} za kWh jest bardzo wysoka - możliwy błąd w danych!")
                else:
                    cena_nocna = cena_raw
            else:
                cena_nocna = cena_raw
                
        if sprzedaz_period.get("calodobowa") and sprzedaz_period["calodobowa"].ilosc_kwh > 0:
            cena_raw = float(sprzedaz_period["calodobowa"].cena_za_kwh)
            if cena_raw > MAX_REASONABLE_PRICE_PER_KWH:
                naleznosc = float(sprzedaz_period["calodobowa"].naleznosc)
                ilosc = float(sprzedaz_period["calodobowa"].ilosc_kwh)
                if ilosc > 0:
                    cena_z_naleznosci = naleznosc / ilosc
                    if cena_z_naleznosci <= MAX_REASONABLE_PRICE_PER_KWH:
                        cena_calodobowa = cena_z_naleznosci
                        print(f"UWAGA: Cena całodobowa {cena_raw} za kWh jest zbyt wysoka. Używam ceny z należności: {cena_z_naleznosci}")
                    else:
                        cena_calodobowa = cena_raw
                        print(f"UWAGA: Cena całodobowa {cena_raw} za kWh jest bardzo wysoka - możliwy błąd w danych!")
                else:
                    cena_calodobowa = cena_raw
            else:
                cena_calodobowa = cena_raw
        
        # Opłaty dystrybucyjne
        oplata_jakosciowa_dzienna = None
        oplata_jakosciowa_nocna = None
        oplata_zmienna_sieciowa_dzienna = None
        oplata_zmienna_sieciowa_nocna = None
        oplata_oze_dzienna = None
        oplata_oze_nocna = None
        oplata_kogeneracyjna_dzienna = None
        oplata_kogeneracyjna_nocna = None
        
        oplata_stala_sieciowa = None
        oplata_przejściowa = None
        oplata_abonamentowa = None
        oplata_mocowa = None
        
        for o in oplaty_period:
            typ_oplaty_upper = o.typ_oplaty.upper()
            if o.jednostka == "kWh":
                if "JAKOŚCIOWA" in typ_oplaty_upper or "JAKOSCIOWA" in typ_oplaty_upper:
                    if o.strefa == "DZIENNA":
                        oplata_jakosciowa_dzienna = float(o.cena)
                    elif o.strefa == "NOCNA":
                        oplata_jakosciowa_nocna = float(o.cena)
                elif "ZMIENNA SIECIOWA" in typ_oplaty_upper:
                    if o.strefa == "DZIENNA":
                        oplata_zmienna_sieciowa_dzienna = float(o.cena)
                    elif o.strefa == "NOCNA":
                        oplata_zmienna_sieciowa_nocna = float(o.cena)
                elif "OZE" in typ_oplaty_upper:
                    if o.strefa == "DZIENNA":
                        oplata_oze_dzienna = float(o.cena)
                    elif o.strefa == "NOCNA":
                        oplata_oze_nocna = float(o.cena)
                elif "KOGENERACYJNA" in typ_oplaty_upper or "KOGENERACYJNA" in typ_oplaty_upper:
                    if o.strefa == "DZIENNA":
                        oplata_kogeneracyjna_dzienna = float(o.cena)
                    elif o.strefa == "NOCNA":
                        oplata_kogeneracyjna_nocna = float(o.cena)
            elif o.jednostka == "zł/mc":
                if "STAŁA SIECIOWA" in typ_oplaty_upper or "STALA SIECIOWA" in typ_oplaty_upper:
                    oplata_stala_sieciowa = float(o.cena)
                elif "PRZEJŚCIOWA" in typ_oplaty_upper or "PRZEJSCIOWA" in typ_oplaty_upper:
                    oplata_przejściowa = float(o.cena)
                elif "ABONAMENTOWA" in typ_oplaty_upper:
                    oplata_abonamentowa = float(o.cena)
                elif "MOCOWA" in typ_oplaty_upper:
                    oplata_mocowa = float(o.cena)
        
        # Obliczamy cenę za 1kWh dla okresu
        cena_1kwh_dzienna = None
        cena_1kwh_nocna = None
        cena_1kwh_calodobowa = None
        
        if cena_dzienna is not None:
            cena_1kwh_dzienna = cena_dzienna
            if oplata_jakosciowa_dzienna is not None:
                cena_1kwh_dzienna += oplata_jakosciowa_dzienna
            if oplata_zmienna_sieciowa_dzienna is not None:
                cena_1kwh_dzienna += oplata_zmienna_sieciowa_dzienna
            if oplata_oze_dzienna is not None:
                cena_1kwh_dzienna += oplata_oze_dzienna
            if oplata_kogeneracyjna_dzienna is not None:
                cena_1kwh_dzienna += oplata_kogeneracyjna_dzienna
            # Zaokrąglenie do 4 miejsc po przecinku
            cena_1kwh_dzienna = round(cena_1kwh_dzienna, 4)
        
        if cena_nocna is not None:
            cena_1kwh_nocna = cena_nocna
            if oplata_jakosciowa_nocna is not None:
                cena_1kwh_nocna += oplata_jakosciowa_nocna
            if oplata_zmienna_sieciowa_nocna is not None:
                cena_1kwh_nocna += oplata_zmienna_sieciowa_nocna
            if oplata_oze_nocna is not None:
                cena_1kwh_nocna += oplata_oze_nocna
            if oplata_kogeneracyjna_nocna is not None:
                cena_1kwh_nocna += oplata_kogeneracyjna_nocna
            # Zaokrąglenie do 4 miejsc po przecinku
            cena_1kwh_nocna = round(cena_1kwh_nocna, 4)
        
        if cena_calodobowa is not None:
            cena_1kwh_calodobowa = cena_calodobowa
            # Dla całodobowej opłaty mogą być bez strefy
            for o in oplaty_period:
                if o.jednostka == "kWh" and (o.strefa is None or o.strefa == "CAŁODOBOWA"):
                    if o.typ_oplaty in ["OPŁATA JAKOŚCIOWA", "OPŁATA ZMIENNA SIECIOWA", 
                                        "OPŁATA OZE", "OPŁATA KOGENERACYJNA"]:
                        cena_1kwh_calodobowa += float(o.cena)
        
        # Suma opłat stałych
        suma_oplat_stalych = 0
        if oplata_stala_sieciowa is not None:
            suma_oplat_stalych += oplata_stala_sieciowa
        if oplata_przejściowa is not None:
            suma_oplat_stalych += oplata_przejściowa
        if oplata_abonamentowa is not None:
            suma_oplat_stalych += oplata_abonamentowa
        if oplata_mocowa is not None:
            suma_oplat_stalych += oplata_mocowa
        
        periods.append({
            "okres": f"OKRES_DYSTRYBUCYJNY_{i+1}",
            "od": current_start,
            "do": dist_period_end,
            "ilosc_kwh_dzienna": ilosc_kwh_dzienna,
            "ilosc_kwh_nocna": ilosc_kwh_nocna,
            "ilosc_kwh_calodobowa": ilosc_kwh_calodobowa,
            "cena_dzienna": cena_dzienna,
            "cena_nocna": cena_nocna,
            "cena_calodobowa": cena_calodobowa,
            "oplata_jakosciowa_dzienna": oplata_jakosciowa_dzienna,
            "oplata_jakosciowa_nocna": oplata_jakosciowa_nocna,
            "oplata_zmienna_sieciowa_dzienna": oplata_zmienna_sieciowa_dzienna,
            "oplata_zmienna_sieciowa_nocna": oplata_zmienna_sieciowa_nocna,
            "oplata_oze_dzienna": oplata_oze_dzienna,
            "oplata_oze_nocna": oplata_oze_nocna,
            "oplata_kogeneracyjna_dzienna": oplata_kogeneracyjna_dzienna,
            "oplata_kogeneracyjna_nocna": oplata_kogeneracyjna_nocna,
            "cena_1kwh_dzienna": cena_1kwh_dzienna,
            "cena_1kwh_nocna": cena_1kwh_nocna,
            "cena_1kwh_calodobowa": cena_1kwh_calodobowa,
            "oplata_stala_sieciowa": oplata_stala_sieciowa,
            "oplata_przejściowa": oplata_przejściowa,
            "oplata_abonamentowa": oplata_abonamentowa,
            "oplata_mocowa": oplata_mocowa,
            "suma_oplat_stalych": suma_oplat_stalych
        })
        
        current_start = dist_period_end + timedelta(days=1)
    
    return periods


def get_tenant_billing_periods(db: Session) -> List[Dict]:
    """
    III. Pobieramy okresy rozliczeniowe najemców z electricity_readings.
    
    UWAGA: data_odczytu_licznika w odczycie reprezentuje datę faktycznego odczytu,
    która jest KOŃCEM okresu rozliczeniowego. Początek okresu to data_odczytu_licznika
    z poprzedniego odczytu + 1 dzień.
    """
    readings = db.query(ElectricityReading).order_by(ElectricityReading.data).all()
    
    periods = []
    for reading in readings:
        # Używamy data_odczytu_licznika jeśli jest dostępna, w przeciwnym razie obliczamy z reading.data
        if reading.data_odczytu_licznika:
            reading_date = reading.data_odczytu_licznika
        else:
            # Fallback: parsujemy datę z formatu 'YYYY-MM'
            year, month = map(int, reading.data.split('-'))
            # Zakładamy, że odczyty są około 10. dnia miesiąca
            reading_date = date(year, month, 10)
        
        periods.append({
            "data": reading.data,
            "data_odczytu": reading_date,
            "reading": reading
        })
    
    return periods


def calculate_bill_for_period(
    tenant_period_start: date,
    tenant_period_end: date,
    distribution_periods: List[Dict],
    usage_kwh_dzienna: float,
    usage_kwh_nocna: float,
    usage_kwh_calodobowa: Optional[float] = None
) -> Dict:
    """
    Oblicza rachunek dla okresu najemcy, uwzględniając różne okresy dystrybucyjne.
    """
    # Znajdujemy, które okresy dystrybucyjne pokrywają się z okresem najemcy
    overlapping_periods = []
    
    for dist_period in distribution_periods:
        # Sprawdzamy przecięcie okresów
        period_start = max(tenant_period_start, dist_period["od"])
        period_end = min(tenant_period_end, dist_period["do"])
        
        if period_start <= period_end:
            days = calculate_days_between(period_start, period_end)
            overlapping_periods.append({
                "period": dist_period,
                "days": days,
                "start": period_start,
                "end": period_end
            })
    
    if not overlapping_periods:
        return {
            "total_cost": 0,
            "details": []
        }
    
    total_days = sum(op["days"] for op in overlapping_periods)
    
    total_cost = 0
    details = []
    
    for op in overlapping_periods:
        period = op["period"]
        days = op["days"]
        proportion = days / total_days if total_days > 0 else 0
        
        # Obliczamy zużycie dla tej części okresu
        if usage_kwh_calodobowa is not None:
            # Taryfa całodobowa
            usage_part = usage_kwh_calodobowa * proportion
            cena_1kwh = period.get("cena_1kwh_calodobowa", 0) or 0
            energy_cost = usage_part * cena_1kwh
        else:
            # Taryfa dwutaryfowa
            usage_dzienna_part = usage_kwh_dzienna * proportion
            usage_nocna_part = usage_kwh_nocna * proportion
            
            cena_dzienna = period.get("cena_1kwh_dzienna", 0) or 0
            cena_nocna = period.get("cena_1kwh_nocna", 0) or 0
            
            energy_cost = (usage_dzienna_part * cena_dzienna) + (usage_nocna_part * cena_nocna)
        
        # Opłaty stałe proporcjonalnie
        suma_oplat_stalych = period.get("suma_oplat_stalych", 0) or 0
        fixed_cost = suma_oplat_stalych * proportion
        
        period_cost = energy_cost + fixed_cost
        total_cost += period_cost
        
        details.append({
            "period": period["okres"],
            "days": days,
            "proportion": proportion,
            "usage_dzienna": usage_kwh_dzienna * proportion if usage_kwh_calodobowa is None else None,
            "usage_nocna": usage_kwh_nocna * proportion if usage_kwh_calodobowa is None else None,
            "usage_calodobowa": usage_kwh_calodobowa * proportion if usage_kwh_calodobowa is not None else None,
            "energy_cost": energy_cost,
            "fixed_cost": fixed_cost,
            "period_cost": period_cost
        })
    
    return {
        "total_cost": total_cost,
        "details": details
    }


def main():
    """Główna funkcja wykonująca obliczenia."""
    parser = argparse.ArgumentParser(
        description="Obliczanie logiki generowania rachunków z faktur",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Przykłady użycia:
  python tools/calculate_bill_logic.py "P/23666363/0001/23" "P/23666363/0002/24"
        """
    )
    parser.add_argument(
        "invoice_prev",
        nargs="?",
        help="Numer faktury poprzedniej (np. 'P/23666363/0001/23')"
    )
    parser.add_argument(
        "invoice_current",
        nargs="?",
        help="Numer faktury obecnej (np. 'P/23666363/0002/24')"
    )
    
    args = parser.parse_args()
    
    if not args.invoice_prev or not args.invoice_current:
        parser.print_help()
        print("\n❌ Błąd: Musisz podać oba numery faktur jako argumenty!")
        print("Przykład: python tools/calculate_bill_logic.py 'P/23666363/0001/23' 'P/23666363/0002/24'")
        sys.exit(1)
    
    invoice_prev_number = args.invoice_prev
    invoice_current_number = args.invoice_current
    
    db = SessionLocal()
    
    try:
        # Pobieramy faktury
        invoice_prev = get_invoice_by_number(db, invoice_prev_number)
        invoice_current = get_invoice_by_number(db, invoice_current_number)
        
        if not invoice_prev:
            print(f"❌ Nie znaleziono faktury poprzedniej: {invoice_prev_number}")
            sys.exit(1)
        if not invoice_current:
            print(f"❌ Nie znaleziono faktury obecnej: {invoice_current_number}")
            sys.exit(1)
        
        print(f"Faktura poprzednia: {invoice_prev.numer_faktury}")
        print(f"Faktura obecna: {invoice_current.numer_faktury}")
        print()
        
        # I. Okresy z odczytów
        print("=" * 80)
        print("I. OKRESY Z ODCZYTÓW")
        print("=" * 80)
        periods_readings = get_periods_from_readings(db, invoice_prev, invoice_current)
        for period in periods_readings:
            print(f"{period['okres']}: {period['od']} - {period['do']}")
            print(f"  Dzienna: {period['dzienna_kwh']} kWh")
            print(f"  Nocna: {period['nocna_kwh']} kWh")
            print(f"  Całodobowa: {period['calodobowa_kwh']} kWh")
            print()
        
        # II. Okresy dystrybucyjne
        print("=" * 80)
        print("II. OKRESY DYSTRYBUCYJNE")
        print("=" * 80)
        distribution_periods = get_distribution_periods(db, invoice_current)
        for period in distribution_periods:
            print(f"{period['okres']}: {period['od']} - {period['do']}")
            print(f"  Ilość kWh dzienna: {period['ilosc_kwh_dzienna']}")
            print(f"  Ilość kWh nocna: {period['ilosc_kwh_nocna']}")
            print(f"  Cena 1kWh dzienna: {period.get('cena_1kwh_dzienna')}")
            print(f"  Cena 1kWh nocna: {period.get('cena_1kwh_nocna')}")
            print(f"  Suma opłat stałych: {period['suma_oplat_stalych']}")
            print()
        
        # III. Okresy najemców
        print("=" * 80)
        print("III. OKRESY NAJEMCÓW")
        print("=" * 80)
        tenant_periods = get_tenant_billing_periods(db)
        for period in tenant_periods:
            print(f"Data: {period['data']} ({period['data_odczytu']})")
        print()
        
        # III. Obliczamy rachunki dla najemców
        print("=" * 80)
        print("III. OBLICZANIE RACHUNKÓW DLA NAJEMCÓW")
        print("=" * 80)
        
        # Filtrujemy okresy najemców, które są w okresie faktury obecnej
        invoice_start = invoice_current.data_poczatku_okresu
        invoice_end = invoice_current.data_konca_okresu
        
        relevant_tenant_periods = [
            tp for tp in tenant_periods
            if invoice_start <= tp['data_odczytu'] <= invoice_end
        ]
        
        # Obliczamy rachunki dla każdego okresu rozliczeniowego najemców
        bills_calculations = {}
        locals_list = ['gora', 'dol', 'gabinet']
        
        for i, tenant_period in enumerate(relevant_tenant_periods):
            if i == 0:
                continue  # Pomijamy pierwszy okres (nie ma poprzedniego)
            
            prev_period = relevant_tenant_periods[i-1]
            # Okres rozliczeniowy: od dnia PO poprzednim odczycie do dnia bieżącego odczytu
            period_start = prev_period['data_odczytu'] + timedelta(days=1)
            period_end = tenant_period['data_odczytu']
            
            # Obliczamy zużycie dla tego okresu
            current_reading = tenant_period['reading']
            previous_reading = prev_period['reading']  # Używamy poprzedniego okresu zamiast get_previous_reading
            usage_data = calculate_all_usage(current_reading, previous_reading)
            
            # Nazwa okresu z faktycznymi datami dla czytelności
            period_key = f"{prev_period['data']} - {tenant_period['data']} ({period_start.strftime('%d.%m.%Y')} - {period_end.strftime('%d.%m.%Y')})"
            bills_calculations[period_key] = {
                "start": period_start,
                "end": period_end,
                "usage": usage_data,
                "bills": {},
                "prev_reading": previous_reading,
                "current_reading": current_reading
            }
            
            # Obliczamy rachunek dla każdego lokalu
            for local_name in locals_list:
                if local_name == 'gora':
                    # GORA używa kluczy: zuzycie_gora_I (dzienna) i zuzycie_gora_II (nocna)
                    gora_data = usage_data.get('gora', {})
                    usage_dzienna_val = gora_data.get('zuzycie_gora_I')
                    usage_nocna_val = gora_data.get('zuzycie_gora_II')
                    usage_lacznie = gora_data.get('zuzycie_gora_lacznie', 0) or 0
                    
                    # Jeśli mamy rozdzielone taryfy, użyj ich
                    if usage_dzienna_val is not None and usage_nocna_val is not None:
                        usage_dzienna = usage_dzienna_val
                        usage_nocna = usage_nocna_val
                    # Jeśli nie mamy rozdzielonych, użyj łącznego i podziel proporcjonalnie
                    # na podstawie proporcji z całego domu
                    elif usage_lacznie > 0:
                        # Pobierz proporcje z domu
                        dom_dzienna = usage_data.get('dom', {}).get('zuzycie_dom_I')
                        dom_nocna = usage_data.get('dom', {}).get('zuzycie_dom_II')
                        dom_lacznie = usage_data.get('dom', {}).get('zuzycie_dom_lacznie', 0) or 0
                        
                        if dom_lacznie > 0 and dom_dzienna is not None and dom_nocna is not None:
                            # Użyj proporcji z domu
                            ratio_dzienna = dom_dzienna / dom_lacznie if dom_lacznie > 0 else 0.7
                            ratio_nocna = dom_nocna / dom_lacznie if dom_lacznie > 0 else 0.3
                            usage_dzienna = usage_lacznie * ratio_dzienna
                            usage_nocna = usage_lacznie * ratio_nocna
                        else:
                            # Domyślna proporcja 70% dzienna, 30% nocna
                            usage_dzienna = usage_lacznie * 0.7
                            usage_nocna = usage_lacznie * 0.3
                    else:
                        usage_dzienna = 0
                        usage_nocna = 0
                elif local_name == 'dol':
                    # DÓŁ używa kluczy: zuzycie_dol_I (dzienna) i zuzycie_dol_II (nocna)
                    dol_data = usage_data.get('dol', {})
                    usage_dzienna_val = dol_data.get('zuzycie_dol_I')
                    usage_nocna_val = dol_data.get('zuzycie_dol_II')
                    usage_lacznie = dol_data.get('zuzycie_dol_lacznie', 0) or 0
                    
                    # Jeśli mamy rozdzielone taryfy, użyj ich
                    if usage_dzienna_val is not None and usage_nocna_val is not None:
                        usage_dzienna = usage_dzienna_val
                        usage_nocna = usage_nocna_val
                    # Jeśli nie mamy rozdzielonych, użyj łącznego i podziel proporcjonalnie
                    elif usage_lacznie > 0:
                        # Pobierz proporcje z domu
                        dom_dzienna = usage_data.get('dom', {}).get('zuzycie_dom_I')
                        dom_nocna = usage_data.get('dom', {}).get('zuzycie_dom_II')
                        dom_lacznie = usage_data.get('dom', {}).get('zuzycie_dom_lacznie', 0) or 0
                        
                        if dom_lacznie > 0 and dom_dzienna is not None and dom_nocna is not None:
                            # Użyj proporcji z domu
                            ratio_dzienna = dom_dzienna / dom_lacznie if dom_lacznie > 0 else 0.7
                            ratio_nocna = dom_nocna / dom_lacznie if dom_lacznie > 0 else 0.3
                            usage_dzienna = usage_lacznie * ratio_dzienna
                            usage_nocna = usage_lacznie * ratio_nocna
                        else:
                            # Domyślna proporcja 70% dzienna, 30% nocna
                            usage_dzienna = usage_lacznie * 0.7
                            usage_nocna = usage_lacznie * 0.3
                    else:
                        usage_dzienna = 0
                        usage_nocna = 0
                elif local_name == 'gabinet':
                    # GABINET - sprawdź czy ma rozdzielone taryfy (aproksymacja 70%/30%)
                    gabinet_data = usage_data.get('gabinet', {})
                    usage_total = gabinet_data.get('zuzycie_gabinet', 0) or 0
                    usage_dzienna_val = gabinet_data.get('zuzycie_gabinet_dzienna')
                    usage_nocna_val = gabinet_data.get('zuzycie_gabinet_nocna')
                    
                    if usage_dzienna_val is not None and usage_nocna_val is not None:
                        # GABINET ma aproksymację 70%/30%
                        usage_dzienna = usage_dzienna_val
                        usage_nocna = usage_nocna_val
                    else:
                        # GABINET bez rozdzielonych taryf - dzienna = całkowita
                        usage_dzienna = usage_total
                        usage_nocna = 0
                
                bill_result = calculate_bill_for_period(
                    period_start,
                    period_end,
                    distribution_periods,
                    usage_dzienna,
                    usage_nocna,
                    None
                )
                
                bills_calculations[period_key]["bills"][local_name] = {
                    "usage_dzienna": usage_dzienna,
                    "usage_nocna": usage_nocna,
                    "total_cost": bill_result["total_cost"],
                    "details": bill_result["details"]
                }
            
            # Obliczamy DOM jako sumę wszystkich lokali dla tego okresu
            dom_usage_dzienna = 0
            dom_usage_nocna = 0
            dom_total_cost = 0
            dom_details = []
            
            for local_name in ['gora', 'dol', 'gabinet']:
                if local_name in bills_calculations[period_key]["bills"]:
                    bill_data = bills_calculations[period_key]["bills"][local_name]
                    dom_usage_dzienna += bill_data['usage_dzienna']
                    dom_usage_nocna += bill_data['usage_nocna']
                    dom_total_cost += bill_data['total_cost']
            
            # Agregujemy szczegóły dla DOM (sumujemy koszty energii i opłaty stałe z każdego okresu dystrybucyjnego)
            # Tworzymy mapę okresów dystrybucyjnych
            dom_details_map = {}
            for local_name in ['gora', 'dol', 'gabinet']:
                if local_name in bills_calculations[period_key]["bills"]:
                    bill_data = bills_calculations[period_key]["bills"][local_name]
                    for detail in bill_data['details']:
                        period_name = detail['period']
                        if period_name not in dom_details_map:
                            dom_details_map[period_name] = {
                                'period': period_name,
                                'days': detail['days'],
                                'proportion': detail['proportion'],
                                'usage_dzienna': 0,
                                'usage_nocna': 0,
                                'energy_cost': 0,
                                'fixed_cost': 0,
                                'period_cost': 0
                            }
                        dom_details_map[period_name]['usage_dzienna'] += detail.get('usage_dzienna', 0) or 0
                        dom_details_map[period_name]['usage_nocna'] += detail.get('usage_nocna', 0) or 0
                        dom_details_map[period_name]['energy_cost'] += detail['energy_cost']
                        dom_details_map[period_name]['fixed_cost'] += detail['fixed_cost']
                        dom_details_map[period_name]['period_cost'] += detail['period_cost']
            
            dom_details = list(dom_details_map.values())
            
            # Dodajemy DOM jako pierwszy w bills
            dom_bills = {
                "usage_dzienna": dom_usage_dzienna,
                "usage_nocna": dom_usage_nocna,
                "total_cost": dom_total_cost,
                "details": dom_details
            }
            # Tworzymy nowy słownik z DOM jako pierwszym
            new_bills = {"dom": dom_bills}
            new_bills.update(bills_calculations[period_key]["bills"])
            bills_calculations[period_key]["bills"] = new_bills
        
        # Zapisujemy wyniki do pliku .md
        with open("docs/BILL_CALCULATION_LOGIC.md", "w", encoding="utf-8") as f:
            f.write("# Obliczenia logiki generowania rachunków\n\n")
            f.write(f"**Faktura poprzednia:** {invoice_prev.numer_faktury}\n")
            f.write(f"**Faktura obecna:** {invoice_current.numer_faktury}\n")
            f.write(f"**Okres faktury obecnej:** {invoice_current.data_poczatku_okresu} - {invoice_current.data_konca_okresu}\n\n")
            
            f.write("## I. Okresy z odczytów\n\n")
            for period in periods_readings:
                f.write(f"### {period['okres']}\n\n")
                f.write(f"- **Od:** {period['od']}\n")
                f.write(f"- **Do:** {period['do']}\n")
                f.write(f"- **Dzienna:** {period['dzienna_kwh']} kWh\n")
                f.write(f"- **Nocna:** {period['nocna_kwh']} kWh\n")
                f.write(f"- **Całodobowa:** {period['calodobowa_kwh']} kWh\n\n")
            
            f.write("## II. Okresy dystrybucyjne\n\n")
            for period in distribution_periods:
                f.write(f"### {period['okres']} ({period['od']} - {period['do']})\n\n")
                f.write(f"- **Od:** {period['od']}\n")
                f.write(f"- **Do:** {period['do']}\n")
                f.write(f"- **Ilość kWh dzienna:** {period['ilosc_kwh_dzienna']}\n")
                f.write(f"- **Ilość kWh nocna:** {period['ilosc_kwh_nocna']}\n")
                cena_dzienna = period.get('cena_1kwh_dzienna')
                cena_nocna = period.get('cena_1kwh_nocna')
                if cena_dzienna is not None:
                    f.write(f"- **Cena 1kWh dzienna:** {round(cena_dzienna, 4)}\n")
                else:
                    f.write(f"- **Cena 1kWh dzienna:** -\n")
                if cena_nocna is not None:
                    f.write(f"- **Cena 1kWh nocna:** {round(cena_nocna, 4)}\n")
                else:
                    f.write(f"- **Cena 1kWh nocna:** -\n")
                f.write(f"- **Suma opłat stałych:** {period['suma_oplat_stalych']}\n\n")
            
            f.write("## III. Obliczenia rachunków dla najemców\n\n")
            for period_key, period_data in bills_calculations.items():
                f.write(f"### Okres rozliczeniowy: {period_key}\n\n")
                f.write(f"- **Od:** {period_data['start']}\n")
                f.write(f"- **Do:** {period_data['end']}\n\n")
                
                # Kolejność: DOM, GÓRA, DÓŁ, GABINET
                display_order = ['dom', 'gora', 'dol', 'gabinet']
                for local_name in display_order:
                    if local_name not in period_data['bills']:
                        continue
                    bill_data = period_data['bills'][local_name]
                    usage_data_period = period_data['usage']
                    f.write(f"#### Lokal: {local_name.upper()}\n\n")
                    f.write(f"- **Zużycie dzienne:** {bill_data['usage_dzienna']:.2f} kWh\n")
                    f.write(f"- **Zużycie nocne:** {bill_data['usage_nocna']:.2f} kWh\n")
                    
                    # Zużycie całkowite
                    usage_total = bill_data['usage_dzienna'] + bill_data['usage_nocna']
                    f.write(f"- **Zużycie całkowite:** {usage_total:.2f} kWh\n")
                    f.write(f"  *Równanie:* `zużycie_całkowite = zużycie_dzienne + zużycie_nocne = {bill_data['usage_dzienna']:.2f} + {bill_data['usage_nocna']:.2f} = {usage_total:.2f} kWh`\n")
                    
                    # Koszt za 1kWh
                    if usage_total > 0:
                        cost_per_kwh = bill_data['total_cost'] / usage_total
                        f.write(f"- **Koszt za 1kWh:** {cost_per_kwh:.4f} zł/kWh\n")
                        f.write(f"  *Równanie:* `koszt_za_1kWh = koszt_całkowity / zużycie_całkowite = {bill_data['total_cost']:.4f} / {usage_total:.2f} = {cost_per_kwh:.4f} zł/kWh`\n")
                    else:
                        f.write(f"- **Koszt za 1kWh:** -\n")
                    
                    f.write(f"- **Koszt całkowity:** {bill_data['total_cost']:.4f} zł\n")
                    # Równanie dla kosztu całkowitego
                    total_cost_parts = [d['period_cost'] for d in bill_data['details']]
                    if len(total_cost_parts) > 0:
                        cost_sum_str = " + ".join([f"{p:.4f}" for p in total_cost_parts])
                        f.write(f"  *Równanie:* `koszt_całkowity = suma_kosztów_okresów = {cost_sum_str} = {bill_data['total_cost']:.4f} zł`\n")
                        f.write(f"  *(Źródło: suma kosztów ze wszystkich okresów dystrybucyjnych pokrywających się z okresem rozliczeniowym)*\n")
                    f.write("\n")
                    
                    # Dodaj równania dla zużycia całkowitego
                    f.write("**Obliczenie zużycia całkowitego:**\n\n")
                    prev_reading = period_data.get('prev_reading')
                    current_reading = period_data.get('current_reading')
                    
                    if local_name == 'dom':
                        dom_data = usage_data_period.get('dom', {})
                        if prev_reading and current_reading:
                            if not current_reading.licznik_dom_jednotaryfowy and not prev_reading.licznik_dom_jednotaryfowy:
                                f.write(f"- *Zużycie dzienne:* `zuzycie_dom_I = odczyt_dom_I_obecny - odczyt_dom_I_poprzedni = {current_reading.odczyt_dom_I} - {prev_reading.odczyt_dom_I} = {dom_data.get('zuzycie_dom_I', 0):.2f} kWh`\n")
                                f.write(f"  *(Źródło: `odczyt_dom_I` z tabeli `electricity_readings` dla okresów {prev_reading.data} i {current_reading.data})*\n")
                                f.write(f"- *Zużycie nocne:* `zuzycie_dom_II = odczyt_dom_II_obecny - odczyt_dom_II_poprzedni = {current_reading.odczyt_dom_II} - {prev_reading.odczyt_dom_II} = {dom_data.get('zuzycie_dom_II', 0):.2f} kWh`\n")
                                f.write(f"  *(Źródło: `odczyt_dom_II` z tabeli `electricity_readings` dla okresów {prev_reading.data} i {current_reading.data})*\n")
                            else:
                                f.write(f"- *Zużycie łączne:* `zuzycie_dom = odczyt_dom_obecny - odczyt_dom_poprzedni`\n")
                                f.write(f"  *(Źródło: `odczyt_dom` z tabeli `electricity_readings`)*\n")
                    elif local_name == 'gora':
                        gora_data = usage_data_period.get('gora', {})
                        dom_data = usage_data_period.get('dom', {})
                        # GÓRA = DOM - DÓŁ (z odczytu, który zawiera GABINET)
                        # Musimy obliczyć zużycie z odczytu DÓŁ
                        dol_reading_I = None
                        dol_reading_II = None
                        if prev_reading and current_reading:
                            if not current_reading.licznik_dol_jednotaryfowy and not prev_reading.licznik_dol_jednotaryfowy:
                                dol_reading_I = current_reading.odczyt_dol_I - prev_reading.odczyt_dol_I
                                dol_reading_II = current_reading.odczyt_dol_II - prev_reading.odczyt_dol_II
                            elif current_reading.licznik_dol_jednotaryfowy and prev_reading.licznik_dol_jednotaryfowy:
                                dol_reading_total = current_reading.odczyt_dol - prev_reading.odczyt_dol
                                # Aproksymacja 70%/30% jeśli brak rozdzielonych taryf
                                dol_reading_I = dol_reading_total * 0.7
                                dol_reading_II = dol_reading_total * 0.3
                        
                        if dol_reading_I is not None and dol_reading_II is not None:
                            f.write(f"- *Zużycie dzienne:* `zuzycie_gora_I = zuzycie_dom_I - zuzycie_dol_z_odczytu_I = {dom_data.get('zuzycie_dom_I', 0):.2f} - {dol_reading_I:.2f} = {gora_data.get('zuzycie_gora_I', 0):.2f} kWh`\n")
                            f.write(f"  *(Źródło: `zuzycie_dom_I` z odczytu głównego licznika DOM, `zuzycie_dol_z_odczytu_I` z odczytu podlicznika DÓŁ - zawiera GABINET)*\n")
                            f.write(f"- *Zużycie nocne:* `zuzycie_gora_II = zuzycie_dom_II - zuzycie_dol_z_odczytu_II = {dom_data.get('zuzycie_dom_II', 0):.2f} - {dol_reading_II:.2f} = {gora_data.get('zuzycie_gora_II', 0):.2f} kWh`\n")
                            f.write(f"  *(Źródło: `zuzycie_dom_II` z odczytu głównego licznika DOM, `zuzycie_dol_z_odczytu_II` z odczytu podlicznika DÓŁ - zawiera GABINET)*\n")
                        else:
                            f.write(f"- *Zużycie dzienne:* `zuzycie_gora_I = zuzycie_dom_I - zuzycie_dol_z_odczytu_I`\n")
                            f.write(f"  *(Źródło: obliczane jako różnica między zużyciem DOM a zużyciem z odczytu DÓŁ)*\n")
                            f.write(f"- *Zużycie nocne:* `zuzycie_gora_II = zuzycie_dom_II - zuzycie_dol_z_odczytu_II`\n")
                            f.write(f"  *(Źródło: obliczane jako różnica między zużyciem DOM a zużyciem z odczytu DÓŁ)*\n")
                    elif local_name == 'dol':
                        dol_data = usage_data_period.get('dol', {})
                        gabinet_data = usage_data_period.get('gabinet', {})
                        gabinet_total = gabinet_data.get('zuzycie_gabinet', 0) or 0
                        dol_usage_total = dol_data.get('zuzycie_dol_lacznie', 0) or 0
                        
                        # Obliczamy zużycie z odczytu DÓŁ (które zawiera GABINET)
                        dol_reading_total = dol_usage_total + gabinet_total
                        
                        f.write(f"- *Zużycie łączne z odczytu DÓŁ (zawiera GABINET):* ")
                        if prev_reading and current_reading:
                            if not current_reading.licznik_dol_jednotaryfowy and not prev_reading.licznik_dol_jednotaryfowy:
                                dol_I_reading = current_reading.odczyt_dol_I - prev_reading.odczyt_dol_I
                                dol_II_reading = current_reading.odczyt_dol_II - prev_reading.odczyt_dol_II
                                dol_reading_total_calc = dol_I_reading + dol_II_reading
                                f.write(f"`zuzycie_dol_z_odczytu = (odczyt_dol_I_obecny - odczyt_dol_I_poprzedni) + (odczyt_dol_II_obecny - odczyt_dol_II_poprzedni) = ({current_reading.odczyt_dol_I} - {prev_reading.odczyt_dol_I}) + ({current_reading.odczyt_dol_II} - {prev_reading.odczyt_dol_II}) = {dol_reading_total_calc:.2f} kWh`\n")
                                f.write(f"  *(Źródło: `odczyt_dol_I` i `odczyt_dol_II` z tabeli `electricity_readings`)*\n")
                            elif current_reading.licznik_dol_jednotaryfowy and prev_reading.licznik_dol_jednotaryfowy:
                                dol_reading_total_calc = current_reading.odczyt_dol - prev_reading.odczyt_dol
                                f.write(f"`zuzycie_dol_z_odczytu = odczyt_dol_obecny - odczyt_dol_poprzedni = {current_reading.odczyt_dol} - {prev_reading.odczyt_dol} = {dol_reading_total_calc:.2f} kWh`\n")
                                f.write(f"  *(Źródło: `odczyt_dol` z tabeli `electricity_readings`)*\n")
                        else:
                            f.write(f"`zuzycie_dol_z_odczytu = {dol_reading_total:.2f} kWh`\n")
                            f.write(f"  *(Źródło: obliczane z odczytów podlicznika DÓŁ)*\n")
                        
                        f.write(f"- *Zużycie łączne (Mikołaj):* `zuzycie_dol = zuzycie_dol_z_odczytu - zuzycie_gabinet = {dol_reading_total:.2f} - {gabinet_total:.2f} = {dol_usage_total:.2f} kWh`\n")
                        f.write(f"  *(Źródło: `zuzycie_dol_z_odczytu` z odczytu podlicznika DÓŁ, `zuzycie_gabinet` z odczytu podlicznika GABINET)*\n")
                        
                        if dol_data.get('zuzycie_dol_I') is not None and dol_data.get('zuzycie_dol_II') is not None:
                            dol_I = dol_data.get('zuzycie_dol_I', 0)
                            dol_II = dol_data.get('zuzycie_dol_II', 0)
                            gabinet_dzienna = gabinet_data.get('zuzycie_gabinet_dzienna')
                            gabinet_nocna = gabinet_data.get('zuzycie_gabinet_nocna')
                            
                            if prev_reading and current_reading and not current_reading.licznik_dol_jednotaryfowy and not prev_reading.licznik_dol_jednotaryfowy:
                                dol_I_reading = current_reading.odczyt_dol_I - prev_reading.odczyt_dol_I
                                dol_II_reading = current_reading.odczyt_dol_II - prev_reading.odczyt_dol_II
                                if gabinet_dzienna is not None and gabinet_nocna is not None:
                                    f.write(f"- *Zużycie dzienne:* `zuzycie_dol_I = zuzycie_dol_z_odczytu_I - zuzycie_gabinet_dzienna = {dol_I_reading:.2f} - {gabinet_dzienna:.2f} = {dol_I:.2f} kWh`\n")
                                    f.write(f"  *(Źródło: `odczyt_dol_I` z tabeli `electricity_readings`, `zuzycie_gabinet_dzienna` z aproksymacji 70%)*\n")
                                    f.write(f"- *Zużycie nocne:* `zuzycie_dol_II = zuzycie_dol_z_odczytu_II - zuzycie_gabinet_nocna = {dol_II_reading:.2f} - {gabinet_nocna:.2f} = {dol_II:.2f} kWh`\n")
                                    f.write(f"  *(Źródło: `odczyt_dol_II` z tabeli `electricity_readings`, `zuzycie_gabinet_nocna` z aproksymacji 30%)*\n")
                                else:
                                    f.write(f"- *Zużycie dzienne:* `zuzycie_dol_I = zuzycie_dol × (zuzycie_dol_z_odczytu_I / zuzycie_dol_z_odczytu_łącznie) = {dol_usage_total:.2f} × ({dol_I_reading:.2f} / {dol_reading_total:.2f}) = {dol_I:.2f} kWh`\n")
                                    f.write(f"  *(Źródło: proporcjonalny podział na podstawie proporcji z odczytu DÓŁ)*\n")
                                    f.write(f"- *Zużycie nocne:* `zuzycie_dol_II = zuzycie_dol × (zuzycie_dol_z_odczytu_II / zuzycie_dol_z_odczytu_łącznie) = {dol_usage_total:.2f} × ({dol_II_reading:.2f} / {dol_reading_total:.2f}) = {dol_II:.2f} kWh`\n")
                                    f.write(f"  *(Źródło: proporcjonalny podział na podstawie proporcji z odczytu DÓŁ)*\n")
                            else:
                                f.write(f"- *Zużycie dzienne:* `zuzycie_dol_I = zuzycie_dol × 0.70 = {dol_usage_total:.2f} × 0.70 = {dol_I:.2f} kWh`\n")
                                f.write(f"  *(Źródło: aproksymacja 70% dzienna, 30% nocna)*\n")
                                f.write(f"- *Zużycie nocne:* `zuzycie_dol_II = zuzycie_dol × 0.30 = {dol_usage_total:.2f} × 0.30 = {dol_II:.2f} kWh`\n")
                                f.write(f"  *(Źródło: aproksymacja 70% dzienna, 30% nocna)*\n")
                    elif local_name == 'gabinet':
                        gabinet_data = usage_data_period.get('gabinet', {})
                        if prev_reading and current_reading:
                            if current_reading.odczyt_gabinet and prev_reading.odczyt_gabinet:
                                f.write(f"- *Zużycie łączne:* `zuzycie_gabinet = odczyt_gabinet_obecny - odczyt_gabinet_poprzedni = {current_reading.odczyt_gabinet} - {prev_reading.odczyt_gabinet} = {gabinet_data.get('zuzycie_gabinet', 0):.2f} kWh`\n")
                                f.write(f"  *(Źródło: `odczyt_gabinet` z tabeli `electricity_readings`)*\n")
                        f.write(f"- *Zużycie dzienne:* `zuzycie_gabinet_dzienna = zuzycie_gabinet × 0.70 = {gabinet_data.get('zuzycie_gabinet', 0):.2f} × 0.70 = {gabinet_data.get('zuzycie_gabinet_dzienna', 0):.2f} kWh`\n")
                        f.write(f"  *(Źródło: aproksymacja 70% dzienna, 30% nocna)*\n")
                        f.write(f"- *Zużycie nocne:* `zuzycie_gabinet_nocna = zuzycie_gabinet × 0.30 = {gabinet_data.get('zuzycie_gabinet', 0):.2f} × 0.30 = {gabinet_data.get('zuzycie_gabinet_nocna', 0):.2f} kWh`\n")
                        f.write(f"  *(Źródło: aproksymacja 70% dzienna, 30% nocna)*\n")
                    
                    f.write("\n")
                    
                    f.write("**Szczegóły obliczeń:**\n\n")
                    for detail in bill_data['details']:
                        period_info = detail['period']
                        dist_period = None
                        for dp in distribution_periods:
                            if dp['okres'] == period_info:
                                dist_period = dp
                                break
                        
                        # Dodajemy daty do nazwy okresu dystrybucyjnego
                        period_name = detail['period']
                        if dist_period:
                            period_name = f"{detail['period']} ({dist_period['od']} - {dist_period['do']})"
                        
                        f.write(f"- **{period_name}:**\n")
                        f.write(f"  - Dni: {detail['days']}\n")
                        
                        # Równanie dla proporcji
                        total_days = sum(d['days'] for d in bill_data['details'])
                        # Obliczamy daty przecięcia okresów
                        tenant_period_start = period_data['start']
                        tenant_period_end = period_data['end']
                        dist_period_start = dist_period['od'] if dist_period else None
                        dist_period_end = dist_period['do'] if dist_period else None
                        
                        f.write(f"  - Proporcja: {detail['proportion']:.4f} ({detail['proportion']*100:.2f}%)\n")
                        if dist_period_start and dist_period_end:
                            # Obliczamy przecięcie okresów
                            overlap_start = max(tenant_period_start, dist_period_start)
                            overlap_end = min(tenant_period_end, dist_period_end)
                            f.write(f"    *Obliczenie dni w przecięciu:* `dni_w_okresie = max(okres_najemcy_start, okres_dystrybucyjny_start) do min(okres_najemcy_end, okres_dystrybucyjny_end) = max({tenant_period_start}, {dist_period_start}) do min({tenant_period_end}, {dist_period_end}) = {overlap_start} do {overlap_end} = {detail['days']} dni`\n")
                            f.write(f"    *Obliczenie dni całkowitych:* `dni_całkowite = suma dni wszystkich przecięć okresów dystrybucyjnych z okresem najemcy = {total_days} dni`\n")
                        f.write(f"    *Równanie:* `proporcja = dni_w_okresie / dni_całkowite = {detail['days']} / {total_days} = {detail['proportion']:.4f}`\n")
                        f.write(f"    *(Źródło: obliczane na podstawie przecięcia okresu rozliczeniowego najemcy ({tenant_period_start} - {tenant_period_end}) z okresem dystrybucyjnym)*\n")
                        
                        # Równania dla zużycia
                        if detail['usage_dzienna'] is not None:
                            f.write(f"  - Zużycie dzienne: {detail['usage_dzienna']:.2f} kWh\n")
                            f.write(f"    *Równanie:* `zużycie_dzienne = zużycie_całkowite_dzienne × proporcja = {bill_data['usage_dzienna']:.2f} × {detail['proportion']:.4f} = {detail['usage_dzienna']:.2f} kWh`\n")
                            f.write(f"    *(Źródło: `zużycie_całkowite_dzienne` z odczytów liczników w tabeli `electricity_readings`)*\n")
                        if detail['usage_nocna'] is not None:
                            f.write(f"  - Zużycie nocne: {detail['usage_nocna']:.2f} kWh\n")
                            f.write(f"    *Równanie:* `zużycie_nocne = zużycie_całkowite_nocne × proporcja = {bill_data['usage_nocna']:.2f} × {detail['proportion']:.4f} = {detail['usage_nocna']:.2f} kWh`\n")
                            f.write(f"    *(Źródło: `zużycie_całkowite_nocne` z odczytów liczników w tabeli `electricity_readings`)*\n")
                        
                        # Równanie dla kosztu energii
                        f.write(f"  - Koszt energii: {detail['energy_cost']:.4f} zł\n")
                        if detail['usage_dzienna'] is not None and detail['usage_nocna'] is not None:
                            cena_dzienna = dist_period.get('cena_1kwh_dzienna', 0) if dist_period else 0
                            cena_nocna = dist_period.get('cena_1kwh_nocna', 0) if dist_period else 0
                            koszt_dzienna_czesc = detail['usage_dzienna'] * cena_dzienna
                            koszt_nocna_czesc = detail['usage_nocna'] * cena_nocna
                            f.write(f"    *Równanie:* `koszt_energii = (zużycie_dzienne × cena_dzienna) + (zużycie_nocne × cena_nocna) = ({detail['usage_dzienna']:.2f} × {cena_dzienna:.4f}) + ({detail['usage_nocna']:.2f} × {cena_nocna:.4f}) = {detail['energy_cost']:.4f} zł`\n")
                            f.write(f"    *(Źródło: `cena_1kwh_dzienna` i `cena_1kwh_nocna` z okresu dystrybucyjnego, obliczone z tabel `electricity_invoice_sprzedaz_energii` i `electricity_invoice_oplata_dystrybucyjna`)*\n")
                            f.write(f"\n")
                            f.write(f"    **SPRAWDZENIE (cena 1kWh × zużycie w danym okresie dystrybucyjnym):**\n")
                            f.write(f"    - `koszt_dzienna = cena_1kWh_dzienna × zużycie_dzienne = {cena_dzienna:.4f} zł/kWh × {detail['usage_dzienna']:.2f} kWh = {koszt_dzienna_czesc:.4f} zł`\n")
                            f.write(f"    - `koszt_nocna = cena_1kWh_nocna × zużycie_nocne = {cena_nocna:.4f} zł/kWh × {detail['usage_nocna']:.2f} kWh = {koszt_nocna_czesc:.4f} zł`\n")
                            f.write(f"    - `koszt_energii = koszt_dzienna + koszt_nocna = {koszt_dzienna_czesc:.4f} zł + {koszt_nocna_czesc:.4f} zł = {detail['energy_cost']:.4f} zł`\n")
                        
                        # Równanie dla opłat stałych
                        f.write(f"  - Opłaty stałe: {detail['fixed_cost']:.4f} zł\n")
                        suma_oplat = dist_period.get('suma_oplat_stalych', 0) if dist_period else 0
                        f.write(f"    *Równanie:* `opłaty_stałe = suma_oplat_stalych × proporcja = {suma_oplat:.4f} × {detail['proportion']:.4f} = {detail['fixed_cost']:.4f} zł`\n")
                        f.write(f"    *(Źródło: `suma_oplat_stalych` z okresu dystrybucyjnego, obliczone z tabeli `electricity_invoice_oplata_dystrybucyjna`)*\n")
                        
                        # Równanie dla kosztu okresu
                        f.write(f"  - Koszt okresu: {detail['period_cost']:.4f} zł\n")
                        f.write(f"    *Równanie:* `koszt_okresu = koszt_energii + opłaty_stałe = {detail['energy_cost']:.4f} + {detail['fixed_cost']:.4f} = {detail['period_cost']:.4f} zł`\n\n")
                
                f.write("\n")
            
            # Obliczamy sumy dla całego DOMU
            total_dom_usage_dzienna = 0
            total_dom_usage_nocna = 0
            total_dom_cost = 0
            total_dom_usage_lacznie = 0
            
            # Sumy per lokal
            total_gora_usage_dzienna = 0
            total_gora_usage_nocna = 0
            total_gora_cost = 0
            total_dol_usage_dzienna = 0
            total_dol_usage_nocna = 0
            total_dol_cost = 0
            total_gabinet_usage_dzienna = 0
            total_gabinet_usage_nocna = 0
            total_gabinet_cost = 0
            
            for period_data in bills_calculations.values():
                for local_name, bill_data in period_data['bills'].items():
                    usage_dz = bill_data['usage_dzienna']
                    usage_noc = bill_data['usage_nocna']
                    cost = bill_data['total_cost']
                    
                    total_dom_usage_dzienna += usage_dz
                    total_dom_usage_nocna += usage_noc
                    total_dom_cost += cost
                    total_dom_usage_lacznie += (usage_dz + usage_noc)
                    
                    if local_name == 'gora':
                        total_gora_usage_dzienna += usage_dz
                        total_gora_usage_nocna += usage_noc
                        total_gora_cost += cost
                    elif local_name == 'dol':
                        total_dol_usage_dzienna += usage_dz
                        total_dol_usage_nocna += usage_noc
                        total_dol_cost += cost
                    elif local_name == 'gabinet':
                        total_gabinet_usage_dzienna += usage_dz
                        total_gabinet_usage_nocna += usage_noc
                        total_gabinet_cost += cost
            
            # Dodajemy sekcję z danymi dla całego DOMU
            f.write("## IV. Podsumowanie dla całego DOMU\n\n")
            f.write("### Całkowite zużycie energii\n\n")
            f.write(f"- **Zużycie dzienne:** {total_dom_usage_dzienna:.2f} kWh\n")
            f.write(f"- **Zużycie nocne:** {total_dom_usage_nocna:.2f} kWh\n")
            f.write(f"- **Zużycie łączne:** {total_dom_usage_lacznie:.2f} kWh\n\n")
            
            f.write("### Rozkład zużycia na lokale\n\n")
            f.write("#### GÓRA:\n")
            f.write(f"- Zużycie dzienne: {total_gora_usage_dzienna:.2f} kWh\n")
            f.write(f"- Zużycie nocne: {total_gora_usage_nocna:.2f} kWh\n")
            f.write(f"- Zużycie łączne: {total_gora_usage_dzienna + total_gora_usage_nocna:.2f} kWh\n")
            f.write(f"- Koszt całkowity: {total_gora_cost:.2f} zł\n\n")
            
            f.write("#### DÓŁ (Mikołaj):\n")
            f.write(f"- Zużycie dzienne: {total_dol_usage_dzienna:.2f} kWh\n")
            f.write(f"- Zużycie nocne: {total_dol_usage_nocna:.2f} kWh\n")
            f.write(f"- Zużycie łączne: {total_dol_usage_dzienna + total_dol_usage_nocna:.2f} kWh\n")
            f.write(f"- Koszt całkowity: {total_dol_cost:.2f} zł\n\n")
            
            f.write("#### GABINET:\n")
            f.write(f"- Zużycie dzienne: {total_gabinet_usage_dzienna:.2f} kWh\n")
            f.write(f"- Zużycie nocne: {total_gabinet_usage_nocna:.2f} kWh\n")
            f.write(f"- Zużycie łączne: {total_gabinet_usage_dzienna + total_gabinet_usage_nocna:.2f} kWh\n")
            f.write(f"- Koszt całkowity: {total_gabinet_cost:.2f} zł\n\n")
            
            f.write("### Całkowite koszty\n\n")
            f.write(f"- **Suma kosztów wszystkich lokali:** {total_dom_cost:.2f} zł\n")
            f.write(f"- **Średnia cena za 1 kWh:** {total_dom_cost / total_dom_usage_lacznie:.4f} zł/kWh\n\n")
            
            # Porównanie z fakturą
            f.write("## V. Porównanie z fakturą\n\n")
            f.write(f"- **Suma na fakturze (do zapłaty):** {float(invoice_current.do_zaplaty):.2f} zł\n")
            f.write(f"- **Suma obliczonych rachunków:** ")
            total_calculated = sum(
                sum(bill['total_cost'] for bill in period_data['bills'].values())
                for period_data in bills_calculations.values()
            )
            f.write(f"{total_calculated:.2f} zł\n")
            f.write(f"- **Różnica:** {abs(float(invoice_current.do_zaplaty) - total_calculated):.2f} zł\n\n")
        
        print("Wyniki zapisane do docs/BILL_CALCULATION_LOGIC.md")
        
    finally:
        db.close()


if __name__ == "__main__":
    main()

