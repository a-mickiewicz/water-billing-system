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
    
    # Przetwórz sprzedaż energii (energia czynna) - zaokrąglone do 4 miejsc
    for s in sprzedaz:
        strefa = s.strefa or "CAŁODOBOWA"
        if strefa not in koszty:
            continue
        koszty[strefa]["energia_czynna"] = round(float(s.cena_za_kwh), 4)
    
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

