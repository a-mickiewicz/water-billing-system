"""
Wyciąganie danych z faktur za prąd w strukturze zgodnej z poprawionym formatem.
"""

import re
from pathlib import Path
from typing import List, Dict, Optional


def extract_invoice_number(text: str) -> Optional[str]:
    """Wyciąga numer faktury."""
    match = re.search(r'FAKTURA VAT NR\s+([A-Z0-9/]+)', text, re.IGNORECASE)
    return match.group(1) if match else None


def extract_period(text: str) -> Optional[Dict[str, str]]:
    """Wyciąga okres rozliczeniowy."""
    match = re.search(r'Należność za okres od\s+(\d{1,2}/\d{1,2}/\d{4})\s+do\s+(\d{1,2}/\d{1,2}/\d{4})', text)
    if match:
        return {'od': match.group(1), 'do': match.group(2)}
    return None


def extract_financial_summary(text: str) -> Dict[str, str]:
    """Wyciąga podsumowanie finansowe."""
    data = {}
    
    # Należność za okres - wartość brutto z linii "1. Należność za okres od DD/MM/YYYY do DD/MM/YYYY KWOTA"
    match = re.search(r'1\.\s+Należność za okres[^0-9]+(\d{1,2}/\d{1,2}/\d{4})\s+do\s+(\d{1,2}/\d{1,2}/\d{4})\s+([\d.,]+)', text)
    if match:
        data['naleznosc_za_okres'] = match.group(3)
    
    # Wartość prognozy z poprzedniej faktury
    match = re.search(r'2\.\s+Wartość prognozy z poprzedniej faktury\s+([\d.,]+)', text)
    if match:
        data['wartosc_prognozy'] = match.group(1)
    
    # Faktury korygujące
    match = re.search(r'3\.\s+Faktury korygujące\s+([\d.,-]+)', text)
    if match:
        data['faktury_korygujace'] = match.group(1)
    
    # Odsetki
    match = re.search(r'4\.\s+Odsetki\s+([\d.,-]+)', text)
    if match:
        data['odsetki'] = match.group(1)
    
    # Bonifikata (jeśli istnieje)
    match = re.search(r'5\.\s+Bonifikata\s+([\d.,-]+)', text)
    if match:
        data['bonifikata'] = match.group(1)
    
    # Wynik rozliczenia - właściwa wartość z "Saldo ( X - Y )" lub "Wynik rozliczenia ( 1 - 2 + 3 + 4 )"
    # Szukaj "6. Wynik rozliczenia ( 1 - 2 + 3 + 4 ) KWOTA" lub "Saldo ( 6 - 7 ) KWOTA"
    match = re.search(r'(?:6\.\s+Wynik rozliczenia[^:]*:\s+|Saldo\s+\([^)]+\)\s+)([\d.,-]+)', text)
    if match:
        data['wynik_rozliczenia'] = match.group(1)
    
    # Kwota nadpłacona
    match = re.search(r'(?:6\.|7\.)\s+Kwota nadpłacona\s+([\d.,-]+)', text)
    if match:
        data['kwota_nadplacona'] = match.group(1)
    
    # Saldo z rozliczenia
    match = re.search(r'Saldo z rozliczenia:\s+([\d.,-]+)\s*zł', text)
    if match:
        data['saldo_z_rozliczenia'] = match.group(1)
    
    # Niedopłata/Nadpłata
    match = re.search(r'(?:Niedopłata|Nadpłata):\s+([\d.,-]+)\s*zł', text)
    if match:
        data['niedoplata_nadplata'] = match.group(1)
    
    # Energia do akcyzy
    match = re.search(r'Od\s+(\d+)\s+kWh energii elektrycznej czynnej', text)
    if match:
        data['energia_do_akcyzy_kwh'] = match.group(1)
    
    # Akcyza
    match = re.search(r'naliczono akcyzę w kwocie\s+([\d.,-]+)\s*zł', text)
    if match:
        data['akcyza'] = match.group(1)
    
    # Zużycie po bilansowaniu
    match = re.search(r'Zużycie po bilansowaniu:\s+([\d.,]+)\s*kWh', text)
    if match:
        data['zuzycie_po_bilansowaniu_kwh'] = match.group(1).replace('.', '')
    
    return data


def extract_prognosis_blankets(text: str) -> List[Dict[str, str]]:
    """Wyciąga blankiety prognozowe."""
    blankets = []
    
    # Szukaj sekcji z blankietami
    # Format dwutaryfowy: P/... DD/MM/YYYY - DD/MM/YYYY ILOŚĆ_D ILOŚĆ_C KWOTA AKCYZA ENERGIA NADPŁATA ODSETKI TERMIN DO_ZAPŁATY
    # Format całodobowy: P/... DD/MM/YYYY - DD/MM/YYYY ILOŚĆ_CALODOBOWA KWOTA AKCYZA ENERGIA NADPŁATA ODSETKI TERMIN DO_ZAPŁATY
    # Spróbuj najpierw format dwutaryfowy (z dwoma wartościami ilości)
    pattern_dwutaryfowy = r'P/(\d+)/(\d+)/(\d+)/(\d+)\s+(\d{1,2}/\d{1,2}/\d{4})\s+-\s+(\d{1,2}/\d{1,2}/\d{4})\s+(\d+)\s+(\d+)\s+([\d.,]+)\s+([\d.,]+)\s+(\d+)\s+([\d.,-]+)\s+([\d.,-]+)\s+(\d{1,2}/\d{1,2}/\d{4})\s+([\d.,-]+)'
    
    matches = re.finditer(pattern_dwutaryfowy, text)
    for match in matches:
        blankets.append({
            'nr_blankietu': f"P/{match.group(1)}/{match.group(2)}/{match.group(3)}/{match.group(4)}",
            'okres_od': match.group(5),
            'okres_do': match.group(6),
            'ilosc_d': match.group(7),
            'ilosc_c': match.group(8),
            'ilosc_calodobowa': None,  # Dla dwutaryfowej
            'kwota_brutto': match.group(9),
            'akcyza': match.group(10),
            'energia_do_akcyzy': match.group(11),
            'nadplata_niedoplata': match.group(12),
            'odsetki': match.group(13),
            'termin_platnosci': match.group(14),
            'do_zaplaty': match.group(15)
        })
    
    # Jeśli nie znaleziono blankietów dwutaryfowych, spróbuj format całodobowy (z jedną wartością ilości)
    if not blankets:
        # Format: P/... DD/MM/YYYY - DD/MM/YYYY ILOŚĆ_CALODOBOWA KWOTA AKCYZA ENERGIA NADPŁATA ODSETKI TERMIN DO_ZAPŁATY
        pattern_calodobowy = r'P/(\d+)/(\d+)/(\d+)/(\d+)\s+(\d{1,2}/\d{1,2}/\d{4})\s+-\s+(\d{1,2}/\d{1,2}/\d{4})\s+(\d+)\s+([\d.,]+)\s+([\d.,]+)\s+(\d+)\s+([\d.,-]+)\s+([\d.,-]+)\s+(\d{1,2}/\d{1,2}/\d{4})\s+([\d.,-]+)'
        matches = re.finditer(pattern_calodobowy, text)
        for match in matches:
            blankets.append({
                'nr_blankietu': f"P/{match.group(1)}/{match.group(2)}/{match.group(3)}/{match.group(4)}",
                'okres_od': match.group(5),
                'okres_do': match.group(6),
                'ilosc_d': None,  # Dla całodobowej
                'ilosc_c': None,  # Dla całodobowej
                'ilosc_calodobowa': match.group(7),  # Jedyna wartość ilości
                'kwota_brutto': match.group(8),
                'akcyza': match.group(9),
                'energia_do_akcyzy': match.group(10),
                'nadplata_niedoplata': match.group(11),
                'odsetki': match.group(12),
                'termin_platnosci': match.group(13),
                'do_zaplaty': match.group(14)
            })
    
    # Ogółem
    match = re.search(r'Ogółem:\s+([\d.,]+)\s+([\d.,]+)\s+(\d+)\s+([\d.,-]+)\s+([\d.,-]+)', text)
    if match:
        blankets.append({
            'ogolem': True,
            'kwota_brutto': match.group(1),
            'akcyza': match.group(2),
            'energia_do_akcyzy': match.group(3),
            'nadplata_niedoplata': match.group(4),
            'do_zaplaty': match.group(5)
        })
    
    return blankets


