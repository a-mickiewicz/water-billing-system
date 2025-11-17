"""
Moduł do sprawdzania czy okres rozliczeniowy jest w pełni rozliczony
i wywoływania backupu po zakończeniu rozliczenia.
"""

from sqlalchemy.orm import Session
from app.models.water import Bill
from app.models.gas import GasBill
from app.models.electricity import ElectricityBill
from app.core.backup import create_all_backups


def is_period_fully_settled(db: Session, period: str) -> bool:
    """
    Sprawdza czy okres rozliczeniowy jest w pełni rozliczony
    (czy są rachunki dla wody, gazu i prądu).
    
    Args:
        db: Sesja bazy danych
        period: Okres rozliczeniowy w formacie 'YYYY-MM'
    
    Returns:
        True jeśli okres jest w pełni rozliczony, False w przeciwnym razie
    """
    # Sprawdź czy są rachunki dla wody
    water_bills = db.query(Bill).filter(Bill.data == period).first()
    if not water_bills:
        return False
    
    # Sprawdź czy są rachunki dla gazu
    gas_bills = db.query(GasBill).filter(GasBill.data == period).first()
    if not gas_bills:
        return False
    
    # Sprawdź czy są rachunki dla prądu
    electricity_bills = db.query(ElectricityBill).filter(ElectricityBill.data == period).first()
    if not electricity_bills:
        return False
    
    return True


def handle_period_settlement(db: Session, period: str) -> dict:
    """
    Obsługuje rozliczenie okresu - sprawdza czy okres jest w pełni rozliczony
    i jeśli tak, wykonuje backup.
    
    Args:
        db: Sesja bazy danych
        period: Okres rozliczeniowy w formacie 'YYYY-MM'
    
    Returns:
        Słownik z informacjami o wykonanych akcjach
    """
    result = {
        "period": period,
        "is_fully_settled": False,
        "backup_created": False,
        "errors": []
    }
    
    # Sprawdź czy okres jest w pełni rozliczony
    if not is_period_fully_settled(db, period):
        result["message"] = f"Okres {period} nie jest jeszcze w pełni rozliczony"
        return result
    
    result["is_fully_settled"] = True
    
    # Utwórz backup
    try:
        backup_results = create_all_backups()
        result["backup_created"] = True
        result["backup_results"] = backup_results
        
        if backup_results.get("errors"):
            result["errors"].extend(backup_results["errors"])
    except Exception as e:
        error_msg = f"Błąd tworzenia backupu: {str(e)}"
        result["errors"].append(error_msg)
        print(f"[ERROR] {error_msg}")
    
    result["message"] = f"Okres {period} został w pełni rozliczony. Backup utworzony."
    return result

