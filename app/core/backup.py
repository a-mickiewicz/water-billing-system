"""
Moduł backupu bazy danych.
Zarządza trzema poziomami backupów:
1. Backup okresowy (po każdym okresie rozliczeniowym) - nadpisuje poprzedni
2. Backup półroczny (co pół roku) - nadpisuje poprzedni
3. Backup roczny (co rok) - nadpisuje poprzedni
"""

import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from sqlalchemy.orm import Session

from app.core.database import DATABASE_URL, BASE_DIR
from app.core.file_encryption import decrypt_file


BACKUP_DIR = Path(BASE_DIR) / "backups"
BACKUP_DIR.mkdir(exist_ok=True)


def create_backup(db_path: str = None, backup_type: str = "period") -> str:
    """
    Tworzy backup bazy danych.
    
    Args:
        db_path: Ścieżka do bazy danych (domyślnie DATABASE_URL)
        backup_type: Typ backupu - "period" (okresowy), "halfyear" (półroczny), "year" (roczny)
    
    Returns:
        Ścieżka do utworzonego pliku backupu
    """
    if db_path is None:
        db_path = DATABASE_URL
    
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Baza danych nie istnieje: {db_path}")
    
    # Nazwa pliku backupu
    date_str = datetime.now().strftime("%Y_%m_%d")
    backup_filename = f"water_billing_backup_{date_str}.db"
    
    # Dla różnych typów backupów używamy różnych folderów
    if backup_type == "period":
        backup_folder = BACKUP_DIR / "period"
    elif backup_type == "halfyear":
        backup_folder = BACKUP_DIR / "halfyear"
    elif backup_type == "year":
        backup_folder = BACKUP_DIR / "year"
    else:
        backup_folder = BACKUP_DIR / "period"
    
    backup_folder.mkdir(exist_ok=True, parents=True)
    
    # Usuń poprzedni backup tego typu (nadpisywanie)
    for old_backup in backup_folder.glob("water_billing_backup_*.db"):
        try:
            old_backup.unlink()
        except Exception as e:
            print(f"Ostrzeżenie: Nie udało się usunąć starego backupu {old_backup}: {e}")
    
    # Utwórz nowy backup
    backup_path = backup_folder / backup_filename
    shutil.copy2(db_path, backup_path)
    
    print(f"[OK] Utworzono backup {backup_type}: {backup_path}")
    return str(backup_path)


def should_create_halfyear_backup() -> bool:
    """Sprawdza czy należy utworzyć backup półroczny (co 6 miesięcy)."""
    halfyear_backup_dir = BACKUP_DIR / "halfyear"
    if not halfyear_backup_dir.exists():
        return True
    
    # Sprawdź datę ostatniego backupu półrocznego
    backups = list(halfyear_backup_dir.glob("water_billing_backup_*.db"))
    if not backups:
        return True
    
    # Pobierz datę z najnowszego backupu
    latest_backup = max(backups, key=lambda p: p.stat().st_mtime)
    backup_date_str = latest_backup.stem.replace("water_billing_backup_", "")
    
    try:
        backup_date = datetime.strptime(backup_date_str, "%Y_%m_%d")
        six_months_ago = datetime.now() - timedelta(days=180)
        return backup_date < six_months_ago
    except ValueError:
        return True


def should_create_year_backup() -> bool:
    """Sprawdza czy należy utworzyć backup roczny (co rok)."""
    year_backup_dir = BACKUP_DIR / "year"
    if not year_backup_dir.exists():
        return True
    
    # Sprawdź datę ostatniego backupu rocznego
    backups = list(year_backup_dir.glob("water_billing_backup_*.db"))
    if not backups:
        return True
    
    # Pobierz datę z najnowszego backupu
    latest_backup = max(backups, key=lambda p: p.stat().st_mtime)
    backup_date_str = latest_backup.stem.replace("water_billing_backup_", "")
    
    try:
        backup_date = datetime.strptime(backup_date_str, "%Y_%m_%d")
        one_year_ago = datetime.now() - timedelta(days=365)
        return backup_date < one_year_ago
    except ValueError:
        return True


def create_all_backups() -> dict:
    """
    Tworzy wszystkie potrzebne backupu (okresowy zawsze, półroczny i roczny jeśli potrzeba).
    
    Returns:
        Słownik z informacjami o utworzonych backupach
    """
    results = {
        "period_backup": None,
        "halfyear_backup": None,
        "year_backup": None,
        "errors": []
    }
    
    # Zawsze tworzymy backup okresowy
    try:
        results["period_backup"] = create_backup(backup_type="period")
    except Exception as e:
        results["errors"].append(f"Błąd tworzenia backupu okresowego: {str(e)}")
    
    # Backup półroczny - jeśli potrzeba
    if should_create_halfyear_backup():
        try:
            results["halfyear_backup"] = create_backup(backup_type="halfyear")
        except Exception as e:
            results["errors"].append(f"Błąd tworzenia backupu półrocznego: {str(e)}")
    
    # Backup roczny - jeśli potrzeba
    if should_create_year_backup():
        try:
            results["year_backup"] = create_backup(backup_type="year")
        except Exception as e:
            results["errors"].append(f"Błąd tworzenia backupu rocznego: {str(e)}")
    
    return results


def get_latest_backup(backup_type: str = "period") -> Optional[str]:
    """
    Pobiera ścieżkę do najnowszego backupu danego typu.
    
    Args:
        backup_type: Typ backupu - "period", "halfyear", "year"
    
    Returns:
        Ścieżka do najnowszego backupu lub None
    """
    if backup_type == "period":
        backup_folder = BACKUP_DIR / "period"
    elif backup_type == "halfyear":
        backup_folder = BACKUP_DIR / "halfyear"
    elif backup_type == "year":
        backup_folder = BACKUP_DIR / "year"
    else:
        backup_folder = BACKUP_DIR / "period"
    
    if not backup_folder.exists():
        return None
    
    backups = list(backup_folder.glob("water_billing_backup_*.db"))
    if not backups:
        return None
    
    latest_backup = max(backups, key=lambda p: p.stat().st_mtime)
    return str(latest_backup)


def decrypt_backup_file(encrypted_file_path: str, output_path: Optional[str] = None) -> str:
    """
    Deszyfruje zaszyfrowany plik backupu.
    
    Args:
        encrypted_file_path: Ścieżka do zaszyfrowanego pliku backupu
        output_path: Ścieżka do odszyfrowanego pliku (opcjonalnie)
    
    Returns:
        Ścieżka do odszyfrowanego pliku backupu
    """
    if not os.path.exists(encrypted_file_path):
        raise FileNotFoundError(f"Zaszyfrowany plik nie istnieje: {encrypted_file_path}")
    
    # Jeśli nie podano output_path, zapisz w folderze backups/decrypted
    if output_path is None:
        decrypted_folder = BACKUP_DIR / "decrypted"
        decrypted_folder.mkdir(exist_ok=True, parents=True)
        
        # Usuń rozszerzenie .encrypted jeśli istnieje
        original_name = Path(encrypted_file_path).stem
        if original_name.endswith('.encrypted'):
            original_name = original_name[:-10]  # Usuń .encrypted
        
        output_path = decrypted_folder / original_name
    
    # Deszyfruj plik
    decrypted_path = decrypt_file(encrypted_file_path, str(output_path))
    
    print(f"[OK] Odszyfrowano backup: {encrypted_file_path} -> {decrypted_path}")
    return decrypted_path

