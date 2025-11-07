# 🔌 Analiza i Projekt Struktury Bazy Danych dla Prądu

## 📊 Wizualizacja Struktury Liczników

```
┌─────────────────────────────────────────────────────────────┐
│                    LICZNIK GŁÓWNY DOM                        │
│  ┌──────────────────────┐  ┌──────────────────────┐        │
│  │  DWUTARYFOWY         │  │  JEDNOTARYFOWY        │        │
│  │  - odczyt_dom_I      │  │  - odczyt_dom         │        │
│  │  - odczyt_dom_II     │  │                       │        │
│  └──────────────────────┘  └──────────────────────┘        │
└─────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ PODLICZNIK   │    │ PODLICZNIK   │    │   GÓRA       │
│    DÓŁ       │    │   GABINET    │    │ (obliczany)  │
│              │    │              │    │              │
│ Dwutaryfowy: │    │ Zawsze       │    │ = DOM -      │
│ - dol_I      │    │ jednotaryfowy│    │   (DÓŁ +     │
│ - dol_II     │    │ - gabinet    │    │   GABINET)   │
│              │    │              │    │              │
│ Jednotaryfowy│    │              │    │              │
│ - dol        │    │              │    │              │
└──────────────┘    └──────────────┘    └──────────────┘
```

---

## 🔍 Analiza Założeń - Identyfikacja Problemów

### ❌ Problemy w pierwotnych założeniach:

1. **Niespójne nazewnictwo**
   - Mieszane: `zuzycie_caly_dom_lacznie` vs `zuzycie_lacznie_dom`
   - Różne warianty tej samej wartości

2. **Złożona logika obliczeń**
   - Wiele warunków if/else dla różnych kombinacji
   - Trudne do utrzymania i testowania

3. **Brak walidacji**
   - Nie sprawdzamy czy poprzedni odczyt istnieje
   - Nie obsługujemy błędów

4. **Redundancja danych**
   - Przechowywanie zarówno odczytów jak i zużycia
   - Można obliczyć zużycie na żądanie

---

## ✅ Uproszczone Rozwiązanie

### Strategia:
1. **Przechowujemy tylko odczyty** - zużycie obliczamy dynamicznie
2. **Ujednolicone nazewnictwo** - spójne konwencje
3. **Funkcje pomocnicze** - uproszczenie logiki obliczeń
4. **Flagi boolean** - jasne określenie typu licznika

---

## 🗄️ Proponowana Struktura Tabeli `electricity_readings`

```sql
CREATE TABLE electricity_readings (
    -- ID i organizacja
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data VARCHAR(7) NOT NULL UNIQUE,  -- Format: 'YYYY-MM' (np. '2025-01')
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- ============================================
    -- LICZNIK GŁÓWNY DOM
    -- ============================================
    -- Flaga typu licznika głównego
    licznik_dom_jednotaryfowy BOOLEAN NOT NULL DEFAULT 0,
    
    -- Odczyty dla licznika głównego
    -- Wariant A: Licznik jednotaryfowy
    odczyt_dom REAL,  -- NULL jeśli dwutaryfowy
    
    -- Wariant B: Licznik dwutaryfowy
    odczyt_dom_I REAL,   -- NULL jeśli jednotaryfowy
    odczyt_dom_II REAL,  -- NULL jeśli jednotaryfowy
    
    -- ============================================
    -- PODLICZNIK DÓŁ
    -- ============================================
    -- Flaga typu licznika dolnego
    licznik_dol_jednotaryfowy BOOLEAN NOT NULL DEFAULT 0,
    
    -- Odczyty dla podlicznika dolnego
    -- Wariant A: Licznik jednotaryfowy
    odczyt_dol REAL,  -- NULL jeśli dwutaryfowy
    
    -- Wariant B: Licznik dwutaryfowy
    odczyt_dol_I REAL,   -- NULL jeśli jednotaryfowy
    odczyt_dol_II REAL,  -- NULL jeśli jednotaryfowy
    
    -- ============================================
    -- PODLICZNIK GABINET
    -- ============================================
    -- Zawsze jednotaryfowy
    odczyt_gabinet REAL NOT NULL,
    
    -- ============================================
    -- ZUŻYCIE (obliczane, nie przechowywane w bazie)
    -- ============================================
    -- Zużycie obliczamy dynamicznie w funkcjach pomocniczych
    -- NIE przechowujemy w bazie - zawsze aktualne względem poprzedniego odczytu
    
    -- Walidacja
    CHECK (
        -- Licznik dom: musi być albo jednotaryfowy, albo dwutaryfowy
        (licznik_dom_jednotaryfowy = 1 AND odczyt_dom IS NOT NULL AND odczyt_dom_I IS NULL AND odczyt_dom_II IS NULL)
        OR
        (licznik_dom_jednotaryfowy = 0 AND odczyt_dom IS NULL AND odczyt_dom_I IS NOT NULL AND odczyt_dom_II IS NOT NULL)
    ),
    CHECK (
        -- Licznik dol: musi być albo jednotaryfowy, albo dwutaryfowy
        (licznik_dol_jednotaryfowy = 1 AND odczyt_dol IS NOT NULL AND odczyt_dol_I IS NULL AND odczyt_dol_II IS NULL)
        OR
        (licznik_dol_jednotaryfowy = 0 AND odczyt_dol IS NULL AND odczyt_dol_I IS NOT NULL AND odczyt_dol_II IS NOT NULL)
    )
);
```

