# Porównanie logiki z BILL_CALCULATION_LOGIC.md z obecną implementacją

## Podsumowanie

**Wniosek:** Obecna implementacja jest **zgodna** z logiką opisaną w `BILL_CALCULATION_LOGIC.md`. Oba podejścia używają tej samej metody obliczeń z overlapping periods.

## Szczegółowe porównanie

### 1. Wyłanianie okresów z faktury

#### BILL_CALCULATION_LOGIC.md:
- Wyłania okresy dystrybucyjne z opłat dystrybucyjnych (grupowane po `data`)
- Dla każdego okresu oblicza:
  - `cena_1kwh_dzienna` = energia_czynna + opłata_jakościowa + opłata_zmienna_sieciowa + opłata_OZE + opłata_kogeneracyjna
  - `cena_1kwh_nocna` = energia_czynna + opłata_jakościowa + opłata_zmienna_sieciowa + opłata_OZE + opłata_kogeneracyjna
  - `suma_oplat_stalych` = opłata_stała_sieciowa + opłata_przejściowa + opłata_abonamentowa + opłata_mocowa

#### Obecna implementacja (`get_distribution_periods`):
```python
# Linie 554-590 w app/services/electricity/manager.py
cena_1kwh_dzienna = cena_dzienna  # energia czynna
if oplata_jakosciowa_dzienna is not None:
    cena_1kwh_dzienna += oplata_jakosciowa_dzienna
if oplata_zmienna_sieciowa_dzienna is not None:
    cena_1kwh_dzienna += oplata_zmienna_sieciowa_dzienna
if oplata_oze_dzienna is not None:
    cena_1kwh_dzienna += oplata_oze_dzienna
if oplata_kogeneracyjna_dzienna is not None:
    cena_1kwh_dzienna += oplata_kogeneracyjna_dzienna
```

**Status:** ✅ **Zgodne** - oba podejścia obliczają `cena_1kwh_dzienna/nocna` jako sumę energii czynnej i wszystkich opłat dystrybucyjnych zmiennych.

### 2. Obliczanie overlapping periods

#### BILL_CALCULATION_LOGIC.md:
```
dni_w_okresie = max(okres_najemcy_start, okres_dystrybucyjny_start) do min(okres_najemcy_end, okres_dystrybucyjny_end)
dni_całkowite = suma dni wszystkich przecięć okresów dystrybucyjnych z okresem najemcy
proporcja = dni_w_okresie / dni_całkowite
```

#### Obecna implementacja (`calculate_bill_for_period_with_overlapping`):
```python
# Linie 647-659 w app/services/electricity/manager.py
period_start = max(tenant_period_start, dist_period["od"])
period_end = min(tenant_period_end, dist_period["do"])

if period_start <= period_end:
    days = self.calculate_days_between(period_start, period_end)
    overlapping_periods.append({
        "period": dist_period,
        "days": days,
        "start": period_start,
        "end": period_end
    })

total_days = sum(op["days"] for op in overlapping_periods)
proportion = days / total_days if total_days > 0 else 0
```

**Status:** ✅ **Zgodne** - oba podejścia obliczają overlapping periods w identyczny sposób.

### 3. Podział zużycia proporcjonalnie

#### BILL_CALCULATION_LOGIC.md:
```
zużycie_dzienne = zużycie_całkowite_dzienne × proporcja
zużycie_nocne = zużycie_całkowite_nocne × proporcja
```

#### Obecna implementacja:
```python
# Linie 694-695 w app/services/electricity/manager.py
usage_dzienna_part = usage_kwh_dzienna * proportion
usage_nocna_part = usage_kwh_nocna * proportion
```

**Status:** ✅ **Zgodne** - oba podejścia dzielą zużycie proporcjonalnie do dni.

### 4. Obliczanie kosztów energii

#### BILL_CALCULATION_LOGIC.md:
```
koszt_energii = (zużycie_dzienne × cena_dzienna) + (zużycie_nocne × cena_nocna)
```

#### Obecna implementacja:
```python
# Linie 697-700 w app/services/electricity/manager.py
cena_dzienna = period.get("cena_1kwh_dzienna", 0) or 0
cena_nocna = period.get("cena_1kwh_nocna", 0) or 0

energy_cost_net = (usage_dzienna_part * cena_dzienna) + (usage_nocna_part * cena_nocna)
```

**Status:** ✅ **Zgodne** - oba podejścia obliczają koszt energii w identyczny sposób.

### 5. Uwzględnienie ujemnego zużycia

#### BILL_CALCULATION_LOGIC.md:
- Przykład: GÓRA II = -6.00 kWh
- Obliczenie: `koszt_nocna = cena_1kWh_nocna × zużycie_nocne = 0.3208 zł/kWh × -6.00 kWh = -1.92 zł`
- Koszt energii: `koszt_energii = koszt_dzienna + koszt_nocna = 328.26 zł + -1.92 zł = 326.34 zł`

