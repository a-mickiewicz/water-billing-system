"""
Skrypt do obliczania rachunków według nowej logiki.
Pobiera dane z faktur i wykonuje obliczenia zgodnie z nową logiką.

Użycie:
    python tools/calculate_bills_new_logic.py [NUMER_FAKTURY_POPRZEDNIEJ] [NUMER_FAKTURY_OBECNEJ]

Przykład:
    python tools/calculate_bills_new_logic.py "P/23666363/0001/23" "P/23666363/0002/24"
"""

import sys
import argparse
from pathlib import Path
from datetime import date, datetime, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session

# Dodaj ścieżkę do projektu
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import SessionLocal
from app.models.electricity_invoice import (
    ElectricityInvoice,
    ElectricityInvoiceOdczyt,
    ElectricityInvoiceSprzedazEnergii,
    ElectricityInvoiceOplataDystrybucyjna,
    ElectricityInvoiceRozliczenieOkres
)
from app.models.electricity import ElectricityReading


def get_invoice_by_number(db: Session, numer_faktury: str):
    """Pobiera fakturę po numerze."""
    return db.query(ElectricityInvoice).filter(
        ElectricityInvoice.numer_faktury == numer_faktury
    ).first()


def get_readings_sorted(db: Session):
    """Pobiera wszystkie odczyty posortowane po dacie."""
    readings = db.query(ElectricityReading).order_by(
        ElectricityReading.data_odczytu_licznika.asc()
    ).all()
    return readings


def calculate_days_in_period(start_date: date, end_date: date):
    """Oblicza liczbę dni w okresie (włącznie z datą końcową)."""
    return (end_date - start_date).days + 1


def get_overlap_days(period_start: date, period_end: date, 
                     reading_start: date, reading_end: date):
    """Oblicza liczbę dni wspólnych między dwoma okresami."""
    overlap_start = max(period_start, reading_start)
    overlap_end = min(period_end, reading_end)
    if overlap_start > overlap_end:
        return 0
    return calculate_days_in_period(overlap_start, overlap_end)


def format_decimal(value):
    """Formatuje Decimal do czytelnego formatu."""
    if value is None:
        return "0.00"
    return f"{float(value):.4f}"


def format_currency(value):
    """Formatuje wartość do formatu walutowego."""
    if value is None:
        return "0.00"
    return f"{float(value):.2f}"


