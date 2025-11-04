# 🏗️ Propozycje Architektury - Rozszerzenie o Gaz i Prąd

## 📋 Zakres rozszerzenia
Rozszerzenie obecnego systemu o rozliczenia za **gaz** i **prąd** dla tych samych lokali, przy zachowaniu obecnej funkcjonalności dla wody.

---

## 🎯 Opcja 1: Rozszerzenie z Enum/Type (Najprostsze)

### Koncept
Dodaj pole `utility_type` (water/gas/electricity) do istniejących tabel, zachowując obecną strukturę.

### Struktura katalogów:
```
water_billing/
├── main.py                    # Uniwersalne endpointy z parametrem utility_type
├── models.py                  # Rozszerzone modele z utility_type enum
├── db.py                      # Bez zmian
├── core/                      # NOWY folder
│   ├── __init__.py
│   ├── utilities.py           # Enum: UtilityType (WATER, GAS, ELECTRICITY)
│   └── base_models.py         # Bazowe klasy dla wszystkich mediów
├── utilities/                  # NOWY folder
│   ├── __init__.py
│   ├── water/                 # Specyficzne dla wody
│   │   ├── manager.py         # meter_manager.py → tutaj
│   │   ├── reader.py          # invoice_reader.py → tutaj
│   │   └── generator.py       # bill_generator.py → tutaj
│   ├── gas/
│   │   ├── manager.py
│   │   ├── reader.py
│   │   └── generator.py
│   └── electricity/
│       ├── manager.py
│       ├── reader.py
│       └── generator.py
├── static/
│   ├── dashboard.html         # Rozszerzony o zakładki dla mediów
└── ...
```

### Baza danych - warianty:

#### Wariant 1A: Pojedyncze tabele z utility_type
```sql
-- Rozszerzone tabele z kolumną utility_type
readings:
  data, utility_type, meter_main, meter_5, meter_5b

invoices:
  data, utility_type, usage, cost_per_unit, ...

bills:
  data, utility_type, local, usage, cost, ...
```

**Zalety:**
- Proste zapytania: `WHERE utility_type = 'GAS'`
- Wspólne endpointy API
- Jeden plik models.py

**Wady:**
- Różne jednostki (m³ vs kWh) w tej samej kolumnie
- Możliwe kolizje kluczy (data + utility_type potrzebne jako PK)

#### Wariant 1B: Osobne tabele z prefixem
```sql
-- Dla każdego medium osobne tabele
water_readings, gas_readings, electricity_readings
water_invoices, gas_invoices, electricity_invoices
water_bills, gas_bills, electricity_bills
```

**Zalety:**
- Czysta separacja danych
- Różne schematy dla różnych mediów
- Łatwiejsze migracje

**Wady:**
- Duplikacja schematu
- Trzeba zarządzać wieloma tabelami

---

## 🏛️ Opcja 2: Modularna Architektura z Abstrakcjami (Zalecana)

### Koncept
Wspólny interfejs/protocol dla wszystkich mediów, osobne implementacje.

### Struktura katalogów:
```
water_billing/
├── main.py                    # Router do odpowiednich modułów
├── db.py                      # Bez zmian
├── core/                      # NOWY - Wspólny kod
│   ├── __init__.py
│   ├── models.py              # Bazowe klasy abstrakcyjne
│   ├── interfaces.py          # Protocols/interfaces dla mediów
│   ├── base_manager.py        # Bazowa klasa dla logiki obliczeń
│   ├── base_reader.py         # Bazowa klasa dla parsowania PDF
│   ├── base_generator.py      # Bazowa klasa dla generowania PDF
│   └── enums.py               # UtilityType enum
├── utilities/                 # NOWY - Implementacje
│   ├── __init__.py
│   ├── water/
│   │   ├── __init__.py
│   │   ├── models.py          # WaterReading, WaterInvoice, WaterBill
│   │   ├── manager.py         # WaterBillingManager(BaseManager)
│   │   ├── reader.py          # WaterInvoiceReader(BaseReader)
│   │   └── generator.py       # WaterBillGenerator(BaseGenerator)
│   ├── gas/
│   │   └── [analogicznie]
│   └── electricity/
│       └── [analogicznie]
├── api/                       # NOWY - Endpointy API
│   ├── __init__.py
│   ├── routes.py              # Router główny
│   ├── water_routes.py        # Endpointy dla wody
│   ├── gas_routes.py          # Endpointy dla gazu
│   └── electricity_routes.py # Endpointy dla prądu
├── static/
│   ├── dashboard.html         # Dashboard z zakładkami mediów
└── ...
```

