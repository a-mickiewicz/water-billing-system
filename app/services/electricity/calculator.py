"""
Logika obliczeń zużycia prądu dla lokali.

Obsługuje:
- Liczniki dwutaryfowe (I, II) i jednotaryfowe
- Migrację między typami liczników
- Obliczanie zużycia dla DOM, DÓŁ, GABINET i GÓRA

Struktura liczników:
- DOM (główny licznik)
- DÓŁ (podlicznik DOM, zawiera GABINET)
- GABINET (podlicznik DÓŁ - zagnieżdżony)
- GÓRA (obliczane: DOM - DÓŁ)
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
            'zuzycie_dom_I': round(zuzycie_I, 4),
            'zuzycie_dom_II': round(zuzycie_II, 4),
            'zuzycie_dom_lacznie': round(zuzycie_I + zuzycie_II, 4)
        }
    
    # SCENARIUSZ B: Aktualny jednotaryfowy, poprzedni dwutaryfowy
    if current.licznik_dom_jednotaryfowy and not previous.licznik_dom_jednotaryfowy:
        poprzedni_lacznie = previous.odczyt_dom_I + previous.odczyt_dom_II
        zuzycie_lacznie = current.odczyt_dom - poprzedni_lacznie
        return {
            'zuzycie_dom_I': None,
            'zuzycie_dom_II': None,
            'zuzycie_dom_lacznie': round(zuzycie_lacznie, 4)
        }
    
    # SCENARIUSZ C: Oba jednotaryfowe
    if current.licznik_dom_jednotaryfowy and previous.licznik_dom_jednotaryfowy:
        zuzycie_lacznie = current.odczyt_dom - previous.odczyt_dom
        return {
            'zuzycie_dom_I': None,
            'zuzycie_dom_II': None,
            'zuzycie_dom_lacznie': round(zuzycie_lacznie, 4)
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
            'zuzycie_dom_I': round(zuzycie_lacznie * ratio_I, 4),
            'zuzycie_dom_II': round(zuzycie_lacznie * ratio_II, 4),
            'zuzycie_dom_lacznie': round(zuzycie_lacznie, 4)
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
    Oblicza zużycie z odczytu podlicznika DÓŁ.
    
    UWAGA: To jest zużycie z odczytu DÓŁ (zawiera GABINET).
    Zużycie lokalu Mikołaj (DOL) oblicza się jako: DÓŁ - GABINET
    (patrz calculate_all_usage).
    
    Args:
        current: Aktualny odczyt
        previous: Poprzedni odczyt (może być None)
    
    Returns:
        Słownik z zużyciem z odczytu DÓŁ:
        {
            'zuzycie_dol': float | None,
            'zuzycie_dol_I': float | None,
            'zuzycie_dol_II': float | None,
            'zuzycie_dol_lacznie': float  # Zawiera GABINET
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
            'zuzycie_dol_I': round(zuzycie_I, 4),
            'zuzycie_dol_II': round(zuzycie_II, 4),
            'zuzycie_dol_lacznie': round(zuzycie_I + zuzycie_II, 4)
        }
    
    # Oba jednotaryfowe
    if current.licznik_dol_jednotaryfowy and previous.licznik_dol_jednotaryfowy:
        zuzycie = current.odczyt_dol - previous.odczyt_dol
        return {
            'zuzycie_dol': round(zuzycie, 4),
            'zuzycie_dol_I': None,
            'zuzycie_dol_II': None,
            'zuzycie_dol_lacznie': round(zuzycie, 4)
        }
    
    # Poprzedni dwutaryfowy, aktualny jednotaryfowy
    if current.licznik_dol_jednotaryfowy and not previous.licznik_dol_jednotaryfowy:
        poprzedni_lacznie = previous.odczyt_dol_I + previous.odczyt_dol_II
        zuzycie = current.odczyt_dol - poprzedni_lacznie
        return {
            'zuzycie_dol': round(zuzycie, 4),
            'zuzycie_dol_I': None,
            'zuzycie_dol_II': None,
            'zuzycie_dol_lacznie': round(zuzycie, 4)
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
            'zuzycie_dol_I': round(zuzycie_lacznie * ratio_I, 4),
            'zuzycie_dol_II': round(zuzycie_lacznie * ratio_II, 4),
            'zuzycie_dol_lacznie': round(zuzycie_lacznie, 4)
        }
    
    return {
        'zuzycie_dol': None,
        'zuzycie_dol_I': None,
        'zuzycie_dol_II': None,
        'zuzycie_dol_lacznie': 0.0
    }


def calculate_gabinet_usage(
    current: ElectricityReading,
    previous: Optional[ElectricityReading],
    dom_is_dual_tariff: bool = False
) -> Dict[str, Optional[float]]:
    """
    Oblicza zużycie dla podlicznika GABINET.
    GABINET jest zawsze jednotaryfowy, ale jeśli główny licznik jest dwutaryfowy,
    to zużycie dzienne/nocne oblicza się przez aproksymację 70%/30%.
    
    Args:
        current: Aktualny odczyt
        previous: Poprzedni odczyt (może być None)
        dom_is_dual_tariff: Czy główny licznik DOM jest dwutaryfowy
    
    Returns:
        Słownik z zużyciem:
        {
            'zuzycie_gabinet': float,
            'zuzycie_gabinet_dzienna': float | None,  # 70% jeśli dom dwutaryfowy
            'zuzycie_gabinet_nocna': float | None     # 30% jeśli dom dwutaryfowy
        }
    """
    if previous is None:
        usage_total = 0.0
    else:
        usage_total = round(current.odczyt_gabinet - previous.odczyt_gabinet, 4)
    
    # Jeśli główny licznik jest dwutaryfowy, aproksymacja 70%/30%
    if dom_is_dual_tariff and usage_total > 0:
        return {
            'zuzycie_gabinet': usage_total,
            'zuzycie_gabinet_dzienna': round(usage_total * 0.7, 4),
            'zuzycie_gabinet_nocna': round(usage_total * 0.3, 4)
        }
    else:
        return {
            'zuzycie_gabinet': usage_total,
            'zuzycie_gabinet_dzienna': None,
            'zuzycie_gabinet_nocna': None
        }


def calculate_gora_usage(
    dom_usage: Dict[str, Optional[float]],
    dol_usage: Dict[str, Optional[float]],
    gabinet_usage: float
) -> Dict[str, Optional[float]]:
    """
    Oblicza zużycie dla GÓRA (brak licznika, obliczane).
    GÓRA = DOM - DÓŁ
    
    Uwaga: W strukturze liczników DÓŁ jest podlicznikiem DOM i zawiera GABINET
    (GABINET jest podlicznikiem DÓŁ), więc GABINET nie jest odejmowany osobno.
    
    Args:
        dom_usage: Zużycie DOM (ze calculate_dom_usage)
        dol_usage: Zużycie DÓŁ (ze calculate_dol_usage) - zawiera już GABINET
        gabinet_usage: Zużycie GABINET (parametr zachowany dla kompatybilności, nie używany)
    
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
        # GÓRA łącznie = suma taryf (DÓŁ już zawiera GABINET)
        zuzycie_lacznie = zuzycie_I + zuzycie_II
        return {
            'zuzycie_gora_I': round(zuzycie_I, 4),
            'zuzycie_gora_II': round(zuzycie_II, 4),
            'zuzycie_gora_lacznie': round(zuzycie_lacznie, 4)
        }
    
    # Jeśli mamy tylko łączne zużycie
    # DÓŁ już zawiera GABINET, więc nie odejmujemy gabinet_usage
    zuzycie_lacznie = dom_usage['zuzycie_dom_lacznie'] - dol_usage['zuzycie_dol_lacznie']
    return {
        'zuzycie_gora_I': None,
        'zuzycie_gora_II': None,
        'zuzycie_gora_lacznie': round(zuzycie_lacznie, 4)
    }