def main():
    parser = argparse.ArgumentParser(
        description="Obliczanie rachunków według nowej logiki",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Przykłady użycia:
  python tools/calculate_bills_new_logic.py "P/23666363/0001/23" "P/23666363/0002/24"
  
Uwaga: Faktura poprzednia jest opcjonalna - jeśli nie zostanie podana, skrypt użyje tylko faktury bieżącej.
        """
    )
    parser.add_argument(
        "invoice_prev",
        nargs="?",
        help="Numer faktury poprzedniej (opcjonalny, np. 'P/23666363/0001/23')"
    )
    parser.add_argument(
        "invoice_current",
        nargs="?",
        help="Numer faktury obecnej (wymagany, np. 'P/23666363/0002/24')"
    )
    
    args = parser.parse_args()
    
    if not args.invoice_current:
        parser.print_help()
        print("\n❌ Błąd: Musisz podać numer faktury obecnej jako argument!")
        print("Przykład: python tools/calculate_bills_new_logic.py 'P/23666363/0002/24'")
        print("Lub z fakturą poprzednią: python tools/calculate_bills_new_logic.py 'P/23666363/0001/23' 'P/23666363/0002/24'")
        sys.exit(1)
    
    invoice_prev_number = args.invoice_prev
    invoice_current_number = args.invoice_current
    
    db = SessionLocal()
    
    try:
        # Pobierz faktury
        invoice_prev = None
        if invoice_prev_number:
            invoice_prev = get_invoice_by_number(db, invoice_prev_number)
            if not invoice_prev:
                print(f"⚠️  Ostrzeżenie: Nie znaleziono faktury poprzedniej: {invoice_prev_number}")
                print("   Kontynuowanie bez faktury poprzedniej...")
        
        invoice_curr = get_invoice_by_number(db, invoice_current_number)
        
        if not invoice_curr:
            print(f"❌ Nie znaleziono faktury obecnej: {invoice_current_number}")
            sys.exit(1)
        
        if invoice_prev:
            print(f"Faktura poprzednia: {invoice_prev.numer_faktury}")
        else:
            print("Faktura poprzednia: BRAK (używamy tylko faktury bieżącej)")
        
        print(f"Faktura bieżąca: {invoice_curr.numer_faktury}")
        print(f"Typ taryfy: {invoice_curr.typ_taryfy}")
        print()
        
        # Okres rozliczeniowy faktury zawsze zaczyna się 1.11.YYYY, a kończy 31.10.YYYY
        invoice_year = invoice_curr.rok
        period_start = date(invoice_year - 1, 11, 1)  # 1.11.2023
        period_end = date(invoice_year, 10, 31)  # 31.10.2024
        
        print(f"Okres rozliczeniowy faktury: {period_start} do {period_end}")
        print()
        
        # I. Wyłaniamy okresy z faktur "Odczyty"
        print("=" * 80)
        print("I. OKRESY Z ODCZYTÓW")
        print("=" * 80)
        
        # Pobierz odczyty z faktury poprzedniej (jeśli istnieje) i bieżącej
        odczyty_prev = []
        if invoice_prev:
            odczyty_prev = db.query(ElectricityInvoiceOdczyt).filter(
                ElectricityInvoiceOdczyt.invoice_id == invoice_prev.id
            ).order_by(ElectricityInvoiceOdczyt.data_odczytu.asc()).all()
        
        odczyty_curr = db.query(ElectricityInvoiceOdczyt).filter(
            ElectricityInvoiceOdczyt.invoice_id == invoice_curr.id
        ).order_by(ElectricityInvoiceOdczyt.data_odczytu.asc()).all()
        
        # Znajdź pierwszy odczyt z faktury bieżącej
        if not odczyty_curr:
            print("Brak odczytów w fakturze bieżącej!")
            return
        
        first_reading_date = odczyty_curr[0].data_odczytu
        
        # OKRES I - od 1.11.YYYY do 31.12.2023 (lub do pierwszego odczytu z faktury bieżącej jeśli jest później)
        okres_i_start = period_start  # 1.11.2023
        # Okres I kończy się 31.12.2023 lub pierwszym odczytem z faktury bieżącej (jeśli jest wcześniejszy)
        okres_i_end = min(date(2023, 12, 31), first_reading_date) if first_reading_date.year == 2023 else date(2023, 12, 31)
        
        print(f"\nOKRES I: {okres_i_start} do {okres_i_end}")
        
        # Znajdź odczyty dla OKRES I
        # Dla OKRES I - pobierz ilość kWh z odczytów
        # Szukamy odczytów POBRANA DZIENNA i POBRANA NOCNA (lub CAŁODOBOWA)
        odczyty_okres_i = []
        
        # Odczyty z faktury poprzedniej (jeśli istnieje)
        for odczyt in odczyty_prev:
            if odczyt.typ_energii == "POBRANA" and okres_i_start <= odczyt.data_odczytu <= okres_i_end:
                odczyty_okres_i.append(odczyt)
        
        # Odczyty z faktury bieżącej w OKRES I
        for odczyt in odczyty_curr:
            if odczyt.typ_energii == "POBRANA" and okres_i_start <= odczyt.data_odczytu <= okres_i_end:
                odczyty_okres_i.append(odczyt)
        
        print(f"  Odczyty w OKRES I:")
        dzienna_kwh_okres_i = 0
        nocna_kwh_okres_i = 0
        calodobowa_kwh_okres_i = 0
        
        for odczyt in odczyty_okres_i:
            if odczyt.strefa == "DZIENNA":
                dzienna_kwh_okres_i += odczyt.ilosc_kwh
                print(f"    DZIENNA: {odczyt.ilosc_kwh} kWh (data: {odczyt.data_odczytu})")
            elif odczyt.strefa == "NOCNA":
                nocna_kwh_okres_i += odczyt.ilosc_kwh
                print(f"    NOCNA: {odczyt.ilosc_kwh} kWh (data: {odczyt.data_odczytu})")
            elif odczyt.strefa is None:
                calodobowa_kwh_okres_i += odczyt.ilosc_kwh
                print(f"    CAŁODOBOWA: {odczyt.ilosc_kwh} kWh (data: {odczyt.data_odczytu})")
        
        print(f"  Suma DZIENNA OKRES I: {dzienna_kwh_okres_i} kWh")
        print(f"  Suma NOCNA OKRES I: {nocna_kwh_okres_i} kWh")
        print(f"  Suma CAŁODOBOWA OKRES I: {calodobowa_kwh_okres_i} kWh")
        
        # OKRES II - od 1.01.2024 do kolejnego odczytu
        # Musimy znaleźć kolejne daty odczytów
        all_reading_dates = sorted(set([o.data_odczytu for o in odczyty_curr]))
        
        okresy_odczytow = []
        okresy_odczytow.append({
            'start': okres_i_start,
            'end': okres_i_end,
            'dzienna': dzienna_kwh_okres_i,
            'nocna': nocna_kwh_okres_i,
            'calodobowa': calodobowa_kwh_okres_i
        })
        
        # Dla kolejnych okresów
        prev_end = okres_i_end
        for i, reading_date in enumerate(all_reading_dates[1:], 1):
            okres_start = prev_end + timedelta(days=1)
            okres_end = reading_date
            
            # Pobierz odczyty dla tego okresu
            dzienna_kwh = 0
            nocna_kwh = 0
            calodobowa_kwh = 0
            
            for odczyt in odczyty_curr:
                if odczyt.typ_energii == "POBRANA" and okres_start <= odczyt.data_odczytu <= okres_end:
                    if odczyt.strefa == "DZIENNA":
                        dzienna_kwh += odczyt.ilosc_kwh
                    elif odczyt.strefa == "NOCNA":
                        nocna_kwh += odczyt.ilosc_kwh
                    elif odczyt.strefa is None:
                        calodobowa_kwh += odczyt.ilosc_kwh
            
            okresy_odczytow.append({
                'start': okres_start,
                'end': okres_end,
                'dzienna': dzienna_kwh,
                'nocna': nocna_kwh,
                'calodobowa': calodobowa_kwh
            })
            
            print(f"\nOKRES {i+1}: {okres_start} do {okres_end}")
            print(f"  DZIENNA: {dzienna_kwh} kWh")
            print(f"  NOCNA: {nocna_kwh} kWh")
            print(f"  CAŁODOBOWA: {calodobowa_kwh} kWh")
            
            prev_end = okres_end
        
        # Ostatni okres kończy się 31.10.YYYY
        if prev_end < period_end:
            ostatni_okres_start = prev_end + timedelta(days=1)
            ostatni_okres_end = period_end
            
            # Pobierz odczyty dla ostatniego okresu
            dzienna_kwh = 0
            nocna_kwh = 0
            calodobowa_kwh = 0
            
            for odczyt in odczyty_curr:
                if odczyt.typ_energii == "POBRANA" and ostatni_okres_start <= odczyt.data_odczytu <= ostatni_okres_end:
                    if odczyt.strefa == "DZIENNA":
                        dzienna_kwh += odczyt.ilosc_kwh
                    elif odczyt.strefa == "NOCNA":
                        nocna_kwh += odczyt.ilosc_kwh
                    elif odczyt.strefa is None:
                        calodobowa_kwh += odczyt.ilosc_kwh
            
            okresy_odczytow.append({
                'start': ostatni_okres_start,
                'end': ostatni_okres_end,
                'dzienna': dzienna_kwh,
                'nocna': nocna_kwh,
                'calodobowa': calodobowa_kwh
            })
            
            print(f"\nOKRES OSTATNI: {ostatni_okres_start} do {ostatni_okres_end}")
            print(f"  DZIENNA: {dzienna_kwh} kWh")
            print(f"  NOCNA: {nocna_kwh} kWh")
            print(f"  CAŁODOBOWA: {calodobowa_kwh} kWh")
        
        # II. Wyłaniamy okresy z "Rozliczenie usługa dystrybucji"
        print("\n" + "=" * 80)
        print("II. OKRESY DYSTRYBUCYJNE")
        print("=" * 80)
        
        # Pobierz rozliczenie okresów z faktury bieżącej
        rozliczenie_okresy = db.query(ElectricityInvoiceRozliczenieOkres).filter(
            ElectricityInvoiceRozliczenieOkres.invoice_id == invoice_curr.id
        ).order_by(ElectricityInvoiceRozliczenieOkres.numer_okresu.asc()).all()
        
        if not rozliczenie_okresy:
            print("Brak rozliczenia okresów w fakturze!")
            return
        
        # Okresy dystrybucyjne odpowiadają datom z rozliczenia okresów
        okresy_dystrybucyjne = []
        
        for i, roz_okres in enumerate(rozliczenie_okresy):
            if i == 0:
                # Pierwszy okres: od 1.11.YYYY do daty pierwszego okresu
                okres_start = period_start
            else:
                # Kolejne okresy: od dnia następnego po poprzednim okresie
                okres_start = okresy_dystrybucyjne[-1]['end'] + timedelta(days=1)
            
            okres_end = roz_okres.data_okresu
            
            # Pobierz dane dla tego okresu
            # a) ilosc_kwh z electricity_invoice_sprzedaz_energii
            sprzedaz_okres = db.query(ElectricityInvoiceSprzedazEnergii).filter(
                ElectricityInvoiceSprzedazEnergii.invoice_id == invoice_curr.id,
                ElectricityInvoiceSprzedazEnergii.data == okres_end
            ).all()
            
            # b) ceny za 1kWh z sprzedaży energii
            cena_dzienna = None
            cena_nocna = None
            cena_calodobowa = None
            ilosc_dzienna = 0
            ilosc_nocna = 0
            ilosc_calodobowa = 0
            
            for sprzedaz in sprzedaz_okres:
                if sprzedaz.strefa == "DZIENNA":
                    ilosc_dzienna = sprzedaz.ilosc_kwh
                    cena_dzienna = sprzedaz.cena_za_kwh
                elif sprzedaz.strefa == "NOCNA":
                    ilosc_nocna = sprzedaz.ilosc_kwh
                    cena_nocna = sprzedaz.cena_za_kwh
                elif sprzedaz.strefa is None or sprzedaz.strefa == "CAŁODOBOWA":
                    ilosc_calodobowa = sprzedaz.ilosc_kwh
                    cena_calodobowa = sprzedaz.cena_za_kwh
            
            # c) opłata jakościowa
            oplata_jakosciowa_dzienna = None
            oplata_jakosciowa_nocna = None
            oplata_jakosciowa_calodobowa = None
            
            oplaty_jakosciowe = db.query(ElectricityInvoiceOplataDystrybucyjna).filter(
                ElectricityInvoiceOplataDystrybucyjna.invoice_id == invoice_curr.id,
                ElectricityInvoiceOplataDystrybucyjna.typ_oplaty.like("%JAKOŚCIOWA%"),
                ElectricityInvoiceOplataDystrybucyjna.data == okres_end
            ).all()
            
            for oplata in oplaty_jakosciowe:
                if oplata.strefa == "DZIENNA":
                    oplata_jakosciowa_dzienna = oplata.cena
                elif oplata.strefa == "NOCNA":
                    oplata_jakosciowa_nocna = oplata.cena
                elif oplata.strefa is None:
                    oplata_jakosciowa_calodobowa = oplata.cena
            
            # d) opłata zmienna sieciowa
            oplata_zmienna_dzienna = None
            oplata_zmienna_nocna = None
            oplata_zmienna_calodobowa = None
            
            oplaty_zmienne = db.query(ElectricityInvoiceOplataDystrybucyjna).filter(
                ElectricityInvoiceOplataDystrybucyjna.invoice_id == invoice_curr.id,
                ElectricityInvoiceOplataDystrybucyjna.typ_oplaty.like("%ZMIENNA%"),
                ElectricityInvoiceOplataDystrybucyjna.data == okres_end
            ).all()
            
            for oplata in oplaty_zmienne:
                if oplata.strefa == "DZIENNA":
                    oplata_zmienna_dzienna = oplata.cena
                elif oplata.strefa == "NOCNA":
                    oplata_zmienna_nocna = oplata.cena
                elif oplata.strefa is None:
                    oplata_zmienna_calodobowa = oplata.cena
            
            # e) opłata OZE
            oplata_oze_dzienna = None
            oplata_oze_nocna = None
            oplata_oze_calodobowa = None
            
            oplaty_oze = db.query(ElectricityInvoiceOplataDystrybucyjna).filter(
                ElectricityInvoiceOplataDystrybucyjna.invoice_id == invoice_curr.id,
                ElectricityInvoiceOplataDystrybucyjna.typ_oplaty.like("%OZE%"),
                ElectricityInvoiceOplataDystrybucyjna.data == okres_end
            ).all()
            
            for oplata in oplaty_oze:
                if oplata.strefa == "DZIENNA":
                    oplata_oze_dzienna = oplata.cena
                elif oplata.strefa == "NOCNA":
                    oplata_oze_nocna = oplata.cena
                elif oplata.strefa is None:
                    oplata_oze_calodobowa = oplata.cena
            
            # f) opłata kogeneracyjna
            oplata_kogeneracyjna_dzienna = None
            oplata_kogeneracyjna_nocna = None
            oplata_kogeneracyjna_calodobowa = None
            
            oplaty_kogeneracyjne = db.query(ElectricityInvoiceOplataDystrybucyjna).filter(
                ElectricityInvoiceOplataDystrybucyjna.invoice_id == invoice_curr.id,
                ElectricityInvoiceOplataDystrybucyjna.typ_oplaty.like("%KOGENERACYJNA%"),
                ElectricityInvoiceOplataDystrybucyjna.data == okres_end
            ).all()
            
            for oplata in oplaty_kogeneracyjne:
                if oplata.strefa == "DZIENNA":
                    oplata_kogeneracyjna_dzienna = oplata.cena
                elif oplata.strefa == "NOCNA":
                    oplata_kogeneracyjna_nocna = oplata.cena
                elif oplata.strefa is None:
                    oplata_kogeneracyjna_calodobowa = oplata.cena
            
            # g) Oblicz cenę za 1kWh (suma b+c+d+e+f)
            cena_calkowita_dzienna = Decimal(0)
            cena_calkowita_nocna = Decimal(0)
            cena_calkowita_calodobowa = Decimal(0)
            
            if cena_dzienna:
                cena_calkowita_dzienna += Decimal(str(cena_dzienna))
            if oplata_jakosciowa_dzienna:
                cena_calkowita_dzienna += Decimal(str(oplata_jakosciowa_dzienna))
            if oplata_zmienna_dzienna:
                cena_calkowita_dzienna += Decimal(str(oplata_zmienna_dzienna))
            if oplata_oze_dzienna:
                cena_calkowita_dzienna += Decimal(str(oplata_oze_dzienna))
            if oplata_kogeneracyjna_dzienna:
                cena_calkowita_dzienna += Decimal(str(oplata_kogeneracyjna_dzienna))
            
            if cena_nocna:
                cena_calkowita_nocna += Decimal(str(cena_nocna))
            if oplata_jakosciowa_nocna:
                cena_calkowita_nocna += Decimal(str(oplata_jakosciowa_nocna))
            if oplata_zmienna_nocna:
                cena_calkowita_nocna += Decimal(str(oplata_zmienna_nocna))
            if oplata_oze_nocna:
                cena_calkowita_nocna += Decimal(str(oplata_oze_nocna))
            if oplata_kogeneracyjna_nocna:
                cena_calkowita_nocna += Decimal(str(oplata_kogeneracyjna_nocna))
            
            if cena_calodobowa:
                cena_calkowita_calodobowa += Decimal(str(cena_calodobowa))
            if oplata_jakosciowa_calodobowa:
                cena_calkowita_calodobowa += Decimal(str(oplata_jakosciowa_calodobowa))
            if oplata_zmienna_calodobowa:
                cena_calkowita_calodobowa += Decimal(str(oplata_zmienna_calodobowa))
            if oplata_oze_calodobowa:
                cena_calkowita_calodobowa += Decimal(str(oplata_oze_calodobowa))
            if oplata_kogeneracyjna_calodobowa:
                cena_calkowita_calodobowa += Decimal(str(oplata_kogeneracyjna_calodobowa))
            
            # h) opłaty stałe
            oplata_stala_sieciowa = None
            oplata_przejściowa = None
            oplata_abonamentowa = None
            oplata_mocowa = None
            
            oplaty_stale = db.query(ElectricityInvoiceOplataDystrybucyjna).filter(
                ElectricityInvoiceOplataDystrybucyjna.invoice_id == invoice_curr.id,
                ElectricityInvoiceOplataDystrybucyjna.jednostka == "zł/mc",
                ElectricityInvoiceOplataDystrybucyjna.data == okres_end
            ).all()
            
            for oplata in oplaty_stale:
                if "STAŁA SIECIOWA" in oplata.typ_oplaty.upper():
                    oplata_stala_sieciowa = oplata.cena
                elif "PRZEJŚCIOWA" in oplata.typ_oplaty.upper():
                    oplata_przejściowa = oplata.cena
                elif "ABONAMENTOWA" in oplata.typ_oplaty.upper():
                    oplata_abonamentowa = oplata.cena
                elif "MOCOWA" in oplata.typ_oplaty.upper():
                    oplata_mocowa = oplata.cena
            
            # i) suma opłat stałych
            suma_oplat_stalych = Decimal(0)
            if oplata_stala_sieciowa:
                suma_oplat_stalych += Decimal(str(oplata_stala_sieciowa))
            if oplata_przejściowa:
                suma_oplat_stalych += Decimal(str(oplata_przejściowa))
            if oplata_abonamentowa:
                suma_oplat_stalych += Decimal(str(oplata_abonamentowa))
            if oplata_mocowa:
                suma_oplat_stalych += Decimal(str(oplata_mocowa))
            
            okresy_dystrybucyjne.append({
                'start': okres_start,
                'end': okres_end,
                'ilosc_dzienna': ilosc_dzienna,
                'ilosc_nocna': ilosc_nocna,
                'ilosc_calodobowa': ilosc_calodobowa,
                'cena_dzienna': cena_dzienna,
                'cena_nocna': cena_nocna,
                'cena_calodobowa': cena_calodobowa,
                'oplata_jakosciowa_dzienna': oplata_jakosciowa_dzienna,
                'oplata_jakosciowa_nocna': oplata_jakosciowa_nocna,
                'oplata_zmienna_dzienna': oplata_zmienna_dzienna,
                'oplata_zmienna_nocna': oplata_zmienna_nocna,
                'oplata_oze_dzienna': oplata_oze_dzienna,
                'oplata_oze_nocna': oplata_oze_nocna,
                'oplata_kogeneracyjna_dzienna': oplata_kogeneracyjna_dzienna,
                'oplata_kogeneracyjna_nocna': oplata_kogeneracyjna_nocna,
                'cena_calkowita_dzienna': cena_calkowita_dzienna,
                'cena_calkowita_nocna': cena_calkowita_nocna,
                'cena_calkowita_calodobowa': cena_calkowita_calodobowa,
                'oplata_stala_sieciowa': oplata_stala_sieciowa,
                'oplata_przejściowa': oplata_przejściowa,
                'oplata_abonamentowa': oplata_abonamentowa,
                'oplata_mocowa': oplata_mocowa,
                'suma_oplat_stalych': suma_oplat_stalych
            })
            
            print(f"\nOKRES_DYSTRYBUCYJNY_{i+1}: {okres_start} do {okres_end}")
            print(f"  a) ilosc_kwh DZIENNA: {ilosc_dzienna} kWh")
            print(f"  a) ilosc_kwh NOCNA: {ilosc_nocna} kWh")
            print(f"  a) ilosc_kwh CAŁODOBOWA: {ilosc_calodobowa} kWh")
            print(f"  b) cena za 1kWh DZIENNA: {format_decimal(cena_dzienna)}")
            print(f"  b) cena za 1kWh NOCNA: {format_decimal(cena_nocna)}")
            print(f"  c) opłata jakościowa DZIENNA: {format_decimal(oplata_jakosciowa_dzienna)}")
            print(f"  c) opłata jakościowa NOCNA: {format_decimal(oplata_jakosciowa_nocna)}")
            print(f"  d) opłata zmienna sieciowa DZIENNA: {format_decimal(oplata_zmienna_dzienna)}")
            print(f"  d) opłata zmienna sieciowa NOCNA: {format_decimal(oplata_zmienna_nocna)}")
            print(f"  e) opłata OZE DZIENNA: {format_decimal(oplata_oze_dzienna)}")
            print(f"  e) opłata OZE NOCNA: {format_decimal(oplata_oze_nocna)}")
            print(f"  f) opłata kogeneracyjna DZIENNA: {format_decimal(oplata_kogeneracyjna_dzienna)}")
            print(f"  f) opłata kogeneracyjna NOCNA: {format_decimal(oplata_kogeneracyjna_nocna)}")
            print(f"  g) CENA CAŁKOWITA za 1kWh DZIENNA: {format_decimal(cena_calkowita_dzienna)}")
            print(f"  g) CENA CAŁKOWITA za 1kWh NOCNA: {format_decimal(cena_calkowita_nocna)}")
            print(f"  h) opłata stała sieciowa: {format_decimal(oplata_stala_sieciowa)}")
            print(f"  h) opłata przejściowa: {format_decimal(oplata_przejściowa)}")
            print(f"  h) opłata abonamentowa: {format_decimal(oplata_abonamentowa)}")
            print(f"  h) opłata mocowa: {format_decimal(oplata_mocowa)}")
            print(f"  i) SUMA OPŁAT STAŁYCH: {format_currency(suma_oplat_stalych)}")
        
        # Ostatni okres dystrybucyjny kończy się 31.10.YYYY
        if okresy_dystrybucyjne and okresy_dystrybucyjne[-1]['end'] < period_end:
            ostatni_okres_start = okresy_dystrybucyjne[-1]['end'] + timedelta(days=1)
            ostatni_okres_end = period_end
            
            # Użyj danych z ostatniego okresu dystrybucyjnego
            ostatni_okres = okresy_dystrybucyjne[-1].copy()
            ostatni_okres['start'] = ostatni_okres_start
            ostatni_okres['end'] = ostatni_okres_end
            okresy_dystrybucyjne.append(ostatni_okres)
        
        # III. Obliczamy dane do wystawienia rachunków dla najemców
        print("\n" + "=" * 80)
        print("III. OBLICZANIE RACHUNKÓW DLA NAJEMCÓW")
        print("=" * 80)
        
        # Pobierz odczyty z electricity_readings
        readings = get_readings_sorted(db)
        
        if not readings:
            print("Brak odczytów w bazie!")
            return
        
        print(f"\nOdczyty w bazie (electricity_readings):")
        for reading in readings:
            print(f"  {reading.data_odczytu_licznika} ({reading.data})")
        
        # Obliczamy rachunki dla każdego okresu między odczytami
        rachunki = []
        
        for i in range(len(readings) - 1):
            reading_start = readings[i]
            reading_end = readings[i + 1]
            
            if not reading_start.data_odczytu_licznika or not reading_end.data_odczytu_licznika:
                continue
            
            okres_rachunkowy_start = reading_start.data_odczytu_licznika
            okres_rachunkowy_end = reading_end.data_odczytu_licznika
            
            print(f"\n{'='*80}")
            print(f"RACHUNEK: {okres_rachunkowy_start} do {okres_rachunkowy_end}")
            print(f"{'='*80}")
            
            # Znajdź które okresy dystrybucyjne pokrywają się z tym okresem rachunkowym
            okresy_w_rachunku = []
            
            for okres_dist in okresy_dystrybucyjne:
                overlap_days = get_overlap_days(
                    okres_dist['start'], okres_dist['end'],
                    okres_rachunkowy_start, okres_rachunkowy_end
                )
                
                if overlap_days > 0:
                    okresy_w_rachunku.append({
                        'okres': okres_dist,
                        'dni': overlap_days
                    })
            
            total_days = calculate_days_in_period(okres_rachunkowy_start, okres_rachunkowy_end)
            
            print(f"\nOkresy dystrybucyjne w tym rachunku:")
            for okres_info in okresy_w_rachunku:
                okres = okres_info['okres']
                dni = okres_info['dni']
                procent = (dni / total_days) * 100
                print(f"  {okres['start']} do {okres['end']}: {dni} dni ({procent:.2f}%)")
            
            # Oblicz zużycie dla każdego lokalu
            # TODO: Oblicz zużycie na podstawie odczytów liczników
            # Na razie tylko pokazujemy strukturę
            
            rachunki.append({
                'start': okres_rachunkowy_start,
                'end': okres_rachunkowy_end,
                'okresy_dystrybucyjne': okresy_w_rachunku,
                'total_days': total_days
            })
        
        # Zapisz wyniki do pliku .md
        output_file = "docs/obliczenia_rachunkow_nowa_logika.md"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("# Obliczenia Rachunków - Nowa Logika\n\n")
            f.write(f"**Faktura poprzednia:** {invoice_prev.numer_faktury}\n")
            f.write(f"**Faktura bieżąca:** {invoice_curr.numer_faktury}\n")
            f.write(f"**Typ taryfy:** {invoice_curr.typ_taryfy}\n")
            f.write(f"**Okres rozliczeniowy:** {period_start} do {period_end}\n\n")
            
            f.write("## I. Okresy z Odczyty\n\n")
            for i, okres in enumerate(okresy_odczytow, 1):
                f.write(f"### OKRES {i}\n\n")
                f.write(f"- **Od:** {okres['start']}\n")
                f.write(f"- **Do:** {okres['end']}\n")
                f.write(f"- **DZIENNA:** {okres['dzienna']} kWh\n")
                f.write(f"- **NOCNA:** {okres['nocna']} kWh\n")
                f.write(f"- **CAŁODOBOWA:** {okres['calodobowa']} kWh\n\n")
            
            f.write("## II. Okresy Dystrybucyjne\n\n")
            for i, okres in enumerate(okresy_dystrybucyjne, 1):
                f.write(f"### OKRES_DYSTRYBUCYJNY_{i}\n\n")
                f.write(f"- **Od:** {okres['start']}\n")
                f.write(f"- **Do:** {okres['end']}\n")
                f.write(f"- **Ilość kWh DZIENNA:** {okres['ilosc_dzienna']} kWh\n")
                f.write(f"- **Ilość kWh NOCNA:** {okres['ilosc_nocna']} kWh\n")
                f.write(f"- **Cena za 1kWh DZIENNA:** {format_decimal(okres['cena_dzienna'])} zł\n")
                f.write(f"- **Cena za 1kWh NOCNA:** {format_decimal(okres['cena_nocna'])} zł\n")
                f.write(f"- **Opłata jakościowa DZIENNA:** {format_decimal(okres['oplata_jakosciowa_dzienna'])} zł/kWh\n")
                f.write(f"- **Opłata jakościowa NOCNA:** {format_decimal(okres['oplata_jakosciowa_nocna'])} zł/kWh\n")
                f.write(f"- **Opłata zmienna sieciowa DZIENNA:** {format_decimal(okres['oplata_zmienna_dzienna'])} zł/kWh\n")
                f.write(f"- **Opłata zmienna sieciowa NOCNA:** {format_decimal(okres['oplata_zmienna_nocna'])} zł/kWh\n")
                f.write(f"- **Opłata OZE DZIENNA:** {format_decimal(okres['oplata_oze_dzienna'])} zł/kWh\n")
                f.write(f"- **Opłata OZE NOCNA:** {format_decimal(okres['oplata_oze_nocna'])} zł/kWh\n")
                f.write(f"- **Opłata kogeneracyjna DZIENNA:** {format_decimal(okres['oplata_kogeneracyjna_dzienna'])} zł/kWh\n")
                f.write(f"- **Opłata kogeneracyjna NOCNA:** {format_decimal(okres['oplata_kogeneracyjna_nocna'])} zł/kWh\n")
                f.write(f"- **CENA CAŁKOWITA za 1kWh DZIENNA:** {format_decimal(okres['cena_calkowita_dzienna'])} zł\n")
                f.write(f"- **CENA CAŁKOWITA za 1kWh NOCNA:** {format_decimal(okres['cena_calkowita_nocna'])} zł\n")
                f.write(f"- **Opłata stała sieciowa:** {format_decimal(okres['oplata_stala_sieciowa'])} zł\n")
                f.write(f"- **Opłata przejściowa:** {format_decimal(okres['oplata_przejściowa'])} zł\n")
                f.write(f"- **Opłata abonamentowa:** {format_decimal(okres['oplata_abonamentowa'])} zł\n")
                f.write(f"- **Opłata mocowa:** {format_decimal(okres['oplata_mocowa'])} zł\n")
                f.write(f"- **SUMA OPŁAT STAŁYCH:** {format_currency(okres['suma_oplat_stalych'])} zł\n\n")
            
            f.write("## III. Rachunki dla Najemców\n\n")
            for rachunek in rachunki:
                f.write(f"### Rachunek: {rachunek['start']} do {rachunek['end']}\n\n")
                f.write(f"**Całkowita liczba dni:** {rachunek['total_days']}\n\n")
                f.write("**Okresy dystrybucyjne:**\n\n")
                for okres_info in rachunek['okresy_dystrybucyjne']:
                    okres = okres_info['okres']
                    dni = okres_info['dni']
                    procent = (dni / rachunek['total_days']) * 100
                    f.write(f"- {okres['start']} do {okres['end']}: {dni} dni ({procent:.2f}%)\n")
                f.write("\n")
        
        print(f"\n\nWyniki zapisane do: {output_file}")
        
    finally:
        db.close()


if __name__ == "__main__":
    main()

