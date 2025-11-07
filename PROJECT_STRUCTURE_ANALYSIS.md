# 📊 Analiza Struktury Projektu - Propozycje Ulepszeń

## 📁 Aktualna Struktura Projektu (Stan na 2025)

```
water_billing/
├── app/                              # ✅ Główna aplikacja (zreorganizowana)
│   ├── __init__.py
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── gas.py                # ✅ Routes dla gazu
│   │       ├── water.py              # ✅ Routes dla wody
│   │       └── electricity.py        # ✅ Routes dla prądu
│   ├── core/
│   │   ├── __init__.py
│   │   └── database.py               # ✅ Baza danych
│   ├── integrations/
│   │   ├── __init__.py
│   │   └── google_sheets.py          # ✅ Integracja Google Sheets
│   ├── models/
│   │   ├── __init__.py
│   │   ├── water.py                  # ✅ Modele wody
│   │   └── gas.py                    # ✅ Modele gazu
│   ├── services/
│   │   ├── __init__.py
│   │   ├── water/
│   │   │   ├── __init__.py
│   │   │   ├── bill_generator.py
│   │   │   ├── invoice_reader.py
│   │   │   └── meter_manager.py
│   │   └── gas/
│   │       ├── __init__.py
│   │       ├── bill_generator.py
│   │       ├── invoice_reader.py
│   │       └── manager.py
│   └── static/
│       └── dashboard.html
│
├── main.py                           # ✅ Główny plik - tylko endpointy pomocnicze
├── run.py                            # Entry point
│
├── migrations/                       # ✅ Migracje (zreorganizowane)
│   ├── __init__.py
│   └── versions/
│       ├── migrate_add_gas_column.py
│       ├── migrate_update_gas_invoice_fields.py
│       └── ...
│
├── tests/                            # ✅ Testy (zreorganizowane)
│   ├── __init__.py
│   ├── fixtures/
│   ├── test_duplicates.py
│   └── test_invoice_reader.py
│
├── tools/                            # ✅ Narzędzia pomocnicze
│   ├── analyze_2022_06.py
│   ├── check_bills.py
│   ├── debug_invoice_parsing.py
│   ├── generate_gas_bill_example.py
│   ├── analyze_electricity_numbers.py    # 🔌 Narzędzia do prądu
│   ├── electricity_test.py
│   └── extract_electricity_structured.py
│
├── scripts/                          # ✅ Skrypty zarządzania
│   └── reset_and_import.py
│
├── docs/                             # ✅ Dokumentacja (zreorganizowana)
│   ├── API_EXAMPLES.md
│   ├── ARCHITECTURE_PROPOSALS.md
│   ├── CALCULATION_LOGIC.md
│   ├── FILES_ANALYSIS.md
│   ├── GAS_IMPLEMENTATION_INSTRUCTIONS.md
│   ├── QUICKSTART.md
│   ├── SECURITY_AUDIT_2025.md
│   └── screenshots/
│
├── invoices_raw/                     # ✅ Faktury źródłowe
│   ├── electricity/                  # 🔌 Faktury prądu (istniejące)
│   │   ├── analysis/
│   │   │   ├── auto_extracted/
│   │   │   ├── correted/
│   │   │   └── *.txt
│   │   ├── parsed/
│   │   └── *.pdf
│   ├── gas/
│   │   └── *.pdf
│   └── *.pdf                         # Faktury wody
│
├── bills/                            # ✅ Wygenerowane rachunki
│   ├── gaz/
│   ├── prad/                         # 🔌 Folder na rachunki prądu (pusty)
│   └── woda/
│
├── requirements.txt
├── README.md
└── PROJECT_STRUCTURE_ANALYSIS.md
```

### ✅ Co zostało zreorganizowane:
- ✅ Struktura `app/` z podziałem na moduły
- ✅ Migracje w `migrations/versions/`
- ✅ Testy w `tests/`
- ✅ Dokumentacja w `docs/`
- ✅ Narzędzia w `tools/`
- ✅ Serwisy dla wody i gazu w `app/services/`
- ✅ Modele w `app/models/`