---

## 📐 Model SQLAlchemy

```python
from sqlalchemy import Column, String, Float, Boolean, Integer, CheckConstraint
from app.core.database import Base

class ElectricityReading(Base):
    """Odczyty liczników prądu."""
    __tablename__ = "electricity_readings"
    
    # ID i organizacja
    id = Column(Integer, primary_key=True, autoincrement=True)
    data = Column(String(7), unique=True, nullable=False)  # 'YYYY-MM'
    
    # ============================================
    # LICZNIK GŁÓWNY DOM
    # ============================================
    licznik_dom_jednotaryfowy = Column(Boolean, nullable=False, default=False)
    odczyt_dom = Column(Float, nullable=True)  # Jednotaryfowy
    odczyt_dom_I = Column(Float, nullable=True)  # Dwutaryfowy - taryfa I
    odczyt_dom_II = Column(Float, nullable=True)  # Dwutaryfowy - taryfa II
    
    # ============================================
    # PODLICZNIK DÓŁ
    # ============================================
    licznik_dol_jednotaryfowy = Column(Boolean, nullable=False, default=False)
    odczyt_dol = Column(Float, nullable=True)  # Jednotaryfowy
    odczyt_dol_I = Column(Float, nullable=True)  # Dwutaryfowy - taryfa I
    odczyt_dol_II = Column(Float, nullable=True)  # Dwutaryfowy - taryfa II
    
    # ============================================
    # PODLICZNIK GABINET
    # ============================================
    odczyt_gabinet = Column(Float, nullable=False)
    
    # Constraints
    __table_args__ = (
        CheckConstraint(
            "(licznik_dom_jednotaryfowy = 1 AND odczyt_dom IS NOT NULL AND odczyt_dom_I IS NULL AND odczyt_dom_II IS NULL) OR "
            "(licznik_dom_jednotaryfowy = 0 AND odczyt_dom IS NULL AND odczyt_dom_I IS NOT NULL AND odczyt_dom_II IS NOT NULL)",
            name="check_dom_meter_type"
        ),
        CheckConstraint(
            "(licznik_dol_jednotaryfowy = 1 AND odczyt_dol IS NOT NULL AND odczyt_dol_I IS NULL AND odczyt_dol_II IS NULL) OR "
            "(licznik_dol_jednotaryfowy = 0 AND odczyt_dol IS NULL AND odczyt_dol_I IS NOT NULL AND odczyt_dol_II IS NOT NULL)",
            name="check_dol_meter_type"
        ),
    )
```

---

## 🧮 Logika Obliczeń - Uproszczona

### Funkcje Pomocnicze

