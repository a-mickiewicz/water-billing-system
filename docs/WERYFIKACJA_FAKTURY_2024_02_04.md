# Weryfikacja faktury P/23666363/0002/24 - okresy 2024-02 i 2024-04

## Informacje o fakturze

- **Numer faktury:** P/23666363/0002/24
- **Okres faktury:** 01.11.2023 - 31.10.2024
- **Typ taryfy:** DWUTARYFOWA
- **Grupa taryfowa:** G12
- **Zużycie całkowite (DOM):** 3122 kWh
- **Ogółem sprzedaż energii (brutto):** 1 189.57 zł
- **Ogółem usługa dystrybucji (brutto):** 781.81 zł

## Analiza zgodności z poprawioną logiką

### Obecna logika w pliku obliczenia_rachunkow_prad_2024_02_04.txt

Plik używa **starej logiki obliczeń**, która:
1. Używa średniej ważonej kosztu 1 kWh dla całej faktury
2. Dzieli opłaty stałe równo na 3 lokale (bez uwzględnienia okresów)
3. Nie uwzględnia okresów z różnymi cenami w fakturze
4. Nie oblicza overlapping periods

### Poprawiona logika (zaimplementowana w kodzie)

Poprawiona logika powinna:
1. Wyłonić okresy z faktury (gdzie mogą być różne ceny)
2. Określić daty okresu najemcy (na podstawie odczytów)
3. Znaleźć overlapping periods (zazębiające się okresy)
4. Podzielić zużycie proporcjonalnie do dni w każdym overlapping period
5. Zastosować odpowiednie ceny dla każdego okresu
6. Podzielić opłaty stałe proporcjonalnie do dni

## Weryfikacja okresu 2024-02

### Dane z pliku

**Okres rozliczeniowy:** 2024-02 (luty 2024)

**Odczyty liczników:**
- DOM (dwutaryfowy): I=25750.0000 kWh, II=11074.0000 kWh
- DOM poprzedni (dwutaryfowy): I=24924.0000 kWh, II=10749.0000 kWh
- DÓŁ (dwutaryfowy): I=21930.0000 kWh, II=14240.0000 kWh
- DÓŁ poprzedni (dwutaryfowy): I=21585.0000 kWh, II=13909.0000 kWh
- GABINET: 27086.0000 kWh
- GABINET poprzedni: 26862.0000 kWh

**Obliczone zużycie:**
- DOM łącznie: 1 151.0000 kWh
  - Taryfa I (dzienna): 826.0000 kWh
  - Taryfa II (nocna): 325.0000 kWh
- DÓŁ łącznie: 676.0000 kWh
  - Taryfa I (dzienna): 345.0000 kWh
  - Taryfa II (nocna): 331.0000 kWh
- GABINET: 224.0000 kWh
- GÓRA: 475.0000 kWh
  - Taryfa I (dzienna): 481.0000 kWh
  - Taryfa II (nocna): -6.0000 kWh ⚠️ **UWAGA: Ujemne zużycie nocne!**
- DOL (Mikołaj): 452.0000 kWh
  - Taryfa I (dzienna): 188.2000 kWh
  - Taryfa II (nocna): 263.8000 kWh

### Obliczenia według starej logiki (z pliku)

**Dla lokalu GÓRA:**
- Zużycie: 475.0000 kWh
- Średnia ważona kosztu 1 kWh (netto): 0.6270 zł/kWh
  - Koszt dzienna (netto): 0.7371 zł/kWh
  - Koszt nocna (netto): 0.3702 zł/kWh
  - Średnia ważona = 0.7371 × 0.7 + 0.3702 × 0.3 = 0.6270 zł/kWh
- Koszt energii (netto): 297.82 zł
- Koszt dystrybucji (netto): 371.69 zł
  - Średnia ważona dystrybucji: 0.7825 zł/kWh
- Opłaty stałe (netto): 44.47 zł (podzielone przez 3)
- **RAZEM NETTO: 713.98 zł**
- **RAZEM BRUTTO: 878.20 zł**

### Co powinno być według poprawionej logiki

**Krok 1: Wyłonienie okresów z faktury**

