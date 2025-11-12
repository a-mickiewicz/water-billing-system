# Analiza zmiany struktury liczników prądu

## 📊 Obecna struktura vs. Nowa struktura

### OBECNA STRUKTURA (hierarchia płaska):
```
DOM (główny licznik)
├── DÓŁ (podlicznik DOM)
├── GABINET (podlicznik DOM - niezależny)
└── GÓRA (obliczane) = DOM - (DÓŁ + GABINET)
```

**Logika obliczeń:**
- `zuzycie_dom` = różnica odczytów DOM
- `zuzycie_dol` = różnica odczytów DÓŁ
- `zuzycie_gabinet` = różnica odczytów GABINET
- `zuzycie_gora` = `zuzycie_dom` - `zuzycie_dol` - `zuzycie_gabinet`

### NOWA STRUKTURA (hierarchia zagnieżdżona):
```
DOM (główny licznik)
├── DÓŁ (podlicznik DOM)
│   └── GABINET (podlicznik DÓŁ)
└── GÓRA (obliczane) = DOM - DÓŁ
```

**Logika obliczeń:**
- `zuzycie_dom` = różnica odczytów DOM
- `zuzycie_dol` = różnica odczytów DÓŁ (zawiera już GABINET)
- `zuzycie_gabinet` = różnica odczytów GABINET
- `zuzycie_gora` = `zuzycie_dom` - `zuzycie_dol`
- `zuzycie_dol_netto` (opcjonalnie) = `zuzycie_dol` - `zuzycie_gabinet` (jeśli potrzebne)

## 🔍 Kluczowe zmiany w logice

### 1. Obliczanie GÓRA

**Obecnie:**
```python
zuzycie_gora = DOM - (DÓŁ + GABINET)
```

**Po zmianie:**
```python
zuzycie_gora = DOM - DÓŁ
```

**Uzasadnienie:** W nowej strukturze DÓŁ już zawiera GABINET, więc nie trzeba go odejmować osobno.

### 2. Interpretacja odczytu DÓŁ

**Ważne pytanie:** Co pokazuje odczyt DÓŁ w nowej strukturze?
- **Opcja A:** Odczyt DÓŁ pokazuje zużycie DÓŁ + GABINET (łącznie)
  - Wtedy: `zuzycie_dol` = różnica odczytów DÓŁ (zawiera GABINET)
  - `zuzycie_gabinet` = różnica odczytów GABINET
  - `zuzycie_dol_netto` = `zuzycie_dol` - `zuzycie_gabinet` (jeśli potrzebne)

- **Opcja B:** Odczyt DÓŁ pokazuje tylko zużycie DÓŁ (bez GABINET)
  - Wtedy: `zuzycie_dol` = różnica odczytów DÓŁ (bez GABINET)
  - `zuzycie_gabinet` = różnica odczytów GABINET
  - `zuzycie_dol_lacznie` = `zuzycie_dol` + `zuzycie_gabinet` (jeśli potrzebne)

**Zakładamy Opcję A** (bardziej prawdopodobna - podlicznik pokazuje sumę).

## 📝 Miejsca w kodzie wymagające zmian

### 1. `app/services/electricity/calculator.py`

#### Funkcja `calculate_gora_usage()` - **GŁÓWNA ZMIANA**

**Obecny kod:**
```python
def calculate_gora_usage(
    dom_usage: Dict[str, Optional[float]],
    dol_usage: Dict[str, Optional[float]],
    gabinet_usage: float
) -> Dict[str, Optional[float]]:
    """
    Oblicza zużycie dla GÓRA (brak licznika, obliczane).
    GÓRA = DOM - (DÓŁ + GABINET)
    """
    # Jeśli mamy rozdzielone taryfy
    if dom_usage['zuzycie_dom_I'] is not None and dol_usage['zuzycie_dol_I'] is not None:
        zuzycie_I = dom_usage['zuzycie_dom_I'] - dol_usage['zuzycie_dol_I']
        zuzycie_II = dom_usage['zuzycie_dom_II'] - dol_usage['zuzycie_dol_II']
        zuzycie_lacznie = zuzycie_I + zuzycie_II  # ❌ BŁĄD: nie odejmuje GABINET
        # ...
    
    # Jeśli mamy tylko łączne zużycie
    zuzycie_lacznie = dom_usage['zuzycie_dom_lacznie'] - dol_usage['zuzycie_dol_lacznie'] - gabinet_usage  # ❌ Odejmuje GABINET
```

