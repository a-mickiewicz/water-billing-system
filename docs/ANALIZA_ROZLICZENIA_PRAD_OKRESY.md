# Analiza rozliczania prądu z uwzględnieniem okresów i zmian cen

## Problem

Obecna implementacja **NIE uwzględnia**:
1. Okresów rozliczeniowych z faktury (gdzie mogą być różne ceny za kWh)
2. Zazębiania się okresów dwumiesięcznych najemców z okresami na fakturze
3. Zmian cen w trakcie okresu faktury

## Obecna implementacja (BŁĘDNA)

### Jak działa obecnie:

```python
# app/services/electricity/manager.py - generate_bills_for_period()

1. Znajduje fakturę dla okresu (np. 2024-02)
   - Sprawdza czy data_poczatku_okresu <= period_date <= data_konca_okresu
   - Bierze CAŁĄ fakturę (np. 01.11.2023 - 31.10.2024)

2. Znajduje blankiet dla okresu (ale go NIE UŻYWA!)
   - blankiet = self.find_blankiet_for_period(db, invoice.id, data)
   - Blankiet jest znaleziony, ale NIE jest używany w obliczeniach!

3. Oblicza koszty używając CAŁEJ faktury:
   - calculate_kwh_cost(invoice.id, db) - oblicza koszt dla CAŁEJ faktury
   - calculate_bill_costs() - używa ogolem_sprzedaz_energii i ogolem_usluga_dystrybucji
   - NIE uwzględnia okresów z różnymi cenami!
```

### Przykład błędu:

**Faktura:** P/23666363/0002/24
- Okres faktury: 01.11.2023 - 31.10.2024
- W trakcie tego okresu były zmiany cen:
  - Okres I: 01.11.2023 - 31.12.2023 (cena 0.50 zł/kWh)
  - Okres II: 01.01.2024 - 31.03.2024 (cena 0.55 zł/kWh)
  - Okres III: 01.04.2024 - 31.10.2024 (cena 0.60 zł/kWh)

**Rachunek najemcy:** 2024-02 (luty 2024)
- Okres najemcy: 01.02.2024 - 29.02.2024
- Powinien uwzględniać:
  - Część w Okresie II (01.02.2024 - 31.03.2024) - cena 0.55 zł/kWh
  - Część w Okresie III (01.04.2024 - 29.02.2024) - NIE, to jest błąd!
  - Faktycznie: cały luty jest w Okresie II

**Obecna implementacja:**
- Używa średniej ceny z CAŁEJ faktury (0.50 + 0.55 + 0.60) / 3 = 0.55 zł/kWh
- LUB używa proporcji z ogolem_sprzedaz_energii (która jest za CAŁY okres faktury)
- **BŁĄD:** Nie uwzględnia, że luty jest w Okresie II z ceną 0.55 zł/kWh

## Poprzednia implementacja (POPRAWNA)

### Jak działała poprzednia logika (w tools/calculate_bill_logic.py):

```python
# I. Wyłanianie okresów z faktury
get_periods_from_readings() - wyłania okresy z odczytów faktury
get_distribution_periods() - wyłania okresy z opłat dystrybucyjnych i sprzedaży energii

# II. Obliczanie rachunku z uwzględnieniem zazębiania
calculate_bill_for_period(
    tenant_period_start,  # np. 01.02.2024
    tenant_period_end,    # np. 29.02.2024
    distribution_periods, # okresy z różnymi cenami
    usage_kwh_dzienna,
    usage_kwh_nocna
)

# III. Logika:
1. Znajduje overlapping periods (zazębiające się okresy)
2. Dla każdego overlapping period:
   - Oblicza liczbę dni zazębienia
   - Oblicza proporcję: dni_zazębienia / dni_całego_okresu_najemcy
   - Dzieli zużycie proporcjonalnie
   - Stosuje cenę z tego okresu
3. Sumuje koszty ze wszystkich overlapping periods
```

