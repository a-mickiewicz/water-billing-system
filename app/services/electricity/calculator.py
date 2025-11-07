"""
Logika obliczeń zużycia prądu dla lokali.

Obsługuje:
- Liczniki dwutaryfowe (I, II) i jednotaryfowe
- Migrację między typami liczników
- Obliczanie zużycia dla DOM, DÓŁ, GABINET i GÓRA
"""

from typing import Dict, Optional, Any
from sqlalchemy.orm import Session
from app.models.electricity import ElectricityReading


def get_previous_reading(db: Session, current_data: str) -> Optional[ElectricityReading]:
    """
    Pobiera poprzedni odczyt (najnowszy przed current_data).
    
    Args:
        db: Sesja bazy danych
        current_data: Data w formacie 'YYYY-MM'
    
    Returns:
        Poprzedni odczyt lub None jeśli nie istnieje
    """
    # Sortowanie po dacie, pobranie poprzedniego
    previous = db.query(ElectricityReading).filter(
        ElectricityReading.data < current_data
    ).order_by(ElectricityReading.data.desc()).first()
    
    return previous


def get_total_dom_reading(reading: ElectricityReading) -> float:
    """
    Zwraca łączny odczyt licznika głównego DOM.
    Dla dwutaryfowego: I + II
    Dla jednotaryfowego: po prostu odczyt_dom
    
    Args:
        reading: Odczyt licznika
    
    Returns:
        Łączny odczyt
    """
    if reading.licznik_dom_jednotaryfowy:
        return reading.odczyt_dom
    else:
        return reading.odczyt_dom_I + reading.odczyt_dom_II


def get_total_dol_reading(reading: ElectricityReading) -> float:
    """
    Zwraca łączny odczyt podlicznika DÓŁ.
    
    Args:
        reading: Odczyt licznika
    
    Returns:
        Łączny odczyt
    """
    if reading.licznik_dol_jednotaryfowy:
        return reading.odczyt_dol
    else:
        return reading.odczyt_dol_I + reading.odczyt_dol_II


def calculate_dom_usage(
    current: ElectricityReading,
    previous: Optional[ElectricityReading]
) -> Dict[str, Optional[float]]:
    """
    Oblicza zużycie dla całego domu.
    
    Args:
        current: Aktualny odczyt
        previous: Poprzedni odczyt (może być None)
    
    Returns:
        Słownik z zużyciem:
        {
            'zuzycie_dom_I': float | None,
            'zuzycie_dom_II': float | None,
            'zuzycie_dom_lacznie': float
        }
    """
    if previous is None:
        return {
            'zuzycie_dom_I': None,
            'zuzycie_dom_II': None,
            'zuzycie_dom_lacznie': 0.0
        }
    
    # SCENARIUSZ A: Oba dwutaryfowe
    if not current.licznik_dom_jednotaryfowy and not previous.licznik_dom_jednotaryfowy:
        zuzycie_I = current.odczyt_dom_I - previous.odczyt_dom_I
        zuzycie_II = current.odczyt_dom_II - previous.odczyt_dom_II
        return {
            'zuzycie_dom_I': zuzycie_I,
            'zuzycie_dom_II': zuzycie_II,
            'zuzycie_dom_lacznie': zuzycie_I + zuzycie_II
        }
    
    # SCENARIUSZ B: Aktualny jednotaryfowy, poprzedni dwutaryfowy
    if current.licznik_dom_jednotaryfowy and not previous.licznik_dom_jednotaryfowy:
        poprzedni_lacznie = previous.odczyt_dom_I + previous.odczyt_dom_II
        zuzycie_lacznie = current.odczyt_dom - poprzedni_lacznie
        return {
            'zuzycie_dom_I': None,
            'zuzycie_dom_II': None,
            'zuzycie_dom_lacznie': zuzycie_lacznie
        }
    
    # SCENARIUSZ C: Oba jednotaryfowe
    if current.licznik_dom_jednotaryfowy and previous.licznik_dom_jednotaryfowy:
        zuzycie_lacznie = current.odczyt_dom - previous.odczyt_dom
        return {
            'zuzycie_dom_I': None,
            'zuzycie_dom_II': None,
            'zuzycie_dom_lacznie': zuzycie_lacznie
        }
    
    # SCENARIUSZ D: Aktualny dwutaryfowy, poprzedni jednotaryfowy (rzadki przypadek)
    # Traktujemy poprzedni jako "łączny" i rozdzielamy proporcjonalnie
    if not current.licznik_dom_jednotaryfowy and previous.licznik_dom_jednotaryfowy:
        poprzedni_lacznie = previous.odczyt_dom
        aktualny_lacznie = current.odczyt_dom_I + current.odczyt_dom_II
        zuzycie_lacznie = aktualny_lacznie - poprzedni_lacznie
        
        # Proporcjonalny podział (można użyć innych metod)
        ratio_I = current.odczyt_dom_I / aktualny_lacznie if aktualny_lacznie > 0 else 0.5
        ratio_II = current.odczyt_dom_II / aktualny_lacznie if aktualny_lacznie > 0 else 0.5
        
        return {
            'zuzycie_dom_I': zuzycie_lacznie * ratio_I,
            'zuzycie_dom_II': zuzycie_lacznie * ratio_II,
            'zuzycie_dom_lacznie': zuzycie_lacznie
        }
    
    return {
        'zuzycie_dom_I': None,
        'zuzycie_dom_II': None,
        'zuzycie_dom_lacznie': 0.0
    }


