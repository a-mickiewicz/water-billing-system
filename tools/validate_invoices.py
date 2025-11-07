"""
Skrypt walidacji wszystkich faktur w bazie danych.
Sprawdza zależności matematyczne i logiczne zgodnie z zaleznosci_walidacji_faktur.txt
"""

import sys
from pathlib import Path
from datetime import datetime, date
from typing import List, Dict, Any, Tuple
from decimal import Decimal

# Dodaj ścieżkę do projektu
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import SessionLocal
from app.models.electricity_invoice import (
    ElectricityInvoice,
    ElectricityInvoiceSprzedazEnergii,
    ElectricityInvoiceOplataDystrybucyjna,
    ElectricityInvoiceOdczyt
)
from app.models.water import Invoice as WaterInvoice
from app.models.gas import GasInvoice


# Tolerancje
TOLERANCE_PLN = 0.01  # 1 grosz
TOLERANCE_KWH = 1.0   # 1 kWh
TOLERANCE_M3 = 0.01   # 0.01 m³
TOLERANCE_VAT = 0.001 # 0.1%


class ValidationResult:
    """Klasa do przechowywania wyników walidacji."""
    def __init__(self):
        self.critical_errors: List[Dict[str, Any]] = []
        self.warnings: List[Dict[str, Any]] = []
        self.info: List[Dict[str, Any]] = []
        self.validated_count = 0
        self.total_count = 0
    
    def add_critical(self, invoice_type: str, invoice_id: str, check_name: str, message: str, details: Dict = None):
        self.critical_errors.append({
            'invoice_type': invoice_type,
            'invoice_id': invoice_id,
            'check_name': check_name,
            'message': message,
            'details': details or {}
        })
    
    def add_warning(self, invoice_type: str, invoice_id: str, check_name: str, message: str, details: Dict = None):
        self.warnings.append({
            'invoice_type': invoice_type,
            'invoice_id': invoice_id,
            'check_name': check_name,
            'message': message,
            'details': details or {}
        })
    
    def add_info(self, invoice_type: str, invoice_id: str, check_name: str, message: str, details: Dict = None):
        self.info.append({
            'invoice_type': invoice_type,
            'invoice_id': invoice_id,
            'check_name': check_name,
            'message': message,
            'details': details or {}
        })


def float_or_zero(value) -> float:
    """Konwertuje wartość na float, zwraca 0 jeśli None."""
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def check_approx_equal(calculated: float, actual: float, tolerance: float) -> bool:
    """Sprawdza czy wartości są równe z tolerancją."""
    return abs(calculated - actual) <= tolerance