```python
def get_previous_reading(db: Session, current_data: str) -> Optional[ElectricityReading]:
    """Pobiera poprzedni odczyt (najnowszy przed current_data)."""
    # Sortowanie po dacie, pobranie poprzedniego
    pass

def get_total_dom_reading(reading: ElectricityReading) -> float:
    """
    Zwraca łączny odczyt licznika głównego DOM.
    Dla dwutaryfowego: I + II
    Dla jednotaryfowego: po prostu odczyt_dom
    """
    if reading.licznik_dom_jednotaryfowy:
        return reading.odczyt_dom
    else:
        return reading.odczyt_dom_I + reading.odczyt_dom_II

def get_total_dol_reading(reading: ElectricityReading) -> float:
    """Zwraca łączny odczyt podlicznika DÓŁ."""
    if reading.licznik_dol_jednotaryfowy:
        return reading.odczyt_dol
    else:
        return reading.odczyt_dol_I + reading.odczyt_dol_II
```

---

## 📊 Obliczenia Zużycia - Szczegółowy Schemat

### 1️⃣ ZUŻYCIE CAŁEGO DOMU

```
┌─────────────────────────────────────────────────────────────┐
│  SCENARIUSZ A: Oba okresy mają licznik dwutaryfowy          │
├─────────────────────────────────────────────────────────────┤
│  zuzycie_dom_I = odczyt_dom_I (aktualny)                   │
│              - odczyt_dom_I (poprzedni)                     │
│                                                              │
│  zuzycie_dom_II = odczyt_dom_II (aktualny)                 │
│               - odczyt_dom_II (poprzedni)                   │
│                                                              │
│  zuzycie_dom_lacznie = zuzycie_dom_I + zuzycie_dom_II      │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  SCENARIUSZ B: Aktualny jednotaryfowy, poprzedni dwutaryfowy│
├─────────────────────────────────────────────────────────────┤
│  zuzycie_dom_lacznie = odczyt_dom (aktualny)                │
│                      - get_total_dom_reading(poprzedni)      │
│                                                              │
│  (gdzie get_total_dom_reading = dom_I + dom_II)            │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  SCENARIUSZ C: Oba okresy mają licznik jednotaryfowy         │
├─────────────────────────────────────────────────────────────┤
│  zuzycie_dom_lacznie = odczyt_dom (aktualny)                │
│                      - odczyt_dom (poprzedni)               │
└─────────────────────────────────────────────────────────────┘
```

**Kod:**

```python
def calculate_dom_usage(current: ElectricityReading, previous: Optional[ElectricityReading]) -> Dict[str, float]:
    """
    Oblicza zużycie dla całego domu.
    Zwraca: {
        'zuzycie_dom_I': float | None,
        'zuzycie_dom_II': float | None,
        'zuzycie_dom_lacznie': float
    }
    """
    if previous is None:
        return {'zuzycie_dom_I': None, 'zuzycie_dom_II': None, 'zuzycie_dom_lacznie': 0.0}
    
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
    
    return {'zuzycie_dom_I': None, 'zuzycie_dom_II': None, 'zuzycie_dom_lacznie': 0.0}
```

---

### 2️⃣ ZUŻYCIE PODLICZNIKA DÓŁ

```
┌─────────────────────────────────────────────────────────────┐
│  SCENARIUSZ A: Oba okresy mają ten sam typ licznika          │
├─────────────────────────────────────────────────────────────┤
│  Dwutaryfowy:                                                │
│    zuzycie_dol_I = odczyt_dol_I (aktualny)                  │
│                  - odczyt_dol_I (poprzedni)                 │
│    zuzycie_dol_II = odczyt_dol_II (aktualny)                │
│                   - odczyt_dol_II (poprzedni)               │
│    zuzycie_dol_lacznie = zuzycie_dol_I + zuzycie_dol_II    │
│                                                              │
│  Jednotaryfowy:                                              │
│    zuzycie_dol = odczyt_dol (aktualny)                      │
│                - odczyt_dol (poprzedni)                     │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  SCENARIUSZ B: Poprzedni dwutaryfowy, aktualny jednotaryfowy│
├─────────────────────────────────────────────────────────────┤
│  zuzycie_dol = odczyt_dol (aktualny)                        │
│            - (odczyt_dol_I + odczyt_dol_II) (poprzedni)     │
└─────────────────────────────────────────────────────────────┘
```

**Kod:**

```python
def calculate_dol_usage(current: ElectricityReading, previous: Optional[ElectricityReading]) -> Dict[str, float]:
    """
    Oblicza zużycie dla podlicznika DÓŁ.
    Zwraca: {
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
```