### Przykład poprawnego obliczenia:

**Okres najemcy:** 01.02.2024 - 29.02.2024 (29 dni)
**Zużycie:** 100 kWh (dzienna: 70 kWh, nocna: 30 kWh)

**Okresy z faktury:**
- Okres I: 01.11.2023 - 31.12.2023 (cena: 0.50 zł/kWh)
- Okres II: 01.01.2024 - 31.03.2024 (cena: 0.55 zł/kWh)
- Okres III: 01.04.2024 - 31.10.2024 (cena: 0.60 zł/kWh)

**Overlapping periods:**
- Okres najemcy (01.02 - 29.02) × Okres II (01.01 - 31.03)
  - Zazębienie: 01.02.2024 - 29.02.2024 (29 dni)
  - Proporcja: 29 / 29 = 1.0 (100%)
  - Zużycie dla tej części: 100 kWh
  - Koszt: 100 kWh × 0.55 zł/kWh = 55.00 zł

**Wynik:** 55.00 zł (używa ceny z Okresu II)

## Różnice między implementacjami

| Aspekt | Obecna (BŁĘDNA) | Poprzednia (POPRAWNA) |
|--------|-----------------|----------------------|
| **Okresy z faktury** | NIE uwzględnia | TAK - wyłania okresy z odczytów i opłat |
| **Zmiany cen** | NIE uwzględnia | TAK - stosuje różne ceny dla różnych okresów |
| **Zazębianie okresów** | NIE uwzględnia | TAK - oblicza overlapping periods |
| **Proporcje dni** | NIE oblicza | TAK - dzieli zużycie proporcjonalnie do dni |
| **Blankiety** | Znajduje ale NIE używa | Używa do wyłaniania okresów |
| **Rozliczenie_okresy** | NIE używa | Używa do wyłaniania okresów |

## Szczegółowa analiza obecnej implementacji

### 1. generate_bills_for_period() - linia 327

```python
def generate_bills_for_period(self, db: Session, data: str):
    # 1. Znajduje fakturę dla okresu
    invoice = ...  # Bierze CAŁĄ fakturę
    
    # 2. Znajduje blankiet (ale NIE używa!)
    blankiet = self.find_blankiet_for_period(db, invoice.id, data)
    # ⚠️ BŁĄD: blankiet jest znaleziony, ale NIE jest używany w obliczeniach!
    
    # 3. Oblicza koszt dla CAŁEJ faktury
    koszty_kwh = calculate_kwh_cost(invoice.id, db)
    # ⚠️ BŁĄD: oblicza koszt dla CAŁEJ faktury, nie dla okresu!
    
    # 4. Oblicza koszty używając CAŁEJ faktury
    costs = self.calculate_bill_costs(invoice, usage_data, local.local, db)
    # ⚠️ BŁĄD: używa ogolem_sprzedaz_energii (za CAŁY okres faktury)
```

### 2. calculate_bill_costs() - linia 123

```python
def calculate_bill_costs(self, invoice, usage_data, local_name, db):
    # Dla taryfy dwutaryfowej:
    koszty_kwh = calculate_kwh_cost(invoice.id, db)
    # ⚠️ BŁĄD: oblicza koszt dla CAŁEJ faktury, nie dla okresu najemcy
    
    koszt_sredni_wazony = koszt_dzienna * 0.7 + koszt_nocna * 0.3
    energy_cost_net = koszt_sredni_wazony * local_usage
    # ⚠️ BŁĄD: używa jednej ceny dla całego zużycia, nie uwzględnia zmian cen
    
    # Dla taryfy całodobowej:
    usage_ratio = local_usage / total_usage
    energy_cost_gross = invoice.ogolem_sprzedaz_energii * usage_ratio
    # ⚠️ BŁĄD: używa ogolem_sprzedaz_energii (za CAŁY okres faktury), 
    # nie uwzględnia, że okres najemcy może być tylko częścią okresu faktury
```

