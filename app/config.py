"""
Konfiguracja aplikacji.
Używa pydantic-settings do zarządzania zmiennymi środowiskowymi.
"""

from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Ustawienia aplikacji z zmiennych środowiskowych."""
    
    # Baza danych
    database_url: str = "sqlite:///./water_billing.db"
    
    # API
    api_title: str = "Water Billing System"
    api_description: str = "System rozliczania rachunków za wodę, ścieki, gaz i prąd"
    api_version: str = "1.0.0"
    
    # CORS
    cors_allow_origins: List[str] = ["*"]  # W produkcji ograniczyć do konkretnych domen
    cors_allow_credentials: bool = True
    cors_allow_methods: List[str] = ["*"]
    cors_allow_headers: List[str] = ["*"]
    
    # Ścieżki
    static_dir: str = "app/static"
    invoices_raw_dir: str = "invoices_raw"
    bills_dir: str = "bills"
    
    # Google Sheets (opcjonalne)
    google_sheets_credentials_path: str = ""
    google_sheets_spreadsheet_id: str = ""
    
    # SMTP (opcjonalne - dla wysyłania emaili)
    smtp_server: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Globalna instancja ustawień
settings = Settings()

