"""
Manager do generowania rachunków łączonych (wszystkie media).
"""

from datetime import date, datetime
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from app.models.combined import CombinedBill
from app.models.water import Bill, Local
from app.models.gas import GasBill
from app.models.electricity import ElectricityBill


class CombinedBillingManager:
    """Zarządzanie rachunkami łączonymi (woda, gaz, prąd)."""
    
    def get_two_month_periods(self, db: Session) -> List[Tuple[str, str]]:
        """
        Zwraca listę dostępnych okresów dwumiesięcznych.
        Okresy są w formacie (YYYY-MM, YYYY-MM) - pierwszy i drugi miesiąc.
        
        Sprawdza, czy dla każdego okresu dwumiesięcznego są rachunki dla wszystkich trzech mediów
        w obu miesiącach dla wszystkich lokali.
        
        Returns:
            Lista tupli (period_start, period_end) gdzie każda tupla to 2 miesiące
        """
        # Pobierz wszystkie unikalne okresy z rachunków wody, gazu i prądu
        water_periods = set()
        gas_periods = set()
        electricity_periods = set()
        
        # Woda
        water_bills = db.query(Bill.data).distinct().all()
        for bill in water_bills:
            water_periods.add(bill.data)
        
        # Gaz
        gas_bills = db.query(GasBill.data).distinct().all()
        for bill in gas_bills:
            gas_periods.add(bill.data)
        
        # Prąd
        electricity_bills = db.query(ElectricityBill.data).distinct().all()
        for bill in electricity_bills:
            electricity_periods.add(bill.data)
        
        # Znajdź wszystkie możliwe okresy (suma wszystkich)
        all_periods = water_periods | gas_periods | electricity_periods
        sorted_periods = sorted(all_periods)
        
        two_month_periods = []
        locals_list = ['gora', 'dol', 'gabinet']
        
        # Sprawdź każdą parę kolejnych miesięcy
        for i in range(len(sorted_periods) - 1):
            period_start = sorted_periods[i]
            period_end = sorted_periods[i + 1]
            
            # Sprawdź czy to kolejne miesiące
            current = datetime.strptime(period_start, '%Y-%m')
            next_period = datetime.strptime(period_end, '%Y-%m')
            months_diff = (next_period.year - current.year) * 12 + (next_period.month - current.month)
            
            if months_diff != 1:
                continue  # Nie są kolejne miesiące
            
            # Sprawdź czy dla tego okresu dwumiesięcznego są rachunki dla wszystkich mediów i lokali
            # Wymagamy, aby dla każdego lokalu były rachunki dla wszystkich trzech mediów
            # (łącznie z obu miesięcy - niekoniecznie w każdym miesiącu osobno)
            has_all_media = True
            
            for local_name in locals_list:
                # Sprawdź wodę - czy są rachunki w którymkolwiek z dwóch miesięcy
                water_bills = db.query(Bill).filter(
                    Bill.data.in_([period_start, period_end]),
                    Bill.local == local_name
                ).all()
                
                # Sprawdź gaz - czy są rachunki w którymkolwiek z dwóch miesięcy
                gas_bills = db.query(GasBill).filter(
                    GasBill.data.in_([period_start, period_end]),
                    GasBill.local == local_name
                ).all()
                
                # Sprawdź prąd - czy są rachunki w którymkolwiek z dwóch miesięcy
                electricity_bills = db.query(ElectricityBill).filter(
                    ElectricityBill.data.in_([period_start, period_end]),
                    ElectricityBill.local == local_name
                ).all()
                
                # Wymagamy, aby były rachunki dla wszystkich trzech mediów (łącznie z obu miesięcy)
                if len(water_bills) == 0 or len(gas_bills) == 0 or len(electricity_bills) == 0:
                    has_all_media = False
                    break
            
            if has_all_media:
                two_month_periods.append((period_start, period_end))
        
        return two_month_periods
    
    def generate_bills_for_period(
        self,
        db: Session,
        period_start: str,
        period_end: str
    ) -> List[CombinedBill]:
        """
        Generuje rachunki łączone dla wszystkich lokali na dany okres dwumiesięczny.
        
        Args:
            db: Sesja bazy danych
            period_start: Pierwszy miesiąc okresu (YYYY-MM)
            period_end: Drugi miesiąc okresu (YYYY-MM)
        
        Returns:
            Lista wygenerowanych rachunków łączonych
        """
        locals_list = ['gora', 'dol', 'gabinet']
        bills = []
        
        for local_name in locals_list:
            # Pobierz rachunki dla każdego medium z obu miesięcy
            # Dla okresu dwumiesięcznego sumujemy koszty z obu miesięcy
            
            # Woda - pobierz rachunki z obu miesięcy
            water_bills = db.query(Bill).filter(
                Bill.data.in_([period_start, period_end]),
                Bill.local == local_name
            ).all()
            
            # Gaz - pobierz rachunki z obu miesięcy
            gas_bills = db.query(GasBill).filter(
                GasBill.data.in_([period_start, period_end]),
                GasBill.local == local_name
            ).all()
            
            # Prąd - pobierz rachunki z obu miesięcy
            electricity_bills = db.query(ElectricityBill).filter(
                ElectricityBill.data.in_([period_start, period_end]),
                ElectricityBill.local == local_name
            ).all()
            
            # Jeśli nie ma rachunków dla wszystkich mediów, pomiń ten lokal
            if not water_bills or not gas_bills or not electricity_bills:
                continue
            
            # Oblicz sumy z obu miesięcy
            total_net = 0.0
            total_gross = 0.0
            
            # Sumuj koszty wody
            for bill in water_bills:
                total_net += bill.net_sum
                total_gross += bill.gross_sum
            
            # Sumuj koszty gazu
            for bill in gas_bills:
                total_net += bill.total_net_sum
                total_gross += bill.total_gross_sum
            
            # Sumuj koszty prądu
            for bill in electricity_bills:
                total_net += bill.total_net_sum
                total_gross += bill.total_gross_sum
            
            # Użyj pierwszych rachunków jako referencji (dla relacji w bazie)
            water_bill = water_bills[0]
            gas_bill = gas_bills[0]
            electricity_bill = electricity_bills[0]
            
            # Pobierz lokal
            local_obj = db.query(Local).filter(Local.local == local_name).first()
            if not local_obj:
                continue
            
            # Sprawdź czy rachunek już istnieje
            existing = db.query(CombinedBill).filter(
                CombinedBill.period_start == period_start,
                CombinedBill.period_end == period_end,
                CombinedBill.local == local_name
            ).first()
            
            if existing:
                # Aktualizuj istniejący rachunek
                # Użyj pierwszych rachunków jako referencji
                existing.water_bill_id = water_bill.id
                existing.gas_bill_id = gas_bill.id
                existing.electricity_bill_id = electricity_bill.id
                existing.total_net_sum = round(total_net, 2)
                existing.total_gross_sum = round(total_gross, 2)
                existing.generated_date = date.today()
                bills.append(existing)
            else:
                # Utwórz nowy rachunek
                # Użyj pierwszych rachunków jako referencji (relacje w bazie)
                combined_bill = CombinedBill(
                    period_start=period_start,
                    period_end=period_end,
                    local=local_name,
                    water_bill_id=water_bill.id,
                    gas_bill_id=gas_bill.id,
                    electricity_bill_id=electricity_bill.id,
                    local_id=local_obj.id,
                    total_net_sum=round(total_net, 2),
                    total_gross_sum=round(total_gross, 2),
                    generated_date=date.today()
                )
                db.add(combined_bill)
                bills.append(combined_bill)
        
        db.commit()
        return bills

