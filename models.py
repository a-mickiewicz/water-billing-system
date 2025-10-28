"""
Modele SQLAlchemy dla bazy danych rozliczeń wodnych.
Definiuje tabele: locals, readings, invoices, bills.
"""

from sqlalchemy import Column, String, Float, Integer, Date, ForeignKey
from sqlalchemy.orm import relationship
from db import Base


class Local(Base):
    """Tabela lokali i przypisanych liczników."""
    __tablename__ = "locals"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    water_meter_name = Column(String(50), unique=True, nullable=False)  # np. 'water_meter_5'
    tenant = Column(String(100))  # Najemca
    local = Column(String(50))    # Nazwa lokalu ('gora', 'gabinet', 'dol')
    
    bills = relationship("Bill", back_populates="local_obj")


class Reading(Base):
    """Odczyty liczników wody."""
    __tablename__ = "readings"
    
    data = Column(String(7), primary_key=True)  # Format: 'YYYY-MM' (np. '2025-02')
    water_meter_main = Column(Float, nullable=False)  # Licznik główny
    water_meter_5 = Column(Integer, nullable=False)   # Lokal "gora"
    water_meter_5b = Column(Integer, nullable=False)  # Lokal "gabinet"
    # water_meter_5a obliczany jako: water_meter_main - (water_meter_5 + water_meter_5b)
    
    bills = relationship("Bill", back_populates="reading")


class Invoice(Base):
    """Faktury dostawcy mediów (woda i ścieki)."""
    __tablename__ = "invoices"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    data = Column(String(7), ForeignKey('readings.data'), nullable=False)  # 'YYYY-MM'
    usage = Column(Float, nullable=False)  # Zużycie w m³
    water_cost_m3 = Column(Float, nullable=False)  # Koszt wody za m³
    sewage_cost_m3 = Column(Float, nullable=False)  # Koszt ścieków za m³
    nr_of_subscription = Column(Integer, nullable=False)  # Liczba miesięcy abonamentu
    water_subscr_cost = Column(Float, nullable=False)  # Koszt abonamentu wody
    sewage_subscr_cost = Column(Float, nullable=False)  # Koszt abonamentu ścieków
    vat = Column(Float, nullable=False)  # VAT (np. 0.08 dla 8%)
    period_start = Column(Date, nullable=False)  # Początek okresu rozliczeniowego
    period_stop = Column(Date, nullable=False)  # Koniec okresu rozliczeniowego
    invoice_number = Column(String(100), nullable=False)  # Numer faktury (może być wiele faktur dla tego samego okresu)
    gross_sum = Column(Float, nullable=False)  # Suma brutto faktury
    
    bills = relationship("Bill", back_populates="invoice")


class Bill(Base):
    """Wygenerowane rachunki dla lokali."""
    __tablename__ = "bills"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    data = Column(String(7), nullable=False)  # 'YYYY-MM'
    local = Column(String(50), nullable=False)  # 'gora', 'gabinet', 'dol'
    
    # Relacje
    reading_id = Column(String(7), ForeignKey('readings.data'))
    invoice_id = Column(Integer, ForeignKey('invoices.id'))
    local_id = Column(Integer, ForeignKey('locals.id'))
    
    reading = relationship("Reading", back_populates="bills")
    invoice = relationship("Invoice", back_populates="bills")
    local_obj = relationship("Local", back_populates="bills")
    
    # Dane odczytu
    reading_value = Column(Float, nullable=False)  # Wartość odczytu licznika dla lokalu
    usage_m3 = Column(Float, nullable=False)  # Zużycie w m³
    
    # Koszty
    cost_water = Column(Float, nullable=False)  # Koszt wody
    cost_sewage = Column(Float, nullable=False)  # Koszt ścieków
    cost_usage_total = Column(Float, nullable=False)  # Suma kosztów zużycia (woda + ścieki)
    
    # Abonamenty
    abonament_water_share = Column(Float, nullable=False)  # Udział w abonamencie wody
    abonament_sewage_share = Column(Float, nullable=False)  # Udział w abonamencie ścieków
    abonament_total = Column(Float, nullable=False)  # Suma abonamentów
    
    # Sumy
    net_sum = Column(Float, nullable=False)  # Suma netto
    gross_sum = Column(Float, nullable=False)  # Suma brutto
    
    # Plik PDF
    pdf_path = Column(String(200))  # Ścieżka do wygenerowanego pliku PDF