### 3. calculate_kwh_cost() - app/services/electricity/cost_calculator.py

```python
def calculate_kwh_cost(invoice_id: int, db: Session):
    # Pobiera sprzedaż energii i opłaty dystrybucyjne dla CAŁEJ faktury
    sprzedaz = db.query(ElectricityInvoiceSprzedazEnergii).filter(...).all()
    oplaty = db.query(ElectricityInvoiceOplataDystrybucyjna).filter(...).all()
    
    # Sumuje wszystkie pozycje z CAŁEJ faktury
    # ⚠️ BŁĄD: nie uwzględnia okresów z różnymi cenami!
```

## Co powinno być zrobione (poprawna logika)

### Krok 1: Wyłanianie okresów z faktury

```python
def get_distribution_periods_from_invoice(db, invoice):
    """
    Wyłania okresy z faktury, gdzie mogą być różne ceny.
    
    Źródła okresów:
    1. electricity_invoice_rozliczenie_okresy (jeśli są)
    2. electricity_invoice_oplaty_dystrybucyjne (grupowane po data)
    3. electricity_invoice_sprzedaz_energii (grupowane po data)
    
    Dla każdego okresu:
    - data_od (początek okresu)
    - data_do (koniec okresu)
    - cena_1kwh_dzienna (netto)
    - cena_1kwh_nocna (netto)
    - cena_1kwh_calodobowa (netto)
    - suma_oplat_stalych (netto)
    """
```

### Krok 2: Obliczanie zazębiających się okresów

```python
def calculate_bill_for_period(
    tenant_period_start: date,  # np. 01.02.2024
    tenant_period_end: date,    # np. 29.02.2024
    distribution_periods: List[Dict],  # okresy z faktury
    usage_kwh_dzienna: float,
    usage_kwh_nocna: float
):
    """
    Oblicza rachunek uwzględniając zazębianie się okresów.
    
    1. Znajduje overlapping periods:
       - Dla każdego okresu z faktury sprawdza czy zazębia się z okresem najemcy
       - Oblicza daty zazębienia: max(start1, start2) do min(end1, end2)
    
    2. Dla każdego overlapping period:
       - Oblicza liczbę dni zazębienia
       - Oblicza proporcję: dni_zazębienia / dni_okresu_najemcy
       - Dzieli zużycie proporcjonalnie: usage_part = usage_total * proportion
       - Stosuje cenę z tego okresu: cost = usage_part * cena_1kwh
       - Dzieli opłaty stałe proporcjonalnie: fixed_cost = suma_oplat_stalych * proportion
    
    3. Sumuje koszty ze wszystkich overlapping periods
    """
```

### Krok 3: Przykład poprawnego obliczenia

**Okres najemcy:** 01.02.2024 - 29.02.2024 (29 dni)
**Zużycie:** 100 kWh (dzienna: 70 kWh, nocna: 30 kWh)

**Okresy z faktury:**
- Okres A: 01.11.2023 - 31.12.2023
  - cena_dzienna: 0.50 zł/kWh, cena_nocna: 0.40 zł/kWh
- Okres B: 01.01.2024 - 31.03.2024
  - cena_dzienna: 0.55 zł/kWh, cena_nocna: 0.45 zł/kWh
- Okres C: 01.04.2024 - 31.10.2024
  - cena_dzienna: 0.60 zł/kWh, cena_nocna: 0.50 zł/kWh

**Overlapping periods:**
- Okres najemcy × Okres B:
  - Zazębienie: 01.02.2024 - 29.02.2024 (29 dni)
  - Proporcja: 29 / 29 = 1.0
  - Zużycie dzienna: 70 kWh × 1.0 = 70 kWh
  - Zużycie nocna: 30 kWh × 1.0 = 30 kWh
  - Koszt energii: (70 × 0.55) + (30 × 0.45) = 38.50 + 13.50 = 52.00 zł
  - Opłaty stałe: suma_oplat_stalych_okres_B × 1.0