def extract_meter_readings(text: str) -> List[Dict[str, str]]:
    """Wyciąga odczyty liczników."""
    readings = []
    seen = set()  # Aby uniknąć duplikatów
    
    # Wyciągnij tylko pierwszą sekcję ODCZYTY (przed "Rozliczenie energii elektrycznej")
    odczyty_section_match = re.search(r'ODCZYTY(.*?)Rozliczenie energii elektrycznej', text, re.IGNORECASE | re.DOTALL)
    if not odczyty_section_match:
        # Jeśli nie ma sekcji "Rozliczenie energii elektrycznej", użyj całego tekstu
        odczyty_section = text
    else:
        odczyty_section = odczyty_section_match.group(1)
    
    # Odczyty energii czynnej pobranej
    # Format: po nagłówku "Licznik rozliczeniowy energii czynnej nr XXX" są linie:
    # "dzienna 31/12/2023 24.320 23.222 1 1.098 0 1.098"
    # lub "całodobowa 31/10/2025 2.273 1 1 2.272 Zdalny 0 2.272" (dla energii całodobowej)
    # Szukaj linii które zaczynają się od "dzienna", "nocna" lub "całodobowa" po nagłówku
    czynna_section = re.search(r'Licznik rozliczeniowy energii czynnej nr\s+\d+([^L]*(?=Licznik rozliczeniowy energii czynnej oddanej|Rozliczenie))', odczyty_section, re.IGNORECASE | re.DOTALL)
    if czynna_section:
        czynna_text = czynna_section.group(1)
        # Szukaj linii: "dzienna/nocna/całodobowa DD/MM/YYYY LICZBA LICZBA LICZBA LICZBA LICZBA LICZBA"
        # Dla całodobowej może być format: "całodobowa 31/10/2025 2.273 1 1 2.272 Zdalny 0 2.272"
        # Obsługa problemów z kodowaniem: "caodobowa" zamiast "całodobowa" (znak "ł" może być źle zakodowany)
        # Użyj bardziej elastycznego wzorca: "ca" + dowolny znak + "odobowa"
        pattern = r'(dzienna|nocna|ca[łl]?odobowa)\s+(\d{1,2}/\d{1,2}/\d{4})\s+(\d{1,3}(?:\.\d{3})*|\d+)\s+(\d{1,3}(?:\.\d{3})*|\d+)\s+(\d+)\s+(\d+(?:\.\d{3})*|\d+)\s+(\d+)\s+(\d+(?:\.\d{3})*|\d+)'
        matches = re.finditer(pattern, czynna_text, re.IGNORECASE)
        for match in matches:
            strefa = match.group(1).lower()
            # Obsługa problemów z kodowaniem - sprawdź czy zawiera "odobowa"
            if 'odobowa' in strefa:
                strefa = None  # Dla energii całodobowej strefa jest None
            key = f"pobrana_{strefa or 'calodobowa'}_{match.group(2)}_{match.group(3)}_{match.group(4)}"
            if key not in seen:
                seen.add(key)
                readings.append({
                    'typ': 'pobrana',
                    'strefa': strefa if strefa else None,
                    'data': match.group(2),
                    'biezace': match.group(3),
                    'poprzednie': match.group(4),
                    'mnozna': match.group(5),
                    'ilosc': match.group(6),
                    'straty': match.group(7),
                    'razem': match.group(8)
                })
    
    # Odczyty energii czynnej oddanej
    oddana_section = re.search(r'Licznik rozliczeniowy energii czynnej oddanej nr\s+\d+([^L]*(?=Licznik rozliczeniowy|Rozliczenie|$))', odczyty_section, re.IGNORECASE | re.DOTALL)
    if oddana_section:
        oddana_text = oddana_section.group(1)
        # Obsługa zarówno "dzienna"/"nocna" jak i "całodobowa" (z problemami kodowania)
        # Użyj bardziej elastycznego wzorca: "ca" + dowolny znak + "odobowa"
        pattern = r'(dzienna|nocna|ca[łl]?odobowa)\s+(\d{1,2}/\d{1,2}/\d{4})\s+(\d{1,3}(?:\.\d{3})*|\d+)\s+(\d{1,3}(?:\.\d{3})*|\d+)\s+(\d+)\s+(\d+(?:\.\d{3})*|\d+)\s+(\d+)\s+(\d+(?:\.\d{3})*|\d+)'
        matches = re.finditer(pattern, oddana_text, re.IGNORECASE)
        for match in matches:
            strefa = match.group(1).lower()
            # Obsługa problemów z kodowaniem - sprawdź czy zawiera "odobowa"
            if 'odobowa' in strefa:
                strefa = None  # Dla energii całodobowej strefa jest None
            key = f"oddana_{strefa or 'calodobowa'}_{match.group(2)}_{match.group(3)}_{match.group(4)}"
            if key not in seen:
                seen.add(key)
                readings.append({
                    'typ': 'oddana',
                    'strefa': strefa if strefa else None,
                    'data': match.group(2),
                    'biezace': match.group(3),
                    'poprzednie': match.group(4),
                    'mnozna': match.group(5),
                    'ilosc': match.group(6),
                    'straty': match.group(7),
                    'razem': match.group(8)
                })
    
    return readings


