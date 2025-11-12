"""
Testy jednostkowe dla logiki obliczeń zużycia prądu.
Testuje wszystkie scenariusze: dwutaryfowe, jednotaryfowe, migracje.
"""

import pytest
from datetime import date
from app.models.electricity import ElectricityReading
from app.services.electricity.calculator import (
    calculate_dom_usage,
    calculate_dol_usage,
    calculate_gabinet_usage,
    calculate_gora_usage,
    calculate_all_usage,
    get_total_dom_reading,
    get_total_dol_reading
)


def create_reading(
    data: str,
    dom_single: bool = True,
    dom_reading: float = None,
    dom_I: float = None,
    dom_II: float = None,
    dol_single: bool = True,
    dol_reading: float = None,
    dol_I: float = None,
    dol_II: float = None,
    gabinet: float = 0.0
) -> ElectricityReading:
    """Pomocnicza funkcja do tworzenia odczytów testowych."""
    reading = ElectricityReading()
    reading.data = data
    reading.licznik_dom_jednotaryfowy = dom_single
    reading.odczyt_dom = dom_reading
    reading.odczyt_dom_I = dom_I
    reading.odczyt_dom_II = dom_II
    reading.licznik_dol_jednotaryfowy = dol_single
    reading.odczyt_dol = dol_reading
    reading.odczyt_dol_I = dol_I
    reading.odczyt_dol_II = dol_II
    reading.odczyt_gabinet = gabinet
    return reading


class TestGetTotalReadings:
    """Testy funkcji pomocniczych get_total_*."""
    
    def test_get_total_dom_reading_single(self):
        """Test łącznego odczytu DOM dla jednotaryfowego."""
        reading = create_reading("2025-01", dom_single=True, dom_reading=1000.0)
        assert get_total_dom_reading(reading) == 1000.0
    
    def test_get_total_dom_reading_dual(self):
        """Test łącznego odczytu DOM dla dwutaryfowego."""
        reading = create_reading("2025-01", dom_single=False, dom_I=1000.0, dom_II=2000.0)
        assert get_total_dom_reading(reading) == 3000.0
    
    def test_get_total_dol_reading_single(self):
        """Test łącznego odczytu DÓŁ dla jednotaryfowego."""
        reading = create_reading("2025-01", dol_single=True, dol_reading=500.0)
        assert get_total_dol_reading(reading) == 500.0
    
    def test_get_total_dol_reading_dual(self):
        """Test łącznego odczytu DÓŁ dla dwutaryfowego."""
        reading = create_reading("2025-01", dol_single=False, dol_I=300.0, dol_II=600.0)
        assert get_total_dol_reading(reading) == 900.0


class TestCalculateDomUsage:
    """Testy obliczania zużycia DOM."""
    
    def test_dom_no_previous(self):
        """Test: brak poprzedniego odczytu."""
        current = create_reading("2025-01", dom_single=True, dom_reading=1000.0)
        result = calculate_dom_usage(current, None)
        assert result['zuzycie_dom_I'] is None
        assert result['zuzycie_dom_II'] is None
        assert result['zuzycie_dom_lacznie'] == 0.0
    
    def test_dom_both_dual_tariff(self):
        """Scenariusz A: Oba okresy dwutaryfowe."""
        previous = create_reading("2024-12", dom_single=False, dom_I=1000.0, dom_II=2000.0)
        current = create_reading("2025-01", dom_single=False, dom_I=1100.0, dom_II=2200.0)
        result = calculate_dom_usage(current, previous)
        assert result['zuzycie_dom_I'] == 100.0
        assert result['zuzycie_dom_II'] == 200.0
        assert result['zuzycie_dom_lacznie'] == 300.0
    
    def test_dom_current_single_previous_dual(self):
        """Scenariusz B: Aktualny jednotaryfowy, poprzedni dwutaryfowy."""
        previous = create_reading("2024-12", dom_single=False, dom_I=1000.0, dom_II=2000.0)
        current = create_reading("2025-01", dom_single=True, dom_reading=3300.0)
        result = calculate_dom_usage(current, previous)
        assert result['zuzycie_dom_I'] is None
        assert result['zuzycie_dom_II'] is None
        assert result['zuzycie_dom_lacznie'] == 300.0  # 3300 - 3000
    
    def test_dom_both_single_tariff(self):
        """Scenariusz C: Oba okresy jednotaryfowe."""
        previous = create_reading("2024-12", dom_single=True, dom_reading=3000.0)
        current = create_reading("2025-01", dom_single=True, dom_reading=3300.0)
        result = calculate_dom_usage(current, previous)
        assert result['zuzycie_dom_I'] is None
        assert result['zuzycie_dom_II'] is None
        assert result['zuzycie_dom_lacznie'] == 300.0
    
    def test_dom_current_dual_previous_single(self):
        """Scenariusz D: Aktualny dwutaryfowy, poprzedni jednotaryfowy (rzadki przypadek)."""
        previous = create_reading("2024-12", dom_single=True, dom_reading=3000.0)
        current = create_reading("2025-01", dom_single=False, dom_I=1100.0, dom_II=2200.0)
        result = calculate_dom_usage(current, previous)
        # Łączne: 3300 - 3000 = 300
        # Proporcje: I=1100/3300=0.333, II=2200/3300=0.667
        assert abs(result['zuzycie_dom_I'] - 100.0) < 0.01  # 300 * 0.333
        assert abs(result['zuzycie_dom_II'] - 200.0) < 0.01  # 300 * 0.667
        assert abs(result['zuzycie_dom_lacznie'] - 300.0) < 0.01