### Baza danych:
```sql
-- Wspólna tabela lokali (bez zmian)
locals: id, water_meter_name, gas_meter_name, electricity_meter_name, ...

-- Osobne tabele dla każdego medium
water_readings: data, water_meter_main, water_meter_5, ...
gas_readings: data, gas_meter_main, gas_meter_5, ...
electricity_readings: data, electricity_meter_main, ...

water_invoices: data, usage, cost_per_m3, ...
gas_invoices: data, usage, cost_per_m3, ...
electricity_invoices: data, usage, cost_per_kwh, ...
```

### Interfejsy (Python Protocols):
```python
# core/interfaces.py
from typing import Protocol

class BillingManagerProtocol(Protocol):
    def calculate_usage(self, current, previous) -> float:
        ...
    
    def calculate_costs(self, usage, invoice) -> dict:
        ...

class InvoiceReaderProtocol(Protocol):
    def parse_invoice(self, pdf_path: str) -> dict:
        ...
```

### Zalety:
- ✅ Zgodność z SOLID principles
- ✅ Łatwe testowanie (mocki dla interfaces)
- ✅ Wspólny kod w core/
- ✅ Łatwe dodawanie nowych mediów
- ✅ Czytelna struktura

### Wady:
- ⚠️ Więcej plików
- ⚠️ Potrzeba refaktoryzacji obecnego kodu

---

## 🔌 Opcja 3: Plugin-based Architecture (Najbardziej elastyczna)

### Koncept
System rejestracji "pluginów" dla mediów, każdy medium to plugin.

### Struktura katalogów:
```
water_billing/
├── main.py                    # Rejestruje pluginy
├── core/
│   ├── plugin_registry.py     # Rejestr dostępnych mediów
│   ├── base_plugin.py         # Klasa bazowa dla pluginów
│   └── ...
├── plugins/                   # NOWY
│   ├── __init__.py
│   ├── water_plugin.py        # Klasa WaterPlugin(BasePlugin)
│   ├── gas_plugin.py
│   └── electricity_plugin.py
├── ...
```

### Implementacja:
```python
# core/base_plugin.py
class BasePlugin(ABC):
    utility_type: str
    unit: str  # "m³", "kWh", etc.
    
    @abstractmethod
    def calculate_usage(self, ...):
        pass
    
    @abstractmethod
    def parse_invoice(self, ...):
        pass

# plugins/water_plugin.py
class WaterPlugin(BasePlugin):
    utility_type = "water"
    unit = "m³"
    # implementacja...
```

**Zalety:**
- ✅ Maksymalna elastyczność
- ✅ Łatwe wyłączanie/włączanie mediów
- ✅ Możliwość pluginów z zewnątrz

**Wady:**
- ⚠️ Overhead dla prostego przypadku
- ⚠️ Złożoność implementacji

---

## 📊 Opcja 4: Hybrydowa - Shared Services (Praktyczna)

### Koncept
Wspólne serwisy dla powtarzalnych operacji, osobne moduły dla specyfiki.

### Struktura katalogów:
```
water_billing/
├── main.py
├── services/                  # NOWY - Wspólne serwisy
│   ├── __init__.py
│   ├── database_service.py    # Operacje DB
│   ├── pdf_service.py         # Generowanie PDF (wspólne)
│   ├── validation_service.py  # Walidacja danych
│   └── calculation_service.py # Wspólne obliczenia
├── utilities/                 # Specyfika mediów
│   ├── water/
│   │   ├── models.py
│   │   ├── business_logic.py  # Specyficzna logika wody
│   │   └── invoice_parser.py # Parsowanie faktur wody
│   ├── gas/
│   │   └── [analogicznie]
│   └── electricity/
│       └── [analogicznie]
└── ...
```

**Zalety:**
- ✅ DRY - wspólny kod w services/
- ✅ Separacja: services (wspólne) vs utilities (specyficzne)
- ✅ Łatwa migracja z obecnego kodu

---

## 🎨 Nazewnictwo - Propozycje

### Opcja A: Prefiksy
- `water_readings`, `gas_readings`, `electricity_readings`
- `water_invoices`, `gas_invoices`, `electricity_invoices`
- `WaterManager`, `GasManager`, `ElectricityManager`

### Opcja B: Suffiksy
- `readings_water`, `readings_gas`, `readings_electricity`
- `InvoiceWater`, `InvoiceGas`, `InvoiceElectricity`

### Opcja C: Wspólne z enum
- `readings` (z kolumną `utility_type`)
- `invoices` (z kolumną `utility_type`)
- `UtilityManager.get('water')`