### ⚠️ Co wymaga dalszej pracy:
- ✅ `main.py` zawiera tylko endpointy pomocnicze, routes dla wody w `app/api/routes/water.py`
- ✅ Struktura dla prądu (electricity) w `app/services/` i `app/models/` - **ZREALIZOWANE**
- ✅ Routes dla prądu w `app/api/routes/electricity.py` - **ZREALIZOWANE**
- ✅ Modele prądu w `app/models/electricity.py` - **ZREALIZOWANE**

---

## 🔍 Obecna Struktura - Identyfikowane Problemy

### ❌ Główne Problemy (Zaktualizowane)

1. **Routes dla wody w `main.py`** ✅ **ZREALIZOWANE**
   - ✅ Routes dla wody zostały przeniesione do `app/api/routes/water.py`
   - ✅ `main.py` zawiera tylko endpointy pomocnicze (root, dashboard, load_sample_data)
   - ✅ Spójność z routes dla gazu (`app/api/routes/gas.py`) i prądu (`app/api/routes/electricity.py`)

2. **Brak pełnej struktury dla prądu** ✅ **ZREALIZOWANE**
   - ✅ `app/models/electricity.py` - **ISTNIEJE**
   - ✅ `app/services/electricity/` - **ISTNIEJE** (calculator.py, invoice_reader.py, manager.py, bill_generator.py)
   - ✅ `app/api/routes/electricity.py` - **ISTNIEJE**
   - ✅ Narzędzia pomocnicze w `tools/` i dane w `invoices_raw/electricity/` - **ISTNIEJĄ**

3. **Brak struktury konfiguracji** ✅ **ZREALIZOWANE**
   - ✅ `app/config.py` - **ISTNIEJE** (centralne zarządzanie konfiguracją z Pydantic Settings)
   - ✅ `pydantic-settings==2.1.0` dodane do `requirements.txt`
   - ⚠️ Brak `.env.example` (opcjonalne, ale zalecane - można utworzyć ręcznie na podstawie `app/config.py`)
   - ✅ Konfiguracja scentralizowana w jednym miejscu
   - ✅ `.env` dodany do `.gitignore` (bezpieczeństwo)

4. **Brak testów dla prądu** ⚠️ **CZĘŚCIOWO ZREALIZOWANE**
   - ✅ `tests/test_electricity_calculator.py` - **ISTNIEJE**
   - ⚠️ Brak `tests/test_electricity_services.py` i `tests/test_electricity_api.py`

### ✅ Rozwiązane Problemy

1. ✅ **Migracje zreorganizowane** - są w `migrations/versions/`
2. ✅ **Testy zreorganizowane** - są w `tests/`
3. ✅ **Dokumentacja zreorganizowana** - jest w `docs/`
4. ✅ **Narzędzia pomocnicze** - są w `tools/`
5. ✅ **Struktura `app/`** - zreorganizowana z podziałem na moduły
6. ✅ **Serwisy dla wody i gazu** - są w `app/services/`
7. ✅ **Modele** - są w `app/models/`
8. ✅ **Core** - wykorzystany (`app/core/database.py`)

---

## ✅ Proponowana Struktura (Zgodna z Best Practices)