def extract_energy_sales(text: str) -> List[Dict[str, str]]:
    """Wyciąga pozycje sprzedaży energii."""
    sales = []
    seen = set()  # Aby uniknąć duplikatów
    
    # Pozycje energii - tylko z sekcji "ROZLICZENIE - SPRZEDAŻ ENERGII" lub "SPRZEDAŻ ENERGII"
    # Szukaj sekcji sprzedaży energii (obsługa problemów z kodowaniem: "SPRZEDA" zamiast "SPRZEDAŻ")
    sale_section_match = re.search(r'(?:ROZLICZENIE - )?SPRZEDA[ŻZ] ENERGII(.*?)(?:ROZLICZENIE - )?US[ŁL]UGA DYSTRYBUCJI', text, re.IGNORECASE | re.DOTALL)
    if sale_section_match:
        sale_section = sale_section_match.group(1)
        # Obsługa zarówno "dzienna"/"nocna" jak i energii całodobowej (z problemami kodowania)
        # Format może być: "dzienna kWh 123 0,1234 15,12 23" lub "caodobowa kWh 165 0,5050 83,33 23"
        pattern1 = r'(dzienna|nocna)\s+kWh\s+(\d+)\s+([\d.,]+)\s+([\d.,]+)\s+(\d+)'
        matches = re.finditer(pattern1, sale_section, re.IGNORECASE)
        for match in matches:
            key = f"{match.group(1)}_{match.group(2)}_{match.group(3)}_{match.group(4)}"
            if key not in seen:
                seen.add(key)
                sales.append({
                    'strefa': match.group(1),
                    'ilosc_kwh': match.group(2),
                    'cena': match.group(3),
                    'naleznosc': match.group(4),
                    'vat': match.group(5)
                })
        
        # Spróbuj też znaleźć energię całodobową (z problemami kodowania: "caodobowa")
        # Format: "caodobowa kWh 165 0,5050 83,33 23" lub "kWh 123 0,1234 15,12 23" (bez strefy)
        # Użyj bardziej elastycznego wzorca: "ca" + dowolny znak + "odobowa"
        pattern2 = r'ca[łl]?odobowa\s+kWh\s+(\d+)\s+([\d.,]+)\s+([\d.,]+)\s+(\d+)'
        matches2 = re.finditer(pattern2, sale_section, re.IGNORECASE)
        for match in matches2:
            key = f"calodobowa_{match.group(1)}_{match.group(2)}_{match.group(3)}"
            if key not in seen:
                seen.add(key)
                sales.append({
                    'strefa': None,  # Dla energii całodobowej strefa jest None
                    'ilosc_kwh': match.group(1),
                    'cena': match.group(2),
                    'naleznosc': match.group(3),
                    'vat': match.group(4)
                })
        
        # Alternatywny format bez słowa "całodobowa" - tylko "kWh" na początku linii
        pattern3 = r'^\s*kWh\s+(\d+)\s+([\d.,]+)\s+([\d.,]+)\s+(\d+)\s*$'
        matches3 = re.finditer(pattern3, sale_section, re.IGNORECASE | re.MULTILINE)
        for match in matches3:
            key = f"calodobowa_alt_{match.group(1)}_{match.group(2)}_{match.group(3)}"
            if key not in seen:
                seen.add(key)
                sales.append({
                    'strefa': None,  # Dla energii całodobowej strefa jest None
                    'ilosc_kwh': match.group(1),
                    'cena': match.group(2),
                    'naleznosc': match.group(3),
                    'vat': match.group(4)
                })
    
    # Upust (jeśli istnieje) - "Upust 10% za niższe zużycie energii - obrót zł -1 136,8700 -136,87 23"
    match = re.search(r'Upust\s+(\d+)%[^:]*obrót[^:]*zł\s+([\d.,-]+)\s+([\d.,-]+)\s+([\d.,-]+)\s+(\d+)', text, re.IGNORECASE)
    if match:
        sales.append({
            'typ': 'upust',
            'procent': match.group(1),
            'ilosc': match.group(2),
            'cena': match.group(3),
            'naleznosc': match.group(4),
            'vat': match.group(5)
        })
    
    return sales