**Wynik:** 52.00 zł + opłaty stałe

## Błędy w obecnej implementacji

### Błąd 1: Nie uwzględnia okresów z faktury
- **Obecnie:** Używa `ogolem_sprzedaz_energii` (za CAŁY okres faktury)
- **Powinno:** Wyłonić okresy z faktury i użyć odpowiednich cen

### Błąd 2: Nie uwzględnia zazębiania się okresów
- **Obecnie:** Traktuje okres najemcy jako jeden blok
- **Powinno:** Znaleźć overlapping periods i obliczyć proporcje dni

### Błąd 3: Nie używa blankietów
- **Obecnie:** Znajduje blankiet ale go NIE używa
- **Powinno:** Użyć blankietów do wyłaniania okresów z różnymi cenami

### Błąd 4: Nie uwzględnia rozliczenie_okresy
- **Obecnie:** Tabela `electricity_invoice_rozliczenie_okresy` istnieje, ale NIE jest używana
- **Powinno:** Użyć `rozliczenie_okresy` do wyłaniania okresów

## Szczegółowy przykład zazębiania się okresów

### Przykład 1: Okres najemcy w jednym okresie faktury

**Faktura:** P/23666363/0002/24
- Okres faktury: 01.11.2023 - 31.10.2024
- Okresy z różnymi cenami:
  - Okres A: 01.11.2023 - 31.12.2023 (cena: 0.50 zł/kWh)
  - Okres B: 01.01.2024 - 31.03.2024 (cena: 0.55 zł/kWh)
  - Okres C: 01.04.2024 - 31.10.2024 (cena: 0.60 zł/kWh)

**Rachunek najemcy:** 2024-02 (luty 2024)
- Okres najemcy: 01.02.2024 - 29.02.2024
- Zużycie: 100 kWh (dzienna: 70 kWh, nocna: 30 kWh)

**Obecna implementacja (BŁĘDNA):**
```
1. Znajduje fakturę: P/23666363/0002/24
2. Używa ogolem_sprzedaz_energii (za CAŁY okres 01.11.2023 - 31.10.2024)
3. Oblicza proporcję: 100 kWh / 3122 kWh (całkowite zużycie z faktury)
4. Koszt = ogolem_sprzedaz_energii * proporcja
   ⚠️ BŁĄD: Używa średniej ceny z CAŁEJ faktury, nie uwzględnia że luty jest w Okresie B
```

**Poprawna implementacja:**
```
1. Wyłania okresy z faktury:
   - Okres A: 01.11.2023 - 31.12.2023 (cena: 0.50 zł/kWh)
   - Okres B: 01.01.2024 - 31.03.2024 (cena: 0.55 zł/kWh)
   - Okres C: 01.04.2024 - 31.10.2024 (cena: 0.60 zł/kWh)

2. Znajduje overlapping periods:
   - Okres najemcy (01.02 - 29.02) × Okres B (01.01 - 31.03)
     * Zazębienie: 01.02.2024 - 29.02.2024 (29 dni)
     * Proporcja: 29 / 29 = 1.0 (100%)

3. Oblicza koszt:
   - Zużycie dzienna: 70 kWh × 1.0 = 70 kWh
   - Zużycie nocna: 30 kWh × 1.0 = 30 kWh
   - Koszt energii: (70 × 0.55) + (30 × 0.45) = 38.50 + 13.50 = 52.00 zł
   - Opłaty stałe: suma_oplat_stalych_okres_B × 1.0
```

### Przykład 2: Okres najemcy zazębia się z dwoma okresami faktury

**Faktura:** P/23666363/0002/24
- Okres A: 01.11.2023 - 31.12.2023 (cena: 0.50 zł/kWh)
- Okres B: 01.01.2024 - 31.03.2024 (cena: 0.55 zł/kWh)
- Okres C: 01.04.2024 - 31.10.2024 (cena: 0.60 zł/kWh)

