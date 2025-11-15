"""
Moduł inicjalizacji bazy danych SQLite z SQLAlchemy.
Tworzy połączenie z bazą danych i sesje.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Ścieżka do bazy danych (w głównym katalogu projektu)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATABASE_URL = os.path.join(BASE_DIR, "water_billing.db")

# Tworzenie silnika bazy danych
engine = create_engine(
    f"sqlite:///{DATABASE_URL}",
    connect_args={"check_same_thread": False}  # Konieczne dla SQLite z FastAPI
)

# Sesja bazy danych
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Baza dla modeli ORM
Base = declarative_base()


def get_db():
    """
    Dependency dla FastAPI - zwraca sesję bazy danych.
    Automatycznie zamyka sesję po użyciu.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Inicjalizuje bazę danych - tworzy wszystkie tabele.
    Obsługuje błędy związane z już istniejącymi indeksami.
    """
    from app.models.water import Local, Reading, Invoice, Bill
    from app.models.gas import GasInvoice, GasBill
    from app.models.electricity import ElectricityReading, ElectricityBill
    from app.models.electricity_invoice import (
        ElectricityInvoice,
        ElectricityInvoiceBlankiet,
        ElectricityInvoiceOdczyt,
        ElectricityInvoiceSprzedazEnergii,
        ElectricityInvoiceOplataDystrybucyjna,
        ElectricityInvoiceRozliczenieOkres
    )
    from app.models.user import User
    from app.models.password_reset import PasswordResetCode
    
    try:
        Base.metadata.create_all(bind=engine, checkfirst=True)
        print("[OK] Baza danych zainicjalizowana")
    except Exception as e:
        # Jeśli błąd dotyczy tylko indeksów, które już istnieją, to to nie jest problem
        error_msg = str(e)
        if "index" in error_msg.lower() and "already exists" in error_msg.lower():
            print("[WARN] Niektóre indeksy już istnieją (używane przez inne tabele), ale tabele są gotowe")
            print("[OK] Baza danych zainicjalizowana")
        else:
            # Jeśli to inny błąd, rzuć go dalej
            raise


if __name__ == "__main__":
    init_db()

