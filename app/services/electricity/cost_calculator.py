"""
Moduł obliczania kosztów 1 kWh dla faktur prądu.
"""

from typing import Dict, Any
from sqlalchemy.orm import Session
from app.models.electricity_invoice import (
    ElectricityInvoiceSprzedazEnergii,
    ElectricityInvoiceOplataDystrybucyjna
)


def calculate_kwh_cost(invoice_id: int, db: Session) -> Dict[str, Any]:
    """
    Oblicza koszt 1 kWh dla faktury (bez uwzględniania fotowoltaiki).
    Zwraca koszt dla każdej strefy (dzienna, nocna, całodobowa).
    
    Koszt 1 kWh = suma:
    - Energia elektryczna czynna (cena_za_kwh z sprzedaz_energii)
    - Opłata jakościowa (cena z oplaty_dystrybucyjne gdzie typ_oplaty = "OPŁATA JAKOŚCIOWA")
    - Opłata zmienna sieciowa (cena z oplaty_dystrybucyjne gdzie typ_oplaty = "OPŁATA ZMIENNA SIECIOWA")
    - Opłata OZE (cena z oplaty_dystrybucyjne gdzie typ_oplaty = "OPŁATA OZE")
    - Opłata kogeneracyjna (cena z oplaty_dystrybucyjne gdzie typ_oplaty = "OPŁATA KOGENERACYJNA")
    """
    # Pobierz sprzedaż energii
    sprzedaz = db.query(ElectricityInvoiceSprzedazEnergii).filter(
        ElectricityInvoiceSprzedazEnergii.invoice_id == invoice_id
    ).all()
    
    # Pobierz opłaty dystrybucyjne
    oplaty = db.query(ElectricityInvoiceOplataDystrybucyjna).filter(
        ElectricityInvoiceOplataDystrybucyjna.invoice_id == invoice_id
    ).all()
    
    # Inicjalizuj słowniki dla każdej strefy
    koszty = {
        "DZIENNA": {
            "energia_czynna": 0.0,
            "oplata_jakosciowa": 0.0,
            "oplata_zmienna_sieciowa": 0.0,
            "oplata_oze": 0.0,
            "oplata_kogeneracyjna": 0.0,
            "suma": 0.0
        },
        "NOCNA": {
            "energia_czynna": 0.0,
            "oplata_jakosciowa": 0.0,
            "oplata_zmienna_sieciowa": 0.0,
            "oplata_oze": 0.0,
            "oplata_kogeneracyjna": 0.0,
            "suma": 0.0
        },
        "CAŁODOBOWA": {
            "energia_czynna": 0.0,
            "oplata_jakosciowa": 0.0,
            "oplata_zmienna_sieciowa": 0.0,
            "oplata_oze": 0.0,
            "oplata_kogeneracyjna": 0.0,
            "suma": 0.0
        }
    }
    
    # Przetwórz sprzedaż energii (energia czynna)
    # Oblicz średnią ważoną ceny NETTO dla każdej strefy na podstawie należności brutto i ilości kWh
    # To pozwala uniknąć błędów gdy w bazie są błędne wartości ceny_za_kwh
    strefa_suma_naleznosci_netto = {}
    strefa_suma_ilosci = {}
    
    for s in sprzedaz:
        # Pomiń upusty (ujemne należności)
        if float(s.naleznosc) < 0:
            continue
            
        strefa = s.strefa or "CAŁODOBOWA"
        if strefa not in koszty:
            continue
        
        # Należność w bazie jest brutto, więc obliczamy netto
        naleznosc_brutto = float(s.naleznosc)
        vat_rate = float(s.vat_procent) / 100.0
        naleznosc_netto = naleznosc_brutto / (1 + vat_rate)
        ilosc_kwh = float(s.ilosc_kwh)
        
        if strefa not in strefa_suma_naleznosci_netto:
            strefa_suma_naleznosci_netto[strefa] = 0.0
            strefa_suma_ilosci[strefa] = 0.0
        
        strefa_suma_naleznosci_netto[strefa] += naleznosc_netto
        strefa_suma_ilosci[strefa] += ilosc_kwh
    
    # Oblicz średnią ważoną ceny NETTO dla każdej strefy
    for strefa in koszty:
        if strefa in strefa_suma_ilosci and strefa_suma_ilosci[strefa] > 0:
            # Średnia ważona cena netto = suma należności netto / suma ilości kWh
            srednia_cena_netto = strefa_suma_naleznosci_netto[strefa] / strefa_suma_ilosci[strefa]
            koszty[strefa]["energia_czynna"] = round(srednia_cena_netto, 4)
    
    # Przetwórz opłaty dystrybucyjne - zaokrąglone do 4 miejsc
    for op in oplaty:
        # Tylko opłaty w jednostce kWh (nie zł/mc)
        if op.jednostka != "kWh":
            continue
        
        strefa = op.strefa or "CAŁODOBOWA"
        if strefa not in koszty:
            continue
        
        typ_oplaty = op.typ_oplaty.upper()
        cena = round(float(op.cena), 4)
        
        # Rozpoznaj typ opłaty (elastyczne dopasowanie)
        if "JAKOŚCIOWA" in typ_oplaty:
            koszty[strefa]["oplata_jakosciowa"] = cena
        elif "ZMIENNA" in typ_oplaty and "SIECIOWA" in typ_oplaty:
            koszty[strefa]["oplata_zmienna_sieciowa"] = cena
        elif "OZE" in typ_oplaty:
            koszty[strefa]["oplata_oze"] = cena
        elif "KOGENERACYJNA" in typ_oplaty:
            koszty[strefa]["oplata_kogeneracyjna"] = cena
    
    # Oblicz sumy dla każdej strefy (zaokrąglone do 4 miejsc po przecinku)
    for strefa in koszty:
        suma = (
            koszty[strefa]["energia_czynna"] +
            koszty[strefa]["oplata_jakosciowa"] +
            koszty[strefa]["oplata_zmienna_sieciowa"] +
            koszty[strefa]["oplata_oze"] +
            koszty[strefa]["oplata_kogeneracyjna"]
        )
        koszty[strefa]["suma"] = round(suma, 4)
    
    # Zwróć tylko strefy, które mają dane
    result = {}
    for strefa, dane in koszty.items():
        if dane["energia_czynna"] > 0 or dane["suma"] > 0:
            result[strefa] = dane
    
    return result


def calculate_kwh_cost_for_blankiet(blankiet_id: int, invoice_id: int, db: Session) -> Dict[str, Any]:
    """
    Oblicza koszt 1 kWh dla blankietu (podokresu) na podstawie faktury.
    Używa tych samych kosztów co faktura (koszty są stałe w całej fakturze).
    """
    return calculate_kwh_cost(invoice_id, db)