#### Obecna implementacja:
```python
# Linie 694-700 w app/services/electricity/manager.py
usage_nocna_part = usage_kwh_nocna * proportion  # Może być ujemne
energy_cost_net = (usage_dzienna_part * cena_dzienna) + (usage_nocna_part * cena_nocna)
```

**Status:** ✅ **Zgodne** - oba podejścia uwzględniają ujemne zużycie w obliczeniach.

### 6. Opłaty stałe proporcjonalnie

#### BILL_CALCULATION_LOGIC.md:
```
opłaty_stałe = suma_oplat_stalych × proporcja
```

#### Obecna implementacja:
```python
# Linie 702-704 w app/services/electricity/manager.py
suma_oplat_stalych = period.get("suma_oplat_stalych", 0) or 0
fixed_cost_net = suma_oplat_stalych * proportion
```

**Status:** ✅ **Zgodne** - oba podejścia dzielą opłaty stałe proporcjonalnie do dni.

### 7. Sumowanie kosztów

#### BILL_CALCULATION_LOGIC.md:
```
koszt_okresu = koszt_energii + opłaty_stałe
koszt_całkowity = suma_kosztów_okresów
```

#### Obecna implementacja:
```python
# Linie 706-707, 727 w app/services/electricity/manager.py
total_energy_cost_net += energy_cost_net
total_fixed_fees_net += fixed_cost_net
total_net_sum = round(total_energy_cost_net + distribution_cost_net + total_fixed_fees_net, 4)
```

**Status:** ⚠️ **Różnica w strukturze, ale wynik jest zgodny:**
- W BILL_CALCULATION_LOGIC.md: `koszt_okresu = koszt_energii + opłaty_stałe` (koszt_energii zawiera już dystrybucję)
- W obecnej implementacji: `total_net_sum = energy_cost_net + distribution_cost_net + fixed_fees_net`
- Ale `distribution_cost_net = 0` w `calculate_bill_for_period_with_overlapping` (komentarz: "dystrybucja jest już wliczona w cenę za kWh")
- Więc faktycznie: `total_net_sum = energy_cost_net + 0 + fixed_fees_net = energy_cost_net + fixed_fees_net` ✅

### 8. Koszty dystrybucji

#### BILL_CALCULATION_LOGIC.md:
- **Brak osobnego obliczania kosztów dystrybucji**
- Dystrybucja jest już wliczona w `cena_1kwh_dzienna/nocna`
- `cena_1kwh_dzienna` = energia_czynna + opłata_jakościowa + opłata_zmienna_sieciowa + opłata_OZE + opłata_kogeneracyjna

#### Obecna implementacja:
```python
# Linie 721-725 w app/services/electricity/manager.py
# Dla dystrybucji: w obecnej implementacji dystrybucja jest już wliczona w cenę za kWh
# (cena_1kwh_dzienna/nocna zawiera już opłaty dystrybucyjne zmienne)
# Więc distribution_cost = 0 (już wliczone w energy_cost)
distribution_cost_net = 0.0
distribution_cost_gross = 0.0
```

**Status:** ✅ **Zgodne** - oba podejścia wliczają dystrybucję w cenę za kWh, nie obliczają osobno.

## Różnice w strukturze (nie w logice)

### 1. Rozdzielenie kosztów w obecnej implementacji

Obecna implementacja rozdziela koszty na:
- `energy_cost_net` - koszt energii (zawiera już dystrybucję)
- `distribution_cost_net` - koszt dystrybucji (zawsze 0 w overlapping periods)
- `fixed_fees_net` - opłaty stałe

To jest zgodne z modelem danych w bazie (`ElectricityBill`), gdzie są osobne pola:
- `energy_cost_gross`
- `distribution_cost_gross`
- `total_net_sum`
- `total_gross_sum`

### 2. Obliczanie VAT

#### BILL_CALCULATION_LOGIC.md:
- Nie pokazuje obliczania VAT osobno
- Prawdopodobnie używa wartości brutto z faktury

#### Obecna implementacja:
```python
# Linie 717-719 w app/services/electricity/manager.py
total_energy_cost_gross = round(total_energy_cost_net * (1 + vat_rate), 4)
total_fixed_fees_gross = round(total_fixed_fees_net * (1 + vat_rate), 4)
vat_rate = 0.23  # VAT 23%
```

**Status:** ✅ **Zgodne** - obecna implementacja oblicza VAT, co jest potrzebne dla modelu danych.

## Przykład porównania - Okres 2024-02, Lokal GÓRA

### BILL_CALCULATION_LOGIC.md:
- Zużycie dzienne: 481.00 kWh
- Zużycie nocne: -6.00 kWh
- Zużycie całkowite: 475.00 kWh
- Koszt całkowity: 359.5424 zł

**Szczegóły:**
- OKRES_DYSTRYBUCYJNY_2 (56 dni, proporcja 0.9333):
  - Zużycie dzienne: 448.93 kWh
  - Zużycie nocne: -5.60 kWh
  - Koszt energii: 326.4636 zł
  - Opłaty stałe: 9.1093 zł
  - Koszt okresu: 335.5729 zł
