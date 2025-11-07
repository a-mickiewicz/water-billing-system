"""
Generowanie rachunków PDF dla lokali za prąd.
"""

from typing import Optional
from pathlib import Path
from sqlalchemy.orm import Session
from app.models.electricity import ElectricityBill


def generate_bill_pdf(
    bill: ElectricityBill,
    output_dir: Path,
    db: Session
) -> Optional[str]:
    """
    Generuje plik PDF rachunku dla lokalu.
    
    TODO: Implementacja generowania PDF
    Wzór podobny do app/services/water/bill_generator.py
    
    Args:
        bill: Rachunek do wygenerowania
        output_dir: Katalog wyjściowy (bills/prad/)
        db: Sesja bazy danych
    
    Returns:
        Ścieżka do wygenerowanego pliku PDF lub None
    """
    # TODO: Implementacja generowania PDF
    # 1. Przygotuj dane (faktura, lokal, zużycie, koszty)
    # 2. Wygeneruj PDF (użyć reportlab lub podobnej biblioteki)
    # 3. Zapisz w bills/prad/
    # 4. Zaktualizuj bill.pdf_path
    
    raise NotImplementedError("Generowanie PDF rachunków prądu - do implementacji")

