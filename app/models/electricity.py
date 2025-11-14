"""
SQLAlchemy models for electricity billing.
Defines tables: electricity_readings, electricity_bills.
NOTE: ElectricityInvoice has been moved to app/models/electricity_invoice.py
"""

from sqlalchemy import Column, String, Float, Boolean, Integer, Date, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship
from app.core.database import Base


class ElectricityReading(Base):
    """
    Electricity meter readings.
    
    Supports:
    - Main meter DOM: dual-tariff (I, II) or single-tariff
    - Submeter DÓŁ: dual-tariff (I, II) or single-tariff (contains GABINET)
    - Submeter GABINET: always single-tariff (nested under DÓŁ)
    - GÓRA: calculated (DOM - DÓŁ)
    
    Hierarchical structure:
    DOM → DÓŁ → GABINET
    """
    __tablename__ = "electricity_readings"
    
    # ID and organization
    id = Column(Integer, primary_key=True, autoincrement=True)
    data = Column(String(7), unique=True, nullable=False)  # Format: 'YYYY-MM' (e.g., '2025-01')
    data_odczytu_licznika = Column(Date, nullable=True)  # Actual meter reading date
    
    # ============================================
    # MAIN METER DOM
    # ============================================
    licznik_dom_jednotaryfowy = Column(Boolean, nullable=False, default=False)
    
    # Variant A: Single-tariff meter
    odczyt_dom = Column(Float, nullable=True)  # NULL if dual-tariff
    
    # Variant B: Dual-tariff meter
    odczyt_dom_I = Column(Float, nullable=True)   # NULL if single-tariff
    odczyt_dom_II = Column(Float, nullable=True)  # NULL if single-tariff
    
    # ============================================
    # SUBMETER DÓŁ
    # ============================================
    licznik_dol_jednotaryfowy = Column(Boolean, nullable=False, default=False)
    
    # Variant A: Single-tariff meter
    odczyt_dol = Column(Float, nullable=True)  # NULL if dual-tariff
    
    # Variant B: Dual-tariff meter
    odczyt_dol_I = Column(Float, nullable=True)   # NULL if single-tariff
    odczyt_dol_II = Column(Float, nullable=True)  # NULL if single-tariff
    
    # ============================================
    # SUBMETER GABINET
    # ============================================
    # Always single-tariff
    odczyt_gabinet = Column(Float, nullable=False)
    
    # Relationships
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
    Generated electricity bills for units.
    
    Cost distribution based on consumption:
    - "gora": calculated (DOM - DÓŁ)
    - "dol": from submeter (contains GABINET)
    - "gabinet": from submeter (DÓŁ submeter)
    """
    __tablename__ = "electricity_bills"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    data = Column(String(7), nullable=False)  # 'YYYY-MM'
    local = Column(String(50), nullable=False)  # 'gora', 'gabinet', 'dol'
    
    # Relationships
    reading_id = Column(Integer, ForeignKey('electricity_readings.id'))
    invoice_id = Column(Integer, ForeignKey('electricity_invoices.id'))
    local_id = Column(Integer, ForeignKey('locals.id'))
    
    reading = relationship("ElectricityReading", back_populates="bills")
    invoice = relationship("ElectricityInvoice", back_populates="bills")
    local_obj = relationship("Local", back_populates="electricity_bills")
    
    # Consumption (kWh)
    usage_kwh = Column(Float, nullable=False)  # Unit consumption (total)
    usage_kwh_dzienna = Column(Float, nullable=True)  # Day consumption (tariff I) - NULL for single-tariff
    usage_kwh_nocna = Column(Float, nullable=True)  # Night consumption (tariff II) - NULL for single-tariff
    
    # Costs distributed proportionally from invoice (gross)
    energy_cost_gross = Column(Float, nullable=False)
    distribution_cost_gross = Column(Float, nullable=False)
    
    # Totals
    total_net_sum = Column(Float, nullable=False)  # Net sum (proportional)
    total_gross_sum = Column(Float, nullable=False)  # Gross sum (proportional)
    
    # PDF file
    pdf_path = Column(String(200))  # Path to generated PDF file