def extract_distribution_fees(text: str) -> List[Dict[str, str]]:
    """Wyciąga opłaty dystrybucyjne."""
    fees = []
    seen = set()  # Aby uniknąć duplikatów
    
    # Wyciągnij sekcję dystrybucji - szukaj do końca sekcji (ogółem wartość - usługa dystrybucji)
    # Sekcja może być na wielu stronach, więc szukaj do "Ogółem wartość - usługa dystrybucji" ale przed "Zużycie po bilansowaniu"
    # Nie kończ na "Ogółem wartość - sprzedaż energii", tylko na "Ogółem wartość - usługa dystrybucji"
    dist_section_match = re.search(r'ROZLICZENIE - USŁUGA DYSTRYBUCJI ENERGII(.*?)(?:Ogółem wartość - usługa dystrybucji|Zużycie po bilansowaniu)', text, re.IGNORECASE | re.DOTALL)
    if not dist_section_match:
        return fees
    
    dist_section = dist_section_match.group(1)
    
    # Sprawdź czy sekcja zawiera "Ogółem wartość - sprzedaż energii" - jeśli tak, to może być problem
    # Ale w tym przypadku opłaty są po "Ogółem wartość - sprzedaż energii", więc powinny być w sekcji
    
    # Opłata stała sieciowa - nagłówek w jednej linii, dane w kolejnych
    # Format: "Opłata stała sieciowa - układ 3-fazowy\nzł/mc DD/MM/YYYY ILOŚĆ WSPÓŁ CENA NALEŻNOŚĆ VAT"
    pattern = r'Opłata stała sieciowa[^\n]*\nzł/mc\s+(\d{1,2}/\d{1,2}/\d{4})\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s+(\d+)'
    matches = re.finditer(pattern, dist_section, re.IGNORECASE | re.MULTILINE)
    for match in matches:
        key = f"stala_{match.group(1)}_{match.group(2)}"
        if key not in seen:
            seen.add(key)
            fees.append({
                'nazwa': 'Opłata stała sieciowa - układ 3-fazowy',
                'jednostka': 'zł/mc',
                'data': match.group(1),
                'ilosc_miesiecy': match.group(2),
                'wspolczynnik1': match.group(3),
                'cena': match.group(4),
                'naleznosc': match.group(5),
                'vat': match.group(6)
            })
    
    # Opłata przejściowa - może być wiele linii zł/mc po nagłówku
    przejściowa_section = re.search(r'Opłata przejściowa[^O]*(?=Opłata mocowa|Opłata zmienna|Ogółem)', dist_section, re.IGNORECASE | re.DOTALL)
    if przejściowa_section:
        przejściowa_text = przejściowa_section.group(0)
        pattern = r'zł/mc\s+(\d{1,2}/\d{1,2}/\d{4})\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s+(\d+)'
        matches = re.finditer(pattern, przejściowa_text, re.IGNORECASE)
        for match in matches:
            # Sprawdź czy to opłata przejściowa (cena około 0,33 zł)
            cena = float(match.group(4).replace(',', '.'))
            if 0.1 <= cena <= 1.0:  # Cena opłaty przejściowej jest w zakresie 0,1-1,0 zł
                key = f"przejściowa_{match.group(1)}_{match.group(2)}"
                if key not in seen:
                    seen.add(key)
                    fees.append({
                        'nazwa': 'Opłata przejściowa > 1200 kWh',
                        'jednostka': 'zł/mc',
                        'data': match.group(1),
                        'ilosc_miesiecy': match.group(2),
                        'wspolczynnik1': match.group(3),
                        'cena': match.group(4),
                        'naleznosc': match.group(5),
                        'vat': match.group(6)
                    })
    
    # Opłata mocowa - może być w dwóch miejscach: po nagłówku i dalej w tekście
    # Format: "Opłata mocowa ( > 2800 kWh)\nzł/mc DD/MM/YYYY ILOŚĆ WSPÓŁ CENA NALEŻNOŚĆ VAT"
    # Może też być w linii: "zł/mc 06/04/2024 3,2 14,9000 47,68 23" (bez nagłówka, dalej w tekście)
    # Najpierw szukaj po nagłówku
    mocowa_section = re.search(r'Opłata mocowa[^O]*(?=Opłata zmienna|Opłata jakościowa|Opłata OZE|Opłata kogeneracyjna|Opłata abonamentowa|Upust|Ogółem|Licznik)', dist_section, re.IGNORECASE | re.DOTALL)
    if mocowa_section:
        mocowa_text = mocowa_section.group(0)
        # Szukaj linii zł/mc które są opłatą mocową (cena 13-14 zł)
        # Format może być: "zł/mc 31/12/2023 2 13,3500 26,70 23" (bez współczynnika) lub "zł/mc 06/04/2024 3,2 14,9000 47,68 23" (ze współczynnikiem)
        # Wzorzec: zł/mc DATA ILOŚĆ [WSPÓŁ] CENA NALEŻNOŚĆ VAT
        pattern = r'zł/mc\s+(\d{1,2}/\d{1,2}/\d{4})\s+([\d.,]+)(?:\s+([\d.,]+))?\s+([\d.,]+)\s+([\d.,]+)\s+(\d+)'
        matches = re.finditer(pattern, mocowa_text, re.IGNORECASE)
        for match in matches:
            cena = float(match.group(4).replace(',', '.'))
            if 10 <= cena <= 20:  # Cena opłaty mocowej jest w zakresie 10-20 zł
                key = f"mocowa_{match.group(1)}_{match.group(2)}"
                if key not in seen:
                    seen.add(key)
                    # Współczynnik może być w group(3) lub może być None
                    wspolczynnik = match.group(3) if match.lastindex >= 3 and match.group(3) else ''
                    fees.append({
                        'nazwa': 'Opłata mocowa ( > 2800 kWh)',
                        'jednostka': 'zł/mc',
                        'data': match.group(1),
                        'ilosc_miesiecy': match.group(2),
                        'wspolczynnik1': wspolczynnik,
                        'cena': match.group(4),
                        'naleznosc': match.group(5),
                        'vat': match.group(6)
                    })
    
    # Szukaj też opłat mocowych które są po "Opłata zmienna" ale przed "Opłata jakościowa"
    # Są to linie typu "zł/mc 06/04/2024 3,2 14,9000 47,68 23" które są kontynuacją opłaty mocowej
    # Znajdź sekcję między "Opłata zmienna" a "Opłata jakościowa"
    after_zmienna = re.search(r'Opłata zmienna[^O]*(?=Opłata jakościowa)', dist_section, re.IGNORECASE | re.DOTALL)
    if after_zmienna:
        after_text = after_zmienna.group(0)
        # Szukaj linii zł/mc z ceną około 14,9 lub 13,3 (cena opłaty mocowej)
        pattern = r'zł/mc\s+(\d{1,2}/\d{1,2}/\d{4})\s+([\d.,]+)\s+([\d.,]+)\s+(1[3-5][,.]\d+)\s+([\d.,]+)\s+(\d+)'
        matches = re.finditer(pattern, after_text, re.IGNORECASE)
        for match in matches:
            cena = float(match.group(4).replace(',', '.'))
            if 13 <= cena <= 15:  # Cena opłaty mocowej jest w zakresie 13-15 zł
                key = f"mocowa_{match.group(1)}_{match.group(2)}"
                if key not in seen:
                    seen.add(key)
                    fees.append({
                        'nazwa': 'Opłata mocowa ( > 2800 kWh)',
                        'jednostka': 'zł/mc',
                        'data': match.group(1),
                        'ilosc_miesiecy': match.group(2),
                        'wspolczynnik1': match.group(3),
                        'cena': match.group(4),
                        'naleznosc': match.group(5),
                        'vat': match.group(6)
                    })
    
    # Opłata zmienna sieciowa - nagłówek w osobnej linii, dane w kolejnych
    zmienna_section = re.search(r'Opłata zmienna sieciowa(.*?)(?=Opłata jakościowa|Opłata OZE|Opłata kogeneracyjna|Opłata abonamentowa|Upust|Ogółem)', dist_section, re.IGNORECASE | re.DOTALL)
    if zmienna_section:
        zmienna_text = zmienna_section.group(1)
        pattern = r'(dzienna|nocna)\s+kWh\s+(\d{1,2}/\d{1,2}/\d{4})\s+(\d+)\s+([\d.,]+)\s+([\d.,]+)\s+(\d+)'
        matches = re.finditer(pattern, zmienna_text, re.IGNORECASE)
        for match in matches:
            key = f"zmienna_{match.group(2)}_{match.group(1)}_{match.group(3)}"
            if key not in seen:
                seen.add(key)
                fees.append({
                    'nazwa': 'Opłata zmienna sieciowa',
                    'strefa': match.group(1),
                    'jednostka': 'kWh',
                    'data': match.group(2),
                    'ilosc_kwh': match.group(3),
                    'cena': match.group(4),
                    'naleznosc': match.group(5),
                    'vat': match.group(6)
                })
    
    # Opłata jakościowa
    jakosciowa_section = re.search(r'Opłata jakościowa(.*?)(?=Opłata OZE|Opłata kogeneracyjna|Opłata abonamentowa|Upust|Ogółem)', dist_section, re.IGNORECASE | re.DOTALL)
    if jakosciowa_section:
        jakosciowa_text = jakosciowa_section.group(1)
        pattern = r'(dzienna|nocna)\s+kWh\s+(\d{1,2}/\d{1,2}/\d{4})\s+(\d+)\s+([\d.,]+)\s+([\d.,]+)\s+(\d+)'
        matches = re.finditer(pattern, jakosciowa_text, re.IGNORECASE)
        for match in matches:
            key = f"jakosciowa_{match.group(2)}_{match.group(1)}_{match.group(3)}"
            if key not in seen:
                seen.add(key)
                fees.append({
                    'nazwa': 'Opłata jakościowa',
                    'strefa': match.group(1),
                    'jednostka': 'kWh',
                    'data': match.group(2),
                    'ilosc_kwh': match.group(3),
                    'cena': match.group(4),
                    'naleznosc': match.group(5),
                    'vat': match.group(6)
                })
    
    # Opłata OZE
    oze_section = re.search(r'Opłata OZE(.*?)(?=Opłata kogeneracyjna|Opłata abonamentowa|Upust|Ogółem)', dist_section, re.IGNORECASE | re.DOTALL)
    if oze_section:
        oze_text = oze_section.group(1)
        pattern = r'(dzienna|nocna)\s+kWh\s+(\d{1,2}/\d{1,2}/\d{4})\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s+(\d+)'
        matches = re.finditer(pattern, oze_text, re.IGNORECASE)
        for match in matches:
            key = f"oze_{match.group(2)}_{match.group(1)}_{match.group(3)}"
            if key not in seen:
                seen.add(key)
                fees.append({
                    'nazwa': 'Opłata OZE',
                    'strefa': match.group(1),
                    'jednostka': 'kWh',
                    'data': match.group(2),
                    'ilosc_kwh': match.group(3).replace('.', ''),
                    'cena': match.group(4),
                    'naleznosc': match.group(5),
                    'vat': match.group(6)
                })
    
    # Opłata kogeneracyjna
    kogeneracyjna_section = re.search(r'Opłata kogeneracyjna(.*?)(?=Opłata abonamentowa|Upust|Ogółem)', dist_section, re.IGNORECASE | re.DOTALL)
    if kogeneracyjna_section:
        kogeneracyjna_text = kogeneracyjna_section.group(1)
        pattern = r'(dzienna|nocna)\s+kWh\s+(\d{1,2}/\d{1,2}/\d{4})\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s+(\d+)'
        matches = re.finditer(pattern, kogeneracyjna_text, re.IGNORECASE)
        for match in matches:
            key = f"kogeneracyjna_{match.group(2)}_{match.group(1)}_{match.group(3)}"
            if key not in seen:
                seen.add(key)
                fees.append({
                    'nazwa': 'Opłata kogeneracyjna',
                    'strefa': match.group(1),
                    'jednostka': 'kWh',
                    'data': match.group(2),
                    'ilosc_kwh': match.group(3).replace('.', ''),
                    'cena': match.group(4),
                    'naleznosc': match.group(5),
                    'vat': match.group(6)
                })
    
    # Opłata abonamentowa
    abonamentowa_section = re.search(r'Opłata abonamentowa(.*?)(?=Upust|Ogółem)', dist_section, re.IGNORECASE | re.DOTALL)
    if abonamentowa_section:
        abonamentowa_text = abonamentowa_section.group(1)
        pattern = r'zł/mc\s+(\d{1,2}/\d{1,2}/\d{4})\s+(\d+)\s+([\d.,]+)\s+([\d.,]+)\s+(\d+)'
        matches = re.finditer(pattern, abonamentowa_text, re.IGNORECASE)
        for match in matches:
            key = f"abonamentowa_{match.group(1)}_{match.group(2)}"
            if key not in seen:
                seen.add(key)
                fees.append({
                    'nazwa': 'Opłata abonamentowa',
                    'jednostka': 'zł/mc',
                    'data': match.group(1),
                    'ilosc_miesiecy': match.group(2),
                    'cena': match.group(3),
                    'naleznosc': match.group(4),
                    'vat': match.group(5)
                })
    
    # Upust (jeśli istnieje) - "Upust 10% za niższe zużycie energii - dystrybucja\nzł 31/10/2024 -1 66,0700 -66,07 23"
    match = re.search(r'Upust\s+(\d+)%[^\n]*dystrybucja[^\n]*\nzł\s+(\d{1,2}/\d{1,2}/\d{4})\s+([\d.,-]+)\s+([\d.,-]+)\s+([\d.,-]+)\s+(\d+)', dist_section, re.IGNORECASE | re.MULTILINE)
    if match:
        fees.append({
            'nazwa': 'Upust 10% za niższe zużycie energii - dystrybucja',
            'jednostka': 'zł',
            'data': match.group(2),
            'ilosc': match.group(3),
            'cena': match.group(4),
            'naleznosc': match.group(5),
            'vat': match.group(6)
        })
    
    return fees