def validate_electricity_invoice(invoice: ElectricityInvoice, db, result: ValidationResult):
    """Waliduje fakturę prądu."""
    invoice_id = f"{invoice.numer_faktury} ({invoice.rok})"
    result.total_count += 1
    
    # 1.1. SPRZEDAŻ ENERGII
    sales = db.query(ElectricityInvoiceSprzedazEnergii).filter(
        ElectricityInvoiceSprzedazEnergii.invoice_id == invoice.id
    ).all()
    
    if sales:
        total_sales_kwh = 0.0
        total_sales_netto = 0.0
        total_sales_brutto = 0.0
        
        for sale in sales:
            # Pomijamy upusty (jeśli są oznaczone jako ujemne należności)
            if float(sale.naleznosc) < 0:
                continue
            
            ilosc_kwh = float(sale.ilosc_kwh)
            cena_za_kwh = float(sale.cena_za_kwh)
            naleznosc = float(sale.naleznosc)
            vat_procent = float(sale.vat_procent) / 100.0
            
            # Sprawdź: cena * ilość ≈ należność
            obliczona_naleznosc = ilosc_kwh * cena_za_kwh
            if not check_approx_equal(obliczona_naleznosc, naleznosc, TOLERANCE_PLN):
                result.add_warning(
                    'PRĄD', invoice_id, 'Sprzedaż energii - cena * ilość',
                    f"cena * ilość ({obliczona_naleznosc:.2f}) != należność ({naleznosc:.2f})",
                    {
                        'tabela': 'electricity_invoice_sprzedaz_energii',
                        'invoice_id': invoice.id,
                        'sale_id': sale.id,
                        'strefa': sale.strefa or 'BRAK',
                        'ilosc_kwh': ilosc_kwh,
                        'cena_za_kwh': cena_za_kwh,
                        'naleznosc': naleznosc,
                        'obliczona_naleznosc': obliczona_naleznosc,
                        'roznica': abs(obliczona_naleznosc - naleznosc)
                    }
                )
            
            # Sprawdź VAT
            naleznosc_netto = naleznosc / (1 + vat_procent)
            naleznosc_brutto = naleznosc
            vat_amount = naleznosc_brutto - naleznosc_netto
            
            total_sales_kwh += ilosc_kwh
            total_sales_netto += naleznosc_netto
            total_sales_brutto += naleznosc_brutto
        
        # Sprawdź sumy
        invoice_usage = float(invoice.zuzycie_kwh)
        if not check_approx_equal(total_sales_kwh, invoice_usage, TOLERANCE_KWH):
            result.add_warning(
                'PRĄD', invoice_id, 'Sprzedaż energii - suma zużycia',
                f"Suma zużycia z pozycji ({total_sales_kwh:.0f}) != zużycie faktury ({invoice_usage:.0f})",
                {
                    'tabela': 'electricity_invoices',
                    'invoice_id': invoice.id,
                    'pole': 'zuzycie_kwh',
                    'suma_zuzycia_z_pozycji': total_sales_kwh,
                    'zuzycie_faktury': invoice_usage,
                    'roznica': abs(total_sales_kwh - invoice_usage)
                }
            )
        
        invoice_energy_net = float_or_zero(invoice.ogolem_sprzedaz_energii) / (1 + 0.23)  # Zakładamy 23% VAT
        if not check_approx_equal(total_sales_netto, invoice_energy_net, TOLERANCE_PLN * 10):
            result.add_warning(
                'PRĄD', invoice_id, 'Sprzedaż energii - suma netto',
                f"Suma netto z pozycji ({total_sales_netto:.2f}) != energia netto faktury ({invoice_energy_net:.2f})",
                {
                    'tabela': 'electricity_invoices',
                    'invoice_id': invoice.id,
                    'pole': 'ogolem_sprzedaz_energii',
                    'suma_netto_z_pozycji': total_sales_netto,
                    'energia_netto_faktury': invoice_energy_net,
                    'ogolem_sprzedaz_energii': float_or_zero(invoice.ogolem_sprzedaz_energii),
                    'roznica': abs(total_sales_netto - invoice_energy_net)
                }
            )
    
    # 1.2. OPŁATY DYSTRYBUCYJNE
    fees = db.query(ElectricityInvoiceOplataDystrybucyjna).filter(
        ElectricityInvoiceOplataDystrybucyjna.invoice_id == invoice.id
    ).all()
    
    if fees:
        total_fees_netto = 0.0
        total_fees_brutto = 0.0
        
        for fee in fees:
            vat_procent = float(fee.vat_procent) / 100.0
            naleznosc = float(fee.naleznosc)
            cena = float(fee.cena)
            
            # Sprawdź w zależności od jednostki
            if fee.jednostka == "kWh" and fee.ilosc_kwh:
                obliczona_naleznosc = cena * float(fee.ilosc_kwh)
                if not check_approx_equal(obliczona_naleznosc, naleznosc, TOLERANCE_PLN):
                    result.add_warning(
                        'PRĄD', invoice_id, 'Opłata dystrybucyjna - cena * ilość',
                        f"{fee.typ_oplaty}: cena * ilość ({obliczona_naleznosc:.2f}) != należność ({naleznosc:.2f})",
                        {
                            'tabela': 'electricity_invoice_oplaty_dystrybucyjne',
                            'invoice_id': invoice.id,
                            'fee_id': fee.id,
                            'typ_oplaty': fee.typ_oplaty,
                            'strefa': fee.strefa or 'BRAK',
                            'jednostka': fee.jednostka,
                            'ilosc_kwh': float(fee.ilosc_kwh),
                            'cena': cena,
                            'naleznosc': naleznosc,
                            'obliczona_naleznosc': obliczona_naleznosc,
                            'roznica': abs(obliczona_naleznosc - naleznosc)
                        }
                    )
            elif fee.jednostka == "zł/mc" and fee.ilosc_miesiecy:
                obliczona_naleznosc = cena * float(fee.ilosc_miesiecy)
                if not check_approx_equal(obliczona_naleznosc, naleznosc, TOLERANCE_PLN):
                    result.add_warning(
                        'PRĄD', invoice_id, 'Opłata dystrybucyjna - cena * miesiące',
                        f"{fee.typ_oplaty}: cena * miesiące ({obliczona_naleznosc:.2f}) != należność ({naleznosc:.2f})",
                        {
                            'tabela': 'electricity_invoice_oplaty_dystrybucyjne',
                            'invoice_id': invoice.id,
                            'fee_id': fee.id,
                            'typ_oplaty': fee.typ_oplaty,
                            'strefa': fee.strefa or 'BRAK',
                            'jednostka': fee.jednostka,
                            'ilosc_miesiecy': float(fee.ilosc_miesiecy),
                            'cena': cena,
                            'naleznosc': naleznosc,
                            'obliczona_naleznosc': obliczona_naleznosc,
                            'roznica': abs(obliczona_naleznosc - naleznosc)
                        }
                    )
            
            naleznosc_netto = naleznosc / (1 + vat_procent)
            total_fees_netto += naleznosc_netto
            total_fees_brutto += naleznosc
    
    # 1.3. ODCZYTY LICZNIKÓW
    readings = db.query(ElectricityInvoiceOdczyt).filter(
        ElectricityInvoiceOdczyt.invoice_id == invoice.id
    ).all()
    
    if readings:
        total_readings_kwh = 0.0
        
        for reading in readings:
            # Sprawdź: ilość = (bieżący - poprzedni) * mnożna
            obliczona_ilosc = (float(reading.biezacy_odczyt) - float(reading.poprzedni_odczyt)) * float(reading.mnozna)
            if not check_approx_equal(obliczona_ilosc, float(reading.ilosc_kwh), TOLERANCE_KWH):
                result.add_warning(
                    'PRĄD', invoice_id, 'Odczyt - obliczenie ilości',
                    f"Odczyt {reading.typ_energii} {reading.strefa or ''}: obliczona ilość ({obliczona_ilosc:.0f}) != ilość ({reading.ilosc_kwh})",
                    {
                        'tabela': 'electricity_invoice_odczyty',
                        'invoice_id': invoice.id,
                        'reading_id': reading.id,
                        'typ_energii': reading.typ_energii,
                        'strefa': reading.strefa or 'BRAK',
                        'biezacy_odczyt': float(reading.biezacy_odczyt),
                        'poprzedni_odczyt': float(reading.poprzedni_odczyt),
                        'mnozna': float(reading.mnozna),
                        'ilosc_kwh': float(reading.ilosc_kwh),
                        'obliczona_ilosc': obliczona_ilosc,
                        'roznica': abs(obliczona_ilosc - float(reading.ilosc_kwh))
                    }
                )
            
            # Sprawdź: razem = ilość + straty
            obliczone_razem = float(reading.ilosc_kwh) + float(reading.straty_kwh)
            if not check_approx_equal(obliczone_razem, float(reading.razem_kwh), TOLERANCE_KWH):
                result.add_warning(
                    'PRĄD', invoice_id, 'Odczyt - razem',
                    f"Odczyt {reading.typ_energii}: ilość + straty ({obliczone_razem:.0f}) != razem ({reading.razem_kwh})",
                    {
                        'tabela': 'electricity_invoice_odczyty',
                        'invoice_id': invoice.id,
                        'reading_id': reading.id,
                        'typ_energii': reading.typ_energii,
                        'ilosc_kwh': float(reading.ilosc_kwh),
                        'straty_kwh': float(reading.straty_kwh),
                        'razem_kwh': float(reading.razem_kwh),
                        'obliczone_razem': obliczone_razem,
                        'roznica': abs(obliczone_razem - float(reading.razem_kwh))
                    }
                )
            
            if reading.typ_energii == "POBRANA":
                total_readings_kwh += float(reading.ilosc_kwh)
        
        # Sprawdź suma odczytów ≈ zużycie
        if not check_approx_equal(total_readings_kwh, invoice_usage, TOLERANCE_KWH * 2):
            result.add_info(
                'PRĄD', invoice_id, 'Odczyt - suma vs zużycie',
                f"Suma odczytów ({total_readings_kwh:.0f}) != zużycie faktury ({invoice_usage:.0f})"
            )
    
    # 1.4. PODSUMOWANIE FINANSOWE
    # Sprawdź daty
    if invoice.data_poczatku_okresu >= invoice.data_konca_okresu:
        result.add_critical(
            'PRĄD', invoice_id, 'Daty okresu',
            f"Data początku ({invoice.data_poczatku_okresu}) >= data końca ({invoice.data_konca_okresu})"
        )
    
    if invoice.data_wystawienia < invoice.data_poczatku_okresu:
        result.add_warning(
            'PRĄD', invoice_id, 'Data wystawienia',
            f"Data wystawienia ({invoice.data_wystawienia}) < data początku okresu ({invoice.data_poczatku_okresu})"
        )
    
    # Sprawdź VAT
    vat_rate = 0.23  # Domyślnie 23%
    total_net = float_or_zero(invoice.ogolem_sprzedaz_energii) / (1 + vat_rate) + float_or_zero(invoice.ogolem_usluga_dystrybucji) / (1 + vat_rate)
    total_gross = float_or_zero(invoice.ogolem_sprzedaz_energii) + float_or_zero(invoice.ogolem_usluga_dystrybucji)
    calculated_vat = total_gross - total_net
    
    # Sprawdź saldo
    calculated_saldo = (
        float_or_zero(invoice.naleznosc_za_okres) +
        float_or_zero(invoice.wynik_rozliczenia) +
        float_or_zero(invoice.odsetki) -
        float_or_zero(invoice.kwota_nadplacona)
    )
    if not check_approx_equal(calculated_saldo, float_or_zero(invoice.saldo_z_rozliczenia), TOLERANCE_PLN * 10):
        result.add_warning(
            'PRĄD', invoice_id, 'Saldo z rozliczenia',
            f"Obliczone saldo ({calculated_saldo:.2f}) != saldo faktury ({float_or_zero(invoice.saldo_z_rozliczenia):.2f})",
            {
                'tabela': 'electricity_invoices',
                'invoice_id': invoice.id,
                'pole': 'saldo_z_rozliczenia',
                'obliczone_saldo': calculated_saldo,
                'saldo_faktury': float_or_zero(invoice.saldo_z_rozliczenia),
                'naleznosc_za_okres': float_or_zero(invoice.naleznosc_za_okres),
                'wynik_rozliczenia': float_or_zero(invoice.wynik_rozliczenia),
                'odsetki': float_or_zero(invoice.odsetki),
                'kwota_nadplacona': float_or_zero(invoice.kwota_nadplacona),
                'roznica': abs(calculated_saldo - float_or_zero(invoice.saldo_z_rozliczenia))
            }
        )
    
    # 1.5. AKCYZA
    if invoice.energia_do_akcyzy_kwh > invoice.zuzycie_kwh:
        result.add_warning(
            'PRĄD', invoice_id, 'Akcyza',
            f"Energia do akcyzy ({invoice.energia_do_akcyzy_kwh}) > zużycie ({invoice.zuzycie_kwh})"
        )
    
    # 1.6. TARYFA
    if invoice.typ_taryfy == "DWUTARYFOWA" and sales:
        strefy = [s.strefa for s in sales if float(s.naleznosc) >= 0 and s.strefa]
        if "DZIENNA" not in strefy or "NOCNA" not in strefy:
            result.add_warning(
                'PRĄD', invoice_id, 'Taryfa',
                f"Taryfa dwutaryfowa, ale brak pozycji dziennej lub nocnej. Strefy: {set(strefy)}"
            )
    
    result.validated_count += 1