```
water_billing/
├── app/                              # Główna aplikacja
│   ├── __init__.py
│   ├── main.py                       # FastAPI app initialization
│   ├── config.py                     # Konfiguracja aplikacji
│   │
│   ├── api/                          # Wszystkie endpointy API
│   │   ├── __init__.py
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── water.py              # Routes dla wody
│   │   │   ├── gas.py                # Routes dla gazu
│   │   │   ├── electricity.py        # 🔌 Routes dla prądu
│   │   │   └── common.py             # Wspólne routes (stats, health)
│   │   └── dependencies.py           # FastAPI dependencies
│   │
│   ├── core/                         # Core functionality
│   │   ├── __init__.py
│   │   ├── database.py              # db.py → tutaj
│   │   └── security.py               # Security utilities (future)
│   │
│   ├── models/                       # Modele bazy danych
│   │   ├── __init__.py
│   │   ├── base.py                   # Base model
│   │   ├── water.py                  # Water models (Local, Reading, Invoice, Bill)
│   │   ├── gas.py                    # Gas models
│   │   └── electricity.py            # 🔌 Electricity models
│   │
│   ├── services/                     # Business logic
│   │   ├── __init__.py
│   │   ├── water/
│   │   │   ├── __init__.py
│   │   │   ├── invoice_reader.py     # invoice_reader.py → tutaj
│   │   │   ├── meter_manager.py      # meter_manager.py → tutaj
│   │   │   ├── bill_generator.py     # bill_generator.py → tutaj
│   │   │   └── calculator.py         # Logika obliczeń
│   │   ├── gas/
│   │   │   ├── __init__.py
│   │   │   ├── invoice_reader.py
│   │   │   ├── bill_generator.py
│   │   │   ├── manager.py
│   │   │   └── calculator.py
│   │   └── electricity/              # 🔌 Serwisy dla prądu
│   │       ├── __init__.py
│   │       ├── invoice_reader.py     # Parsowanie faktur prądu
│   │       ├── bill_generator.py     # Generowanie rachunków prądu
│   │       ├── manager.py            # Zarządzanie odczytami i rozliczeniami
│   │       └── calculator.py         # Logika obliczeń dla prądu
│   │
│   ├── integrations/                 # Integracje zewnętrzne
│   │   ├── __init__.py
│   │   └── google_sheets.py          # gsheets_integration.py → tutaj
│   │
│   └── static/                       # Frontend
│       └── dashboard.html
│
├── migrations/                       # Migracje bazy danych
│   ├── __init__.py
│   ├── versions/
│   │   ├── migrate_add_gas_column.py
│   │   ├── migrate_update_gas_invoice_fields.py
│   │   └── ...
│   └── alembic.ini                   # Jeśli używasz Alembic
│
├── tests/                            # Testy
│   ├── __init__.py
│   ├── test_models.py
│   ├── test_api.py
│   ├── test_services.py
│   └── fixtures/
│
├── tools/                            # Skrypty pomocnicze (nie testy!)
│   ├── analyze_2022_06.py
│   ├── check_bills.py
│   ├── debug_invoice_parsing.py
│   └── generate_gas_bill_example.py
│
├── scripts/                          # Skrypty do zarządzania
│   ├── reset_and_import.py
│   └── init_db.py
│
├── docs/                             # Dokumentacja
│   ├── README.md                     # Główny README
│   ├── QUICKSTART.md
│   ├── API_EXAMPLES.md
│   ├── CALCULATION_LOGIC.md
│   ├── ARCHITECTURE.md
│   ├── DEPLOYMENT.md
│   └── screenshots/
│
├── config/                           # Konfiguracja (opcjonalnie)
│   ├── .env.example
│   └── settings.py
│
├── invoices_raw/                     # Faktury źródłowe
│   ├── electricity/                  # 🔌 Faktury prądu
│   ├── gas/                          # Faktury gazu
│   └── *.pdf                         # Faktury wody
│
├── bills/                            # Wygenerowane rachunki
│   ├── prad/                         # 🔌 Rachunki prądu
│   ├── gaz/                          # Rachunki gazu
│   └── woda/                         # Rachunki wody
│
├── .gitignore
├── requirements.txt
├── pyproject.toml                    # Nowoczesna konfiguracja projektu
├── README.md                          # Link do docs/README.md
└── run.py                            # Entry point (minimalny)
```

---

## 🔌 Szczegółowa Struktura dla Prądu (Electricity)

### Struktura folderów i plików do utworzenia:

```
app/
├── models/
│   └── electricity.py              # Modele: ElectricityLocal, ElectricityReading, 
│                                   #         ElectricityInvoice, ElectricityBill
│
├── services/
│   └── electricity/
│       ├── __init__.py
│       ├── invoice_reader.py       # Parsowanie faktur PDF prądu (ENEA)
│       ├── bill_generator.py      # Generowanie rachunków PDF dla lokali
│       ├── manager.py             # Zarządzanie odczytami i rozliczeniami
│       └── calculator.py         # Logika obliczeń kosztów prądu
│
└── api/
    └── routes/
        └── electricity.py         # Endpointy API dla prądu
```

### Pliki do utworzenia:

#### 1. `app/models/electricity.py`
- `ElectricityLocal` - Lokale z licznikami prądu
- `ElectricityReading` - Odczyty liczników prądu
- `ElectricityInvoice` - Faktury za prąd (ENEA)
- `ElectricityBill` - Wygenerowane rachunki dla lokali