def extract_summaries(text: str) -> Dict[str, str]:
    """Wyciąga podsumowania."""
    summaries = {}
    
    # Ogółem sprzedaż energii
    match = re.search(r'Ogółem wartość - sprzedaż energii:\s+([\d.,]+)', text, re.IGNORECASE)
    if match:
        summaries['ogolem_sprzedaz_energii'] = match.group(1)
    
    # Ogółem usługa dystrybucji
    match = re.search(r'Ogółem wartość - usługa dystrybucji:\s+([\d.,]+)', text, re.IGNORECASE)
    if match:
        summaries['ogolem_usluga_dystrybucji'] = match.group(1)
    
    # Ogółem wartość - szukaj "Ogółem wartość - 1.971,38" lub "Zużycie po bilansowaniu: 3.122 kWh Ogółem wartość: 1.971,38"
    # Format: "Zużycie po bilansowaniu: 3.122 kWh Ogółem wartość: 1.971,38"
    match = re.search(r'Zużycie po bilansowaniu[^:]*:\s+[\d.,]+\s+kWh[^:]*Ogółem wartość[^:]*:\s+([\d.,]+)', text, re.IGNORECASE | re.DOTALL)
    if match:
        summaries['ogolem_wartosc'] = match.group(1)
    
    # Grupa taryfowa
    match = re.search(r'Grupa taryfowa:\s+([A-Z0-9]+)', text)
    if match:
        summaries['grupa_taryfowa'] = match.group(1)
    
    # Energia zużyta w roku
    match = re.search(r'Energia zużyta w roku\s+(\d{4}):\s+(\d+)\s*kWh', text)
    if match:
        summaries['energia_zuzyta_w_roku'] = f"{match.group(2)} kWh"
        summaries['rok'] = match.group(1)
    
    return summaries