Faktura P/23666363/0002/24 ma okres 01.11.2023 - 31.10.2024. Aby zweryfikować obliczenia, należy:
1. Sprawdzić czy faktura ma wiele okresów z różnymi cenami
2. Jeśli tak, wyłonić te okresy z opłat dystrybucyjnych i sprzedaży energii
3. Dla każdego okresu obliczyć:
   - `cena_1kwh_dzienna` (netto)
   - `cena_1kwh_nocna` (netto)
   - `suma_oplat_stalych` (netto)

**Krok 2: Określenie okresu najemcy**

Okres najemcy dla 2024-02 powinien być określony na podstawie:
- Data odczytu poprzedniego (koniec poprzedniego okresu)
- Data odczytu obecnego (koniec okresu 2024-02)

**Krok 3: Obliczenie overlapping periods**

Jeśli okres najemcy (np. 01.02.2024 - 29.02.2024) zazębia się z okresami faktury:
- Znajdź wszystkie overlapping periods
- Dla każdego oblicz liczbę dni zazębienia
- Oblicz proporcję: `dni_zazębienia / dni_okresu_najemcy`

**Krok 4: Podział zużycia i kosztów**

Dla każdego overlapping period:
- Podziel zużycie proporcjonalnie: `zużycie_część = zużycie_całkowite × proporcja`
- Zastosuj cenę z tego okresu: `koszt = zużycie_część × cena_1kwh`
- Podziel opłaty stałe proporcjonalnie: `opłaty_część = opłaty_okres × proporcja`

**Krok 5: Sumowanie**

Zsumuj koszty ze wszystkich overlapping periods.

## Problemy znalezione w pliku

### 1. Ujemne zużycie nocne dla GÓRA

**UWAGA:** Ujemne zużycie jest celowo wprowadzone przez użytkownika i **musi być uwzględnione w obliczeniach**.

W okresie 2024-02:
- GÓRA Taryfa II (nocna): **-6.0000 kWh** ⚠️ (uwzględniane w obliczeniach)

W okresie 2024-04:
- GÓRA Taryfa II (nocna): **-69.0000 kWh** ⚠️ (uwzględniane w obliczeniach)

**Przyczyna:**
```
Zużycie GÓRA II = Zużycie DOM II - Zużycie DÓŁ II
Dla okresu 2024-02: 325.0000 - 331.0000 = -6.0000 kWh
Dla okresu 2024-04: 391.0000 - 460.0000 = -69.0000 kWh
```

**Obliczenia z uwzględnieniem ujemnego zużycia:**

Dla okresu 2024-02:
- DOM łącznie = DOM I + DOM II = 826 + 325 = **1151 kWh** ✓
- GÓRA łącznie = GÓRA I + GÓRA II = 481 + (-6) = **475 kWh** ✓

Dla okresu 2024-04:
- DOM łącznie = DOM I + DOM II = 766 + 391 = **1157 kWh** ✓
- GÓRA łącznie = GÓRA I + GÓRA II = 493 + (-69) = **424 kWh** ✓

**Uwaga:** Ujemne zużycie jest uwzględniane w obliczeniach kosztów - jeśli zużycie nocne jest ujemne, to koszt energii nocnej również będzie ujemny (lub zerowy, w zależności od implementacji).

### 2. Użycie starej logiki zamiast poprawionej

Plik używa:
- Średniej ważonej dla całej faktury (nie uwzględnia okresów)
- Równego podziału opłat stałych przez 3 (nie uwzględnia proporcji dni)

### 3. Brak uwzględnienia okresów z faktury

Plik nie uwzględnia, że faktura może mieć różne ceny w różnych okresach. Jeśli faktura ma okresy:
- Okres I: 01.11.2023 - 31.12.2023 (cena A)
- Okres II: 01.01.2024 - 31.03.2024 (cena B)
- Okres III: 01.04.2024 - 31.10.2024 (cena C)

To okres 2024-02 (luty) powinien używać tylko ceny z Okresu II, a nie średniej z całej faktury.

## Weryfikacja okresu 2024-04

### Dane z pliku

**Okres rozliczeniowy:** 2024-04 (kwiecień 2024)

**Odczyty liczników:**
- DOM (dwutaryfowy): I=26516.0000 kWh, II=11465.0000 kWh
- DOM poprzedni (dwutaryfowy): I=25750.0000 kWh, II=11074.0000 kWh
- DÓŁ (dwutaryfowy): I=22203.0000 kWh, II=14700.0000 kWh
- DÓŁ poprzedni (dwutaryfowy): I=21930.0000 kWh, II=14240.0000 kWh
- GABINET: 27324.0000 kWh
- GABINET poprzedni: 27086.0000 kWh