---

### 3️⃣ ZUŻYCIE PODLICZNIKA GABINET

```
┌─────────────────────────────────────────────────────────────┐
│  Zawsze jednotaryfowy - proste obliczenie                   │
├─────────────────────────────────────────────────────────────┤
│  zuzycie_gabinet = odczyt_gabinet (aktualny)                │
│                        - odczyt_gabinet (poprzedni)         │
└─────────────────────────────────────────────────────────────┘
```

**Kod:**

```python
def calculate_gabinet_usage(current: ElectricityReading, previous: Optional[ElectricityReading]) -> float:
    """Oblicza zużycie dla podlicznika GABINET."""
    if previous is None:
        return 0.0
    return current.odczyt_gabinet - previous.odczyt_gabinet
```

---

### 4️⃣ ZUŻYCIE GÓRA (obliczane, brak licznika)

```
┌─────────────────────────────────────────────────────────────┐
│  GÓRA = DOM - (DÓŁ + GABINET)                               │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  SCENARIUSZ A: Oba okresy dwutaryfowe                       │
│  ────────────────────────────────────────                   │
│  zuzycie_gora_I = zuzycie_dom_I - zuzycie_dol_I            │
│  zuzycie_gora_II = zuzycie_dom_II - zuzycie_dol_II          │
│  zuzycie_gora_lacznie = zuzycie_gora_I + zuzycie_gora_II   │
│                          - zuzycie_gabinet                  │
│                                                              │
│  SCENARIUSZ B: Aktualny jednotaryfowy, poprzedni dwutaryfowy│
│  ────────────────────────────────────────────────────────   │
│  zuzycie_gora_lacznie = zuzycie_dom_lacznie                │
│                          - zuzycie_dol_lacznie             │
│                          - zuzycie_gabinet                  │
│                                                              │
│  SCENARIUSZ C: Oba okresy jednotaryfowe                     │
│  ────────────────────────────────────────                   │
│  zuzycie_gora_lacznie = zuzycie_dom_lacznie                │
│                          - zuzycie_dol_lacznie             │
│                          - zuzycie_gabinet                  │
└─────────────────────────────────────────────────────────────┘
```

**Kod:**

```python
def calculate_gora_usage(
    dom_usage: Dict[str, float],
    dol_usage: Dict[str, float],
    gabinet_usage: float
) -> Dict[str, float]:
    """
    Oblicza zużycie dla GÓRA (brak licznika, obliczane).
    Zwraca: {
        'zuzycie_gora_I': float | None,
        'zuzycie_gora_II': float | None,
        'zuzycie_gora_lacznie': float
    }
    """
    # Jeśli mamy rozdzielone taryfy (oba dwutaryfowe)
    if dom_usage['zuzycie_dom_I'] is not None and dol_usage['zuzycie_dol_I'] is not None:
        zuzycie_I = dom_usage['zuzycie_dom_I'] - dol_usage['zuzycie_dol_I']
        zuzycie_II = dom_usage['zuzycie_dom_II'] - dol_usage['zuzycie_dol_II']
        # GABINET zawsze odejmujemy od łącznego
        zuzycie_lacznie = zuzycie_I + zuzycie_II - gabinet_usage
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
```

---

## 📋 Kompletna Funkcja Obliczająca Wszystkie Zużycia

```python
def calculate_all_usage(
    current: ElectricityReading,
    previous: Optional[ElectricityReading],
    db: Session
) -> Dict[str, Any]:
    """
    Oblicza wszystkie zużycia dla danego okresu.
    Zwraca kompleksowy słownik z wszystkimi wartościami.
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
```

---

## 🎯 Przykłady Obliczeń

### Przykład 1: Oba okresy dwutaryfowe