def format_output(invoice_name: str, data: Dict) -> str:
    """Formatuje dane do postaci zgodnej z poprawionym formatem."""
    lines = []
    
    lines.append(f"ANALIZA DANYCH LICZBOWYCH - {invoice_name}")
    lines.append("=" * 80)
    lines.append("")
    
    # Sekcja główna
    if 'invoice_number' in data:
        lines.append(f"Numer faktury: {data['invoice_number']}")
    
    if 'period' in data:
        lines.append(f"Okres od: {data['period']['od']} do: {data['period']['do']}")
    
    financial = data.get('financial', {})
    if 'naleznosc_za_okres' in financial:
        lines.append(f"Naleznosc za okres: {financial['naleznosc_za_okres']}")
    if 'wartosc_prognozy' in financial:
        lines.append(f"Wartosc prognozy: {financial['wartosc_prognozy']}")
    if 'faktury_korygujace' in financial:
        lines.append(f"Faktury korygujace: {financial['faktury_korygujace']}")
    if 'odsetki' in financial:
        lines.append(f"Odsetki: {financial['odsetki']}")
    if 'bonifikata' in financial:
        lines.append(f"Bonifikata: {financial['bonifikata']}")
    if 'wynik_rozliczenia' in financial:
        lines.append(f"Wynik rozliczenia: {financial['wynik_rozliczenia']}")
    if 'kwota_nadplacona' in financial:
        lines.append(f"Kwota nadplacona: {financial['kwota_nadplacona']}")
    if 'energia_do_akcyzy_kwh' in financial:
        lines.append(f"Energia do akcyzy kWh: {financial['energia_do_akcyzy_kwh']}")
    if 'akcyza' in financial:
        lines.append(f"Akcyza: {financial['akcyza']}")
    if 'saldo_z_rozliczenia' in financial:
        lines.append(f"Saldo z rozliczenia: {financial['saldo_z_rozliczenia']}")
    if 'zuzycie_po_bilansowaniu_kwh' in financial:
        lines.append(f"Zuzycie po bilansowaniu kWh: {financial['zuzycie_po_bilansowaniu_kwh']}")
    if 'niedoplata_nadplata' in financial:
        lines.append(f"Niedoplata: {financial['niedoplata_nadplata']}")
    
    lines.append("")
    
    # Przewidywane należności
    blankets = data.get('blankets', [])
    if blankets:
        # Okres przewidywanej należności (z pierwszego i ostatniego blankietu)
        if len(blankets) > 1 and not blankets[0].get('ogolem'):
            first = blankets[0]
            last = [b for b in blankets if not b.get('ogolem')][-1]
            lines.append(f"Okres przewidywanej naleznosci: {first['okres_od']} do {last['okres_do']}")
        
        # Ogółem
        ogolem = [b for b in blankets if b.get('ogolem')]
        if ogolem:
            lines.append(f"Przewidywalna naleznosc ogolem: {ogolem[0]['do_zaplaty']}")
        
        lines.append("")
        lines.append("")
        lines.append("Przewidywana naleznosc na okres: od " + (blankets[0]['okres_od'] if blankets else '') + " do " + (last['okres_do'] if len(blankets) > 1 else ''))
        
        for blanket in blankets:
            if not blanket.get('ogolem'):
                lines.append(f"{blanket['nr_blankietu']} {blanket['okres_od']} - {blanket['okres_do']}, {blanket['ilosc_d']}, {blanket['ilosc_c']}, {blanket['kwota_brutto']}, {blanket['akcyza']}, {blanket['energia_do_akcyzy']}, {blanket['nadplata_niedoplata']}, {blanket['odsetki']}, {blanket['termin_platnosci']}, {blanket['do_zaplaty']}")
        
        if ogolem:
            lines.append(f"Ogółem do zaplaty: {ogolem[0]['do_zaplaty']}")
        
        lines.append("")
        lines.append("")
        lines.append("")
        lines.append("")
    
    # Grupuj dane po okresach (datach) - ODCZYTY, SPRZEDAŻ i DYSTRYBUCJA razem
    readings = data.get('readings', [])
    sales = data.get('sales', [])
    fees = data.get('fees', [])
    
    # Wyciągnij wszystkie unikalne daty z ODCZYTÓW i DYSTRYBUCJI
    dates = set()
    for r in readings:
        if 'data' in r:
            dates.add(r['data'])
    for f in fees:
        if 'data' in f:
            dates.add(f['data'])
    
    if dates:
        # Sortuj daty chronologicznie (DD/MM/YYYY)
        sorted_dates = sorted(dates, key=lambda x: (int(x.split('/')[2]), int(x.split('/')[1]), int(x.split('/')[0])))
        
        lines.append("")
        lines.append("        - ROZLICZENIE PO OKRESACH (dzienna i nocna razem dla każdej daty):")
        lines.append("")
        
        # Filtruj sprzedaż bez upustów (upusty na końcu)
        sales_without_upust = [s for s in sales if s.get('typ') != 'upust']
        upusts = [s for s in sales if s.get('typ') == 'upust']
        
        # Indeks dla sprzedaży (po kolei: dzienna, nocna, dzienna, nocna...)
        sales_index = 0
        
        for period_num, date in enumerate(sorted_dates, 1):
            lines.append(f"OKRES {period_num}: {date}")
            lines.append("  ODCZYTY:")
            
            # ODCZYTY - pobrana dzienna
            pobrana_dzienna = [r for r in readings if r.get('typ') == 'pobrana' and r.get('strefa') == 'dzienna' and r.get('data') == date]
            if pobrana_dzienna:
                r = pobrana_dzienna[0]
                lines.append(f"    dzienna (pobrana): biezace {r['biezace']}, poprzednie {r['poprzednie']}, mnozna {r['mnozna']}, razem kWh {r['razem']}")
            
            # ODCZYTY - pobrana nocna
            pobrana_nocna = [r for r in readings if r.get('typ') == 'pobrana' and r.get('strefa') == 'nocna' and r.get('data') == date]
            if pobrana_nocna:
                r = pobrana_nocna[0]
                lines.append(f"    nocna (pobrana): biezace {r['biezace']}, poprzednie {r['poprzednie']}, mnozna {r['mnozna']}, razem kWh {r['razem']}")
            
            # ODCZYTY - oddana dzienna
            oddana_dzienna = [r for r in readings if r.get('typ') == 'oddana' and r.get('strefa') == 'dzienna' and r.get('data') == date]
            if oddana_dzienna:
                r = oddana_dzienna[0]
                lines.append(f"    dzienna (oddana): biezace {r['biezace']}, poprzednie {r['poprzednie']}, mnozna {r['mnozna']}, razem kWh {r['razem']}")
            
            # ODCZYTY - oddana nocna
            oddana_nocna = [r for r in readings if r.get('typ') == 'oddana' and r.get('strefa') == 'nocna' and r.get('data') == date]
            if oddana_nocna:
                r = oddana_nocna[0]
                lines.append(f"    nocna (oddana): biezace {r['biezace']}, poprzednie {r['poprzednie']}, mnozna {r['mnozna']}, razem kWh {r['razem']}")
            
            lines.append("  SPRZEDAŻ ENERGII:")
            
            # SPRZEDAŻ - dzienna (po kolei)
            if sales_index < len(sales_without_upust) and sales_without_upust[sales_index].get('strefa') == 'dzienna':
                sale = sales_without_upust[sales_index]
                lines.append(f"    dzienna: ilosc {sale['ilosc_kwh']} kWh, cena {sale['cena']}, naleznosc {sale['naleznosc']}, VAT {sale['vat']}%")
                sales_index += 1
            
            # SPRZEDAŻ - nocna (po kolei)
            if sales_index < len(sales_without_upust) and sales_without_upust[sales_index].get('strefa') == 'nocna':
                sale = sales_without_upust[sales_index]
                lines.append(f"    nocna: ilosc {sale['ilosc_kwh']} kWh, cena {sale['cena']}, naleznosc {sale['naleznosc']}, VAT {sale['vat']}%")
                sales_index += 1
            
            lines.append("  DYSTRYBUCJA:")
            
            # DYSTRYBUCJA - wszystkie opłaty z tą datą
            fees_for_date = [f for f in fees if f.get('data') == date]
            
            # Grupuj opłaty według nazwy
            fees_by_name = {}
            for fee in fees_for_date:
                name = fee['nazwa']
                if name not in fees_by_name:
                    fees_by_name[name] = []
                fees_by_name[name].append(fee)
            
            # Wypisz opłaty w odpowiedniej kolejności
            order = [
                'Opłata stała sieciowa - układ 3-fazowy',
                'Opłata przejściowa > 1200 kWh',
                'Opłata mocowa ( > 2800 kWh)',
                'Opłata zmienna sieciowa',
                'Opłata jakościowa',
                'Opłata OZE',
                'Opłata kogeneracyjna',
                'Opłata abonamentowa',
                'Upust 10% za niższe zużycie energii - dystrybucja'
            ]
            
            for fee_name in order:
                if fee_name in fees_by_name:
                    for fee in fees_by_name[fee_name]:
                        if 'strefa' in fee:
                            # Opłaty ze strefą (dzienna/nocna)
                            lines.append(f"    {fee_name}: {fee['strefa']} {fee['jednostka']} {fee.get('ilosc_kwh', '')} {fee.get('cena', '')} {fee.get('naleznosc', '')} {fee.get('vat', '')}")
                        else:
                            # Opłaty bez strefy
                            if fee_name == 'Upust 10% za niższe zużycie energii - dystrybucja':
                                lines.append(f"    {fee_name}: {fee['jednostka']} {fee.get('ilosc', '')} ,{fee.get('cena', '')} ,{fee.get('naleznosc', '')}, {fee.get('vat', '')}")
                            else:
                                wspolczynnik = fee.get('wspolczynnik1', '')
                                if wspolczynnik and wspolczynnik != '0,0000' and wspolczynnik != '0.0000' and wspolczynnik != '':
                                    lines.append(f"    {fee_name}: {fee['jednostka']} {fee.get('ilosc_miesiecy', fee.get('ilosc', ''))} {wspolczynnik} {fee.get('cena', '')} {fee.get('naleznosc', '')} {fee.get('vat', '')}")
                                else:
                                    lines.append(f"    {fee_name}: {fee['jednostka']} {fee.get('ilosc_miesiecy', fee.get('ilosc', ''))} {fee.get('cena', '')} {fee.get('naleznosc', '')} {fee.get('vat', '')}")
            
            lines.append("")
        
        # Upusty na końcu (jeśli są)
        if upusts:
            lines.append("UPUSTY (na końcu faktury):")
            for upust in upusts:
                lines.append(f"  Upust {upust['procent']}%: ilosc {upust['ilosc']}, cena {upust['cena']}, naleznosc {upust['naleznosc']}, VAT {upust['vat']}%")
            lines.append("")
    
    # Podsumowania
    summaries = data.get('summaries', {})
    if 'ogolem_sprzedaz_energii' in summaries:
        lines.append(f"Ogolem sprzedaz energii: {summaries['ogolem_sprzedaz_energii']}")
    if 'ogolem_usluga_dystrybucji' in summaries:
        lines.append(f"Ogolem usluga dystrybucji: {summaries['ogolem_usluga_dystrybucji']}")
    if 'ogolem_wartosc' in summaries:
        lines.append(f"Ogolem wartosc: {summaries['ogolem_wartosc']}")
    if 'grupa_taryfowa' in summaries:
        lines.append(f"Grupa taryfowa: {summaries['grupa_taryfowa']}")
    if 'energia_zuzyta_w_roku' in summaries:
        lines.append(f"Energia zuzyta w roku {summaries.get('rok', '')}: {summaries['energia_zuzyta_w_roku']}")
    
    return "\n".join(lines)