def validate_water_invoice(invoice: WaterInvoice, result: ValidationResult):
    """Waliduje fakturę wody."""
    invoice_id = f"{invoice.invoice_number} ({invoice.data})"
    result.total_count += 1
    
    # 2.1. POZYCJE WODY I ŚCIEKÓW
    usage = float(invoice.usage)
    water_cost_m3 = float(invoice.water_cost_m3)
    sewage_cost_m3 = float(invoice.sewage_cost_m3)
    vat = float(invoice.vat)
    
    # Oblicz wartości netto
    water_value_netto = usage * water_cost_m3
    sewage_value_netto = usage * sewage_cost_m3
    
    # Oblicz wartości brutto
    water_value_brutto = water_value_netto * (1 + vat)
    sewage_value_brutto = sewage_value_netto * (1 + vat)
    
    # 2.2. ABONAMENTY
    nr_of_subscription = int(invoice.nr_of_subscription)
    water_subscr_cost = float(invoice.water_subscr_cost)
    sewage_subscr_cost = float(invoice.sewage_subscr_cost)
    
    water_subscr_netto = nr_of_subscription * water_subscr_cost
    sewage_subscr_netto = nr_of_subscription * sewage_subscr_cost
    
    water_subscr_brutto = water_subscr_netto * (1 + vat)
    sewage_subscr_brutto = sewage_subscr_netto * (1 + vat)
    
    # 2.4. SUMY
    total_netto = water_value_netto + sewage_value_netto + water_subscr_netto + sewage_subscr_netto
    total_brutto_calculated = total_netto * (1 + vat)
    total_brutto_sum = water_value_brutto + sewage_value_brutto + water_subscr_brutto + sewage_subscr_brutto
    
    if not check_approx_equal(total_brutto_calculated, float(invoice.gross_sum), TOLERANCE_PLN * 10):
        result.add_warning(
            'WODA', invoice_id, 'Suma brutto',
            f"Obliczona suma brutto ({total_brutto_calculated:.2f}) != suma faktury ({float(invoice.gross_sum):.2f})",
            {
                'tabela': 'invoices',
                'invoice_id': invoice.id,
                'pole': 'gross_sum',
                'obliczona_suma_brutto': total_brutto_calculated,
                'suma_faktury': float(invoice.gross_sum),
                'total_netto': total_netto,
                'vat': vat,
                'roznica': abs(total_brutto_calculated - float(invoice.gross_sum))
            }
        )
    
    if not check_approx_equal(total_brutto_sum, float(invoice.gross_sum), TOLERANCE_PLN * 10):
        result.add_warning(
            'WODA', invoice_id, 'Suma brutto - suma pozycji',
            f"Suma pozycji brutto ({total_brutto_sum:.2f}) != suma faktury ({float(invoice.gross_sum):.2f})",
            {
                'tabela': 'invoices',
                'invoice_id': invoice.id,
                'pole': 'gross_sum',
                'suma_pozycji_brutto': total_brutto_sum,
                'suma_faktury': float(invoice.gross_sum),
                'water_value_brutto': water_value_brutto,
                'sewage_value_brutto': sewage_value_brutto,
                'water_subscr_brutto': water_subscr_brutto,
                'sewage_subscr_brutto': sewage_subscr_brutto,
                'roznica': abs(total_brutto_sum - float(invoice.gross_sum))
            }
        )
    
    # 2.5. OKRES ROZLICZENIOWY
    if invoice.period_start >= invoice.period_stop:
        result.add_critical(
            'WODA', invoice_id, 'Daty okresu',
            f"Data początku ({invoice.period_start}) >= data końca ({invoice.period_stop})"
        )
    
    days_diff = (invoice.period_stop - invoice.period_start).days
    expected_months = days_diff / 30.0
    if abs(expected_months - nr_of_subscription) > 1.0:
        result.add_info(
            'WODA', invoice_id, 'Okres abonamentu',
            f"Liczba dni ({days_diff}) nie odpowiada liczbie miesięcy abonamentu ({nr_of_subscription})"
        )
    
    result.validated_count += 1