```
OKRES POPRZEDNI (2024-12):
  DOM: I=1000, II=2000  → łącznie: 3000
  DÓŁ: I=300, II=600    → łącznie: 900
  GABINET: 100

OKRES AKTUALNY (2025-01):
  DOM: I=1100, II=2200  → łącznie: 3300
  DÓŁ: I=350, II=700    → łącznie: 1050
  GABINET: 150

OBLICZENIA:
  zuzycie_dom_I = 1100 - 1000 = 100
  zuzycie_dom_II = 2200 - 2000 = 200
  zuzycie_dom_lacznie = 100 + 200 = 300
  
  zuzycie_dol_I = 350 - 300 = 50
  zuzycie_dol_II = 700 - 600 = 100
  zuzycie_dol_lacznie = 50 + 100 = 150
  
  zuzycie_gabinet = 150 - 100 = 50
  
  zuzycie_gora_I = 100 - 50 = 50
  zuzycie_gora_II = 200 - 100 = 100
  zuzycie_gora_lacznie = 50 + 100 = 150
```

### Przykład 2: Migracja z dwutaryfowego na jednotaryfowy

```
OKRES POPRZEDNI (2024-12) - DWUTARYFOWY:
  DOM: I=1000, II=2000  → łącznie: 3000
  DÓŁ: I=300, II=600    → łącznie: 900
  GABINET: 100

OKRES AKTUALNY (2025-01) - JEDNOTARYFOWY:
  DOM: 3300
  DÓŁ: 1050
  GABINET: 150

OBLICZENIA:
  zuzycie_dom_lacznie = 3300 - 3000 = 300
  
  zuzycie_dol_lacznie = 1050 - 900 = 150
  
  zuzycie_gabinet = 150 - 100 = 50
  
  zuzycie_gora_lacznie = 300 - 150 - 50 = 100
```

---

## ✅ Zalety Proponowanego Rozwiązania

1. **Prostota** - Przechowujemy tylko odczyty, zużycie obliczamy
2. **Spójność** - Ujednolicone nazewnictwo i logika
3. **Elastyczność** - Obsługa migracji między typami liczników
4. **Walidacja** - Constraints w bazie danych
5. **Testowalność** - Funkcje pomocnicze łatwe do testowania
6. **Czytelność** - Jasna struktura i dokumentacja

---

## ⚠️ Uwagi i Rozważania

1. **Proporcjonalny podział przy migracji**
   - W scenariuszu D (aktualny dwutaryfowy, poprzedni jednotaryfowy)
   - Można użyć innych metod podziału (np. równy 50/50)

2. **Brak poprzedniego odczytu**
   - Pierwszy odczyt: wszystkie zużycia = 0
   - Można dodać flagę `is_first_reading`

3. **Ujemne zużycie**
   - Może wystąpić przy błędach odczytu
   - Dodać walidację i ostrzeżenia

4. **Zaokrąglenia**
   - kWh mogą mieć miejsca dziesiętne
   - Użyć odpowiedniej precyzji (np. 2 miejsca)

---

## 🔄 Diagram Przepływu Obliczeń

```
┌─────────────────────────────────────────────────────────────┐
│                    NOWY ODCZYT                              │
│              (electricity_readings)                         │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
        ┌───────────────────────────────┐
        │  Pobierz poprzedni odczyt     │
        │  (najnowszy przed current)    │
        └───────────────┬───────────────┘
                        │
        ┌───────────────┴───────────────┐
        │                               │
        ▼                               ▼
┌───────────────┐              ┌───────────────┐
│ Poprzedni     │              │ Brak          │
│ istnieje     │              │ poprzedniego   │
└───────┬───────┘              └───────┬───────┘
        │                               │
        │                               │
        ▼                               ▼
┌─────────────────────────────────────────────────────────────┐
│  OBLICZ ZUŻYCIE DOM                                          │
│  ┌────────────────────────────────────────────────────┐    │
│  │ Sprawdź typy liczników (aktualny i poprzedni)     │    │
│  │                                                     │    │
│  │ A) Oba dwutaryfowe → I i II osobno                 │    │
│  │ B) Aktualny 1-taryfowy, poprzedni 2-taryfowy      │    │
│  │    → łączny od poprzedniego łącznego               │    │
│  │ C) Oba 1-taryfowe → proste odejmowanie            │    │
│  │ D) Aktualny 2-taryfowy, poprzedni 1-taryfowy      │    │
│  │    → proporcjonalny podział                        │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│  OBLICZ ZUŻYCIE DÓŁ                                          │
│  (analogicznie jak DOM)                                      │
└─────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│  OBLICZ ZUŻYCIE GABINET                                      │
│  zuzycie = odczyt_aktualny - odczyt_poprzedni               │
└─────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│  OBLICZ ZUŻYCIE GÓRA                                         │
│  zuzycie_gora = zuzycie_dom - zuzycie_dol - zuzycie_gabinet │
└─────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│  ZWRÓĆ WYNIKI                                                │
│  {                                                           │
│    'dom': {...},                                            │
│    'dol': {...},                                            │
│    'gabinet': {...},                                         │
│    'gora': {...}                                            │
│  }                                                           │
└─────────────────────────────────────────────────────────────┘
```