def format_full_output(invoice_name: str, data: Dict) -> str:
    """Formatuje pełne sparsowanie z wszystkimi szczegółami."""
    lines = []
    
    lines.append("=" * 80)
    lines.append(f"PEŁNE SPARSOWANIE FAKTURY - {invoice_name}")
    lines.append("=" * 80)
    lines.append("")
    
    # 1. PODSTAWOWE INFORMACJE
    lines.append("=" * 80)
    lines.append("1. PODSTAWOWE INFORMACJE O FAKTURZE")
    lines.append("=" * 80)
    if 'invoice_number' in data and data['invoice_number']:
        lines.append(f"Numer faktury: {data['invoice_number']}")
    if 'period' in data and data['period']:
        lines.append(f"Okres rozliczeniowy: od {data['period']['od']} do {data['period']['do']}")
    lines.append("")
    
    # 2. PODSUMOWANIE FINANSOWE
    lines.append("=" * 80)
    lines.append("2. PODSUMOWANIE FINANSOWE")
    lines.append("=" * 80)
    financial = data.get('financial', {})
    for key, value in financial.items():
        lines.append(f"  {key}: {value}")
    lines.append("")
    
    # 3. PRZEWIDYWANE NALEŻNOŚCI (BLANKIETY)
    lines.append("=" * 80)
    lines.append("3. PRZEWIDYWANE NALEŻNOŚCI (BLANKIETY PROGNOZOWE)")
    lines.append("=" * 80)
    blankets = data.get('blankets', [])
    if blankets:
        for i, blanket in enumerate(blankets, 1):
            if blanket.get('ogolem'):
                lines.append(f"  BLANKIET {i}: OGÓŁEM")
                lines.append(f"    Do zapłaty: {blanket.get('do_zaplaty', '')}")
            else:
                lines.append(f"  BLANKIET {i}: {blanket.get('nr_blankietu', '')}")
                lines.append(f"    Okres: {blanket.get('okres_od', '')} - {blanket.get('okres_do', '')}")
                lines.append(f"    Ilość dzienna: {blanket.get('ilosc_d', '')} kWh")
                lines.append(f"    Ilość całkowita: {blanket.get('ilosc_c', '')} kWh")
                lines.append(f"    Kwota brutto: {blanket.get('kwota_brutto', '')} zł")
                lines.append(f"    Akcyza: {blanket.get('akcyza', '')} zł")
                lines.append(f"    Energia do akcyzy: {blanket.get('energia_do_akcyzy', '')} kWh")
                lines.append(f"    Nadpłata/Niedopłata: {blanket.get('nadplata_niedoplata', '')} zł")
                lines.append(f"    Odsetki: {blanket.get('odsetki', '')} zł")
                lines.append(f"    Termin płatności: {blanket.get('termin_platnosci', '')}")
                lines.append(f"    Do zapłaty: {blanket.get('do_zaplaty', '')} zł")
    else:
        lines.append("  Brak blankietów prognozowych")
    lines.append("")
    
    # 4. ODCZYTY LICZNIKÓW - SZCZEGÓŁOWO
    lines.append("=" * 80)
    lines.append("4. ODCZYTY LICZNIKÓW - SZCZEGÓŁOWO")
    lines.append("=" * 80)
    readings = data.get('readings', [])
    if readings:
        # Grupuj po typie
        pobrana = [r for r in readings if r.get('typ') == 'pobrana']
        oddana = [r for r in readings if r.get('typ') == 'oddana']
        
        if pobrana:
            lines.append("  ENERGIA CZYNNA POBRANA:")
            for r in sorted(pobrana, key=lambda x: (x.get('data', ''), x.get('strefa', ''))):
                lines.append(f"    {r.get('strefa', '').upper()}: data {r.get('data', '')}")
                lines.append(f"      Bieżący odczyt: {r.get('biezace', '')}")
                lines.append(f"      Poprzedni odczyt: {r.get('poprzednie', '')}")
                lines.append(f"      Mnożna: {r.get('mnozna', '')}")
                lines.append(f"      Ilość: {r.get('ilosc', '')} kWh")
                lines.append(f"      Straty: {r.get('straty', '')} kWh")
                lines.append(f"      Razem: {r.get('razem', '')} kWh")
        
        if oddana:
            lines.append("  ENERGIA CZYNNA ODDANA:")
            for r in sorted(oddana, key=lambda x: (x.get('data', ''), x.get('strefa', ''))):
                lines.append(f"    {r.get('strefa', '').upper()}: data {r.get('data', '')}")
                lines.append(f"      Bieżący odczyt: {r.get('biezace', '')}")
                lines.append(f"      Poprzedni odczyt: {r.get('poprzednie', '')}")
                lines.append(f"      Mnożna: {r.get('mnozna', '')}")
                lines.append(f"      Ilość: {r.get('ilosc', '')} kWh")
                lines.append(f"      Straty: {r.get('straty', '')} kWh")
                lines.append(f"      Razem: {r.get('razem', '')} kWh")
    else:
        lines.append("  Brak odczytów liczników")
    lines.append("")
    
    # 5. SPRZEDAŻ ENERGII - SZCZEGÓŁOWO
    lines.append("=" * 80)
    lines.append("5. SPRZEDAŻ ENERGII - SZCZEGÓŁOWO")
    lines.append("=" * 80)
    sales = data.get('sales', [])
    if sales:
        sales_normal = [s for s in sales if s.get('typ') != 'upust']
        upusts = [s for s in sales if s.get('typ') == 'upust']
        
        for i, sale in enumerate(sales_normal, 1):
            lines.append(f"  POZYCJA {i}:")
            lines.append(f"    Strefa: {sale.get('strefa', '').upper()}")
            lines.append(f"    Ilość: {sale.get('ilosc_kwh', '')} kWh")
            lines.append(f"    Cena: {sale.get('cena', '')} zł/kWh")
            lines.append(f"    Należność: {sale.get('naleznosc', '')} zł")
            lines.append(f"    VAT: {sale.get('vat', '')}%")
        
        if upusts:
            lines.append("  UPUSTY:")
            for upust in upusts:
                lines.append(f"    Upust {upust.get('procent', '')}%:")
                lines.append(f"      Ilość: {upust.get('ilosc', '')}")
                lines.append(f"      Cena: {upust.get('cena', '')} zł")
                lines.append(f"      Należność: {upust.get('naleznosc', '')} zł")
                lines.append(f"      VAT: {upust.get('vat', '')}%")
    else:
        lines.append("  Brak pozycji sprzedaży energii")
    lines.append("")
    
    # 6. OPŁATY DYSTRYBUCYJNE - SZCZEGÓŁOWO
    lines.append("=" * 80)
    lines.append("6. OPŁATY DYSTRYBUCYJNE - SZCZEGÓŁOWO")
    lines.append("=" * 80)
    fees = data.get('fees', [])
    if fees:
        # Grupuj po nazwie
        fees_by_name = {}
        for fee in fees:
            name = fee.get('nazwa', 'Nieznana opłata')
            if name not in fees_by_name:
                fees_by_name[name] = []
            fees_by_name[name].append(fee)
        
        for fee_name, fee_list in sorted(fees_by_name.items()):
            lines.append(f"  {fee_name.upper()}:")
            for fee in fee_list:
                if 'strefa' in fee:
                    lines.append(f"    {fee.get('strefa', '').upper()}:")
                    lines.append(f"      Jednostka: {fee.get('jednostka', '')}")
                    lines.append(f"      Data: {fee.get('data', '')}")
                    lines.append(f"      Ilość kWh: {fee.get('ilosc_kwh', '')}")
                    lines.append(f"      Cena: {fee.get('cena', '')} zł")
                    lines.append(f"      Należność: {fee.get('naleznosc', '')} zł")
                    lines.append(f"      VAT: {fee.get('vat', '')}%")
                else:
                    lines.append(f"    Jednostka: {fee.get('jednostka', '')}")
                    lines.append(f"    Data: {fee.get('data', '')}")
                    if 'ilosc_miesiecy' in fee:
                        lines.append(f"    Ilość miesięcy: {fee.get('ilosc_miesiecy', '')}")
                    if 'wspolczynnik1' in fee and fee.get('wspolczynnik1'):
                        lines.append(f"    Współczynnik: {fee.get('wspolczynnik1', '')}")
                    lines.append(f"    Cena: {fee.get('cena', '')} zł")
                    lines.append(f"    Należność: {fee.get('naleznosc', '')} zł")
                    lines.append(f"    VAT: {fee.get('vat', '')}%")
    else:
        lines.append("  Brak opłat dystrybucyjnych")
    lines.append("")
    
    # 7. ROZLICZENIE PO OKRESACH (jak w poprzednim formacie)
    lines.append("=" * 80)
    lines.append("7. ROZLICZENIE PO OKRESACH (dzienna i nocna razem)")
    lines.append("=" * 80)
    lines.append("")
    
    # Wyciągnij wszystkie unikalne daty
    dates = set()
    for r in readings:
        if 'data' in r:
            dates.add(r['data'])
    for f in fees:
        if 'data' in f:
            dates.add(f['data'])
    
    if dates:
        sorted_dates = sorted(dates, key=lambda x: (int(x.split('/')[2]), int(x.split('/')[1]), int(x.split('/')[0])))
        
        sales_without_upust = [s for s in sales if s.get('typ') != 'upust']
        upusts = [s for s in sales if s.get('typ') == 'upust']
        sales_index = 0
        
        for period_num, date in enumerate(sorted_dates, 1):
            lines.append(f"OKRES {period_num}: {date}")
            lines.append("  ODCZYTY:")
            
            # ODCZYTY
            for r_type, r_label in [('pobrana', 'pobrana'), ('oddana', 'oddana')]:
                for r_strefa in ['dzienna', 'nocna']:
                    matching = [r for r in readings if r.get('typ') == r_type and r.get('strefa') == r_strefa and r.get('data') == date]
                    if matching:
                        r = matching[0]
                        lines.append(f"    {r_strefa} ({r_label}): biezace {r['biezace']}, poprzednie {r['poprzednie']}, mnozna {r['mnozna']}, razem kWh {r['razem']}")
            
            lines.append("  SPRZEDAŻ ENERGII:")
            if sales_index < len(sales_without_upust) and sales_without_upust[sales_index].get('strefa') == 'dzienna':
                sale = sales_without_upust[sales_index]
                lines.append(f"    dzienna: ilosc {sale['ilosc_kwh']} kWh, cena {sale['cena']}, naleznosc {sale['naleznosc']}, VAT {sale['vat']}%")
                sales_index += 1
            if sales_index < len(sales_without_upust) and sales_without_upust[sales_index].get('strefa') == 'nocna':
                sale = sales_without_upust[sales_index]
                lines.append(f"    nocna: ilosc {sale['ilosc_kwh']} kWh, cena {sale['cena']}, naleznosc {sale['naleznosc']}, VAT {sale['vat']}%")
                sales_index += 1
            
            lines.append("  DYSTRYBUCJA:")
            fees_for_date = [f for f in fees if f.get('data') == date]
            fees_by_name_date = {}
            for fee in fees_for_date:
                name = fee['nazwa']
                if name not in fees_by_name_date:
                    fees_by_name_date[name] = []
                fees_by_name_date[name].append(fee)
            
            order = [
                'Opłata stała sieciowa - układ 3-fazowy',
                'Opłata przejściowa > 1200 kWh',
                'Opłata mocowa ( > 2800 kWh)',
                'Opłata zmienna sieciowa',
                'Opłata jakościowa',
                'Opłata OZE',
                'Opłata kogeneracyjna',
                'Opłata abonamentowa',
                'Upust 10% za niższe zużycie energii - dystrybucja'
            ]
            
            for fee_name in order:
                if fee_name in fees_by_name_date:
                    for fee in fees_by_name_date[fee_name]:
                        if 'strefa' in fee:
                            lines.append(f"    {fee_name}: {fee['strefa']} {fee['jednostka']} {fee.get('ilosc_kwh', '')} {fee.get('cena', '')} {fee.get('naleznosc', '')} {fee.get('vat', '')}")
                        else:
                            if fee_name == 'Upust 10% za niższe zużycie energii - dystrybucja':
                                lines.append(f"    {fee_name}: {fee['jednostka']} {fee.get('ilosc', '')} ,{fee.get('cena', '')} ,{fee.get('naleznosc', '')}, {fee.get('vat', '')}")
                            else:
                                wspolczynnik = fee.get('wspolczynnik1', '')
                                if wspolczynnik and wspolczynnik != '0,0000' and wspolczynnik != '0.0000' and wspolczynnik != '':
                                    lines.append(f"    {fee_name}: {fee['jednostka']} {fee.get('ilosc_miesiecy', fee.get('ilosc', ''))} {wspolczynnik} {fee.get('cena', '')} {fee.get('naleznosc', '')} {fee.get('vat', '')}")
                                else:
                                    lines.append(f"    {fee_name}: {fee['jednostka']} {fee.get('ilosc_miesiecy', fee.get('ilosc', ''))} {fee.get('cena', '')} {fee.get('naleznosc', '')} {fee.get('vat', '')}")
            lines.append("")
        
        if upusts:
            lines.append("UPUSTY (na końcu faktury):")
            for upust in upusts:
                lines.append(f"  Upust {upust['procent']}%: ilosc {upust['ilosc']}, cena {upust['cena']}, naleznosc {upust['naleznosc']}, VAT {upust['vat']}%")
            lines.append("")
    
    # 8. PODSUMOWANIA
    lines.append("=" * 80)
    lines.append("8. PODSUMOWANIA")
    lines.append("=" * 80)
    summaries = data.get('summaries', {})
    for key, value in summaries.items():
        lines.append(f"  {key}: {value}")
    lines.append("")
    
    lines.append("=" * 80)
    lines.append("KONIEC SPARSOWANIA")
    lines.append("=" * 80)
    
    return "\n".join(lines)


