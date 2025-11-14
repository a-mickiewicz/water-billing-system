"""
SQLAlchemy models for gas billing.
Defines tables: gas_invoices, gas_bills.
Note: Gas readings are not stored - all data is in the invoice.
"""

from sqlalchemy import Column, String, Float, Integer, Date, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class GasInvoice(Base):
    """Gas provider invoices (PGNiG)."""
    __tablename__ = "gas_invoices"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    data = Column(String(7), nullable=False)  # 'YYYY-MM' (generated from period_start)
    
    # Billing period (bi-monthly)
    period_start = Column(Date, nullable=False)  # e.g., 2019-04-03
    period_stop = Column(Date, nullable=False)   # e.g., 2019-06-08
    
    # Meter readings
    previous_reading = Column(Float, nullable=False)  # Previous reading (m³)
    current_reading = Column(Float, nullable=False)   # Current reading (m³)
    
    # Gas fuel
    fuel_usage_m3 = Column(Float, nullable=False)      # Quantity (m³)
    fuel_price_net = Column(Float, nullable=False)     # Net price per m³
    fuel_value_net = Column(Float, nullable=False)    # Net value
    fuel_vat_amount = Column(Float, nullable=False)   # VAT amount (23%)
    fuel_value_gross = Column(Float, nullable=False)   # Gross value
    
    # Subscription fee
    subscription_quantity = Column(Integer, nullable=False)  # Number of months
    subscription_price_net = Column(Float, nullable=False)   # Net price per month
    subscription_value_net = Column(Float, nullable=False)    # Net value
    subscription_vat_amount = Column(Float, nullable=False)  # VAT amount (23%)
    subscription_value_gross = Column(Float, nullable=False) # Gross value
    
    # Fixed distribution fee
    distribution_fixed_quantity = Column(Integer, nullable=False)  # Number of months
    distribution_fixed_price_net = Column(Float, nullable=False)   # Net price per month
    distribution_fixed_vat_amount = Column(Float, nullable=False)  # VAT amount (23%)
    distribution_fixed_value_gross = Column(Float, nullable=False) # Gross value
    
    # Fixed distribution fee - additional fields
    distribution_fixed_value_net = Column(Float, nullable=False)  # Net value
    
    # Variable distribution fee
    distribution_variable_usage_m3 = Column(Float, nullable=False)  # Consumption in m³
    distribution_variable_conversion_factor = Column(Float, nullable=False)  # Conversion factor
    distribution_variable_usage_kwh = Column(Float, nullable=False)  # Consumption in kWh
    distribution_variable_price_net = Column(Float, nullable=False)   # Net price per kWh
    distribution_variable_value_net = Column(Float, nullable=False)  # Net value
    distribution_variable_vat_amount = Column(Float, nullable=False)  # VAT amount (23%)
    distribution_variable_value_gross = Column(Float, nullable=False) # Gross value
    
    # Variable distribution fee 2 (if occurs twice)
    distribution_variable_2_usage_m3 = Column(Float, nullable=True)  # Consumption in m³
    distribution_variable_2_conversion_factor = Column(Float, nullable=True)  # Conversion factor
    distribution_variable_2_usage_kwh = Column(Float, nullable=True)  # Consumption in kWh
    distribution_variable_2_price_net = Column(Float, nullable=True)   # Net price per kWh
    distribution_variable_2_value_net = Column(Float, nullable=True)  # Net value
    
    # Gas fuel - additional fields
    fuel_conversion_factor = Column(Float, nullable=False)  # Conversion factor (kWh/m³)
    fuel_usage_kwh = Column(Float, nullable=False)  # Consumption in kWh
    
    # VAT
    vat_rate = Column(Float, nullable=False)  # VAT (0.23 for 23%)
    vat_amount = Column(Float, nullable=False)  # Total VAT amount
    
    # Totals
    total_net_sum = Column(Float, nullable=False)  # Total net value
    total_gross_sum = Column(Float, nullable=False)      # Total gross value
    
    # Interest and payment
    late_payment_interest = Column(Float, nullable=False, default=0.0)  # Late payment interest
    amount_to_pay = Column(Float, nullable=False)  # Amount to pay
    payment_due_date = Column(Date, nullable=False)  # Payment due date
    
    # Balance before settlement (optional)
    balance_before_settlement = Column(Float, nullable=True)
    
    # Invoice number
    invoice_number = Column(String(100), nullable=False)  # Format: "Faktura VAT P/43562821/0003/25"
    
    bills = relationship("GasBill", back_populates="invoice", cascade="all, delete-orphan")


class GasBill(Base):
    """
    Generated gas bills for units.
    
    Cost distribution:
    - "gora": 58% (0.58)
    - "dol": 25% (0.25)
    - "gabinet": 17% (0.17)
    """
    __tablename__ = "gas_bills"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    data = Column(String(7), nullable=False)
    local = Column(String(50), nullable=False)  # 'gora', 'gabinet', 'dol'
    
    invoice_id = Column(Integer, ForeignKey('gas_invoices.id'))
    local_id = Column(Integer, ForeignKey('locals.id'))
    
    # Cost distribution
    cost_share = Column(Float, nullable=False)  # 0.58 for gora, 0.25 for dol, 0.17 for gabinet
    
    # Costs distributed proportionally from invoice (gross)
    fuel_cost_gross = Column(Float, nullable=False)
    subscription_cost_gross = Column(Float, nullable=False)
    distribution_fixed_cost_gross = Column(Float, nullable=False)
    distribution_variable_cost_gross = Column(Float, nullable=False)
    
    # Totals
    total_net_sum = Column(Float, nullable=False)    # Net sum (proportional)
    total_gross_sum = Column(Float, nullable=False)  # Gross sum (proportional)
    
    pdf_path = Column(String(200))
    
    invoice = relationship("GasInvoice", back_populates="bills")
    local_obj = relationship("Local", back_populates="gas_bills")