def validate_gas_invoice(invoice: GasInvoice, result: ValidationResult):
    """Waliduje fakturę gazu."""
    invoice_id = f"{invoice.invoice_number} ({invoice.data})"
    result.total_count += 1
    
    vat_rate = float_or_zero(invoice.vat_rate)
    
    # 3.1. PALIWO GAZOWE
    if invoice.previous_reading and invoice.current_reading:
        calculated_usage_m3 = float(invoice.current_reading) - float(invoice.previous_reading)
        if not check_approx_equal(calculated_usage_m3, float_or_zero(invoice.fuel_usage_m3), TOLERANCE_M3):
            result.add_warning(
                'GAZ', invoice_id, 'Zużycie paliwa',
                f"Obliczone zużycie z odczytów ({calculated_usage_m3:.2f}) != zużycie faktury ({float_or_zero(invoice.fuel_usage_m3):.2f})"
            )
    
    if invoice.fuel_conversion_factor and invoice.fuel_usage_m3:
        calculated_kwh = float(invoice.fuel_usage_m3) * float(invoice.fuel_conversion_factor)
        if not check_approx_equal(calculated_kwh, float_or_zero(invoice.fuel_usage_kwh), TOLERANCE_KWH):
            result.add_warning(
                'GAZ', invoice_id, 'Konwersja m³ na kWh',
                f"Obliczone kWh ({calculated_kwh:.0f}) != kWh faktury ({float_or_zero(invoice.fuel_usage_kwh):.0f})",
                {
                    'tabela': 'gas_invoices',
                    'invoice_id': invoice.id,
                    'pole': 'fuel_usage_kwh',
                    'fuel_usage_m3': float(invoice.fuel_usage_m3),
                    'fuel_conversion_factor': float(invoice.fuel_conversion_factor),
                    'fuel_usage_kwh': float_or_zero(invoice.fuel_usage_kwh),
                    'obliczone_kwh': calculated_kwh,
                    'roznica': abs(calculated_kwh - float_or_zero(invoice.fuel_usage_kwh))
                }
            )
    
    if invoice.fuel_price_net and invoice.fuel_usage_kwh:
        calculated_value_net = float(invoice.fuel_usage_kwh) * float(invoice.fuel_price_net)
        if not check_approx_equal(calculated_value_net, float_or_zero(invoice.fuel_value_net), TOLERANCE_PLN * 10):
            result.add_warning(
                'GAZ', invoice_id, 'Wartość paliwa',
                f"Obliczona wartość netto ({calculated_value_net:.2f}) != wartość faktury ({float_or_zero(invoice.fuel_value_net):.2f})",
                {
                    'tabela': 'gas_invoices',
                    'invoice_id': invoice.id,
                    'pole': 'fuel_value_net',
                    'fuel_usage_kwh': float(invoice.fuel_usage_kwh),
                    'fuel_price_net': float(invoice.fuel_price_net),
                    'fuel_value_net': float_or_zero(invoice.fuel_value_net),
                    'obliczona_wartosc_netto': calculated_value_net,
                    'roznica': abs(calculated_value_net - float_or_zero(invoice.fuel_value_net))
                }
            )
    
    # 3.2. ABONAMENT
    if invoice.subscription_quantity and invoice.subscription_price_net:
        calculated_subscr_net = float(invoice.subscription_quantity) * float(invoice.subscription_price_net)
        if not check_approx_equal(calculated_subscr_net, float_or_zero(invoice.subscription_value_net), TOLERANCE_PLN):
            result.add_warning(
                'GAZ', invoice_id, 'Abonament',
                f"Obliczona wartość netto ({calculated_subscr_net:.2f}) != wartość faktury ({float_or_zero(invoice.subscription_value_net):.2f})"
            )
    
    # 3.3. DYSTRYBUCJA STAŁA
    if invoice.distribution_fixed_quantity and invoice.distribution_fixed_price_net:
        calculated_dist_fixed_net = float(invoice.distribution_fixed_quantity) * float(invoice.distribution_fixed_price_net)
        if not check_approx_equal(calculated_dist_fixed_net, float_or_zero(invoice.distribution_fixed_value_net), TOLERANCE_PLN):
            result.add_warning(
                'GAZ', invoice_id, 'Dystrybucja stała',
                f"Obliczona wartość netto ({calculated_dist_fixed_net:.2f}) != wartość faktury ({float_or_zero(invoice.distribution_fixed_value_net):.2f})"
            )
    
    # 3.4. DYSTRYBUCJA ZMIENNA
    if invoice.distribution_variable_usage_m3 and invoice.distribution_variable_conversion_factor:
        calculated_kwh = float(invoice.distribution_variable_usage_m3) * float(invoice.distribution_variable_conversion_factor)
        if not check_approx_equal(calculated_kwh, float_or_zero(invoice.distribution_variable_usage_kwh), TOLERANCE_KWH):
            result.add_warning(
                'GAZ', invoice_id, 'Dystrybucja zmienna - konwersja',
                f"Obliczone kWh ({calculated_kwh:.0f}) != kWh faktury ({float_or_zero(invoice.distribution_variable_usage_kwh):.0f})",
                {
                    'tabela': 'gas_invoices',
                    'invoice_id': invoice.id,
                    'pole': 'distribution_variable_usage_kwh',
                    'distribution_variable_usage_m3': float(invoice.distribution_variable_usage_m3),
                    'distribution_variable_conversion_factor': float(invoice.distribution_variable_conversion_factor),
                    'distribution_variable_usage_kwh': float_or_zero(invoice.distribution_variable_usage_kwh),
                    'obliczone_kwh': calculated_kwh,
                    'roznica': abs(calculated_kwh - float_or_zero(invoice.distribution_variable_usage_kwh))
                }
            )
    
    if invoice.distribution_variable_usage_kwh and invoice.distribution_variable_price_net:
        calculated_value_net = float(invoice.distribution_variable_usage_kwh) * float(invoice.distribution_variable_price_net)
        if not check_approx_equal(calculated_value_net, float_or_zero(invoice.distribution_variable_value_net), TOLERANCE_PLN * 10):
            result.add_warning(
                'GAZ', invoice_id, 'Dystrybucja zmienna - wartość',
                f"Obliczona wartość netto ({calculated_value_net:.2f}) != wartość faktury ({float_or_zero(invoice.distribution_variable_value_net):.2f})",
                {
                    'tabela': 'gas_invoices',
                    'invoice_id': invoice.id,
                    'pole': 'distribution_variable_value_net',
                    'distribution_variable_usage_kwh': float(invoice.distribution_variable_usage_kwh),
                    'distribution_variable_price_net': float(invoice.distribution_variable_price_net),
                    'distribution_variable_value_net': float_or_zero(invoice.distribution_variable_value_net),
                    'obliczona_wartosc_netto': calculated_value_net,
                    'roznica': abs(calculated_value_net - float_or_zero(invoice.distribution_variable_value_net))
                }
            )
    
    # 3.5. PODSUMOWANIE FINANSOWE
    total_net_calculated = (
        float_or_zero(invoice.fuel_value_net) +
        float_or_zero(invoice.subscription_value_net) +
        float_or_zero(invoice.distribution_fixed_value_net) +
        float_or_zero(invoice.distribution_variable_value_net)
    )
    
    if invoice.distribution_variable_2_value_net:
        total_net_calculated += float_or_zero(invoice.distribution_variable_2_value_net)
    
    if not check_approx_equal(total_net_calculated, float_or_zero(invoice.total_net_sum), TOLERANCE_PLN * 10):
        result.add_warning(
            'GAZ', invoice_id, 'Suma netto',
            f"Obliczona suma netto ({total_net_calculated:.2f}) != suma faktury ({float_or_zero(invoice.total_net_sum):.2f})"
        )
    
    calculated_vat = total_net_calculated * vat_rate
    if not check_approx_equal(calculated_vat, float_or_zero(invoice.vat_amount), TOLERANCE_PLN * 10):
        result.add_warning(
            'GAZ', invoice_id, 'VAT',
            f"Obliczony VAT ({calculated_vat:.2f}) != VAT faktury ({float_or_zero(invoice.vat_amount):.2f})"
        )
    
    calculated_gross = total_net_calculated * (1 + vat_rate)
    if not check_approx_equal(calculated_gross, float_or_zero(invoice.total_gross_sum), TOLERANCE_PLN * 10):
        result.add_warning(
            'GAZ', invoice_id, 'Suma brutto',
            f"Obliczona suma brutto ({calculated_gross:.2f}) != suma faktury ({float_or_zero(invoice.total_gross_sum):.2f})"
        )
    
    calculated_amount_to_pay = float_or_zero(invoice.total_gross_sum) + float_or_zero(invoice.late_payment_interest)
    if not check_approx_equal(calculated_amount_to_pay, float_or_zero(invoice.amount_to_pay), TOLERANCE_PLN):
        result.add_warning(
            'GAZ', invoice_id, 'Kwota do zapłaty',
            f"Obliczona kwota ({calculated_amount_to_pay:.2f}) != kwota faktury ({float_or_zero(invoice.amount_to_pay):.2f})"
        )
    
    # 3.6. OKRES ROZLICZENIOWY
    if invoice.period_start >= invoice.period_stop:
        result.add_critical(
            'GAZ', invoice_id, 'Daty okresu',
            f"Data początku ({invoice.period_start}) >= data końca ({invoice.period_stop})"
        )
    
    result.validated_count += 1


