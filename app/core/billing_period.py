"""
Moduł do sprawdzania czy okres rozliczeniowy jest w pełni rozliczony
i wywoływania backupu po zakończeniu rozliczenia.
"""

from sqlalchemy.orm import Session
from app.models.water import Bill
from app.models.gas import GasBill
from app.models.electricity import ElectricityBill
from app.core.backup import create_all_backups
from app.core.email_sender import send_backup_to_user_email
from app.models.user import User


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
    i jeśli tak, wykonuje backup i wysyła email.
    
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
        "email_sent": False,
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
    
    # Wyślij email do wszystkich użytkowników (oprócz admina)
    try:
        users = db.query(User).filter(
            User.is_admin == False,
            User.email.isnot(None)
        ).all()
        
        email_sent_count = 0
        for user in users:
            if user.email:
                try:
                    if send_backup_to_user_email(user.email):
                        email_sent_count += 1
                except Exception as e:
                    error_msg = f"Błąd wysyłania email do {user.email}: {str(e)}"
                    result["errors"].append(error_msg)
                    print(f"[ERROR] {error_msg}")
        
        if email_sent_count > 0:
            result["email_sent"] = True
            result["emails_sent_count"] = email_sent_count
    except Exception as e:
        error_msg = f"Błąd wysyłania emaili: {str(e)}"
        result["errors"].append(error_msg)
        print(f"[ERROR] {error_msg}")
    
    result["message"] = f"Okres {period} został w pełni rozliczony. Backup utworzony."
    return result

