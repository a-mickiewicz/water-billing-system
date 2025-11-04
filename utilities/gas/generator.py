"""
Moduł generowania plików PDF rachunków za gaz.
Generuje osobne rachunki PDF dla każdego lokalu.
"""

from pathlib import Path
from sqlalchemy.orm import Session
from utilities.gas.models import GasBill


def generate_bill_pdf(db: Session, bill: GasBill) -> str:
    """
    Generuje plik PDF rachunku za gaz.
    
    TODO: Implementacja generowania PDF
    Na razie zwraca tylko ścieżkę.
    
    Args:
        db: Sesja bazy danych
        bill: Rachunek gazu
    
    Returns:
        Ścieżka do wygenerowanego pliku PDF
    """
    # Utwórz folder dla rachunków gazu
    bills_folder = Path("bills/gas")
    bills_folder.mkdir(parents=True, exist_ok=True)
    
    # Nazwa pliku
    filename = f"gas_bill_{bill.data}_{bill.local}_{bill.id}.pdf"
    pdf_path = bills_folder / filename
    
    # TODO: Implementacja generowania PDF
    # Można użyć reportlab, fpdf, lub innej biblioteki
    # Podobnie jak w bill_generator.py dla wody
    
    print(f"[INFO] Generowanie PDF rachunku gazu: {pdf_path}")
    print(f"[TODO] Implementacja generowania PDF - plik: {pdf_path}")
    
    return str(pdf_path)


def generate_all_bills_for_period(db: Session, period: str) -> list[str]:
    """
    Generuje pliki PDF dla wszystkich rachunków gazu w danym okresie.
    
    Args:
        db: Sesja bazy danych
        period: Okres rozliczeniowy w formacie 'YYYY-MM'
    
    Returns:
        Lista ścieżek do wygenerowanych plików PDF
    """
    bills = db.query(GasBill).filter(GasBill.data == period).all()
    pdf_files = []
    
    for bill in bills:
        pdf_path = generate_bill_pdf(db, bill)
        bill.pdf_path = pdf_path
        pdf_files.append(pdf_path)
    
    db.commit()
    
    return pdf_files