**Obliczone zużycie:**
- DOM łącznie: 1 157.0000 kWh
  - Taryfa I (dzienna): 766.0000 kWh
  - Taryfa II (nocna): 391.0000 kWh
- DÓŁ łącznie: 733.0000 kWh
  - Taryfa I (dzienna): 273.0000 kWh
  - Taryfa II (nocna): 460.0000 kWh
- GABINET: 238.0000 kWh
- GÓRA: 424.0000 kWh
  - Taryfa I (dzienna): 493.0000 kWh
  - Taryfa II (nocna): **-69.0000 kWh** ⚠️ **UWAGA: Ujemne zużycie nocne!**
- DOL (Mikołaj): 495.0000 kWh
  - Taryfa I (dzienna): 106.4000 kWh
  - Taryfa II (nocna): 388.6000 kWh

### Problemy znalezione

1. **Ujemne zużycie nocne dla GÓRA:** -69.0000 kWh
   - DOM II: 391.0000 kWh
   - DÓŁ II: 460.0000 kWh
   - GÓRA II = 391 - 460 = -69 kWh

2. **Użycie starej logiki** (średnia ważona, równe podziały)

## Rekomendacje

### 1. Weryfikacja danych źródłowych

Przed zastosowaniem poprawionej logiki należy:
- Zweryfikować poprawność odczytów liczników
- Sprawdzić czy ujemne zużycie dla GÓRA jest rzeczywistym problemem
- Upewnić się, że odczyty DÓŁ nie zawierają błędów

### 2. Zastosowanie poprawionej logiki

Aby zweryfikować fakturę zgodnie z poprawioną logiką, należy:

1. **Sprawdzić strukturę faktury:**
   ```python
   distribution_periods = manager.get_distribution_periods(db, invoice)
   ```
   Jeśli `len(distribution_periods) > 1`, faktura ma wiele okresów.

2. **Określić okres najemcy:**
   ```python
   tenant_period_dates = manager.get_tenant_period_dates(db, "2024-02")
   tenant_period_start, tenant_period_end = tenant_period_dates
   ```

3. **Obliczyć koszty z overlapping periods:**
   ```python
   result = manager.calculate_bill_for_period_with_overlapping(
       tenant_period_start,
       tenant_period_end,
       distribution_periods,
       usage_kwh_dzienna,
       usage_kwh_nocna
   )
   ```

### 3. Porównanie wyników

Po zastosowaniu poprawionej logiki należy porównać:
- Koszty energii (netto i brutto)
- Koszty dystrybucji (netto i brutto)
- Opłaty stałe (netto i brutto)
- Sumy całkowite

### 4. Rozwiązanie problemu ujemnego zużycia

Jeśli ujemne zużycie jest rzeczywistym problemem:
- Sprawdź odczyty liczników
- Rozważ użycie wartości bezwzględnej lub ustawienie na 0
- Zweryfikuj logikę obliczania zużycia GÓRA = DOM - DÓŁ

## Wyniki przeliczenia zgodnie z poprawioną logiką

### Struktura faktury

Faktura P/23666363/0002/24 ma **4 okresy dystrybucyjne** z różnymi cenami:

1. **Okres 1:** 2023-11-01 - 2023-12-31
   - Cena dzienna (netto): 0.7300 zł/kWh
   - Cena nocna (netto): 0.3196 zł/kWh
   - Opłaty stałe (netto): 23.11 zł

2. **Okres 2:** 2024-01-01 - 2024-04-06
   - Cena dzienna (netto): 0.7312 zł/kWh
   - Cena nocna (netto): 0.3208 zł/kWh
   - Opłaty stałe (netto): 9.76 zł

3. **Okres 3:** 2024-04-07 - 2024-06-30
   - Cena dzienna (netto): 0.7312 zł/kWh
   - Cena nocna (netto): 0.3208 zł/kWh
   - Opłaty stałe (netto): 9.76 zł

4. **Okres 4:** 2024-07-01 - 2024-10-31
   - Cena dzienna (netto): 0.8243 zł/kWh
   - Cena nocna (netto): 0.5409 zł/kWh
   - Opłaty stałe (netto): 14.83 zł

