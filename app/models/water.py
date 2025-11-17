"""
SQLAlchemy models for water billing database.
Defines tables: locals, readings, invoices, bills.
"""

from sqlalchemy import Column, String, Float, Integer, Date, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class Local(Base):
    """Units table with assigned meters."""
    __tablename__ = "locals"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    water_meter_name = Column(String(50), unique=True, nullable=True)  # e.g., 'water_meter_5'
    gas_meter_name = Column(String(50), unique=True, nullable=True)    # Gas meter (NEW)
    tenant = Column(String(100))  # Tenant name
    local = Column(String(50))    # Unit name ('gora', 'gabinet', 'dol')
    email = Column(String(200), nullable=True)  # Email address for sending bills
    
    bills = relationship("Bill", back_populates="local_obj")
    gas_bills = relationship("GasBill", back_populates="local_obj", cascade="all, delete-orphan")
    electricity_bills = relationship("ElectricityBill", back_populates="local_obj", cascade="all, delete-orphan")
    combined_bills = relationship("CombinedBill", back_populates="local_obj", cascade="all, delete-orphan")


class Reading(Base):
    """Water meter readings."""
    __tablename__ = "readings"
    
    data = Column(String(7), primary_key=True)  # Format: 'YYYY-MM' (e.g., '2025-02')
    water_meter_main = Column(Float, nullable=False)  # Main meter (DOM)
    water_meter_5 = Column(Integer, nullable=False)   # Unit "gora" - physical meter
    water_meter_5a = Column(Integer, nullable=False)  # Unit "gabinet" - physical meter
    water_meter_5b = Column(Integer, nullable=False)  # Unit "dol" (Mikołaj) - calculated as: water_meter_main - (water_meter_5 + water_meter_5a)
    
    bills = relationship("Bill", back_populates="reading")


class Invoice(Base):
    """Utility provider invoices (water and sewage)."""
    __tablename__ = "invoices"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    data = Column(String(7), ForeignKey('readings.data'), nullable=False)  # 'YYYY-MM'
    usage = Column(Float, nullable=False)  # Consumption in m³
    water_cost_m3 = Column(Float, nullable=False)  # Water cost per m³
    sewage_cost_m3 = Column(Float, nullable=False)  # Sewage cost per m³
    nr_of_subscription = Column(Integer, nullable=False)  # Number of subscription months
    water_subscr_cost = Column(Float, nullable=False)  # Water subscription cost
    sewage_subscr_cost = Column(Float, nullable=False)  # Sewage subscription cost
    vat = Column(Float, nullable=False)  # VAT (e.g., 0.08 for 8%)
    period_start = Column(Date, nullable=False)  # Billing period start
    period_stop = Column(Date, nullable=False)  # Billing period end
    invoice_number = Column(String(100), nullable=False)  # Invoice number (multiple invoices possible for same period)
    gross_sum = Column(Float, nullable=False)  # Invoice gross sum
    
    bills = relationship("Bill", back_populates="invoice")


class Bill(Base):
    """Generated bills for units."""
    __tablename__ = "bills"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    data = Column(String(7), nullable=False)  # 'YYYY-MM'
    local = Column(String(50), nullable=False)  # 'gora', 'gabinet', 'dol'
    
    # Relationships
    reading_id = Column(String(7), ForeignKey('readings.data'))
    invoice_id = Column(Integer, ForeignKey('invoices.id'))
    local_id = Column(Integer, ForeignKey('locals.id'))
    
    reading = relationship("Reading", back_populates="bills")
    invoice = relationship("Invoice", back_populates="bills")
    local_obj = relationship("Local", back_populates="bills")
    
    # Reading data
    reading_value = Column(Float, nullable=False)  # Meter reading value for the unit
    usage_m3 = Column(Float, nullable=False)  # Consumption in m³
    
    # Costs
    cost_water = Column(Float, nullable=False)  # Water cost
    cost_sewage = Column(Float, nullable=False)  # Sewage cost
    cost_usage_total = Column(Float, nullable=False)  # Total consumption costs (water + sewage)
    
    # Subscriptions
    abonament_water_share = Column(Float, nullable=False)  # Water subscription share
    abonament_sewage_share = Column(Float, nullable=False)  # Sewage subscription share
    abonament_total = Column(Float, nullable=False)  # Total subscriptions
    
    # Totals
    net_sum = Column(Float, nullable=False)  # Net sum
    gross_sum = Column(Float, nullable=False)  # Gross sum
    
    # PDF file
    pdf_path = Column(String(200))  # Path to generated PDF file