---

## 🎯 Diagram Decyzyjny - Typ Licznika DOM

```
                    ┌─────────────┐
                    │  NOWY ODCZYT│
                    └──────┬──────┘
                           │
                           ▼
            ┌───────────────────────────┐
            │ licznik_dom_jednotaryfowy│
            │         = ?              │
            └───────┬───────────┬───────┘
                    │           │
          ┌─────────┘           └─────────┐
          │ TRUE                           │ FALSE
          ▼                                 ▼
    ┌─────────────┐                  ┌─────────────┐
    │ JEDNOTARYFOWY│                  │ DWUTARYFOWY │
    │              │                  │             │
    │ odczyt_dom   │                  │ odczyt_dom_I│
    │ (NOT NULL)   │                  │ odczyt_dom_II│
    │              │                  │ (NOT NULL)  │
    │ odczyt_dom_I │                  │             │
    │ = NULL       │                  │ odczyt_dom  │
    │ odczyt_dom_II│                  │ = NULL      │
    │ = NULL       │                  │             │
    └─────────────┘                  └─────────────┘
```

---

## 📊 Tabela Porównawcza - Scenariusze Obliczeń

| Scenariusz | Aktualny DOM | Poprzedni DOM | Aktualny DÓŁ | Poprzedni DÓŁ | Metoda Obliczeń |
|------------|--------------|--------------|--------------|---------------|-----------------|
| **1** | 2-taryfowy | 2-taryfowy | 2-taryfowy | 2-taryfowy | Odejmowanie I i II osobno |
| **2** | 1-taryfowy | 2-taryfowy | 1-taryfowy | 2-taryfowy | Od łącznego poprzedniego |
| **3** | 1-taryfowy | 1-taryfowy | 1-taryfowy | 1-taryfowy | Proste odejmowanie |
| **4** | 2-taryfowy | 1-taryfowy | 2-taryfowy | 1-taryfowy | Proporcjonalny podział |
| **5** | 2-taryfowy | 2-taryfowy | 1-taryfowy | 2-taryfowy | Mieszane (DOM: osobno, DÓŁ: od łącznego) |
| **6** | 1-taryfowy | 2-taryfowy | 2-taryfowy | 1-taryfowy | Mieszane (DOM: od łącznego, DÓŁ: proporcjonalny) |

---

## 📝 Podsumowanie

**Struktura tabeli:**
- ✅ Tylko odczyty (nie przechowujemy zużycia)
- ✅ Flagi boolean dla typu licznika
- ✅ Constraints dla walidacji
- ✅ NULL dla nieużywanych pól

**Obliczenia:**
- ✅ Funkcje pomocnicze dla każdego typu zużycia
- ✅ Obsługa wszystkich scenariuszy migracji
- ✅ Czytelna logika warunkowa

**Uproszczenia względem pierwotnych założeń:**
1. ❌ Usunięto: `zuzycie_caly_dom_lacznie` vs `zuzycie_lacznie_dom` → ✅ Ujednolicono: `zuzycie_dom_lacznie`
2. ❌ Usunięto: Przechowywanie zużycia w bazie → ✅ Obliczamy dynamicznie
3. ❌ Usunięto: Złożone warunki if/else → ✅ Funkcje pomocnicze z jasną logiką
4. ✅ Dodano: Walidację w bazie danych (CHECK constraints)
5. ✅ Dodano: Obsługę rzadkich scenariuszy (aktualny 2-taryfowy, poprzedni 1-taryfowy)

**Następne kroki:**
1. Implementacja modelu SQLAlchemy
2. Utworzenie migracji
3. Implementacja funkcji obliczeniowych
4. Testy jednostkowe dla wszystkich scenariuszy
5. Integracja z API
6. Dokumentacja API endpoints