#### 2. `app/services/electricity/invoice_reader.py`
- Parsowanie faktur PDF z ENEA
- Wyciąganie danych: data, zużycie (kWh), koszty, opłaty dystrybucyjne
- Wykorzystanie istniejących narzędzi: `tools/extract_electricity_structured.py`

#### 3. `app/services/electricity/manager.py`
- Zarządzanie odczytami liczników
- Rozliczanie zużycia między lokalami
- Obliczanie kosztów na podstawie faktur

#### 4. `app/services/electricity/bill_generator.py`
- Generowanie rachunków PDF dla każdego lokalu
- Wzór podobny do `app/services/water/bill_generator.py`
- Zapis w `bills/prad/`

#### 5. `app/services/electricity/calculator.py`
- Logika obliczeń kosztów prądu
- Podział kosztów między lokale
- Uwzględnienie opłat stałych i zmiennych

#### 6. `app/api/routes/electricity.py`
- `GET /api/electricity/locals` - Lista lokali
- `GET /api/electricity/readings` - Odczyty liczników
- `GET /api/electricity/invoices` - Faktury
- `GET /api/electricity/bills` - Wygenerowane rachunki
- `POST /api/electricity/readings` - Dodanie odczytu
- `POST /api/electricity/invoices` - Upload faktury PDF
- `POST /api/electricity/generate-bills` - Generowanie rachunków

### Migracje bazy danych:

```
migrations/versions/
└── migrate_add_electricity_tables.py
```

Tabele do utworzenia:
- `electricity_locals` - Lokale z licznikami prądu
- `electricity_readings` - Odczyty liczników
- `electricity_invoices` - Faktury za prąd
- `electricity_bills` - Wygenerowane rachunki

### Testy:

```
tests/
├── test_electricity_models.py
├── test_electricity_services.py
└── test_electricity_api.py
```

### Narzędzia pomocnicze (już istniejące):

```
tools/
├── analyze_electricity_numbers.py    # ✅ Istnieje
├── electricity_test.py                # ✅ Istnieje
└── extract_electricity_structured.py  # ✅ Istnieje
```

### Dane źródłowe (już istniejące):

```
invoices_raw/electricity/              # ✅ Istnieje
├── analysis/                          # ✅ Istnieje
│   ├── auto_extracted/                # ✅ Istnieje
│   ├── correted/                      # ✅ Istnieje
│   └── *.txt                          # ✅ Istnieje
├── parsed/                            # ✅ Istnieje
└── *.pdf                              # ✅ Istnieje (ENEA 2021-2024)
```

---

## 🎯 Korzyści z Reorganizacji

### 1. **Separacja Odpowiedzialności**
- ✅ `app/` - cała logika aplikacji
- ✅ `migrations/` - tylko migracje
- ✅ `tests/` - tylko testy
- ✅ `tools/` - tylko narzędzia pomocnicze
- ✅ `docs/` - tylko dokumentacja

### 2. **Spójność Struktury**
- ✅ Wszystkie API routes w jednym miejscu
- ✅ Wszystkie modele w `models/`
- ✅ Wszystkie serwisy w `services/` z podziałem na media
- ✅ Wspólna struktura dla wody, gazu i prądu

### 3. **Łatwiejsze Utrzymanie**
- ✅ Łatwe znajdowanie plików
- ✅ Jasne granice modułów
- ✅ Łatwiejsze testowanie
- ✅ Łatwiejsze dodawanie nowych mediów (prąd już przygotowany)
- ✅ Spójna struktura dla wszystkich mediów (woda, gaz, prąd)

### 4. **Zgodność z Best Practices**
- ✅ Struktura zgodna z FastAPI best practices
- ✅ Zgodna z Python packaging standards
- ✅ Przygotowana na skalowanie

---

## 📋 Plan Migracji (Krok po Kroku)

### Faza 1: Utworzenie Nowej Struktury
1. Utworzyć foldery: `app/`, `migrations/`, `tests/`, `docs/`
2. Przenieść pliki zgodnie z nową strukturą
3. Zaktualizować importy w wszystkich plikach