class TestCalculateDolUsage:
    """Testy obliczania zużycia DÓŁ."""
    
    def test_dol_no_previous(self):
        """Test: brak poprzedniego odczytu."""
        current = create_reading("2025-01", dol_single=True, dol_reading=500.0)
        result = calculate_dol_usage(current, None)
        assert result['zuzycie_dol'] is None
        assert result['zuzycie_dol_I'] is None
        assert result['zuzycie_dol_II'] is None
        assert result['zuzycie_dol_lacznie'] == 0.0
    
    def test_dol_both_dual_tariff(self):
        """Oba okresy dwutaryfowe."""
        previous = create_reading("2024-12", dol_single=False, dol_I=300.0, dol_II=600.0)
        current = create_reading("2025-01", dol_single=False, dol_I=350.0, dol_II=700.0)
        result = calculate_dol_usage(current, previous)
        assert result['zuzycie_dol'] is None
        assert result['zuzycie_dol_I'] == 50.0
        assert result['zuzycie_dol_II'] == 100.0
        assert result['zuzycie_dol_lacznie'] == 150.0
    
    def test_dol_both_single_tariff(self):
        """Oba okresy jednotaryfowe."""
        previous = create_reading("2024-12", dol_single=True, dol_reading=900.0)
        current = create_reading("2025-01", dol_single=True, dol_reading=1050.0)
        result = calculate_dol_usage(current, previous)
        assert result['zuzycie_dol'] == 150.0
        assert result['zuzycie_dol_I'] is None
        assert result['zuzycie_dol_II'] is None
        assert result['zuzycie_dol_lacznie'] == 150.0
    
    def test_dol_current_single_previous_dual(self):
        """Poprzedni dwutaryfowy, aktualny jednotaryfowy."""
        previous = create_reading("2024-12", dol_single=False, dol_I=300.0, dol_II=600.0)
        current = create_reading("2025-01", dol_single=True, dol_reading=1050.0)
        result = calculate_dol_usage(current, previous)
        assert result['zuzycie_dol'] == 150.0  # 1050 - 900
        assert result['zuzycie_dol_I'] is None
        assert result['zuzycie_dol_II'] is None
        assert result['zuzycie_dol_lacznie'] == 150.0
    
    def test_dol_current_dual_previous_single(self):
        """Aktualny dwutaryfowy, poprzedni jednotaryfowy."""
        previous = create_reading("2024-12", dol_single=True, dol_reading=900.0)
        current = create_reading("2025-01", dol_single=False, dol_I=350.0, dol_II=700.0)
        result = calculate_dol_usage(current, previous)
        # Łączne: 1050 - 900 = 150
        # Proporcje: I=350/1050=0.333, II=700/1050=0.667
        assert result['zuzycie_dol'] is None
        assert abs(result['zuzycie_dol_I'] - 50.0) < 0.01
        assert abs(result['zuzycie_dol_II'] - 100.0) < 0.01
        assert abs(result['zuzycie_dol_lacznie'] - 150.0) < 0.01