def calculate_dol_usage(
    current: ElectricityReading,
    previous: Optional[ElectricityReading]
) -> Dict[str, Optional[float]]:
    """
    Oblicza zużycie dla podlicznika DÓŁ.
    
    Args:
        current: Aktualny odczyt
        previous: Poprzedni odczyt (może być None)
    
    Returns:
        Słownik z zużyciem:
        {
            'zuzycie_dol': float | None,
            'zuzycie_dol_I': float | None,
            'zuzycie_dol_II': float | None,
            'zuzycie_dol_lacznie': float
        }
    """
    if previous is None:
        return {
            'zuzycie_dol': None,
            'zuzycie_dol_I': None,
            'zuzycie_dol_II': None,
            'zuzycie_dol_lacznie': 0.0
        }
    
    # Oba dwutaryfowe
    if not current.licznik_dol_jednotaryfowy and not previous.licznik_dol_jednotaryfowy:
        zuzycie_I = current.odczyt_dol_I - previous.odczyt_dol_I
        zuzycie_II = current.odczyt_dol_II - previous.odczyt_dol_II
        return {
            'zuzycie_dol': None,
            'zuzycie_dol_I': zuzycie_I,
            'zuzycie_dol_II': zuzycie_II,
            'zuzycie_dol_lacznie': zuzycie_I + zuzycie_II
        }
    
    # Oba jednotaryfowe
    if current.licznik_dol_jednotaryfowy and previous.licznik_dol_jednotaryfowy:
        zuzycie = current.odczyt_dol - previous.odczyt_dol
        return {
            'zuzycie_dol': zuzycie,
            'zuzycie_dol_I': None,
            'zuzycie_dol_II': None,
            'zuzycie_dol_lacznie': zuzycie
        }
    
    # Poprzedni dwutaryfowy, aktualny jednotaryfowy
    if current.licznik_dol_jednotaryfowy and not previous.licznik_dol_jednotaryfowy:
        poprzedni_lacznie = previous.odczyt_dol_I + previous.odczyt_dol_II
        zuzycie = current.odczyt_dol - poprzedni_lacznie
        return {
            'zuzycie_dol': zuzycie,
            'zuzycie_dol_I': None,
            'zuzycie_dol_II': None,
            'zuzycie_dol_lacznie': zuzycie
        }
    
    # Aktualny dwutaryfowy, poprzedni jednotaryfowy (rzadki przypadek)
    if not current.licznik_dol_jednotaryfowy and previous.licznik_dol_jednotaryfowy:
        poprzedni_lacznie = previous.odczyt_dol
        aktualny_lacznie = current.odczyt_dol_I + current.odczyt_dol_II
        zuzycie_lacznie = aktualny_lacznie - poprzedni_lacznie
        
        # Proporcjonalny podział
        ratio_I = current.odczyt_dol_I / aktualny_lacznie if aktualny_lacznie > 0 else 0.5
        ratio_II = current.odczyt_dol_II / aktualny_lacznie if aktualny_lacznie > 0 else 0.5
        
        return {
            'zuzycie_dol': None,
            'zuzycie_dol_I': zuzycie_lacznie * ratio_I,
            'zuzycie_dol_II': zuzycie_lacznie * ratio_II,
            'zuzycie_dol_lacznie': zuzycie_lacznie
        }
    
    return {
        'zuzycie_dol': None,
        'zuzycie_dol_I': None,
        'zuzycie_dol_II': None,
        'zuzycie_dol_lacznie': 0.0
    }


