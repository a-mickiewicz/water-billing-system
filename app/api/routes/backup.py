"""
Endpointy do zarządzania backupami bazy danych.
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.auth import get_current_user
from app.core.backup import create_backup, create_all_backups, get_latest_backup, decrypt_backup_file
from app.core.email_sender import send_backup_to_user_email
from app.models.user import User
import tempfile
import os

router = APIRouter(prefix="/api/backup", tags=["backup"])


@router.post("/create")
def create_manual_backup(
    backup_type: str = "period",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Tworzy ręczny backup bazy danych.
    
    Args:
        backup_type: Typ backupu - "period" (okresowy), "halfyear" (półroczny), "year" (roczny), "all" (wszystkie)
    """
    try:
        if backup_type == "all":
            results = create_all_backups()
            return {
                "message": "Utworzono wszystkie backupu",
                "results": results
            }
        else:
            backup_path = create_backup(backup_type=backup_type)
            return {
                "message": f"Utworzono backup {backup_type}",
                "backup_path": backup_path
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Błąd tworzenia backupu: {str(e)}")


@router.post("/send-email")
def send_backup_email_manual(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Wysyła najnowszy backup okresowy na email użytkownika.
    """
    if not current_user.email:
        raise HTTPException(
            status_code=400,
            detail="Użytkownik nie ma ustawionego email. Ustaw email w preferencjach."
        )
    
    try:
        success = send_backup_to_user_email(current_user.email)
        if success:
            return {
                "message": f"Backup wysłany na email: {current_user.email}",
                "email": current_user.email
            }
        else:
            raise HTTPException(
                status_code=500,
                detail="Nie udało się wysłać email. Sprawdź konfigurację SMTP."
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Błąd wysyłania email: {str(e)}")


@router.get("/latest")
def get_latest_backup_info(
    backup_type: str = "period",
    current_user: User = Depends(get_current_user)
):
    """
    Pobiera informacje o najnowszym backupie.
    """
    backup_path = get_latest_backup(backup_type=backup_type)
    if not backup_path:
        return {
            "message": f"Brak backupu typu {backup_type}",
            "backup_path": None
        }
    
    from pathlib import Path
    from datetime import datetime
    
    backup_file = Path(backup_path)
    if backup_file.exists():
        stat = backup_file.stat()
        return {
            "backup_path": backup_path,
            "filename": backup_file.name,
            "size": stat.st_size,
            "created": datetime.fromtimestamp(stat.st_mtime).isoformat()
        }
    
    return {
        "message": "Backup nie istnieje",
        "backup_path": None
    }


@router.post("/decrypt")
def decrypt_backup(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """
    Deszyfruje zaszyfrowany plik backupu przesłany przez użytkownika.
    Plik musi być zaszyfrowany przez tę aplikację (używając tego samego klucza).
    """
    if not file.filename or not file.filename.endswith('.encrypted'):
        raise HTTPException(
            status_code=400,
            detail="Plik musi mieć rozszerzenie .encrypted"
        )
    
    # Zapisz przesłany plik tymczasowo
    temp_dir = tempfile.gettempdir()
    temp_encrypted_path = os.path.join(temp_dir, file.filename)
    
    try:
        # Zapisz przesłany plik
        with open(temp_encrypted_path, 'wb') as f:
            content = file.file.read()
            f.write(content)
        
        # Deszyfruj plik
        decrypted_path = decrypt_backup_file(temp_encrypted_path)
        
        # Przeczytaj odszyfrowany plik
        with open(decrypted_path, 'rb') as f:
            decrypted_data = f.read()
        
        # Usuń pliki tymczasowe
        try:
            os.remove(temp_encrypted_path)
        except:
            pass
        
        from fastapi.responses import Response
        from pathlib import Path
        
        # Zwróć odszyfrowany plik jako odpowiedź
        decrypted_filename = Path(decrypted_path).name
        return Response(
            content=decrypted_data,
            media_type='application/octet-stream',
            headers={
                'Content-Disposition': f'attachment; filename="{decrypted_filename}"'
            }
        )
        
    except ValueError as e:
        # Błąd deszyfrowania (np. zły klucz)
        try:
            os.remove(temp_encrypted_path)
        except:
            pass
        raise HTTPException(
            status_code=400,
            detail=f"Nie udało się odszyfrować pliku. Upewnij się, że plik został zaszyfrowany przez tę aplikację: {str(e)}"
        )
    except Exception as e:
        try:
            os.remove(temp_encrypted_path)
        except:
            pass
        raise HTTPException(
            status_code=500,
            detail=f"Błąd deszyfrowania pliku: {str(e)}"
        )