def format_details(details: Dict) -> str:
    """Formatuje szczegóły do czytelnej formy."""
    if not details:
        return ""
    
    parts = []
    if 'tabela' in details:
        parts.append(f"**Tabela:** `{details['tabela']}`")
    if 'invoice_id' in details:
        parts.append(f"**ID faktury:** {details['invoice_id']}")
    if 'sale_id' in details:
        parts.append(f"**ID sprzedaży:** {details['sale_id']}")
    if 'fee_id' in details:
        parts.append(f"**ID opłaty:** {details['fee_id']}")
    if 'reading_id' in details:
        parts.append(f"**ID odczytu:** {details['reading_id']}")
    if 'pole' in details:
        parts.append(f"**Pole:** `{details['pole']}`")
    if 'strefa' in details:
        parts.append(f"**Strefa:** {details['strefa']}")
    if 'typ_oplaty' in details:
        parts.append(f"**Typ opłaty:** {details['typ_oplaty']}")
    
    # Szczegóły dla sprzedaży energii
    if 'ilosc_kwh' in details and 'cena_za_kwh' in details:
        parts.append(f"**Ilość:** {details['ilosc_kwh']:.0f} kWh")
        parts.append(f"**Cena za kWh:** {details['cena_za_kwh']:.4f} zł")
        if 'naleznosc' in details:
            parts.append(f"**Należność (faktura):** {details['naleznosc']:.2f} zł")
        if 'obliczona_naleznosc' in details:
            parts.append(f"**Należność (obliczona):** {details['obliczona_naleznosc']:.2f} zł")
    
    # Szczegóły dla opłat dystrybucyjnych
    if 'jednostka' in details:
        parts.append(f"**Jednostka:** {details['jednostka']}")
        if details['jednostka'] == 'kWh' and 'ilosc_kwh' in details:
            parts.append(f"**Ilość:** {details['ilosc_kwh']:.0f} kWh")
            if 'cena' in details:
                parts.append(f"**Cena za kWh:** {details['cena']:.4f} zł")
        elif details['jednostka'] == 'zł/mc' and 'ilosc_miesiecy' in details:
            parts.append(f"**Ilość miesięcy:** {details['ilosc_miesiecy']:.0f}")
            if 'cena' in details:
                parts.append(f"**Cena za miesiąc:** {details['cena']:.2f} zł")
        if 'naleznosc' in details:
            parts.append(f"**Należność (faktura):** {details['naleznosc']:.2f} zł")
        if 'obliczona_naleznosc' in details:
            parts.append(f"**Należność (obliczona):** {details['obliczona_naleznosc']:.2f} zł")
    
    # Szczegóły dla odczytów
    if 'biezacy_odczyt' in details and 'poprzedni_odczyt' in details:
        parts.append(f"**Odczyt bieżący:** {details['biezacy_odczyt']:.0f}")
        parts.append(f"**Odczyt poprzedni:** {details['poprzedni_odczyt']:.0f}")
        if 'mnozna' in details:
            parts.append(f"**Mnożna:** {details['mnozna']:.0f}")
        if 'ilosc_kwh' in details:
            parts.append(f"**Ilość (faktura):** {details['ilosc_kwh']:.0f} kWh")
        if 'obliczona_ilosc' in details:
            parts.append(f"**Ilość (obliczona):** {details['obliczona_ilosc']:.0f} kWh")
        if 'straty_kwh' in details:
            parts.append(f"**Straty:** {details['straty_kwh']:.0f} kWh")
        if 'razem_kwh' in details:
            parts.append(f"**Razem (faktura):** {details['razem_kwh']:.0f} kWh")
        if 'obliczone_razem' in details:
            parts.append(f"**Razem (obliczone):** {details['obliczone_razem']:.0f} kWh")
    
    # Szczegóły dla sum
    if 'suma_netto_z_pozycji' in details:
        parts.append(f"**Suma netto (z pozycji):** {details['suma_netto_z_pozycji']:.2f} zł")
    if 'energia_netto_faktury' in details:
        parts.append(f"**Energia netto (faktura):** {details['energia_netto_faktury']:.2f} zł")
    if 'suma_zuzycia_z_pozycji' in details:
        parts.append(f"**Suma zużycia (z pozycji):** {details['suma_zuzycia_z_pozycji']:.0f} kWh")
    if 'zuzycie_faktury' in details:
        parts.append(f"**Zużycie (faktura):** {details['zuzycie_faktury']:.0f} kWh")
    if 'obliczona_suma_brutto' in details:
        parts.append(f"**Suma brutto (obliczona):** {details['obliczona_suma_brutto']:.2f} zł")
    if 'suma_faktury' in details:
        parts.append(f"**Suma (faktura):** {details['suma_faktury']:.2f} zł")
    if 'suma_pozycji_brutto' in details:
        parts.append(f"**Suma pozycji brutto:** {details['suma_pozycji_brutto']:.2f} zł")
    if 'obliczone_saldo' in details:
        parts.append(f"**Saldo (obliczone):** {details['obliczone_saldo']:.2f} zł")
    if 'saldo_faktury' in details:
        parts.append(f"**Saldo (faktura):** {details['saldo_faktury']:.2f} zł")
    
    # Szczegóły dla gazu
    if 'fuel_usage_m3' in details:
        parts.append(f"**Zużycie m³:** {details['fuel_usage_m3']:.2f}")
    if 'fuel_conversion_factor' in details:
        parts.append(f"**Współczynnik konwersji:** {details['fuel_conversion_factor']:.4f}")
    if 'fuel_usage_kwh' in details:
        parts.append(f"**Zużycie kWh:** {details['fuel_usage_kwh']:.0f}")
    if 'fuel_price_net' in details:
        parts.append(f"**Cena netto za kWh:** {details['fuel_price_net']:.4f} zł")
    if 'fuel_value_net' in details:
        parts.append(f"**Wartość netto (faktura):** {details['fuel_value_net']:.2f} zł")
    if 'distribution_variable_usage_m3' in details:
        parts.append(f"**Zużycie m³ (dystrybucja):** {details['distribution_variable_usage_m3']:.2f}")
    if 'distribution_variable_conversion_factor' in details:
        parts.append(f"**Współczynnik (dystrybucja):** {details['distribution_variable_conversion_factor']:.4f}")
    if 'distribution_variable_usage_kwh' in details:
        parts.append(f"**Zużycie kWh (dystrybucja):** {details['distribution_variable_usage_kwh']:.0f}")
    if 'distribution_variable_price_net' in details:
        parts.append(f"**Cena netto za kWh (dystrybucja):** {details['distribution_variable_price_net']:.4f} zł")
    if 'distribution_variable_value_net' in details:
        parts.append(f"**Wartość netto (dystrybucja, faktura):** {details['distribution_variable_value_net']:.2f} zł")
    
    if 'roznica' in details:
        parts.append(f"**Różnica:** {details['roznica']:.2f}")
    
    return " | ".join(parts)