**Nowy kod:**
```python
def calculate_gora_usage(
    dom_usage: Dict[str, Optional[float]],
    dol_usage: Dict[str, Optional[float]],
    gabinet_usage: float  # Parametr nadal potrzebny dla kompatybilności, ale nie używany w obliczeniach
) -> Dict[str, Optional[float]]:
    """
    Oblicza zużycie dla GÓRA (brak licznika, obliczane).
    GÓRA = DOM - DÓŁ
    
    Uwaga: W nowej strukturze DÓŁ jest podlicznikiem DOM i zawiera GABINET,
    więc GABINET nie jest odejmowany osobno.
    """
    # Jeśli mamy rozdzielone taryfy (oba dwutaryfowe)
    if dom_usage['zuzycie_dom_I'] is not None and dol_usage['zuzycie_dol_I'] is not None:
        zuzycie_I = dom_usage['zuzycie_dom_I'] - dol_usage['zuzycie_dol_I']
        zuzycie_II = dom_usage['zuzycie_dom_II'] - dol_usage['zuzycie_dol_II']
        zuzycie_lacznie = zuzycie_I + zuzycie_II  # ✅ DÓŁ już zawiera GABINET
        return {
            'zuzycie_gora_I': round(zuzycie_I, 4),
            'zuzycie_gora_II': round(zuzycie_II, 4),
            'zuzycie_gora_lacznie': round(zuzycie_lacznie, 4)
        }
    
    # Jeśli mamy tylko łączne zużycie
    zuzycie_lacznie = dom_usage['zuzycie_dom_lacznie'] - dol_usage['zuzycie_dol_lacznie']  # ✅ Nie odejmujemy GABINET
    return {
        'zuzycie_gora_I': None,
        'zuzycie_gora_II': None,
        'zuzycie_gora_lacznie': round(zuzycie_lacznie, 4)
    }
```

**Zmiany:**
- Usunięcie odejmowania `gabinet_usage` z obliczeń
- Aktualizacja komentarzy i dokumentacji
- Parametr `gabinet_usage` można zostawić dla kompatybilności wstecznej lub usunąć

### 2. Komentarze i dokumentacja

#### `app/models/electricity.py`
```python
# Obecnie:
# - GÓRA: obliczane (DOM - DÓŁ - GABINET)

# Po zmianie:
# - GÓRA: obliczane (DOM - DÓŁ)
# - GABINET: podlicznik DÓŁ (zagnieżdżony)
```

#### `app/services/electricity/calculator.py`
```python
# Obecnie:
# Obsługuje:
# - Obliczanie zużycia dla DOM, DÓŁ, GABINET i GÓRA

# Po zmianie:
# Obsługuje:
# - Obliczanie zużycia dla DOM, DÓŁ, GABINET i GÓRA
# - Struktura: DOM → DÓŁ → GABINET (zagnieżdżona)
```

### 3. Testy jednostkowe

#### `tests/test_electricity_calculator.py`

**Obecne testy wymagają aktualizacji:**

```python
# Przykład testu - przed zmianą:
def test_gora_calculation():
    dom_usage = {'zuzycie_dom_lacznie': 300.0}
    dol_usage = {'zuzycie_dol_lacznie': 150.0}
    gabinet_usage = 50.0
    
    result = calculate_gora_usage(dom_usage, dol_usage, gabinet_usage)
    assert result['zuzycie_gora_lacznie'] == 100.0  # 300 - 150 - 50

# Po zmianie:
def test_gora_calculation():
    dom_usage = {'zuzycie_dom_lacznie': 300.0}
    dol_usage = {'zuzycie_dol_lacznie': 200.0}  # DÓŁ zawiera już GABINET (150 + 50)
    gabinet_usage = 50.0  # Nie używane w obliczeniach
    
    result = calculate_gora_usage(dom_usage, dol_usage, gabinet_usage)
    assert result['zuzycie_gora_lacznie'] == 100.0  # 300 - 200
```

### 4. Inne miejsca (sprawdzenie)

