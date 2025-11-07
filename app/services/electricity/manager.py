"""
Moduł zarządzania odczytami i rozliczaniem rachunków za prąd.
Oblicza koszty na podstawie faktur i dzieli proporcjonalnie między lokale.
"""

from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.models.electricity import ElectricityReading, ElectricityBill
from app.models.electricity_invoice import ElectricityInvoice
from app.models.water import Local
from app.services.electricity.calculator import (
    calculate_all_usage,
    get_previous_reading
)


class ElectricityBillingManager:
    """Zarządzanie odczytami i rozliczaniem rachunków za prąd."""
    
    def get_usage_for_period(
        self,
        db: Session,
        data: str
    ) -> Optional[Dict[str, Any]]:
        """
        Pobiera i oblicza zużycie dla danego okresu.
        
        Args:
            db: Sesja bazy danych
            data: Data w formacie 'YYYY-MM'
        
        Returns:
            Słownik z zużyciem dla wszystkich lokali lub None
        """
        current = db.query(ElectricityReading).filter(
            ElectricityReading.data == data
        ).first()
        
        if not current:
            return None
        
        previous = get_previous_reading(db, data)
        return calculate_all_usage(current, previous)
    
    def get_usage_for_local(
        self,
        db: Session,
        data: str,
        local_name: str
    ) -> Optional[float]:
        """
        Pobiera zużycie dla konkretnego lokalu w danym okresie.
        
        Args:
            db: Sesja bazy danych
            data: Data w formacie 'YYYY-MM'
            local_name: Nazwa lokalu ('gora', 'dol', 'gabinet')
        
        Returns:
            Zużycie w kWh lub None
        """
        usage_data = self.get_usage_for_period(db, data)
        if not usage_data:
            return None
        
        if local_name == 'gora':
            return usage_data['gora']['zuzycie_gora_lacznie']
        elif local_name == 'dol':
            return usage_data['dol']['zuzycie_dol_lacznie']
        elif local_name == 'gabinet':
            return usage_data['gabinet']['zuzycie_gabinet']
        else:
            return None
    
    def calculate_bill_costs(
        self,
        invoice: ElectricityInvoice,
        usage_data: Dict[str, Any],
        local_name: str,
        db: Session
    ) -> Dict[str, float]:
        """
        Oblicza koszty dla pojedynczego rachunku prądu.
        
        Args:
            invoice: Faktura prądu
            usage_data: Dane zużycia (ze calculate_all_usage)
            local_name: Nazwa lokalu ('gora', 'dol', 'gabinet')
            db: Sesja bazy danych
        
        Returns:
            Słownik z obliczonymi kosztami dla lokalu
        """
        # Pobierz zużycie dla lokalu z usage_data
        if local_name == 'gora':
            local_usage = usage_data['gora']['zuzycie_gora_lacznie']
        elif local_name == 'dol':
            local_usage = usage_data['dol']['zuzycie_dol_lacznie']
        elif local_name == 'gabinet':
            local_usage = usage_data['gabinet']['zuzycie_gabinet']
        else:
            local_usage = 0.0
        
        if local_usage is None or local_usage <= 0:
            return {
                'usage_kwh': 0.0,
                'energy_cost_gross': 0.0,
                'distribution_cost_gross': 0.0,
                'total_net_sum': 0.0,
                'total_gross_sum': 0.0
            }
        
        # Oblicz proporcję zużycia
        total_usage = usage_data['dom']['zuzycie_dom_lacznie']
        if total_usage <= 0:
            return {
                'usage_kwh': local_usage,
                'energy_cost_gross': 0.0,
                'distribution_cost_gross': 0.0,
                'total_net_sum': 0.0,
                'total_gross_sum': 0.0
            }
        
        usage_ratio = local_usage / total_usage
        
        # Rozdziel koszty proporcjonalnie
        energy_cost_gross = invoice.energy_value_gross * usage_ratio
        distribution_cost_gross = invoice.distribution_fees_gross * usage_ratio
        
        # Oblicz netto (zakładając ten sam VAT)
        vat_rate = invoice.vat_rate
        energy_cost_net = energy_cost_gross / (1 + vat_rate)
        distribution_cost_net = distribution_cost_gross / (1 + vat_rate)
        
        total_net_sum = energy_cost_net + distribution_cost_net
        total_gross_sum = energy_cost_gross + distribution_cost_gross
        
        return {
            'usage_kwh': local_usage,
            'energy_cost_gross': energy_cost_gross,
            'distribution_cost_gross': distribution_cost_gross,
            'total_net_sum': total_net_sum,
            'total_gross_sum': total_gross_sum
        }
    
    def generate_bills_for_period(
        self,
        db: Session,
        data: str
    ) -> list[ElectricityBill]:
        """
        Generuje rachunki dla wszystkich lokali w danym okresie.
        
        Args:
            db: Sesja bazy danych
            data: Data w formacie 'YYYY-MM'
        
        Returns:
            Lista wygenerowanych rachunków
        """
        # Pobierz fakturę dla okresu
        invoice = db.query(ElectricityInvoice).filter(
            ElectricityInvoice.data == data
        ).first()
        
        if not invoice:
            raise ValueError(f"Brak faktury dla okresu {data}")
        
        # Pobierz dane zużycia
        usage_data = self.get_usage_for_period(db, data)
        if not usage_data:
            raise ValueError(f"Brak odczytów dla okresu {data}")
        
        # Pobierz lokale
        locals = db.query(Local).all()
        bills = []
        
        for local in locals:
            # Oblicz koszty
            costs = self.calculate_bill_costs(invoice, usage_data, local.local, db)
            
            # Sprawdź czy rachunek już istnieje
            existing_bill = db.query(ElectricityBill).filter(
                ElectricityBill.data == data,
                ElectricityBill.local == local.local
            ).first()
            
            if existing_bill:
                # Aktualizuj istniejący
                existing_bill.usage_kwh = costs['usage_kwh']
                existing_bill.energy_cost_gross = costs['energy_cost_gross']
                existing_bill.distribution_cost_gross = costs['distribution_cost_gross']
                existing_bill.total_net_sum = costs['total_net_sum']
                existing_bill.total_gross_sum = costs['total_gross_sum']
                bills.append(existing_bill)
            else:
                # Utwórz nowy
                bill = ElectricityBill(
                    data=data,
                    local=local.local,
                    reading_id=None,  # TODO: powiązać z odczytem
                    invoice_id=invoice.id,
                    local_id=local.id,
                    usage_kwh=costs['usage_kwh'],
                    energy_cost_gross=costs['energy_cost_gross'],
                    distribution_cost_gross=costs['distribution_cost_gross'],
                    total_net_sum=costs['total_net_sum'],
                    total_gross_sum=costs['total_gross_sum']
                )
                db.add(bill)
                bills.append(bill)
        
        db.commit()
        return bills

