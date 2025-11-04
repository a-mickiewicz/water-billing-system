"""
Modele SQLAlchemy dla gazu.
Definiuje tabele: gas_invoices, gas_bills.
Uwaga: Odczyty gazu nie są przechowywane - wszystkie dane są w fakturze.
"""

from sqlalchemy import Column, String, Float, Integer, Date, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class GasInvoice(Base):
    """Faktury dostawcy gazu (PGNiG)."""
    __tablename__ = "gas_invoices"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    data = Column(String(7), nullable=False)  # 'YYYY-MM' (generowane z period_start)
    
    # Okres rozliczeniowy (dwumiesięczny)
    period_start = Column(Date, nullable=False)  # np. 2019-04-03
    period_stop = Column(Date, nullable=False)   # np. 2019-06-08
    
    # Odczyty liczników
    previous_reading = Column(Float, nullable=False)  # Odczyt poprzedni (m³)
    current_reading = Column(Float, nullable=False)   # Odczyt obecny (m³)
    
    # Paliwo gazowe
    fuel_usage_m3 = Column(Float, nullable=False)      # Ilość (m³)
    fuel_price_net = Column(Float, nullable=False)     # Cena netto za m³
    fuel_value_net = Column(Float, nullable=False)    # Wartość netto
    fuel_vat_amount = Column(Float, nullable=False)   # Kwota VAT (23%)
    fuel_value_gross = Column(Float, nullable=False)   # Wartość brutto
    
    # Opłata abonamentowa
    subscription_quantity = Column(Integer, nullable=False)  # Ilość miesięcy
    subscription_price_net = Column(Float, nullable=False)   # Cena netto za miesiąc
    subscription_value_net = Column(Float, nullable=False)    # Wartość netto
    subscription_vat_amount = Column(Float, nullable=False)  # Kwota VAT (23%)
    subscription_value_gross = Column(Float, nullable=False) # Wartość brutto
    
    # Opłata dystrybucyjna stała
    distribution_fixed_quantity = Column(Integer, nullable=False)  # Ilość miesięcy
    distribution_fixed_price_net = Column(Float, nullable=False)   # Cena netto za miesiąc
    distribution_fixed_vat_amount = Column(Float, nullable=False)  # Kwota VAT (23%)
    distribution_fixed_value_gross = Column(Float, nullable=False) # Wartość brutto
    
    # Opłata dystrybucyjna stała - dodatkowe pola
    distribution_fixed_value_net = Column(Float, nullable=False)  # Wartość netto
    
    # Opłata dystrybucyjna zmienna
    distribution_variable_usage_m3 = Column(Float, nullable=False)  # Zużycie w m³
    distribution_variable_conversion_factor = Column(Float, nullable=False)  # Współczynnik konwersji
    distribution_variable_usage_kwh = Column(Float, nullable=False)  # Zużycie w kWh
    distribution_variable_price_net = Column(Float, nullable=False)   # Cena netto za kWh
    distribution_variable_value_net = Column(Float, nullable=False)  # Wartość netto
    distribution_variable_vat_amount = Column(Float, nullable=False)  # Kwota VAT (23%)
    distribution_variable_value_gross = Column(Float, nullable=False) # Wartość brutto
    
    # Opłata dystrybucyjna zmienna 2 (jeśli występuje dwukrotnie)
    distribution_variable_2_usage_m3 = Column(Float, nullable=True)  # Zużycie w m³
    distribution_variable_2_conversion_factor = Column(Float, nullable=True)  # Współczynnik konwersji
    distribution_variable_2_usage_kwh = Column(Float, nullable=True)  # Zużycie w kWh
    distribution_variable_2_price_net = Column(Float, nullable=True)   # Cena netto za kWh
    distribution_variable_2_value_net = Column(Float, nullable=True)  # Wartość netto
    
    # Paliwo gazowe - dodatkowe pola
    fuel_conversion_factor = Column(Float, nullable=False)  # Współczynnik konwersji (kWh/m³)
    fuel_usage_kwh = Column(Float, nullable=False)  # Zużycie w kWh
    
    # VAT
    vat_rate = Column(Float, nullable=False)  # VAT (0.23 dla 23%)
    vat_amount = Column(Float, nullable=False)  # Kwota VAT ogółem
    
    # Sumy
    total_net_sum = Column(Float, nullable=False)  # Wartość netto ogółem
    total_gross_sum = Column(Float, nullable=False)      # Wartość brutto całość
    
    # Odsetki i płatność
    late_payment_interest = Column(Float, nullable=False, default=0.0)  # Odsetki za nieterminowe wpłaty
    amount_to_pay = Column(Float, nullable=False)  # Do zapłaty
    payment_due_date = Column(Date, nullable=False)  # Termin płatności
    
    # Stan należności przed rozliczeniem (opcjonalne)
    balance_before_settlement = Column(Float, nullable=True)
    
    # Numer faktury
    invoice_number = Column(String(100), nullable=False)  # Format: "Faktura VAT P/43562821/0003/25"
    
    bills = relationship("GasBill", back_populates="invoice", cascade="all, delete-orphan")


class GasBill(Base):
    """
    Wygenerowane rachunki gazu dla lokali.
    
    Rozdzielenie kosztów:
    - "gora": 50% (0.5)
    - "dol": 25% (0.25)
    - "gabinet": 25% (0.25)
    """
    __tablename__ = "gas_bills"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    data = Column(String(7), nullable=False)
    local = Column(String(50), nullable=False)  # 'gora', 'gabinet', 'dol'
    
    invoice_id = Column(Integer, ForeignKey('gas_invoices.id'))
    local_id = Column(Integer, ForeignKey('locals.id'))
    
    # Rozdzielenie kosztów
    cost_share = Column(Float, nullable=False)  # 0.58 dla gora, 0.25 dla dol, 0.17 dla gabinet
    
    # Koszty rozdzielone proporcjonalnie z faktury (brutto)
    fuel_cost_gross = Column(Float, nullable=False)
    subscription_cost_gross = Column(Float, nullable=False)
    distribution_fixed_cost_gross = Column(Float, nullable=False)
    distribution_variable_cost_gross = Column(Float, nullable=False)
    
    # Sumy
    total_net_sum = Column(Float, nullable=False)    # Suma netto (proporcjonalna)
    total_gross_sum = Column(Float, nullable=False)  # Suma brutto (proporcjonalna)
    
    pdf_path = Column(String(200))
    
    invoice = relationship("GasInvoice", back_populates="bills")
    local_obj = relationship("Local", back_populates="gas_bills")