def calculate_all_usage(
    current: ElectricityReading,
    previous: Optional[ElectricityReading]
) -> Dict[str, Any]:
    """
    Oblicza wszystkie zużycia dla danego okresu.
    
    Logika:
    - DOM: zużycie z głównego licznika
    - DÓŁ: zużycie z odczytu podlicznika DÓŁ (zawiera GABINET)
    - GABINET: zużycie z odczytu podlicznika GABINET
    - Mikołaj (DOL): DÓŁ - GABINET (obliczane)
    - GÓRA: DOM - DÓŁ (obliczane)
    
    Aproksymacja 70%/30%:
    - Jeśli główny licznik jest dwutaryfowy, a nie mamy rozdzielonych taryf:
      * Mikołaj: 70% dzienna, 30% nocna z (DÓŁ - GABINET)
      * GABINET: 70% dzienna, 30% nocna
    
    Args:
        current: Aktualny odczyt
        previous: Poprzedni odczyt (może być None)
    
    Returns:
        Kompleksowy słownik z wszystkimi wartościami:
        {
            'data': str,
            'dom': {...},
            'dol': {...},  # Zużycie Mikołaja (DÓŁ - GABINET)
            'gabinet': {...},
            'gora': {...}
        }
    """
    # 1. Zużycie DOM
    dom_usage = calculate_dom_usage(current, previous)
    dom_is_dual_tariff = dom_usage['zuzycie_dom_I'] is not None
    
    # 2. Zużycie z odczytu DÓŁ (zawiera GABINET)
    dol_reading_usage = calculate_dol_usage(current, previous)
    
    # 3. Zużycie GABINET
    gabinet_data = calculate_gabinet_usage(current, previous, dom_is_dual_tariff)
    gabinet_usage_total = gabinet_data['zuzycie_gabinet']
    
    # 4. Zużycie Mikołaja (DOL) = DÓŁ - GABINET
    dol_usage_lacznie = dol_reading_usage['zuzycie_dol_lacznie'] - gabinet_usage_total
    
    # Oblicz zużycie dzienne/nocne dla Mikołaja
    dol_usage_dzienna = None
    dol_usage_nocna = None
    
    # Jeśli mamy rozdzielone taryfy dla DÓŁ
    if dol_reading_usage['zuzycie_dol_I'] is not None and dol_reading_usage['zuzycie_dol_II'] is not None:
        # Mikołaj = DÓŁ - GABINET (dla każdej taryfy osobno)
        gabinet_dzienna = gabinet_data.get('zuzycie_gabinet_dzienna')
        gabinet_nocna = gabinet_data.get('zuzycie_gabinet_nocna')
        
        if gabinet_dzienna is not None and gabinet_nocna is not None:
            # GABINET ma aproksymację 70%/30%
            dol_usage_dzienna = dol_reading_usage['zuzycie_dol_I'] - gabinet_dzienna
            dol_usage_nocna = dol_reading_usage['zuzycie_dol_II'] - gabinet_nocna
        else:
            # GABINET nie ma rozdzielonych taryf, ale DÓŁ ma
            # Używamy proporcji z DÓŁ
            dol_total = dol_reading_usage['zuzycie_dol_I'] + dol_reading_usage['zuzycie_dol_II']
            if dol_total > 0:
                ratio_I = dol_reading_usage['zuzycie_dol_I'] / dol_total
                ratio_II = dol_reading_usage['zuzycie_dol_II'] / dol_total
                dol_usage_dzienna = dol_usage_lacznie * ratio_I
                dol_usage_nocna = dol_usage_lacznie * ratio_II
    # Jeśli główny licznik jest dwutaryfowy, ale DÓŁ nie ma rozdzielonych taryf
    elif dom_is_dual_tariff and dol_usage_lacznie > 0:
        # Aproksymacja 70%/30%
        dol_usage_dzienna = dol_usage_lacznie * 0.7
        dol_usage_nocna = dol_usage_lacznie * 0.3
    
    dol_usage = {
        'zuzycie_dol': None if (dol_usage_dzienna is not None or dol_usage_nocna is not None) else dol_usage_lacznie,
        'zuzycie_dol_I': round(dol_usage_dzienna, 4) if dol_usage_dzienna is not None else None,
        'zuzycie_dol_II': round(dol_usage_nocna, 4) if dol_usage_nocna is not None else None,
        'zuzycie_dol_lacznie': round(dol_usage_lacznie, 4)
    }
    
    # 5. Zużycie GÓRA (obliczane: DOM - DÓŁ)
    # Używamy dol_reading_usage (z odczytu), bo GÓRA = DOM - DÓŁ (który zawiera GABINET)
    gora_usage = calculate_gora_usage(dom_usage, dol_reading_usage, gabinet_usage_total)
    
    return {
        'data': current.data,
        'dom': dom_usage,
        'dol': dol_usage,  # Zużycie Mikołaja (DÓŁ - GABINET)
        'gabinet': gabinet_data,
        'gora': gora_usage
    }