def calculate_gabinet_usage(
    current: ElectricityReading,
    previous: Optional[ElectricityReading]
) -> float:
    """
    Oblicza zużycie dla podlicznika GABINET.
    Zawsze jednotaryfowy.
    
    Args:
        current: Aktualny odczyt
        previous: Poprzedni odczyt (może być None)
    
    Returns:
        Zużycie w kWh
    """
    if previous is None:
        return 0.0
    return current.odczyt_gabinet - previous.odczyt_gabinet


def calculate_gora_usage(
    dom_usage: Dict[str, Optional[float]],
    dol_usage: Dict[str, Optional[float]],
    gabinet_usage: float
) -> Dict[str, Optional[float]]:
    """
    Oblicza zużycie dla GÓRA (brak licznika, obliczane).
    GÓRA = DOM - (DÓŁ + GABINET)
    
    Args:
        dom_usage: Zużycie DOM (ze calculate_dom_usage)
        dol_usage: Zużycie DÓŁ (ze calculate_dol_usage)
        gabinet_usage: Zużycie GABINET
    
    Returns:
        Słownik z zużyciem:
        {
            'zuzycie_gora_I': float | None,
            'zuzycie_gora_II': float | None,
            'zuzycie_gora_lacznie': float
        }
    """
    # Jeśli mamy rozdzielone taryfy (oba dwutaryfowe)
    if dom_usage['zuzycie_dom_I'] is not None and dol_usage['zuzycie_dol_I'] is not None:
        zuzycie_I = dom_usage['zuzycie_dom_I'] - dol_usage['zuzycie_dol_I']
        zuzycie_II = dom_usage['zuzycie_dom_II'] - dol_usage['zuzycie_dol_II']
        # GÓRA łącznie = suma taryf (GABINET jest osobnym podlicznikiem, nie częścią DÓŁ)
        zuzycie_lacznie = zuzycie_I + zuzycie_II
        return {
            'zuzycie_gora_I': zuzycie_I,
            'zuzycie_gora_II': zuzycie_II,
            'zuzycie_gora_lacznie': zuzycie_lacznie
        }
    
    # Jeśli mamy tylko łączne zużycie
    zuzycie_lacznie = dom_usage['zuzycie_dom_lacznie'] - dol_usage['zuzycie_dol_lacznie'] - gabinet_usage
    return {
        'zuzycie_gora_I': None,
        'zuzycie_gora_II': None,
        'zuzycie_gora_lacznie': zuzycie_lacznie
    }


def calculate_all_usage(
    current: ElectricityReading,
    previous: Optional[ElectricityReading]
) -> Dict[str, Any]:
    """
    Oblicza wszystkie zużycia dla danego okresu.
    
    Args:
        current: Aktualny odczyt
        previous: Poprzedni odczyt (może być None)
    
    Returns:
        Kompleksowy słownik z wszystkimi wartościami:
        {
            'data': str,
            'dom': {...},
            'dol': {...},
            'gabinet': {'zuzycie_gabinet': float},
            'gora': {...}
        }
    """
    # 1. Zużycie DOM
    dom_usage = calculate_dom_usage(current, previous)
    
    # 2. Zużycie DÓŁ
    dol_usage = calculate_dol_usage(current, previous)
    
    # 3. Zużycie GABINET
    gabinet_usage = calculate_gabinet_usage(current, previous)
    
    # 4. Zużycie GÓRA (obliczane)
    gora_usage = calculate_gora_usage(dom_usage, dol_usage, gabinet_usage)
    
    return {
        'data': current.data,
        'dom': dom_usage,
        'dol': dol_usage,
        'gabinet': {
            'zuzycie_gabinet': gabinet_usage
        },
        'gora': gora_usage
    }