def analyze_invoice(input_file: Path, output_file: Path):
    """Analizuje fakturę i zapisuje w poprawionym formacie."""
    print(f"Analizowanie: {input_file.name}")
    
    with open(input_file, 'r', encoding='utf-8') as f:
        text = f.read()
    
    # Wyciągnij wszystkie dane
    data = {
        'invoice_number': extract_invoice_number(text),
        'period': extract_period(text),
        'financial': extract_financial_summary(text),
        'blankets': extract_prognosis_blankets(text),
        'readings': extract_meter_readings(text),
        'sales': extract_energy_sales(text),
        'fees': extract_distribution_fees(text),
        'summaries': extract_summaries(text)
    }
    
    # Formatuj i zapisz (standardowy format)
    output = format_output(input_file.name, data)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(output)
    
    print(f"  Zapisano do: {output_file.name}")
    
    # Zapisz również pełne sparsowanie
    full_output_file = output_file.parent / f"{output_file.stem}_full.txt"
    full_output = format_full_output(input_file.name, data)
    
    with open(full_output_file, 'w', encoding='utf-8') as f:
        f.write(full_output)
    
    print(f"  Zapisano pełne sparsowanie do: {full_output_file.name}")


def main():
    """Główna funkcja."""
    parsed_dir = Path("invoices_raw/electricity/parsed")
    output_dir = Path("invoices_raw/electricity/analysis/auto_extracted")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    txt_files = sorted([f for f in parsed_dir.glob("*.txt")])
    
    if not txt_files:
        print(f"Nie znaleziono plikow do analizy w: {parsed_dir}")
        return
    
    print(f"Znaleziono {len(txt_files)} faktur do analizy:")
    for txt_file in txt_files:
        print(f"  - {txt_file.name}")
    
    print(f"\nDane zostana zapisane w: {output_dir}")
    print("=" * 80)
    
    for txt_file in txt_files:
        output_filename = txt_file.name.replace('.txt', '_auto.txt')
        output_path = output_dir / output_filename
        analyze_invoice(txt_file, output_path)
    
    print("\n" + "=" * 80)
    print("KONIEC ANALIZY")
    print("=" * 80)


if __name__ == "__main__":
    main()