#### `app/services/electricity/manager.py`
- Sprawdzić, czy są jakieś założenia dotyczące struktury
- Funkcja `calculate_bill_costs()` - prawdopodobnie bez zmian

#### `tools/calculate_bill_logic.py`
- Sprawdzić logikę proporcjonalnego dzielenia - może wymagać aktualizacji

#### Dokumentacja
- `docs/CALCULATION_LOGIC.md` - aktualizacja
- `prad_analiza.md` - aktualizacja przykładów

## 🛠️ Plan implementacji

### Krok 1: Przygotowanie (niskie ryzyko)
1. ✅ Utworzenie dokumentacji zmian (ten plik)
2. ✅ Analiza wpływu na istniejące dane
3. ✅ Przygotowanie testów jednostkowych

### Krok 2: Zmiana funkcji `calculate_gora_usage()` (średnie ryzyko)
1. Zmodyfikować funkcję w `app/services/electricity/calculator.py`
2. Zaktualizować komentarze i docstringi
3. Dodać parametr konfiguracyjny (opcjonalnie) dla kompatybilności wstecznej

### Krok 3: Aktualizacja testów (niskie ryzyko)
1. Zaktualizować istniejące testy w `tests/test_electricity_calculator.py`
2. Dodać nowe testy dla nowej struktury
3. Uruchomić wszystkie testy

### Krok 4: Aktualizacja dokumentacji (niskie ryzyko)
1. Zaktualizować komentarze w kodzie
2. Zaktualizować `docs/CALCULATION_LOGIC.md`
3. Zaktualizować `prad_analiza.md`

### Krok 5: Weryfikacja (wysokie ryzyko)
1. Sprawdzić obliczenia na rzeczywistych danych
2. Porównać wyniki przed i po zmianie
3. Zweryfikować, czy rachunki są generowane poprawnie

## ⚠️ Uwagi i ryzyka

### 1. Kompatybilność wsteczna
- **Problem:** Istniejące dane mogą być obliczone według starej logiki
- **Rozwiązanie:** 
  - Dodać flagę konfiguracyjną `meter_structure_version` w bazie danych
  - Albo: migracja danych (przeliczenie wszystkich rachunków)

### 2. Walidacja danych
- **Problem:** Jak sprawdzić, czy odczyty są zgodne z nową strukturą?
- **Rozwiązanie:**
  - Dodać walidację: `DOM >= DÓŁ >= GABINET` (dla nowej struktury)
  - Dodać walidację: `DOM >= DÓŁ + GABINET` (dla starej struktury)

### 3. Migracja danych
- **Problem:** Czy przeliczyć istniejące rachunki?
- **Rozwiązanie:**
  - Opcja A: Zostawić stare rachunki, nowe obliczać według nowej logiki
  - Opcja B: Przeliczyć wszystkie rachunki (wymaga backupu)

## 📋 Checklist implementacji

- [ ] 1. Zmodyfikować `calculate_gora_usage()` w `app/services/electricity/calculator.py`
- [ ] 2. Zaktualizować komentarze w `app/models/electricity.py`
- [ ] 3. Zaktualizować testy w `tests/test_electricity_calculator.py`
- [ ] 4. Zaktualizować dokumentację w `docs/`
- [ ] 5. Dodać walidację danych (opcjonalnie)
- [ ] 6. Dodać flagę konfiguracyjną dla kompatybilności wstecznej (opcjonalnie)
- [ ] 7. Przetestować na rzeczywistych danych
- [ ] 8. Zweryfikować generowanie rachunków

## 💡 Najłatwiejsza implementacja

**Najprostsze podejście:**
1. Zmienić tylko funkcję `calculate_gora_usage()` - usunąć odejmowanie GABINET
2. Zaktualizować komentarze
3. Zaktualizować testy
4. Przetestować na nowych danych

**Bez kompatybilności wstecznej:**
- Założyć, że wszystkie nowe odczyty będą zgodne z nową strukturą
- Stare rachunki pozostają bez zmian

**Z kompatybilnością wsteczną:**
- Dodać parametr `meter_structure` do `ElectricityReading` lub konfiguracji
- W `calculate_gora_usage()` sprawdzać strukturę i wybierać odpowiednią formułę

