# Analiza bezpieczeństwa plików do pushowania na Git

## Status plików

### ✅ BEZPIECZNE DO PUSHOWANIA (już w staging)

1. **docs/GIT_INSTRUKCJE.md** ✅
   - Dokumentacja Git
   - Brak wrażliwych danych

2. **docs/WERYFIKACJA_FAKTURY_2024_02_04.md** ✅
   - Dokumentacja weryfikacji faktury
   - Zawiera numery faktur i kwoty (dane przykładowe do weryfikacji)
   - Brak haseł, kluczy API, danych osobowych

3. **tools/verify_invoice_calculation.py** ✅
   - Skrypt weryfikacyjny
   - Brak hardcoded credentials
   - Używa tylko bazy danych (konfiguracja poza kodem)

### ✅ BEZPIECZNE DO PUSHOWANIA (zmodyfikowane pliki kodu)

4. **app/api/routes/electricity.py** ✅
   - Kod API
   - Brak wrażliwych danych

5. **app/models/electricity.py** ✅
   - Modele danych
   - Brak wrażliwych danych

6. **app/models/electricity_invoice.py** ✅
   - Modele faktur
   - Brak wrażliwych danych

7. **app/services/electricity/bill_generator.py** ✅
   - Generator rachunków
   - Brak wrażliwych danych

8. **app/services/electricity/cost_calculator.py** ✅
   - Kalkulator kosztów
   - Brak wrażliwych danych

9. **app/services/electricity/manager.py** ✅
   - Manager rozliczeń
   - Brak wrażliwych danych

10. **app/static/dashboard.html** ✅
    - Interfejs użytkownika
    - Brak wrażliwych danych

### ⚠️ DO SPRAWDZENIA (nieśledzone pliki)

11. **docs/ANALIZA_ROZLICZENIA_PRAD_OKRESY.md** ⚠️
    - Dokumentacja analizy
    - **Sprawdź:** Czy zawiera wrażliwe dane (numery faktur, kwoty)
    - **Rekomendacja:** Jeśli zawiera tylko przykładowe dane do dokumentacji - OK

12. **migrations/versions/migrate_add_electricity_flag_columns.py** ✅
    - Migracja bazy danych
    - Brak wrażliwych danych
    - **Rekomendacja:** Dodaj do staging

13. **tools/analyze_bill_calculation.py** ✅
    - Skrypt analizy
    - Brak hardcoded credentials
    - **Rekomendacja:** Dodaj do staging

14. **tools/analyze_fixed_fees.py** ✅
    - Skrypt analizy opłat stałych
    - Brak hardcoded credentials
    - **Rekomendacja:** Dodaj do staging

15. **tools/check_invoice_prices.py** ✅
    - Skrypt sprawdzania cen
    - Brak hardcoded credentials
    - **Rekomendacja:** Dodaj do staging

16. **tools/test_electricity_periods*.py** ✅
    - Testy jednostkowe
    - Brak wrażliwych danych
    - **Rekomendacja:** Dodaj do staging

17. **tools/obliczenia_rachunkow_prad_2024_02_04.py** ⚠️
    - Skrypt obliczeń
    - **Sprawdź:** Czy zawiera hardcoded dane wrażliwe
    - **Rekomendacja:** Jeśli używa tylko danych z bazy - OK

### ❌ NIE PUSHOWAĆ (zawierają wrażliwe dane)

18. **obliczenia_rachunkow_prad_2024_02_04.txt** ❌
    - Zawiera szczegółowe dane faktury (numery, kwoty, zużycie)
    - **Rekomendacja:** Dodaj do `.gitignore` lub przenieś do folderu ignorowanego
    - **Alternatywa:** Jeśli to tylko przykładowe dane do dokumentacji, można pushować

19. **password_reset_code.txt** ❌
    - Zawiera kod resetujący hasło i email
    - **Status:** Już w `.gitignore` ✅
    - **Rekomendacja:** NIE PUSHOWAĆ

## Rekomendacje

### Bezpieczne do dodania do staging:

```bash
# Dokumentacja (sprawdź czy nie ma wrażliwych danych)
git add docs/ANALIZA_ROZLICZENIA_PRAD_OKRESY.md

# Migracje
git add migrations/versions/migrate_add_electricity_flag_columns.py

# Narzędzia i skrypty
git add tools/analyze_bill_calculation.py
git add tools/analyze_fixed_fees.py
git add tools/check_invoice_prices.py
git add tools/test_electricity_periods.py
git add tools/test_electricity_periods_detailed.py
git add tools/test_electricity_periods_overlapping.py
git add tools/test_electricity_periods_specific.py

# Sprawdź przed dodaniem:
git add tools/obliczenia_rachunkow_prad_2024_02_04.py
```

### NIE dodawać:

```bash
# Plik z danymi faktury (zawiera wrażliwe dane)
# obliczenia_rachunkow_prad_2024_02_04.txt - NIE DODAWAĆ

# Plik z kodem resetującym hasło (już w .gitignore)
# password_reset_code.txt - NIE DODAWAĆ
```

### Opcjonalnie - dodaj do .gitignore:

Jeśli `obliczenia_rachunkow_prad_2024_02_04.txt` zawiera wrażliwe dane:

```bash
# Dodaj do .gitignore
echo "obliczenia_rachunkow_prad_*.txt" >> .gitignore
```

## Sprawdzenie przed pushowaniem

### 1. Sprawdź czy nie ma wrażliwych danych w plikach:

```bash
# Szukaj haseł, kluczy API, tokenów
grep -r "password\|secret\|api_key\|token" --include="*.py" --include="*.md" tools/ docs/

# Szukaj emaili (może zawierać dane osobowe)
grep -r "@" --include="*.py" --include="*.md" tools/ docs/
```

### 2. Sprawdź rozmiar plików:

```bash
# Duże pliki mogą być problemem
find . -type f -size +1M -not -path "./venv/*" -not -path "./.git/*"
```

### 3. Sprawdź czy pliki są w .gitignore:

```bash
git check-ignore -v obliczenia_rachunkow_prad_2024_02_04.txt
```

## Podsumowanie

### ✅ BEZPIECZNE (można pushować):
- Wszystkie pliki w staging area (3 pliki)
- Wszystkie zmodyfikowane pliki kodu (7 plików)
- Większość nieśledzonych plików narzędziowych

### ⚠️ DO SPRAWDZENIA:
- `docs/ANALIZA_ROZLICZENIA_PRAD_OKRESY.md` - sprawdź zawartość
- `tools/obliczenia_rachunkow_prad_2024_02_04.py` - sprawdź czy nie ma hardcoded danych

### ❌ NIE PUSHOWAĆ:
- `obliczenia_rachunkow_prad_2024_02_04.txt` - zawiera szczegółowe dane faktury
- `password_reset_code.txt` - zawiera kod resetujący hasło (już w .gitignore)

## Szybka komenda do bezpiecznego dodania

```bash
# Dodaj bezpieczne pliki
git add docs/ANALIZA_ROZLICZENIA_PRAD_OKRESY.md
git add migrations/versions/migrate_add_electricity_flag_columns.py
git add tools/analyze_bill_calculation.py
git add tools/analyze_fixed_fees.py
git add tools/check_invoice_prices.py
git add tools/test_electricity_periods*.py

# Sprawdź przed dodaniem (opcjonalnie):
# git add tools/obliczenia_rachunkow_prad_2024_02_04.py
```

