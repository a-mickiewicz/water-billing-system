"""
Modele SQLAlchemy dla prądu.
Definiuje tabele: electricity_readings, electricity_bills.
UWAGA: ElectricityInvoice został przeniesiony do app/models/electricity_invoice.py
"""

from sqlalchemy import Column, String, Float, Boolean, Integer, Date, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship
from app.core.database import Base


class ElectricityReading(Base):
    """
    Odczyty liczników prądu.
    
    Obsługuje:
    - Licznik główny DOM: dwutaryfowy (I, II) lub jednotaryfowy
    - Podlicznik DÓŁ: dwutaryfowy (I, II) lub jednotaryfowy
    - Podlicznik GABINET: zawsze jednotaryfowy
    - GÓRA: obliczane (DOM - DÓŁ - GABINET)
    """
    __tablename__ = "electricity_readings"
    
    # ID i organizacja
    id = Column(Integer, primary_key=True, autoincrement=True)
    data = Column(String(7), unique=True, nullable=False)  # Format: 'YYYY-MM' (np. '2025-01')
    
    # ============================================
    # LICZNIK GŁÓWNY DOM
    # ============================================
    licznik_dom_jednotaryfowy = Column(Boolean, nullable=False, default=False)
    
    # Wariant A: Licznik jednotaryfowy
    odczyt_dom = Column(Float, nullable=True)  # NULL jeśli dwutaryfowy
    
    # Wariant B: Licznik dwutaryfowy
    odczyt_dom_I = Column(Float, nullable=True)   # NULL jeśli jednotaryfowy
    odczyt_dom_II = Column(Float, nullable=True)  # NULL jeśli jednotaryfowy
    
    # ============================================
    # PODLICZNIK DÓŁ
    # ============================================
    licznik_dol_jednotaryfowy = Column(Boolean, nullable=False, default=False)
    
    # Wariant A: Licznik jednotaryfowy
    odczyt_dol = Column(Float, nullable=True)  # NULL jeśli dwutaryfowy
    
    # Wariant B: Licznik dwutaryfowy
    odczyt_dol_I = Column(Float, nullable=True)   # NULL jeśli jednotaryfowy
    odczyt_dol_II = Column(Float, nullable=True)  # NULL jeśli jednotaryfowy
    
    # ============================================
    # PODLICZNIK GABINET
    # ============================================
    # Zawsze jednotaryfowy
    odczyt_gabinet = Column(Float, nullable=False)
    
    # Relacje
    bills = relationship("ElectricityBill", back_populates="reading", cascade="all, delete-orphan")
    
    # Constraints
    __table_args__ = (
        CheckConstraint(
            "(licznik_dom_jednotaryfowy = 1 AND odczyt_dom IS NOT NULL AND odczyt_dom_I IS NULL AND odczyt_dom_II IS NULL) OR "
            "(licznik_dom_jednotaryfowy = 0 AND odczyt_dom IS NULL AND odczyt_dom_I IS NOT NULL AND odczyt_dom_II IS NOT NULL)",
            name="check_dom_meter_type"
        ),
        CheckConstraint(
            "(licznik_dol_jednotaryfowy = 1 AND odczyt_dol IS NOT NULL AND odczyt_dol_I IS NULL AND odczyt_dol_II IS NULL) OR "
            "(licznik_dol_jednotaryfowy = 0 AND odczyt_dol IS NULL AND odczyt_dol_I IS NOT NULL AND odczyt_dol_II IS NOT NULL)",
            name="check_dol_meter_type"
        ),
    )


class ElectricityBill(Base):
    """
    Wygenerowane rachunki prądu dla lokali.
    
    Rozdzielenie kosztów na podstawie zużycia:
    - "gora": obliczane (DOM - DÓŁ - GABINET)
    - "dol": z podlicznika
    - "gabinet": z podlicznika
    """
    __tablename__ = "electricity_bills"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    data = Column(String(7), nullable=False)  # 'YYYY-MM'
    local = Column(String(50), nullable=False)  # 'gora', 'gabinet', 'dol'
    
    # Relacje
    reading_id = Column(Integer, ForeignKey('electricity_readings.id'))
    invoice_id = Column(Integer, ForeignKey('electricity_invoices.id'))
    local_id = Column(Integer, ForeignKey('locals.id'))
    
    reading = relationship("ElectricityReading", back_populates="bills")
    invoice = relationship("ElectricityInvoice", back_populates="bills")
    local_obj = relationship("Local", back_populates="electricity_bills")
    
    # Zużycie (kWh)
    usage_kwh = Column(Float, nullable=False)  # Zużycie dla lokalu
    
    # Koszty rozdzielone proporcjonalnie z faktury (brutto)
    energy_cost_gross = Column(Float, nullable=False)
    distribution_cost_gross = Column(Float, nullable=False)
    
    # Sumy
    total_net_sum = Column(Float, nullable=False)  # Suma netto (proporcjonalna)
    total_gross_sum = Column(Float, nullable=False)  # Suma brutto (proporcjonalna)
    
    # Plik PDF
    pdf_path = Column(String(200))  # Ścieżka do wygenerowanego pliku PDF

