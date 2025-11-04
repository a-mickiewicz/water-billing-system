"""
Modele bazy danych - eksport wszystkich modeli.
"""

from app.models.water import Local, Reading, Invoice, Bill
from app.models.gas import GasInvoice, GasBill

__all__ = [
    "Local",
    "Reading", 
    "Invoice",
    "Bill",
    "GasInvoice",
    "GasBill"
]