---

## 🗄️ Baza danych - Szczegółowe propozycje

### Wariant A: Single Table Inheritance
```sql
-- Jedna tabela, różne kolumny dla różnych mediów (NULL dla niewłaściwych)
readings:
  id, data, utility_type,
  water_meter_main, gas_meter_main, electricity_meter_main,
  meter_5, meter_5b
```

### Wariant B: Table Per Type (Zalecany)
```sql
-- Osobne tabele dla każdego medium
water_readings (data PK, water_meter_main, water_meter_5, ...)
gas_readings (data PK, gas_meter_main, gas_meter_5, ...)
electricity_readings (data PK, electricity_meter_main, ...)
```

### Wariant C: Polymorphic Associations
```sql
-- Tabela bazowa + tabele specyficzne
utility_readings (id PK, utility_type, data)
water_readings (id FK -> utility_readings, water_meter_main, ...)
gas_readings (id FK -> utility_readings, gas_meter_main, ...)
```

---

## 🔄 Migracja - Propozycje

### Strategia 1: Ewolucyjna (Zalecana)
1. **Faza 1:** Refaktoryzacja obecnego kodu do `utilities/water/`
2. **Faza 2:** Utworzenie `core/` z abstrakcjami
3. **Faza 3:** Implementacja gazu używając abstrakcji
4. **Faza 4:** Implementacja prądu

### Strategia 2: Wielka migracja
- Refaktoryzacja wszystkiego naraz
- Wyższe ryzyko, ale szybsza implementacja

---

## 📝 API Endpoints - Propozycje

### Wariant 1: Prefix w URL
```
/api/water/readings/
/api/gas/readings/
/api/electricity/readings/
```

### Wariant 2: Query parameter
```
/api/readings/?utility=water
/api/readings/?utility=gas
```

### Wariant 3: Wspólne endpointy z enum
```
/api/readings/          # Wszystkie media
/api/readings/water/    # Tylko woda
/api/bills/{utility}/   # {utility} = water|gas|electricity
```

---

## 🎯 Moja Rekomendacja

**Opcja 2: Modularna Architektura z Abstrakcjami** + **Table Per Type** dla bazy danych

### Dlaczego?
1. ✅ **Skalowalność** - łatwo dodać kolejne media
2. ✅ **Maintainability** - jasny podział odpowiedzialności
3. ✅ **Testowalność** - łatwe mocki i testy
4. ✅ **DRY** - wspólny kod w core/
5. ✅ **Profesjonalizm** - zgodne z wzorcami SOLID

### Struktura docelowa:
```
water_billing/
├── main.py
├── core/
│   ├── models.py              # Bazowe klasy
│   ├── interfaces.py          # Protocols
│   └── enums.py               # UtilityType
├── utilities/
│   ├── water/                 # Obecny kod przeniesiony tutaj
│   ├── gas/                   # Nowa implementacja
│   └── electricity/           # Nowa implementacja
├── api/
│   └── routes.py              # Routing z utility_type
└── static/
    └── dashboard.html         # Multi-tab dashboard
```

---

## 🤔 Pytania do rozważenia

1. **Czy gaz i prąd mają te same lokale?**
   - Jeśli tak → wspólna tabela `locals`
   - Jeśli nie → osobne tabele lub rozszerzona struktura

2. **Czy faktury mają ten sam format PDF?**
   - Jeśli różne → osobne parsery w każdym module
   - Jeśli podobne → wspólny parser z konfiguracją

3. **Czy algorytm rozliczania jest identyczny?**
   - Jeśli tak → wspólna logika w core/
   - Jeśli różny → osobne implementacje

4. **Czy rachunki PDF mają ten sam szablon?**
   - Jeśli tak → wspólny generator z parametrami
   - Jeśli nie → osobne generatory

---

## 📊 Porównanie opcji

| Kryterium | Opcja 1 (Enum) | Opcja 2 (Modularna) | Opcja 3 (Plugin) | Opcja 4 (Hybrydowa) |
|-----------|----------------|-------------------|------------------|-------------------|
| **Złożoność** | ⭐ Niska | ⭐⭐ Średnia | ⭐⭐⭐ Wysoka | ⭐⭐ Średnia |
| **Skalowalność** | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| **Testowalność** | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| **Migracja** | ⭐⭐⭐ Łatwa | ⭐⭐ Średnia | ⭐ Trudna | ⭐⭐ Średnia |
| **Czytelność** | ⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ |
| **DRY** | ⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |

---

**Którą opcję wybierasz? Mogę przygotować szczegółowy plan implementacji wybranej opcji.**