class TestCalculateGabinetUsage:
    """Testy obliczania zużycia GABINET."""
    
    def test_gabinet_no_previous(self):
        """Test: brak poprzedniego odczytu."""
        current = create_reading("2025-01", gabinet=100.0)
        result = calculate_gabinet_usage(current, None, dom_is_dual_tariff=False)
        assert result['zuzycie_gabinet'] == 0.0
        assert result['zuzycie_gabinet_dzienna'] is None
        assert result['zuzycie_gabinet_nocna'] is None
    
    def test_gabinet_normal_single_tariff(self):
        """Normalne obliczenie zużycia GABINET (główny licznik jednotaryfowy)."""
        previous = create_reading("2024-12", gabinet=100.0)
        current = create_reading("2025-01", gabinet=150.0)
        result = calculate_gabinet_usage(current, previous, dom_is_dual_tariff=False)
        assert result['zuzycie_gabinet'] == 50.0
        assert result['zuzycie_gabinet_dzienna'] is None
        assert result['zuzycie_gabinet_nocna'] is None
    
    def test_gabinet_with_approximation(self):
        """Obliczenie zużycia GABINET z aproksymacją 70%/30% (główny licznik dwutaryfowy)."""
        previous = create_reading("2024-12", gabinet=100.0)
        current = create_reading("2025-01", gabinet=150.0)
        result = calculate_gabinet_usage(current, previous, dom_is_dual_tariff=True)
        assert result['zuzycie_gabinet'] == 50.0
        assert result['zuzycie_gabinet_dzienna'] == 35.0  # 50 * 0.7
        assert result['zuzycie_gabinet_nocna'] == 15.0  # 50 * 0.3


class TestCalculateGoraUsage:
    """Testy obliczania zużycia GÓRA."""
    
    def test_gora_both_dual_tariff(self):
        """Scenariusz A: Oba dwutaryfowe - rozdzielone taryfy.
        
        W nowej strukturze: DÓŁ zawiera GABINET, więc GÓRA = DOM - DÓŁ.
        """
        dom_usage = {
            'zuzycie_dom_I': 100.0,
            'zuzycie_dom_II': 200.0,
            'zuzycie_dom_lacznie': 300.0
        }
        dol_usage = {
            'zuzycie_dol': None,
            'zuzycie_dol_I': 50.0,
            'zuzycie_dol_II': 100.0,
            'zuzycie_dol_lacznie': 150.0  # Zawiera już GABINET
        }
        gabinet_usage = 50.0  # Parametr zachowany dla kompatybilności, nie używany
        
        result = calculate_gora_usage(dom_usage, dol_usage, gabinet_usage)
        assert result['zuzycie_gora_I'] == 50.0  # 100 - 50
        assert result['zuzycie_gora_II'] == 100.0  # 200 - 100
        assert result['zuzycie_gora_lacznie'] == 150.0  # 50 + 100 (nie odejmujemy GABINET)
    
    def test_gora_single_tariff(self):
        """Scenariusz B/C: Tylko łączne zużycie.
        
        W nowej strukturze: DÓŁ zawiera GABINET, więc GÓRA = DOM - DÓŁ.
        """
        dom_usage = {
            'zuzycie_dom_I': None,
            'zuzycie_dom_II': None,
            'zuzycie_dom_lacznie': 300.0
        }
        dol_usage = {
            'zuzycie_dol': 150.0,
            'zuzycie_dol_I': None,
            'zuzycie_dol_II': None,
            'zuzycie_dol_lacznie': 150.0  # Zawiera już GABINET
        }
        gabinet_usage = 50.0  # Parametr zachowany dla kompatybilności, nie używany
        
        result = calculate_gora_usage(dom_usage, dol_usage, gabinet_usage)
        assert result['zuzycie_gora_I'] is None
        assert result['zuzycie_gora_II'] is None
        assert result['zuzycie_gora_lacznie'] == 150.0  # 300 - 150 (nie odejmujemy GABINET)