### Faza 2: Refaktoryzacja
1. Podzielić `main.py` na moduły routes
2. Przenieść logikę biznesową do `services/`
3. Ujednolicić strukturę dla wody i gazu
4. Dodać pełną strukturę dla prądu (electricity)

### Faza 3: Testy i Dokumentacja
1. Utworzyć strukture testów
2. Zaktualizować dokumentację
3. Dodać `.env.example`

### Faza 4: Cleanup
1. Usunąć puste foldery
2. Zaktualizować `.gitignore`
3. Zaktualizować README

---

## ⚠️ Uwagi

1. **Backward Compatibility**: Zachować możliwość uruchomienia przez `python main.py` lub `python run.py`
2. **Import Paths**: Użyć względnych importów lub ustawić PYTHONPATH
3. **Git History**: Rozważyć `git mv` zamiast zwykłego przenoszenia, aby zachować historię

---

## 🔧 Zalecane Dodatkowe Ulepszenia

1. **Konfiguracja przez zmienne środowiskowe**
   ```python
   # config.py
   from pydantic_settings import BaseSettings
   
   class Settings(BaseSettings):
       database_url: str = "sqlite:///./water_billing.db"
       api_title: str = "Water Billing System"
       # ...
   ```

2. **Użycie Alembic do migracji**
   - Zamiast ręcznych skryptów migracyjnych
   - Automatyczne zarządzanie wersjami schematu

3. **Struktura testów**
   ```
   tests/
   ├── unit/
   │   ├── test_models.py
   │   └── test_services.py
   ├── integration/
   │   └── test_api.py
   └── fixtures/
       └── sample_data.py
   ```

4. **Type Hints i Docstrings**
   - Dodać type hints wszędzie
   - Ujednolicić format docstrings (Google style)

5. **Pre-commit hooks**
   - `black` dla formatowania
   - `flake8` dla lintowania
   - `mypy` dla type checking

---

## 📝 Podsumowanie

**Obecna struktura:** 9/10 - ✅ Zreorganizowana, działa dobrze, prąd zaimplementowany, routes dla wody przeniesione
**Proponowana struktura:** 9/10 - Profesjonalna, skalowalna, zgodna z best practices

**Priorytet:** Niski (projekt działa dobrze, główne problemy strukturalne rozwiązane)

**Szacowany czas migracji:** < 1 godzina (pozostało: testy services/api dla prądu, implementacja bill_generator dla prądu)

---

## 📋 Plan Implementacji Prądu (Electricity)

### Krok 1: Modele bazy danych
- [x] Utworzyć `app/models/electricity.py` ✅
- [x] Zdefiniować modele: ElectricityReading, ElectricityInvoice, ElectricityBill ✅
- [x] Utworzyć migrację `migrate_add_electricity_tables.py` ✅
- [x] Uruchomić migrację ✅

### Krok 2: Serwisy
- [x] Utworzyć `app/services/electricity/invoice_reader.py` ✅
  - Wykorzystuje logikę z `tools/extract_electricity_structured.py` ✅
  - Parsowanie faktur ENEA ✅
- [x] Utworzyć `app/services/electricity/manager.py` ✅
  - Zarządzanie odczytami ✅
  - Rozliczanie zużycia ✅
- [x] Utworzyć `app/services/electricity/bill_generator.py` ✅
  - Placeholder dla generowania rachunków PDF (do implementacji później)
- [x] Utworzyć `app/services/electricity/calculator.py` ✅
  - Logika obliczeń kosztów ✅

### Krok 3: API Routes
- [x] Utworzyć `app/api/routes/electricity.py` ✅
- [x] Dodać wszystkie endpointy (CRUD dla readings, invoices, bills) ✅
- [x] Zarejestrować router w `main.py` ✅

### Krok 4: Testy
- [x] Utworzyć `tests/test_electricity_calculator.py` ✅
- [ ] Utworzyć `tests/test_electricity_services.py` ⚠️
- [ ] Utworzyć `tests/test_electricity_api.py` ⚠️

### Krok 5: Integracja z dashboardem
- [x] Dodać zakładkę "Prąd" w `app/static/dashboard.html` ✅
- [x] Dodać widoki dla odczytów, faktur i rachunków prądu ✅

**Status implementacji:** 90% ukończone (pozostało: testy services/api, implementacja bill_generator)

