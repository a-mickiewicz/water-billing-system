# Logika obliczania zużycia wody

## Jak działa obliczanie zużycia

### Podstawowa zasada
Zużycie jest obliczane jako **różnica między obecnym a poprzednim odczytem licznika**.

### Przykład

#### Odczyty liczników:

**Poprzedni odczyt (2024-12):**
- `water_meter_main`: 100.5 m³
- `water_meter_5` (gora): 45 m³
- `water_meter_5b` (gabinet): 35 m³

**Obecny odczyt (2025-02):**
- `water_meter_main`: 145.5 m³
- `water_meter_5` (gora): 60 m³
- `water_meter_5b` (gabinet): 50 m³

#### Obliczenie zużycia:

**Gora:**
```
Zużycie = 60 - 45 = 15 m³
```

**Gabinet:**
```
Zużycie = 50 - 35 = 15 m³
```

**Dol:**
```
Różnica main = 145.5 - 100.5 = 45 m³
Różnica gora = 60 - 45 = 15 m³  
Różnica gabinet = 50 - 35 = 15 m³
Zużycie dol = 45 - (15 + 15) = 15 m³
```

**Całkowite zużycie:**
```
15 + 15 + 15 = 45 m³
```

## Kalkulacja dla każdego lokalu

### 1. Gora (water_meter_5)
```python
usage_gora = current_reading.water_meter_5 - previous_reading.water_meter_5
```

### 2. Gabinet (water_meter_5b)
```python
usage_gabinet = current_reading.water_meter_5b - previous_reading.water_meter_5b
```

### 3. Dol (water_meter_5a)
```python
# Obliczamy jako: (main_obecny - main_poprzedni) - (suma różnic pozostałych)
usage_main = current_reading.water_meter_main - previous_reading.water_meter_main
usage_gora = current_reading.water_meter_5 - previous_reading.water_meter_5
usage_gabinet = current_reading.water_meter_5b - previous_reading.water_meter_5b
usage_dol = usage_main - (usage_gora + usage_gabinet)
```

## Obsługa pierwszego odczytu

Jeśli to pierwszy odczyt w systemie (brak poprzedniego odczytu), system przyjmuje:
- Zużycie = obecny stan licznika
- Jest to sytuacja wyjściowa dla następnych obliczeń

## Korekta według faktury

System porównuje:
- `usage` z faktury dostawcy (całkowite zużycie według dostawcy)
- Sumę różnic odczytów dla wszystkich lokali

Jeśli istnieje różnica, jest ona doliczana/odliczana na lokal "gora" (domyślnie).

### Przykład korekty:
```
Zużycie z faktury: 45.5 m³
Suma z odczytów: 45.0 m³
Różnica: 0.5 m³

→ Korekta 0.5 m³ dodana do lokalu "gora"
```

## Obsługa wielu faktur dla jednego okresu

System obsługuje sytuację, gdy dla jednego okresu rozliczeniowego istnieje **wiele faktur** (np. z powodu podwyżki kosztów w środku okresu).

### Jak działa:

**Przykład:**
- Okres: 2025-02
- Faktura 1: 01.01-15.02 (koszt 10 zł/m³)
- Faktura 2: 16.02-28.02 (koszt 12 zł/m³)

**Obliczenia:**
1. System pobiera **wszystkie faktury** dla okresu
2. Oblicza **średnie ważone koszty** z wszystkich faktur
3. Sumuje **abonamenty** z wszystkich faktur
4. Aplikuje średnie koszty do zużycia każdego lokalu

### Formuła średniej ważonej:
```
weighted_cost = Σ(cost_i * usage_i) / Σ(usage_i)
```

## Abonamenty

Abonamenty (woda i ścieki) są dzielone równo na 3 lokale:

```python
abonament_water_share = (water_subscr_cost * nr_of_subscription) / 3
abonament_sewage_share = (sewage_subscr_cost * nr_of_subscription) / 3
total_abonament = abonament_water_share + abonament_sewage_share
```

## Suma końcowa

```python
cost_water = usage_m3 * water_cost_m3
cost_sewage = usage_m3 * sewage_cost_m3
cost_usage = cost_water + cost_sewage
net_sum = cost_usage + abonament_total
gross_sum = net_sum * (1 + vat)
```