**Rachunek najemcy:** 2024-03 (marzec 2024)
- Okres najemcy: 01.03.2024 - 31.03.2024 (31 dzień)
- Zużycie: 120 kWh (dzienna: 84 kWh, nocna: 36 kWh)

**Poprawna implementacja:**
```
1. Wyłania okresy z faktury (jak wyżej)

2. Znajduje overlapping periods:
   - Okres najemcy (01.03 - 31.03) × Okres B (01.01 - 31.03)
     * Zazębienie: 01.03.2024 - 31.03.2024 (31 dzień)
     * Proporcja: 31 / 31 = 1.0 (100%)

3. Oblicza koszt:
   - Zużycie dzienna: 84 kWh × 1.0 = 84 kWh
   - Zużycie nocna: 36 kWh × 1.0 = 36 kWh
   - Koszt energii: (84 × 0.55) + (36 × 0.45) = 46.20 + 16.20 = 62.40 zł
```

**Rachunek najemcy:** 2024-04 (kwiecień 2024)
- Okres najemcy: 01.04.2024 - 30.04.2024 (30 dni)
- Zużycie: 150 kWh (dzienna: 105 kWh, nocna: 45 kWh)

**Poprawna implementacja:**
```
1. Wyłania okresy z faktury (jak wyżej)

2. Znajduje overlapping periods:
   - Okres najemcy (01.04 - 30.04) × Okres C (01.04 - 31.10)
     * Zazębienie: 01.04.2024 - 30.04.2024 (30 dni)
     * Proporcja: 30 / 30 = 1.0 (100%)

3. Oblicza koszt:
   - Zużycie dzienna: 105 kWh × 1.0 = 105 kWh
   - Zużycie nocna: 45 kWh × 1.0 = 45 kWh
   - Koszt energii: (105 × 0.60) + (45 × 0.50) = 63.00 + 22.50 = 85.50 zł
```

### Przykład 3: Okres najemcy zazębia się z DWOMA okresami faktury

**Rachunek najemcy:** 2024-03/04 (marzec-kwiecień 2024) - dwumiesięczny
- Okres najemcy: 01.03.2024 - 30.04.2024 (61 dni)
- Zużycie: 250 kWh (dzienna: 175 kWh, nocna: 75 kWh)

**Poprawna implementacja:**
```
1. Wyłania okresy z faktury:
   - Okres B: 01.01.2024 - 31.03.2024 (cena: 0.55 zł/kWh)
   - Okres C: 01.04.2024 - 31.10.2024 (cena: 0.60 zł/kWh)

2. Znajduje overlapping periods:
   
   a) Okres najemcy (01.03 - 30.04) × Okres B (01.01 - 31.03)
      * Zazębienie: 01.03.2024 - 31.03.2024 (31 dzień)
      * Proporcja: 31 / 61 = 0.5082 (50.82%)
      * Zużycie dzienna: 175 kWh × 0.5082 = 88.94 kWh
      * Zużycie nocna: 75 kWh × 0.5082 = 38.12 kWh
      * Koszt energii: (88.94 × 0.55) + (38.12 × 0.45) = 48.92 + 17.15 = 66.07 zł
      * Opłaty stałe: suma_oplat_stalych_okres_B × 0.5082
   
   b) Okres najemcy (01.03 - 30.04) × Okres C (01.04 - 31.10)
      * Zazębienie: 01.04.2024 - 30.04.2024 (30 dni)
      * Proporcja: 30 / 61 = 0.4918 (49.18%)
      * Zużycie dzienna: 175 kWh × 0.4918 = 86.06 kWh
      * Zużycie nocna: 75 kWh × 0.4918 = 36.89 kWh
      * Koszt energii: (86.06 × 0.60) + (36.89 × 0.50) = 51.64 + 18.45 = 70.09 zł
      * Opłaty stałe: suma_oplat_stalych_okres_C × 0.4918

3. Sumuje koszty:
   - Koszt energii: 66.07 + 70.09 = 136.16 zł
   - Opłaty stałe: (suma_B × 0.5082) + (suma_C × 0.4918)
   - RAZEM: 136.16 + opłaty stałe
```