class TestCalculateAllUsage:
    """Testy kompleksowej funkcji calculate_all_usage."""
    
    def test_all_usage_complete_scenario(self):
        """Kompletny scenariusz: wszystkie typy zużycia."""
        previous = create_reading(
            "2024-12",
            dom_single=False, dom_I=1000.0, dom_II=2000.0,
            dol_single=False, dol_I=300.0, dol_II=600.0,
            gabinet=100.0
        )
        current = create_reading(
            "2025-01",
            dom_single=False, dom_I=1100.0, dom_II=2200.0,
            dol_single=False, dol_I=350.0, dol_II=700.0,
            gabinet=150.0
        )
        
        result = calculate_all_usage(current, previous)
        
        # Sprawdź strukturę
        assert result['data'] == "2025-01"
        assert 'dom' in result
        assert 'dol' in result
        assert 'gabinet' in result
        assert 'gora' in result
        
        # Sprawdź wartości DOM
        assert result['dom']['zuzycie_dom_I'] == 100.0
        assert result['dom']['zuzycie_dom_II'] == 200.0
        assert result['dom']['zuzycie_dom_lacznie'] == 300.0
        
        # Sprawdź wartości DÓŁ (z odczytu - zawiera GABINET)
        # DÓŁ z odczytu: I=50, II=100, łącznie=150
        # GABINET: 50 (z aproksymacją: 35 dzienna, 15 nocna)
        # Mikołaj (DOL) = DÓŁ - GABINET: I=50-35=15, II=100-15=85, łącznie=100
        assert result['dol']['zuzycie_dol_I'] == 15.0  # 50 - 35
        assert result['dol']['zuzycie_dol_II'] == 85.0  # 100 - 15
        assert result['dol']['zuzycie_dol_lacznie'] == 100.0  # 150 - 50
        
        # Sprawdź wartości GABINET (z aproksymacją 70%/30%)
        assert result['gabinet']['zuzycie_gabinet'] == 50.0
        assert result['gabinet']['zuzycie_gabinet_dzienna'] == 35.0  # 50 * 0.7
        assert result['gabinet']['zuzycie_gabinet_nocna'] == 15.0  # 50 * 0.3
        
        # Sprawdź wartości GÓRA
        # W nowej strukturze: GÓRA = DOM - DÓŁ (DÓŁ zawiera GABINET)
        assert result['gora']['zuzycie_gora_I'] == 50.0  # 100 - 50
        assert result['gora']['zuzycie_gora_II'] == 100.0  # 200 - 100
        assert result['gora']['zuzycie_gora_lacznie'] == 150.0  # 300 - 150 (nie odejmujemy GABINET)
    
    def test_all_usage_no_previous(self):
        """Test: brak poprzedniego odczytu."""
        current = create_reading("2025-01", dom_single=True, dom_reading=1000.0, gabinet=100.0)
        result = calculate_all_usage(current, None)
        
        assert result['dom']['zuzycie_dom_lacznie'] == 0.0
        assert result['dol']['zuzycie_dol_lacznie'] == 0.0
        assert result['gabinet']['zuzycie_gabinet'] == 0.0
        assert result['gabinet']['zuzycie_gabinet_dzienna'] is None
        assert result['gabinet']['zuzycie_gabinet_nocna'] is None
        assert result['gora']['zuzycie_gora_lacznie'] == 0.0
    
    def test_all_usage_migration_scenario(self):
        """Scenariusz migracji: poprzedni dwutaryfowy, aktualny jednotaryfowy."""
        previous = create_reading(
            "2024-12",
            dom_single=False, dom_I=1000.0, dom_II=2000.0,
            dol_single=False, dol_I=300.0, dol_II=600.0,
            gabinet=100.0
        )
        current = create_reading(
            "2025-01",
            dom_single=True, dom_reading=3300.0,
            dol_single=True, dol_reading=1050.0,
            gabinet=150.0
        )
        
        result = calculate_all_usage(current, previous)
        
        # DOM: 3300 - 3000 = 300
        assert result['dom']['zuzycie_dom_lacznie'] == 300.0
        
        # DÓŁ z odczytu: 1050 - 900 = 150 (zawiera GABINET)
        # GABINET: 150 - 100 = 50
        # Mikołaj (DOL): 150 - 50 = 100
        assert result['dol']['zuzycie_dol_lacznie'] == 100.0  # DÓŁ - GABINET
        
        # GABINET: 150 - 100 = 50 (jednotaryfowy, więc bez aproksymacji)
        assert result['gabinet']['zuzycie_gabinet'] == 50.0
        assert result['gabinet']['zuzycie_gabinet_dzienna'] is None  # Główny licznik jednotaryfowy
        assert result['gabinet']['zuzycie_gabinet_nocna'] is None
        
        # GÓRA: 300 - 150 = 150 (w nowej strukturze DÓŁ zawiera GABINET)
        assert result['gora']['zuzycie_gora_lacznie'] == 150.0

