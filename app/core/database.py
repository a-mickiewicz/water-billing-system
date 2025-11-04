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
    """
    from app.models.water import Local, Reading, Invoice, Bill
    from app.models.gas import GasInvoice, GasBill
    
    Base.metadata.create_all(bind=engine)
    print("[OK] Baza danych zainicjalizowana")


if __name__ == "__main__":
    init_db()

