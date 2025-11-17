"""
Model dla rachunków łączonych (wszystkie media: woda, gaz, prąd).
"""

from sqlalchemy import Column, String, Float, Integer, ForeignKey, Date
from sqlalchemy.orm import relationship
from app.core.database import Base


class CombinedBill(Base):
    """
    Rachunek łączony zawierający wszystkie media (woda/ścieki, gaz, prąd) dla lokalu.
    Okres rozliczeniowy to 2 miesiące (format: YYYY-MM do YYYY-MM).
    """
    __tablename__ = "combined_bills"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Okres rozliczeniowy (2 miesiące)
    period_start = Column(String(7), nullable=False)  # 'YYYY-MM' - pierwszy miesiąc
    period_end = Column(String(7), nullable=False)   # 'YYYY-MM' - drugi miesiąc
    local = Column(String(50), nullable=False)  # 'gora', 'gabinet', 'dol'
    
    # Relationships do rachunków poszczególnych mediów
    water_bill_id = Column(Integer, ForeignKey('bills.id'), nullable=True)
    gas_bill_id = Column(Integer, ForeignKey('gas_bills.id'), nullable=True)
    electricity_bill_id = Column(Integer, ForeignKey('electricity_bills.id'), nullable=True)
    local_id = Column(Integer, ForeignKey('locals.id'), nullable=False)
    
    # Relationships
    water_bill = relationship("Bill", foreign_keys=[water_bill_id])
    gas_bill = relationship("GasBill", foreign_keys=[gas_bill_id])
    electricity_bill = relationship("ElectricityBill", foreign_keys=[electricity_bill_id])
    local_obj = relationship("Local", back_populates="combined_bills")
    
    # Sumy łączone
    total_net_sum = Column(Float, nullable=False)  # Suma netto wszystkich mediów
    total_gross_sum = Column(Float, nullable=False)  # Suma brutto wszystkich mediów
    
    # Data wygenerowania
    generated_date = Column(Date, nullable=False)  # Data wygenerowania rachunku
    
    # PDF file
    pdf_path = Column(String(200))  # Path to generated PDF file
    
    # Email status
    email_sent_date = Column(Date, nullable=True)  # Data wysłania emaila do najemcy

