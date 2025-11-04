"""
Moduł zarządzania licznikami i rozliczaniem rachunków za gaz.
Oblicza koszty na podstawie faktur i dzieli proporcjonalnie między lokale.
"""

from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.models.gas import GasInvoice, GasBill
from app.models.water import Local


class GasBillingManager:
    """Zarządzanie licznikami i rozliczaniem rachunków za gaz."""
    
    def calculate_bill_costs(
        self,
        invoice: GasInvoice,
        local_name: str
    ) -> dict:
        """
        Oblicza koszty dla pojedynczego rachunku gazu.
        
        Algorytm (tak jak w generatorze PDF):
        1. Używamy total_gross_sum z faktury (bez odsetek) jako podstawy
        2. Dzielimy proporcjonalnie według udziału lokalu
        3. Obliczamy wartości szczegółowe proporcjonalnie z faktury (jeśli są dostępne)
           lub używamy tylko total_gross_sum
        
        Args:
            invoice: Faktura gazu
            local_name: Nazwa lokalu ('gora', 'dol', 'gabinet')
        
        Returns:
            Słownik z obliczonymi kosztami dla lokalu
        """
        # Proporcje dla lokali
        if local_name == 'gora':
            share = 0.58  # 58%
        elif local_name == 'dol':
            share = 0.25  # 25%
        elif local_name == 'gabinet':
            share = 0.17  # 17%
        else:
            raise ValueError(f"Nieznany lokal: {local_name}")
        
        # Oblicz kwotę brutto bez odsetek (tak jak w generatorze PDF)
        house_gross_without_interest = invoice.total_gross_sum - invoice.late_payment_interest
        local_gross_base = house_gross_without_interest * share
        
        # Jeśli wartości szczegółowe w fakturze są dostępne (nie są 0), użyj ich
        # W przeciwnym razie rozdziel proporcjonalnie z total_gross_sum
        if (invoice.fuel_value_gross > 0 or invoice.subscription_value_gross > 0 or 
            invoice.distribution_fixed_value_gross > 0 or invoice.distribution_variable_value_gross > 0):
            # Użyj wartości szczegółowych z faktury
            fuel_cost_gross = invoice.fuel_value_gross * share
            subscription_cost_gross = invoice.subscription_value_gross * share
            distribution_fixed_cost_gross = invoice.distribution_fixed_value_gross * share
            distribution_variable_cost_gross = invoice.distribution_variable_value_gross * share
        else:
            # Jeśli wartości szczegółowe są 0, rozdziel total_gross_sum proporcjonalnie
            # Używamy proporcji z całkowitej kwoty brutto (bez odsetek)
            # Dla uproszczenia dzielimy równo między wszystkie kategorie
            fuel_cost_gross = local_gross_base * 0.25  # 25% dla paliwa
            subscription_cost_gross = local_gross_base * 0.25  # 25% dla abonamentu
            distribution_fixed_cost_gross = local_gross_base * 0.25  # 25% dla dystrybucji stałej
            distribution_variable_cost_gross = local_gross_base * 0.25  # 25% dla dystrybucji zmiennej
        
        # Suma brutto dla lokalu (powinna być równa local_gross_base)
        total_gross = local_gross_base
        
        # Suma netto (używamy VAT rate z faktury)
        total_net = total_gross / (1 + invoice.vat_rate)
        
        return {
            'cost_share': share,
            'fuel_cost_gross': fuel_cost_gross,
            'subscription_cost_gross': subscription_cost_gross,
            'distribution_fixed_cost_gross': distribution_fixed_cost_gross,
            'distribution_variable_cost_gross': distribution_variable_cost_gross,
            'total_net_sum': total_net,
            'total_gross_sum': total_gross
        }
    
    def generate_bills_for_period(self, db: Session, period: str) -> list[GasBill]:
        """
        Generuje rachunki gazu dla wszystkich lokali na dany okres.
        
        Algorytm:
        1. Pobierz WSZYSTKIE faktury dla okresu (może być wiele)
        2. Dla każdej faktury i każdego lokalu:
           - Oblicz proporcjonalne koszty (58%/25%/17%)
           - Utwórz rachunek
        3. Jeśli jest wiele faktur, sumuj koszty dla każdego lokalu
        
        UWAGA: Wszystkie dane są w fakturze - nie ma osobnych odczytów.
        Używamy bezpośrednio kosztów brutto z faktury.
        
        Args:
            db: Sesja bazy danych
            period: Okres rozliczeniowy w formacie 'YYYY-MM'
        
        Returns:
            Lista wygenerowanych rachunków
        """
        # 1. Pobierz wszystkie faktury dla okresu
        invoices = db.query(GasInvoice).filter(GasInvoice.data == period).all()
        if not invoices:
            raise ValueError(f"Brak faktur dla okresu {period}")
        
        # 3. Dla każdego lokalu i każdej faktury oblicz koszty
        locals_list = ['gora', 'dol', 'gabinet']
        bills = []
        
        for local_name in locals_list:
            # Sumuj koszty ze wszystkich faktur dla tego lokalu
            total_fuel_gross = 0
            total_subscription_gross = 0
            total_dist_fixed_gross = 0
            total_dist_variable_gross = 0
            
            for invoice in invoices:
                costs = self.calculate_bill_costs(invoice, local_name)
                total_fuel_gross += costs['fuel_cost_gross']
                total_subscription_gross += costs['subscription_cost_gross']
                total_dist_fixed_gross += costs['distribution_fixed_cost_gross']
                total_dist_variable_gross += costs['distribution_variable_cost_gross']
            
            # Suma brutto bazowa (bez odsetek) - tak jak w generatorze PDF
            total_gross_base = (total_fuel_gross + total_subscription_gross + 
                              total_dist_fixed_gross + total_dist_variable_gross)
            
            # Suma netto bazowa
            # Musimy użyć VAT rate z faktury, nie hardkodowanego 1.23
            invoice_vat_rate = invoices[0].vat_rate if invoices else 0.23
            total_net_base = total_gross_base / (1 + invoice_vat_rate)
            
            # Oblicz ostateczną kwotę brutto (z uwzględnieniem odsetek dla "gora")
            # Tak samo jak w generatorze PDF
            local_gross_sum = total_gross_base
            local_net_sum = total_net_base
            local_vat = local_net_sum * invoice_vat_rate
            
            # Dla lokalu "gora" dodajemy odsetki za spóźnienie
            if local_name == 'gora' and invoices[0].late_payment_interest > 0:
                interest_net = invoices[0].late_payment_interest / (1 + invoice_vat_rate)
                local_net_sum += interest_net
                local_vat = local_net_sum * invoice_vat_rate
                local_gross_sum = local_net_sum + local_vat
            
            # Utwórz rachunek
            local_obj = db.query(Local).filter(Local.local == local_name).first()
            if not local_obj:
                raise ValueError(f"Brak lokalizacji '{local_name}' w bazie")
            
            bill = GasBill(
                data=period,
                local=local_name,
                invoice_id=invoices[0].id,  # Pierwsza faktura
                local_id=local_obj.id,
                cost_share=0.58 if local_name == 'gora' else (0.25 if local_name == 'dol' else 0.17),
                fuel_cost_gross=round(total_fuel_gross, 2),
                subscription_cost_gross=round(total_subscription_gross, 2),
                distribution_fixed_cost_gross=round(total_dist_fixed_gross, 2),
                distribution_variable_cost_gross=round(total_dist_variable_gross, 2),
                total_net_sum=round(local_net_sum, 2),  # Z uwzględnieniem odsetek dla gora
                total_gross_sum=round(local_gross_sum, 2)  # Ostateczna kwota brutto do zapłaty
            )
            
            db.add(bill)
            bills.append(bill)
        
        db.commit()
        
        return bills