## Jak wyłaniać okresy z faktury

### Metoda 1: Z opłat dystrybucyjnych (get_distribution_periods)

```python
def get_distribution_periods(db, invoice):
    """
    Wyłania okresy z opłat dystrybucyjnych i sprzedaży energii.
    
    Logika:
    1. Pobiera opłaty dystrybucyjne, sortowane po dacie
    2. Grupuje opłaty po datach (każda unikalna data = nowy okres)
    3. Dla każdego okresu:
       - Okres zaczyna się: data końca poprzedniego okresu + 1 dzień
       - Okres kończy się: data z opłat
       - Pobiera sprzedaż energii dla tego okresu (po kolejności)
       - Oblicza ceny za 1 kWh (sprzedaż + opłaty zmienne)
       - Sumuje opłaty stałe
    """
```

**Przykład:**
```
Opłaty dystrybucyjne:
- data: 31.12.2023 → Okres I: 01.11.2023 - 31.12.2023
- data: 31.03.2024 → Okres II: 01.01.2024 - 31.03.2024
- data: 31.10.2024 → Okres III: 01.04.2024 - 31.10.2024
```

### Metoda 2: Z rozliczenie_okresy (jeśli są dostępne)

```python
def get_periods_from_rozliczenie_okresy(db, invoice):
    """
    Wyłania okresy z tabeli electricity_invoice_rozliczenie_okresy.
    
    Jeśli faktura ma rozliczenie_okresy, użyj ich do wyłaniania okresów.
    Każdy okres ma:
    - data_okresu (data końca okresu)
    - numer_okresu (kolejność)
    """
```

### Metoda 3: Z blankietów (fallback)

```python
def get_periods_from_blankiety(db, invoice):
    """
    Wyłania okresy z blankietów (jeśli nie ma rozliczenie_okresy).
    
    Każdy blankiet ma:
    - poczatek_podokresu
    - koniec_podokresu
    - ilosc_dzienna_kwh, ilosc_nocna_kwh (dla dwutaryfowej)
    - kwota_brutto (można obliczyć cenę)
    """
```

## Rekomendacja

Należy przywrócić logikę z `tools/calculate_bill_logic.py`:
1. Wyłanianie okresów z faktury (z odczytów, opłat, sprzedaży energii)
2. Obliczanie overlapping periods
3. Proporcjonalne dzielenie zużycia i kosztów
4. Stosowanie różnych cen dla różnych części okresu najemcy

### Krok po kroku:

1. **Wyłonić okresy z faktury:**
   - Użyć `get_distribution_periods()` z `tools/calculate_bill_logic.py`
   - Lub użyć `rozliczenie_okresy` jeśli są dostępne
   - Każdy okres ma: data_od, data_do, cena_1kwh_dzienna, cena_1kwh_nocna, suma_oplat_stalych

2. **Dla każdego rachunku najemcy:**
   - Określić okres najemcy (data_odczytu_licznika z poprzedniego i obecnego odczytu)
   - Znaleźć overlapping periods z okresami faktury
   - Obliczyć proporcje dni dla każdego overlapping period
   - Podzielić zużycie proporcjonalnie
   - Zastosować odpowiednie ceny
   - Zsumować koszty

3. **Zintegrować z obecnym systemem:**
   - Zmodyfikować `calculate_bill_costs()` w `ElectricityBillingManager`
   - Dodać funkcję `get_distribution_periods()` do `ElectricityBillingManager`
   - Dodać funkcję `calculate_bill_for_period_with_overlapping()` do `ElectricityBillingManager`