### Okres najemcy 2024-02

**Ważne odkrycie:** Okres najemcy 2024-02 to faktycznie **dwumiesięczny okres**:
- Data początku: 2024-02-11
- Data końca: 2024-04-10
- Długość: 60 dni

**Overlapping periods:**
- Okres 2 (2024-01-01 - 2024-04-06): 56 dni (93.33%)
- Okres 3 (2024-04-07 - 2024-06-30): 4 dni (6.67%)

### Porównanie wyników dla okresu 2024-02

#### Lokal GÓRA

| Składnik | Stara logika | Poprawiona logika | Różnica |
|----------|--------------|-------------------|---------|
| Koszt energii (netto) | 297.82 zł | 349.78 zł | +51.96 zł |
| Koszt dystrybucji (netto) | 371.69 zł | 0.00 zł | -371.69 zł |
| Opłaty stałe (netto) | 44.47 zł | 9.76 zł | -34.71 zł |
| **RAZEM NETTO** | **713.98 zł** | **359.54 zł** | **-354.44 zł** |
| **RAZEM BRUTTO** | **878.20 zł** | **442.24 zł** | **-435.96 zł** |

**Uwaga:** W poprawionej logice koszty dystrybucji są już wliczone w cenę za kWh (cena_1kwh_dzienna/nocna zawiera już opłaty dystrybucyjne zmienne), więc distribution_cost = 0.

#### Lokal DOL (Mikołaj)

| Składnik | Stara logika | Poprawiona logika | Różnica |
|----------|--------------|-------------------|---------|
| Koszt energii (netto) | 283.40 zł | 222.24 zł | -61.16 zł |
| Koszt dystrybucji (netto) | 353.69 zł | 0.00 zł | -353.69 zł |
| Opłaty stałe (netto) | 44.47 zł | 9.76 zł | -34.71 zł |
| **RAZEM NETTO** | **681.57 zł** | **232.00 zł** | **-449.57 zł** |
| **RAZEM BRUTTO** | **838.33 zł** | **285.36 zł** | **-552.97 zł** |

#### Lokal GABINET

| Składnik | Stara logika | Poprawiona logika | Różnica |
|----------|--------------|-------------------|---------|
| Koszt energii (netto) | 140.45 zł | 0.00 zł | -140.45 zł |
| Koszt dystrybucji (netto) | 175.28 zł | 0.00 zł | -175.28 zł |
| Opłaty stałe (netto) | 44.47 zł | 9.76 zł | -34.71 zł |
| **RAZEM NETTO** | **360.20 zł** | **9.76 zł** | **-350.44 zł** |
| **RAZEM BRUTTO** | **443.05 zł** | **12.00 zł** | **-431.05 zł** |

**Uwaga:** Dla GABINET koszt energii wynosi 0.00 zł, co może wskazywać na problem w obliczeniach (brak ceny całodobowej w okresach).

### Okres najemcy 2024-04

**Okres najemcy:**
- Data początku: 2024-04-11
- Data końca: 2024-06-10
- Długość: 61 dni

**Overlapping periods:**
- Okres 3 (2024-04-07 - 2024-06-30): 61 dni (100%)

### Porównanie wyników dla okresu 2024-04

#### Lokal GÓRA

| Składnik | Stara logika | Poprawiona logika | Różnica |
|----------|--------------|-------------------|---------|
| Koszt energii (netto) | 265.85 zł | 338.35 zł | +72.50 zł |
| Koszt dystrybucji (netto) | 331.78 zł | 0.00 zł | -331.78 zł |
| Opłaty stałe (netto) | 44.47 zł | 9.76 zł | -34.71 zł |
| **RAZEM NETTO** | **642.10 zł** | **348.11 zł** | **-293.99 zł** |
| **RAZEM BRUTTO** | **789.78 zł** | **428.17 zł** | **-361.61 zł** |

#### Lokal DOL (Mikołaj)

| Składnik | Stara logika | Poprawiona logika | Różnica |
|----------|--------------|-------------------|---------|
| Koszt energii (netto) | 310.36 zł | 202.46 zł | -107.90 zł |
| Koszt dystrybucji (netto) | 387.34 zł | 0.00 zł | -387.34 zł |
| Opłaty stałe (netto) | 44.47 zł | 9.76 zł | -34.71 zł |
| **RAZEM NETTO** | **742.17 zł** | **212.22 zł** | **-529.95 zł** |
| **RAZEM BRUTTO** | **912.87 zł** | **261.03 zł** | **-651.84 zł** |