- OKRES_DYSTRYBUCYJNY_3 (4 dni, proporcja 0.0667):
  - Zużycie dzienne: 32.07 kWh
  - Zużycie nocne: -0.40 kWh
  - Koszt energii: 23.3188 zł
  - Opłaty stałe: 0.6507 zł
  - Koszt okresu: 23.9695 zł
- **Suma:** 335.5729 + 23.9695 = 359.5424 zł

### Obecna implementacja (z weryfikacji):
- Zużycie dzienne: 481.00 kWh
- Zużycie nocne: -6.00 kWh
- Zużycie całkowite: 475.00 kWh
- Koszt energii (netto): 349.78 zł
- Opłaty stałe (netto): 9.76 zł
- **RAZEM NETTO:** 359.54 zł

**Szczegóły:**
- OKRES_DYSTRYBUCYJNY_2 (56 dni, proporcja 0.9333):
  - Koszt energii (netto): 326.46 zł
  - Opłaty stałe (netto): 9.11 zł
- OKRES_DYSTRYBUCYJNY_3 (4 dni, proporcja 0.0667):
  - Koszt energii (netto): 23.32 zł
  - Opłaty stałe (netto): 0.65 zł

**Status:** ✅ **Zgodne** - wyniki są identyczne (359.5424 ≈ 359.54, różnica tylko w zaokrągleniu).

## Różnice w starej logice (fallback)

### Stara logika w `calculate_bill_costs` (gdy jest jeden okres):

```python
# Linie 218-260 w app/services/electricity/manager.py
# Używa średniej ważonej dla całej faktury
koszt_sredni_wazony = round(koszt_dzienna * 0.7 + koszt_nocna * 0.3, 4)
energy_cost_net = round(koszt_sredni_wazony * local_usage, 4)

# Oblicza dystrybucję osobno
dystrybucja_srednia_wazona = round(dystrybucja_dzienna * 0.7 + dystrybucja_nocna * 0.3, 4)
distribution_cost_net = round(dystrybucja_srednia_wazona * local_usage, 4)
```

**Problem:** Stara logika:
- ❌ Nie uwzględnia okresów z faktury
- ❌ Używa średniej ważonej dla całej faktury
- ❌ Oblicza dystrybucję osobno (podwójne liczenie?)
- ❌ Dzieli opłaty stałe równo przez 3 (nie proporcjonalnie do dni)

### Nowa logika (overlapping periods):

```python
# Linie 621-740 w app/services/electricity/manager.py
# Używa overlapping periods
# Dzieli zużycie proporcjonalnie
# Dzieli opłaty stałe proporcjonalnie
# Dystrybucja jest wliczona w cenę za kWh
```

**Status:** ✅ **Zgodna z BILL_CALCULATION_LOGIC.md**

## Wnioski

### ✅ Co działa dobrze:

1. **Overlapping periods** - implementacja jest zgodna z dokumentacją
2. **Proporcje dni** - obliczane identycznie
3. **Dzielenie zużycia** - proporcjonalne dzielenie działa poprawnie
4. **Ujemne zużycie** - uwzględniane w obliczeniach
5. **Ceny za kWh** - zawierają już dystrybucję (zgodnie z dokumentacją)
6. **Opłaty stałe** - dzielone proporcjonalnie do dni

### ⚠️ Różnice strukturalne (nie wpływają na wyniki):

1. **Rozdzielenie kosztów** - obecna implementacja rozdziela na `energy_cost`, `distribution_cost`, `fixed_fees` dla zgodności z modelem danych, ale `distribution_cost = 0` w overlapping periods
2. **Obliczanie VAT** - obecna implementacja oblicza VAT osobno, co jest potrzebne dla modelu danych

### ❌ Problem w starej logice (fallback):

Gdy faktura ma tylko jeden okres, używana jest stara logika, która:
- Nie uwzględnia overlapping periods (bo nie ma wielu okresów)
- Używa średniej ważonej dla całej faktury
- Oblicza dystrybucję osobno (może być podwójne liczenie?)
- Dzieli opłaty stałe równo przez 3 (nie proporcjonalnie do dni)

**Rekomendacja:** Sprawdź czy stara logika nie liczy dystrybucji podwójnie (raz w `cena_1kwh`, drugi raz jako `distribution_cost`).

## Rekomendacje

1. ✅ **Obecna implementacja overlapping periods jest zgodna z BILL_CALCULATION_LOGIC.md**
2. ⚠️ **Sprawdź starą logikę (fallback)** - może liczyć dystrybucję podwójnie
3. ✅ **Ujemne zużycie jest obsługiwane poprawnie**
4. ✅ **Proporcje dni są obliczane poprawnie**

## Przykład weryfikacji - Okres 2024-02, Lokal GÓRA

### Z BILL_CALCULATION_LOGIC.md:
- Koszt całkowity: **359.5424 zł** (netto)

### Z obecnej implementacji (weryfikacja):
- RAZEM NETTO: **359.54 zł**

### Różnica:
- **0.0024 zł** (różnica tylko w zaokrągleniu) ✅

**Wniosek:** Implementacja jest **zgodna** z dokumentacją.