def generate_markdown_report(result: ValidationResult) -> str:
    """Generuje raport w formacie Markdown."""
    lines = []
    lines.append("# Raport Walidacji Faktur")
    lines.append("")
    lines.append(f"**Data wygenerowania:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    lines.append(f"**Zwalidowane faktury:** {result.validated_count} / {result.total_count}")
    lines.append("")
    
    # Statystyki
    lines.append("## Statystyki")
    lines.append("")
    lines.append(f"- ✅ **Zwalidowane:** {result.validated_count}")
    lines.append(f"- ❌ **Błędy krytyczne:** {len(result.critical_errors)}")
    lines.append(f"- ⚠️ **Ostrzeżenia:** {len(result.warnings)}")
    lines.append(f"- ℹ️ **Informacje:** {len(result.info)}")
    lines.append("")
    
    # Błędy krytyczne
    if result.critical_errors:
        lines.append("## ❌ Błędy Krytyczne")
        lines.append("")
        for error in result.critical_errors:
            lines.append(f"### {error['invoice_type']} - {error['invoice_id']}")
            lines.append(f"**Sprawdzenie:** {error['check_name']}")
            lines.append(f"**Błąd:** {error['message']}")
            if error['details']:
                lines.append(f"**Szczegóły:** {error['details']}")
            lines.append("")
    
    # Ostrzeżenia
    if result.warnings:
        lines.append("## ⚠️ Ostrzeżenia")
        lines.append("")
        # Grupuj po typie faktury
        by_type = {}
        for warning in result.warnings:
            inv_type = warning['invoice_type']
            if inv_type not in by_type:
                by_type[inv_type] = []
            by_type[inv_type].append(warning)
        
        for inv_type, warnings_list in by_type.items():
            lines.append(f"### {inv_type}")
            lines.append("")
            for warning in warnings_list:
                lines.append(f"- **{warning['invoice_id']}** - {warning['check_name']}: {warning['message']}")
                details_str = format_details(warning.get('details', {}))
                if details_str:
                    lines.append(f"  - *{details_str}*")
            lines.append("")
    
    # Informacje
    if result.info:
        lines.append("## ℹ️ Informacje")
        lines.append("")
        for info in result.info:
            lines.append(f"- **{info['invoice_id']}** - {info['check_name']}: {info['message']}")
        lines.append("")
    
    # Wnioski
    lines.append("## 📊 Wnioski")
    lines.append("")
    
    if not result.critical_errors and not result.warnings:
        lines.append("✅ **Wszystkie faktury są poprawnie sparsowane!**")
        lines.append("")
        lines.append("Nie znaleziono żadnych błędów krytycznych ani ostrzeżeń.")
    else:
        if result.critical_errors:
            lines.append(f"❌ **Znaleziono {len(result.critical_errors)} błędów krytycznych** wymagających natychmiastowej naprawy.")
            lines.append("")
        
        if result.warnings:
            lines.append(f"⚠️ **Znaleziono {len(result.warnings)} ostrzeżeń** - warto je sprawdzić i poprawić.")
            lines.append("")
        
        # Statystyki po typach
        errors_by_type = {}
        warnings_by_type = {}
        for error in result.critical_errors:
            inv_type = error['invoice_type']
            errors_by_type[inv_type] = errors_by_type.get(inv_type, 0) + 1
        
        for warning in result.warnings:
            inv_type = warning['invoice_type']
            warnings_by_type[inv_type] = warnings_by_type.get(inv_type, 0) + 1
        
        if errors_by_type or warnings_by_type:
            lines.append("### Rozkład błędów i ostrzeżeń po typach faktur:")
            lines.append("")
            for inv_type in set(list(errors_by_type.keys()) + list(warnings_by_type.keys())):
                errors_count = errors_by_type.get(inv_type, 0)
                warnings_count = warnings_by_type.get(inv_type, 0)
                lines.append(f"- **{inv_type}:** {errors_count} błędów krytycznych, {warnings_count} ostrzeżeń")
            lines.append("")
        
        # Najczęstsze problemy
        check_counts = {}
        for error in result.critical_errors + result.warnings:
            check_name = error['check_name']
            check_counts[check_name] = check_counts.get(check_name, 0) + 1
        
        if check_counts:
            lines.append("### Najczęstsze problemy:")
            lines.append("")
            sorted_checks = sorted(check_counts.items(), key=lambda x: x[1], reverse=True)
            for check_name, count in sorted_checks[:10]:
                lines.append(f"- {check_name}: {count} wystąpień")
            lines.append("")
    
    lines.append("---")
    lines.append("")
    lines.append("*Raport wygenerowany automatycznie przez skrypt walidacji faktur*")
    
    return "\n".join(lines)


def main():
    """Główna funkcja walidacji."""
    print("Rozpoczynam walidacje faktur...")
    print("")
    
    db = SessionLocal()
    result = ValidationResult()
    
    try:
        # Waliduj faktury prądu
        print("Walidacja faktur pradu...")
        electricity_invoices = db.query(ElectricityInvoice).all()
        print(f"   Znaleziono {len(electricity_invoices)} faktur pradu")
        for invoice in electricity_invoices:
            validate_electricity_invoice(invoice, db, result)
        
        # Waliduj faktury wody
        print("Walidacja faktur wody...")
        water_invoices = db.query(WaterInvoice).all()
        print(f"   Znaleziono {len(water_invoices)} faktur wody")
        for invoice in water_invoices:
            validate_water_invoice(invoice, result)
        
        # Waliduj faktury gazu
        print("Walidacja faktur gazu...")
        gas_invoices = db.query(GasInvoice).all()
        print(f"   Znaleziono {len(gas_invoices)} faktur gazu")
        for invoice in gas_invoices:
            validate_gas_invoice(invoice, result)
        
        print("")
        print("Walidacja zakonczona!")
        print("")
        print(f"   Zwalidowane: {result.validated_count} / {result.total_count}")
        print(f"   Bledy krytyczne: {len(result.critical_errors)}")
        print(f"   Ostrzezenia: {len(result.warnings)}")
        print(f"   Informacje: {len(result.info)}")
        print("")
        
        # Generuj raport
        report = generate_markdown_report(result)
        report_path = project_root / "prad_walidacja_faktur.md"
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"Raport zapisany do: {report_path}")
        
    finally:
        db.close()


if __name__ == "__main__":
    main()