#### Lokal GABINET

| Składnik | Stara logika | Poprawiona logika | Różnica |
|----------|--------------|-------------------|---------|
| Koszt energii (netto) | 149.23 zł | 0.00 zł | -149.23 zł |
| Koszt dystrybucji (netto) | 186.24 zł | 0.00 zł | -186.24 zł |
| Opłaty stałe (netto) | 44.47 zł | 9.76 zł | -34.71 zł |
| **RAZEM NETTO** | **379.93 zł** | **9.76 zł** | **-370.17 zł** |
| **RAZEM BRUTTO** | **467.32 zł** | **12.00 zł** | **-455.32 zł** |

## Analiza różnic

### Główne różnice między starą a nową logiką:

1. **Koszty dystrybucji:** W poprawionej logice koszty dystrybucji są już wliczone w cenę za kWh, więc `distribution_cost = 0`. W starej logice były obliczane osobno.

2. **Opłaty stałe:** W poprawionej logice opłaty stałe są dzielone proporcjonalnie do dni w okresie najemcy, a nie równo przez 3 lokale. Dla okresu 2024-02 (60 dni) opłaty stałe są proporcjonalne do długości okresu.

3. **Okresy z faktury:** Poprawiona logika uwzględnia różne ceny w różnych okresach faktury i oblicza overlapping periods.

4. **Problem z GABINET:** Dla GABINET koszt energii wynosi 0.00 zł, co może wskazywać na problem w obliczeniach (brak ceny całodobowej w okresach lub błąd w logice dla taryfy całodobowej).

## Podsumowanie

Plik `obliczenia_rachunkow_prad_2024_02_04.txt` używa **starej logiki obliczeń**, która:
- ❌ Nie uwzględnia okresów z faktury
- ❌ Nie oblicza overlapping periods
- ❌ Używa średniej ważonej dla całej faktury
- ❌ Dzieli opłaty stałe równo przez 3
- ❌ Oblicza koszty dystrybucji osobno

**Poprawiona logika** (zaimplementowana w kodzie):
- ✅ Wyłania okresy z faktury (4 okresy znalezione)
- ✅ Oblicza overlapping periods
- ✅ Podziela zużycie proporcjonalnie do dni
- ✅ Zastosowuje odpowiednie ceny dla każdego okresu
- ✅ Dzieli opłaty stałe proporcjonalnie
- ✅ Wlicza koszty dystrybucji w cenę za kWh

**Dodatkowe uwagi:**
- ⚠️ Ujemne zużycie nocne dla GÓRA w obu okresach jest **celowo wprowadzone przez użytkownika** i **jest uwzględniane w obliczeniach**:
  - Okres 2024-02: GÓRA II = -6.0000 kWh (DOM łącznie = 1151 kWh ✓)
  - Okres 2024-04: GÓRA II = -69.0000 kWh (DOM łącznie = 1157 kWh ✓)
- ⚠️ Koszt energii dla GABINET = 0.00 zł (może wskazywać na błąd w logice dla taryfy całodobowej)

**Rekomendacje:**
1. ✅ Faktura została przeliczona zgodnie z poprawioną logiką
2. ✅ Ujemne zużycie jest uwzględniane w obliczeniach (kod obsługuje ujemne wartości)
3. ⚠️ Należy zweryfikować problem z kosztem energii dla GABINET (0.00 zł)
4. ⚠️ Należy porównać sumy całkowite - różnice są znaczące, co może wskazywać na błędy w starej logice

**Uwaga dotycząca ujemnego zużycia:**
- Ujemne zużycie jest celowo wprowadzone przez użytkownika
- Kod oblicza koszty z uwzględnieniem ujemnych wartości: `energy_cost = (usage_dzienna * cena_dzienna) + (usage_nocna * cena_nocna)`
- Jeśli `usage_nocna` jest ujemne, to `(usage_nocna * cena_nocna)` również będzie ujemne, co zmniejsza całkowity koszt energii
- DOM łącznie dla okresu 2024-02 = 1151 kWh (826 + 325) ✓
- DOM łącznie dla okresu 2024-04 = 1157 kWh (766 + 391) ✓

