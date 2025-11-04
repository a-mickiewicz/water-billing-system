# 🔧 Instrukcje Implementacji Rozszerzenia o Gaz

> **Dokument dla AI**: Ten plik zawiera instrukcje i schematy do implementacji funkcjonalności gazu w systemie rozliczeń mediów.
> 
> **Status**: Szablon do uzupełnienia przez użytkownika
> 
> **Ostatnia aktualizacja**: [DATA]

---

## 📋 Spis Treści

1. [Architektura Systemu](#architektura-systemu)
2. [Struktura Bazy Danych](#struktura-bazy-danych)
3. [Modele Danych](#modele-danych)
4. [API Endpoints](#api-endpoints)
5. [Parsowanie Faktur PDF](#parsowanie-faktur-pdf)
6. [Algorytmy Obliczeń](#algorytmy-obliczeń)
7. [Generowanie Rachunków PDF](#generowanie-rachunków-pdf)
8. [Dashboard Frontend](#dashboard-frontend)
9. [Plan Implementacji](#plan-implementacji)

---

## 🏗️ Architektura Systemu

### Zasady Ogólne

- **Separacja mediów**: Każde medium (woda, gaz, prąd) ma osobne moduły i tabele
- **Wspólny kod**: Logika wspólna znajduje się w `core/`
- **Modularność**: Każde medium ma własny folder w `utilities/`
- **API z prefixami**: Endpointy są rozdzielone przez prefix w URL (`/api/water/`, `/api/gas/`, `/api/electricity/`)

### Struktura Katalogów

```
water_billing/
├── main.py                    # Router główny - rejestruje endpointy z prefixami
├── db.py                      # Bez zmian - wspólna inicjalizacja bazy
├── models.py                  # Wspólne modele bazowe (jeśli potrzebne)
│
├── core/                      # NOWY - Wspólny kod
│   ├── __init__.py
│   ├── models.py              # Bazowe klasy abstrakcyjne (jeśli potrzebne)
│   ├── interfaces.py          # Protocols/interfaces dla mediów (opcjonalne)
│   ├── base_manager.py        # Bazowa klasa dla logiki obliczeń (opcjonalne)
│   ├── base_reader.py         # Bazowa klasa dla parsowania PDF (opcjonalne)
│   ├── base_generator.py      # Bazowa klasa dla generowania PDF (opcjonalne)
│   └── enums.py               # UtilityType enum (jeśli potrzebne)
│
├── utilities/                 # NOWY - Implementacje specyficzne dla mediów
│   ├── __init__.py
│   ├── water/                 # Istniejący kod wody (do refaktoryzacji)
│   │   ├── __init__.py
│   │   ├── models.py          # WaterReading, WaterInvoice, WaterBill
│   │   ├── manager.py         # WaterBillingManager (z meter_manager.py)
│   │   ├── reader.py          # WaterInvoiceReader (z invoice_reader.py)
│   │   └── generator.py       # WaterBillGenerator (z bill_generator.py)
│   │
│   ├── gas/                   # NOWY - Implementacja dla gazu
│   │   ├── __init__.py
│   │   ├── models.py          # GasReading, GasInvoice, GasBill
│   │   ├── manager.py         # GasBillingManager
│   │   ├── reader.py          # GasInvoiceReader
│   │   └── generator.py       # GasBillGenerator
│   │
│   └── electricity/           # PRZYSZŁOŚĆ - Implementacja dla prądu
│       └── [analogicznie]
│
├── api/                       # NOWY - Endpointy API
│   ├── __init__.py
│   ├── routes.py              # Router główny - rejestruje podrouty
│   ├── water_routes.py        # Endpointy dla wody (/api/water/*)
│   ├── gas_routes.py          # NOWY - Endpointy dla gazu (/api/gas/*)
│   └── electricity_routes.py # PRZYSZŁOŚĆ - Endpointy dla prądu
│
├── static/
│   ├── dashboard.html         # Rozszerzony o zakładki dla mediów
│
└── invoices_raw/
    ├── water/                 # Faktury wody (opcjonalnie)
    ├── gas/                   # NOWY - Faktury gazu
    └── electricity/           # PRZYSZŁOŚĆ - Faktury prądu
```

---

## 🗄️ Struktura Bazy Danych

### Zasada: Osobne Tabele dla Każdego Medium

Każde medium ma własne tabele:
- `water_readings`, `gas_readings`, `electricity_readings`
- `water_invoices`, `gas_invoices`, `electricity_invoices`
- `water_bills`, `gas_bills`, `electricity_bills`

### Tabela Lokali (Wspólna)

Tabela `locals` zawiera informacje o wszystkich licznikach dla wszystkich mediów.

**UWAGA - Nazewnictwo liczników wody:**
- `water_meter_5` = lokal "gora" (bez zmian)
- `water_meter_5a` = lokal "gabinet" (zmiana!)
- `water_meter_5b` = lokal "dol" (zmiana!)

```sql
CREATE TABLE locals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    -- Woda (istniejące)
    water_meter_name VARCHAR(50) UNIQUE,
    -- Gaz (NOWE)
    gas_meter_name VARCHAR(50) UNIQUE,
    -- Prąd (PRZYSZŁOŚĆ)
    electricity_meter_name VARCHAR(50) UNIQUE,
    
    tenant VARCHAR(100),
    local VARCHAR(50)  -- 'gora', 'gabinet', 'dol'
);
```

### Tabele dla Gazu

#### gas_readings

**Struktura liczników gazu jest prosta:**
- Jest **jeden główny licznik** (`gas_meter`)
- **NIE MA** podliczników dla poszczególnych lokali
- Koszty rozdzielane są proporcjonalnie na podstawie zużycia z faktury

```sql
CREATE TABLE gas_readings (
    data VARCHAR(7) PRIMARY KEY,  -- Format: 'YYYY-MM' (generowane z period_start faktury)
    gas_meter FLOAT NOT NULL      -- Główny licznik gazu (m³)
    -- Uwaga: NIE MA podliczników! Koszty dzielone proporcjonalnie
);
```

**Jednostka:** m³ (metr sześcienny)

#### gas_invoices

**Struktura faktury gazu (PGNiG):**
- Okres rozliczeniowy dwumiesięczny
- Nazwa okresu (`data`): YYYY-MM generowana z `period_start` (np. 2019-04-03 → "2019-04")

```sql
CREATE TABLE gas_invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data VARCHAR(7) NOT NULL,  -- 'YYYY-MM' (generowane z period_start, np. "2019-04")
    
    -- Okres rozliczeniowy faktury (dwumiesięczny)
    period_start DATE NOT NULL,  -- np. 2019-04-03
    period_stop DATE NOT NULL,   -- np. 2019-06-08
    
    -- Odczyty liczników
    previous_reading FLOAT NOT NULL,  -- Odczyt poprzedni (m³)
    current_reading FLOAT NOT NULL,   -- Odczyt obecny (m³)
    
    -- Paliwo gazowe
    fuel_usage_m3 FLOAT NOT NULL,           -- Ilość (m³)
    fuel_price_net FLOAT NOT NULL,          -- Cena netto za m³
    fuel_value_net FLOAT NOT NULL,           -- Wartość netto (ilość * cena)
    fuel_vat_amount FLOAT NOT NULL,         -- Kwota VAT (23%)
    fuel_value_gross FLOAT NOT NULL,        -- Wartość brutto
    
    -- Opłata abonamentowa
    subscription_quantity INTEGER NOT NULL,  -- Ilość miesięcy
    subscription_price_net FLOAT NOT NULL,   -- Cena netto za miesiąc
    subscription_value_net FLOAT NOT NULL,   -- Wartość netto
    subscription_vat_amount FLOAT NOT NULL,  -- Kwota VAT (23%)
    subscription_value_gross FLOAT NOT NULL, -- Wartość brutto
    
    -- Opłata dystrybucyjna stała
    distribution_fixed_quantity INTEGER NOT NULL,  -- Ilość miesięcy
    distribution_fixed_price_net FLOAT NOT NULL,    -- Cena netto za miesiąc
    distribution_fixed_vat_amount FLOAT NOT NULL,   -- Kwota VAT (23%)
    distribution_fixed_value_gross FLOAT NOT NULL,  -- Wartość brutto
    
    -- Opłata dystrybucyjna zmienna
    distribution_variable_quantity INTEGER NOT NULL,  -- Ilość miesięcy
    distribution_variable_price_net FLOAT NOT NULL,    -- Cena netto za miesiąc
    distribution_variable_vat_amount FLOAT NOT NULL,  -- Kwota VAT (23%)
    distribution_variable_value_gross FLOAT NOT NULL,  -- Wartość brutto
    
    -- VAT
    vat_rate FLOAT NOT NULL,  -- VAT (0.23 dla 23%)
    
    -- Stan należności przed rozliczeniem (opcjonalne, jeszcze nie wiadomo co z tym)
    balance_before_settlement FLOAT,  -- Stan należności przed rozliczeniem
    
    -- Numer faktury i suma
    invoice_number VARCHAR(100) NOT NULL,  -- Format: "Faktura VAT 1870315009/205"
    total_gross_sum FLOAT NOT NULL         -- Suma brutto całej faktury
);
```

**Uwagi:**
- Jednostka zużycia: m³
- VAT: 23% (0.23) dla wszystkich pozycji
- Format numeru faktury: "Faktura VAT 1870315009/205"
- Faktury zawierają nazwę PGNiG (może być użyte do weryfikacji)

#### gas_bills

**Rozdzielenie kosztów gazu:**
- **"gora"**: 50% (0.5) z całkowitego kosztu faktury brutto
- **"dol"**: 25% (0.25) z całkowitego kosztu faktury brutto
- **"gabinet"**: 25% (0.25) z całkowitego kosztu faktury brutto

**Uwaga:** Do obliczenia rachunków bierzemy **zużycie brutto z faktury** i dzielimy na powyższe proporcje.

```sql
CREATE TABLE gas_bills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data VARCHAR(7) NOT NULL,  -- 'YYYY-MM'
    local VARCHAR(50) NOT NULL,  -- 'gora', 'gabinet', 'dol'
    
    -- Relacje
    reading_id VARCHAR(7),      -- FK -> gas_readings.data
    invoice_id INTEGER,          -- FK -> gas_invoices.id
    local_id INTEGER,            -- FK -> locals.id
    
    -- Rozdzielenie kosztów (z faktury brutto)
    -- "gora": 50%, "dol": 25%, "gabinet": 25%
    cost_share FLOAT NOT NULL,     -- Udział w kosztach (0.5, 0.25, 0.25)
    
    -- Koszty rozdzielone proporcjonalnie z faktury
    fuel_cost_gross FLOAT NOT NULL,              -- Udział w koszcie paliwa (brutto)
    subscription_cost_gross FLOAT NOT NULL,      -- Udział w opłacie abonamentowej (brutto)
    distribution_fixed_cost_gross FLOAT NOT NULL,    -- Udział w opłacie dystrybucyjnej stałej (brutto)
    distribution_variable_cost_gross FLOAT NOT NULL, -- Udział w opłacie dystrybucyjnej zmiennej (brutto)
    
    -- Sumy
    total_net_sum FLOAT NOT NULL,    -- Suma netto (proporcjonalna część)
    total_gross_sum FLOAT NOT NULL,  -- Suma brutto (proporcjonalna część)
    
    -- Plik PDF
    pdf_path VARCHAR(200)      -- Ścieżka do wygenerowanego pliku PDF
);
```

---

## 📊 Modele Danych

### Model GasReading

```python
# utilities/gas/models.py

from sqlalchemy import Column, String, Float
from db import Base

class GasReading(Base):
    """
    Odczyty liczników gazu.
    
    UWAGA: Jest tylko jeden główny licznik gazu!
    Koszty rozdzielane są proporcjonalnie na podstawie faktury.
    """
    __tablename__ = "gas_readings"
    
    data = Column(String(7), primary_key=True)  # Format: 'YYYY-MM'
    gas_meter = Column(Float, nullable=False)   # Główny licznik gazu (m³)
    # Uwaga: NIE MA podliczników dla lokali!
```

### Model GasInvoice

```python
# utilities/gas/models.py

from sqlalchemy import Column, String, Float, Integer, Date

class GasInvoice(Base):
    """Faktury dostawcy gazu (PGNiG)."""
    __tablename__ = "gas_invoices"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    data = Column(String(7), nullable=False)  # 'YYYY-MM' (generowane z period_start)
    
    # Okres rozliczeniowy (dwumiesięczny)
    period_start = Column(Date, nullable=False)  # np. 2019-04-03
    period_stop = Column(Date, nullable=False)   # np. 2019-06-08
    
    # Odczyty liczników
    previous_reading = Column(Float, nullable=False)  # Odczyt poprzedni (m³)
    current_reading = Column(Float, nullable=False)   # Odczyt obecny (m³)
    
    # Paliwo gazowe
    fuel_usage_m3 = Column(Float, nullable=False)      # Ilość (m³)
    fuel_price_net = Column(Float, nullable=False)     # Cena netto za m³
    fuel_value_net = Column(Float, nullable=False)    # Wartość netto
    fuel_vat_amount = Column(Float, nullable=False)   # Kwota VAT (23%)
    fuel_value_gross = Column(Float, nullable=False)   # Wartość brutto
    
    # Opłata abonamentowa
    subscription_quantity = Column(Integer, nullable=False)  # Ilość miesięcy
    subscription_price_net = Column(Float, nullable=False)   # Cena netto za miesiąc
    subscription_value_net = Column(Float, nullable=False)    # Wartość netto
    subscription_vat_amount = Column(Float, nullable=False)  # Kwota VAT (23%)
    subscription_value_gross = Column(Float, nullable=False) # Wartość brutto
    
    # Opłata dystrybucyjna stała
    distribution_fixed_quantity = Column(Integer, nullable=False)  # Ilość miesięcy
    distribution_fixed_price_net = Column(Float, nullable=False)   # Cena netto za miesiąc
    distribution_fixed_vat_amount = Column(Float, nullable=False)  # Kwota VAT (23%)
    distribution_fixed_value_gross = Column(Float, nullable=False) # Wartość brutto
    
    # Opłata dystrybucyjna zmienna
    distribution_variable_quantity = Column(Integer, nullable=False)  # Ilość miesięcy
    distribution_variable_price_net = Column(Float, nullable=False)   # Cena netto za miesiąc
    distribution_variable_vat_amount = Column(Float, nullable=False)  # Kwota VAT (23%)
    distribution_variable_value_gross = Column(Float, nullable=False) # Wartość brutto
    
    # VAT
    vat_rate = Column(Float, nullable=False)  # VAT (0.23 dla 23%)
    
    # Stan należności przed rozliczeniem (opcjonalne)
    balance_before_settlement = Column(Float, nullable=True)
    
    # Numer faktury i suma
    invoice_number = Column(String(100), nullable=False)  # Format: "Faktura VAT 1870315009/205"
    total_gross_sum = Column(Float, nullable=False)      # Suma brutto całej faktury
```

### Model GasBill

```python
# utilities/gas/models.py

from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship

class GasBill(Base):
    """
    Wygenerowane rachunki gazu dla lokali.
    
    Rozdzielenie kosztów:
    - "gora": 50% (0.5)
    - "dol": 25% (0.25)
    - "gabinet": 25% (0.25)
    """
    __tablename__ = "gas_bills"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    data = Column(String(7), nullable=False)
    local = Column(String(50), nullable=False)  # 'gora', 'gabinet', 'dol'
    
    reading_id = Column(String(7), ForeignKey('gas_readings.data'))
    invoice_id = Column(Integer, ForeignKey('gas_invoices.id'))
    local_id = Column(Integer, ForeignKey('locals.id'))
    
    # Rozdzielenie kosztów
    cost_share = Column(Float, nullable=False)  # 0.5 dla gora, 0.25 dla dol/gabinet
    
    # Koszty rozdzielone proporcjonalnie z faktury (brutto)
    fuel_cost_gross = Column(Float, nullable=False)
    subscription_cost_gross = Column(Float, nullable=False)
    distribution_fixed_cost_gross = Column(Float, nullable=False)
    distribution_variable_cost_gross = Column(Float, nullable=False)
    
    # Sumy
    total_net_sum = Column(Float, nullable=False)    # Suma netto (proporcjonalna)
    total_gross_sum = Column(Float, nullable=False)  # Suma brutto (proporcjonalna)
    
    pdf_path = Column(String(200))
    
    reading = relationship("GasReading", back_populates="bills")
    invoice = relationship("GasInvoice", back_populates="bills")
    local_obj = relationship("Local", back_populates="gas_bills")
```

**Uwagi do uzupełnienia:**
- [ ] Czy modele są kompletne? Czy brakuje jakichś pól?
- [ ] Czy relacje w modelach są poprawne?

---

## 🔌 API Endpoints

### Struktura URL z Prefixami

Wszystkie endpointy dla gazu mają prefix `/api/gas/`:

- `/api/gas/readings/` - Odczyt odczytów gazu
- `/api/gas/invoices/` - Odczyt faktur gazu
- `/api/gas/bills/` - Odczyt rachunków gazu
- `/api/gas/bills/generate/{period}` - Generowanie rachunków

### Przykładowe Endpointy dla Gazu

#### GET /api/gas/readings/

```python
@app.get("/api/gas/readings/", response_model=List[dict])
def get_gas_readings(db: Session = Depends(get_db)):
    """Pobiera listę wszystkich odczytów gazu."""
    readings = db.query(GasReading).order_by(desc(GasReading.data)).all()
    return [{
        "data": r.data,
        "gas_meter": r.gas_meter
    } for r in readings]
```

#### POST /api/gas/readings/

```python
@app.post("/api/gas/readings/")
def create_gas_reading(
    data: str,
    gas_meter: float,
    db: Session = Depends(get_db)
):
    """Tworzy nowy odczyt licznika gazu (tylko jeden główny licznik)."""
    # Implementacja - tylko jeden licznik główny
    pass
```

**Uwagi do uzupełnienia:**
- [ ] Lista wszystkich potrzebnych endpointów dla gazu
- [ ] Czy są jakieś specyficzne endpointy dla gazu (nie ma ich dla wody)?

---

## 📄 Parsowanie Faktur PDF

### Uwaga: Każde Medium Ma Inny Format Faktury

Faktury gazu mają **inny format PDF** niż faktury wody, więc potrzebny jest **osobny parser**.

### Struktura GasInvoiceReader

```python
# utilities/gas/reader.py

import pdfplumber
from typing import Optional, Dict
from sqlalchemy.orm import Session

class GasInvoiceReader:
    """Parser faktur PDF dla gazu."""
    
    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Wyciąga tekst z pliku PDF faktury gazu."""
        # Podobnie jak WaterInvoiceReader, ale może wymagać innych opcji
        pass
    
    def parse_invoice_data(self, text: str) -> Optional[Dict]:
        """
        Parsuje dane z faktury gazu na podstawie tekstu PDF.
        
        UWAGA: To jest specyficzne dla formatu faktur gazu!
        Musi być dostosowane do rzeczywistego formatu faktur.
        """
        data = {}
        
        # Szukaj numeru faktury (Format: "Faktura VAT 1870315009/205")
        # Wzorzec: "Faktura VAT" + numer z "/"
        invoice_match = re.search(r'Faktura\s+VAT\s+(\d+/\d+)', text, re.IGNORECASE)
        if invoice_match:
            data['invoice_number'] = f"Faktura VAT {invoice_match.group(1)}"
        
        # Weryfikacja: czy to faktura PGNiG (może być użyte do walidacji)
        has_pgng = 'PGNiG' in text.upper()
        
        # Szukaj odczytów liczników
        # Poprzedni odczyt i obecny odczyt
        
        # Szukaj zużycia paliwa gazowego (ilość m³)
        # Format: pozycja "za paliwo gazowe" z ilością, ceną netto, wartością netto, VAT, wartością brutto
        
        # Szukaj opłaty abonamentowej
        # Format: ilość miesięcy, cena netto, wartość netto, VAT, wartość brutto
        
        # Szukaj opłaty dystrybucyjnej stałej
        # Format: ilość miesięcy, cena netto, VAT, wartość brutto
        
        # Szukaj opłaty dystrybucyjnej zmiennej
        # Format: ilość miesięcy, cena netto, VAT, wartość brutto
        
        # Szukaj dat okresu rozliczeniowego (dwumiesięczny)
        # Format: od DD-MM-YYYY do DD-MM-YYYY
        
        # Szukaj VAT (23% dla wszystkich pozycji)
        
        # Szukaj sumy brutto całej faktury
        
        return data
    
    def load_invoice_from_pdf(self, db: Session, pdf_path: str, period: Optional[str] = None) -> Optional[GasInvoice]:
        """
        Parsuje fakturę gazu z pliku PDF.
        
        UWAGA: Przed zapisem do bazy danych, należy wyświetlić dane w dashboardzie
        dla użytkownika do weryfikacji i ewentualnej zmiany.
        Zobacz sekcję "Dashboard Frontend" - Parsowanie z weryfikacją.
        """
        # Parsuj dane, ale NIE zapisuj od razu - zwróć dane do weryfikacji
        pass
    
    def save_invoice_after_verification(self, db: Session, invoice_data: dict) -> Optional[GasInvoice]:
        """
        Zapisuje fakturę do bazy danych po weryfikacji przez użytkownika.
        Wywoływane z dashboardu po zatwierdzeniu przez użytkownika.
        """
        pass
```

### Do Uzupełnienia

**Ważne pytania dotyczące faktur gazu:**

**Zdefiniowane wymagania:**

1. **Format numeru faktury:**
   - Format: `Faktura VAT 1870315009/205`
   - Wzorzec: `Faktura VAT` + numer z "/"

2. **Struktura faktury (PGNiG):**
   - Faktura zawiera nazwę **PGNiG** (może być użyte do weryfikacji)
   - Okres rozliczeniowy: **dwumiesięczny** (np. od 2019-04-03 do 2019-06-08)
   - Nazwa okresu: YYYY-MM generowana z `period_start` (np. 2019-04)

3. **Pozycje w fakturze:**
   - **Za paliwo gazowe**: ilość (m³), cena netto, wartość netto, VAT (23%), kwota VAT, wartość brutto
   - **Opłata abonamentowa**: ilość (miesięcy), cena netto, wartość netto, VAT (23%), kwota VAT, wartość brutto
   - **Opłata dystrybucyjna stała**: ilość (miesięcy), cena netto, VAT (23%), kwota VAT, wartość brutto
   - **Opłata dystrybucyjna zmienna**: ilość (miesięcy), cena netto, VAT (23%), kwota VAT, wartość brutto
   - **Stan należności przed rozliczeniem**: (nie wiadomo jeszcze co z tym robić)

4. **Jednostka:** m³ (metr sześcienny)

5. **VAT:** 23% (0.23) dla wszystkich pozycji

6. **Odczyty liczników:**
   - Odczyt poprzedni
   - Odczyt obecny

**Zalecenie:** 
- Przeanalizuj przykładowe faktury gazu
- Dodaj przykładowe fragmenty tekstu z faktury do tego dokumentu
- Określ dokładne wzorce regex do wyszukiwania danych

---

## 🧮 Algorytmy Obliczeń

### Uwaga: Algorytmy Są Różne dla Każdego Medium

Algorytmy obliczania kosztów dla gazu są **inne niż woda**. 

**Kluczowa różnica:**
- Woda: oblicza zużycie z odczytów liczników dla każdego lokalu osobno
- Gaz: **NIE oblicza zużycia z odczytów!** Używa zużycia brutto z faktury i dzieli proporcjonalnie

### GasBillingManager

```python
# utilities/gas/manager.py

from sqlalchemy.orm import Session
from utilities.gas.models import GasReading, GasInvoice, GasBill
from models import Local  # Tabela lokali (wspólna dla wszystkich mediów)

class GasBillingManager:
    """Zarządzanie licznikami i rozliczaniem rachunków za gaz."""
    
    def calculate_bill_costs(
        self,
        invoice: GasInvoice,
        local_name: str
    ) -> dict:
        """
        Oblicza koszty dla pojedynczego rachunku gazu.
        
        Algorytm:
        1. Bierzemy całkowite koszty brutto z faktury:
           - fuel_value_gross (paliwo gazowe)
           - subscription_value_gross (opłata abonamentowa)
           - distribution_fixed_value_gross (opłata dystrybucyjna stała)
           - distribution_variable_value_gross (opłata dystrybucyjna zmienna)
        
        2. Dzielimy proporcjonalnie:
           - "gora": 50% (0.5) z każdego kosztu
           - "dol": 25% (0.25) z każdego kosztu
           - "gabinet": 25% (0.25) z każdego kosztu
        
        3. Obliczamy sumę netto i brutto dla lokalu
        """
        # Proporcje dla lokali
        if local_name == 'gora':
            share = 0.5  # 50%
        elif local_name in ['dol', 'gabinet']:
            share = 0.25  # 25%
        else:
            raise ValueError(f"Nieznany lokal: {local_name}")
        
        # Rozdziel koszty z faktury (brutto)
        fuel_cost_gross = invoice.fuel_value_gross * share
        subscription_cost_gross = invoice.subscription_value_gross * share
        distribution_fixed_cost_gross = invoice.distribution_fixed_value_gross * share
        distribution_variable_cost_gross = invoice.distribution_variable_value_gross * share
        
        # Suma brutto dla lokalu
        total_gross = (fuel_cost_gross + subscription_cost_gross + 
                      distribution_fixed_cost_gross + distribution_variable_cost_gross)
        
        # Suma netto (bez VAT 23%)
        total_net = total_gross / 1.23  # Odwrotność VAT
        
        return {
            'cost_share': share,
            'fuel_cost_gross': fuel_cost_gross,
            'subscription_cost_gross': subscription_cost_gross,
            'distribution_fixed_cost_gross': distribution_fixed_cost_gross,
            'distribution_variable_cost_gross': distribution_variable_cost_gross,
            'total_net_sum': total_net,
            'total_gross_sum': total_gross
        }
    
    def generate_bills_for_period(self, db: Session, period: str) -> list[GasBill]:
        """
        Generuje rachunki gazu dla wszystkich lokali na dany okres.
        
        Algorytm:
        1. Pobierz odczyt dla okresu (opcjonalne, tylko do przechowania)
        2. Pobierz WSZYSTKIE faktury dla okresu (może być wiele)
        3. Dla każdej faktury i każdego lokalu:
           - Oblicz proporcjonalne koszty (50%/25%/25%)
           - Utwórz rachunek
        4. Jeśli jest wiele faktur, sumuj koszty dla każdego lokalu
        
        UWAGA: NIE obliczamy zużycia z odczytów!
        Używamy bezpośrednio kosztów brutto z faktury.
        """
        # 1. Pobierz odczyt (opcjonalnie, tylko do przechowania w relacji)
        reading = db.query(GasReading).filter(GasReading.data == period).first()
        
        # 2. Pobierz wszystkie faktury dla okresu
        invoices = db.query(GasInvoice).filter(GasInvoice.data == period).all()
        if not invoices:
            raise ValueError(f"Brak faktur dla okresu {period}")
        
        # 3. Dla każdego lokalu i każdej faktury oblicz koszty
        locals_list = ['gora', 'dol', 'gabinet']
        bills = []
        
        for local_name in locals_list:
            # Sumuj koszty ze wszystkich faktur dla tego lokalu
            total_fuel_gross = 0
            total_subscription_gross = 0
            total_dist_fixed_gross = 0
            total_dist_variable_gross = 0
            
            for invoice in invoices:
                costs = self.calculate_bill_costs(invoice, local_name)
                total_fuel_gross += costs['fuel_cost_gross']
                total_subscription_gross += costs['subscription_cost_gross']
                total_dist_fixed_gross += costs['distribution_fixed_cost_gross']
                total_dist_variable_gross += costs['distribution_variable_cost_gross']
            
            # Suma brutto i netto
            total_gross = (total_fuel_gross + total_subscription_gross + 
                          total_dist_fixed_gross + total_dist_variable_gross)
            total_net = total_gross / 1.23  # Odwrotność VAT 23%
            
            # Utwórz rachunek
            local_obj = db.query(Local).filter(Local.local == local_name).first()
            if not local_obj:
                raise ValueError(f"Brak lokalizacji '{local_name}' w bazie")
            
            bill = GasBill(
                data=period,
                local=local_name,
                reading_id=period if reading else None,
                invoice_id=invoices[0].id,  # Pierwsza faktura
                local_id=local_obj.id,
                cost_share=0.5 if local_name == 'gora' else 0.25,
                fuel_cost_gross=round(total_fuel_gross, 2),
                subscription_cost_gross=round(total_subscription_gross, 2),
                distribution_fixed_cost_gross=round(total_dist_fixed_gross, 2),
                distribution_variable_cost_gross=round(total_dist_variable_gross, 2),
                total_net_sum=round(total_net, 2),
                total_gross_sum=round(total_gross, 2)
            )
            
            db.add(bill)
            bills.append(bill)
        
        db.commit()
        return bills
```

### Podsumowanie Algorytmów

**Zdefiniowane algorytmy:**

1. **Obliczanie zużycia:**
   - ❌ **NIE obliczamy zużycia z odczytów!**
   - ✅ Używamy bezpośrednio kosztów brutto z faktury
   - Odczyty są przechowywane tylko do informacji (nie używane w obliczeniach)

2. **Kalkulacja kosztów:**
   - Bierzemy całkowite koszty brutto z faktury:
     - Paliwo gazowe (fuel_value_gross)
     - Opłata abonamentowa (subscription_value_gross)
     - Opłata dystrybucyjna stała (distribution_fixed_value_gross)
     - Opłata dystrybucyjna zmienna (distribution_variable_value_gross)
   - Dzielimy proporcjonalnie:
     - "gora": 50% (0.5)
     - "dol": 25% (0.25)
     - "gabinet": 25% (0.25)

3. **Wiele faktur dla jednego okresu:**
   - ✅ Obsługiwane: jeśli jest wiele faktur, sumujemy koszty dla każdego lokalu

4. **VAT:**
   - Wszystkie pozycje mają VAT 23% (0.23)
   - Suma netto = suma brutto / 1.23

5. **Brak korekt:**
   - ❌ Nie ma korekt różnic między fakturą a odczytami (nie używamy odczytów do obliczeń)
   - ❌ Nie ma kompensacji między okresami

---

## 📝 Generowanie Rachunków PDF

### GasBillGenerator

```python
# utilities/gas/generator.py

from sqlalchemy.orm import Session
from utilities.gas.models import GasBill

class GasBillGenerator:
    """Generowanie plików PDF rachunków za gaz."""
    
    def generate_bill_pdf(self, db: Session, bill: GasBill) -> str:
        """
        Generuje plik PDF rachunku za gaz.
        
        UWAGA: Szablon PDF może się różnić od wody!
        [DO UZUPEŁNIENIA: Jak wygląda szablon rachunku za gaz?]
        """
        # Podobnie jak WaterBillGenerator, ale z innym szablonem
        pass
```

### Szablon Rachunku

**Uwaga:** Rachunki generowane są **osobno dla każdego medium** (dopóki użytkownik nie zdecyduje inaczej).

**Dane do wyświetlenia w rachunku za gaz:**
- Okres rozliczeniowy (data)
- Lokal (gora/gabinet/dol)
- Proporcja kosztów (50% dla gora, 25% dla dol/gabinet)
- Rozdzielone koszty:
  - Paliwo gazowe (brutto): `fuel_cost_gross`
  - Opłata abonamentowa (brutto): `subscription_cost_gross`
  - Opłata dystrybucyjna stała (brutto): `distribution_fixed_cost_gross`
  - Opłata dystrybucyjna zmienna (brutto): `distribution_variable_cost_gross`
- Suma netto: `total_net_sum`
- Suma brutto: `total_gross_sum`

**Formatowanie:**
- Jednostka: m³ (metr sześcienny)
- Wszystkie kwoty z 2 miejscami po przecinku
- VAT: 23% (można wyświetlić w podsumowaniu)

---

## 🖥️ Dashboard Frontend

### Rozszerzenie Dashboardu

Dashboard powinien mieć **zakładki dla każdego medium**:

- Zakładka "Woda" (istniejąca)
- Zakładka "Gaz" (NOWA)
- Zakładka "Prąd" (PRZYSZŁOŚĆ)

### Struktura Dashboardu

```html
<!-- static/dashboard.html -->

<div class="tabs">
    <button class="tab" data-tab="water">Woda</button>
    <button class="tab" data-tab="gas">Gaz</button>
    <button class="tab" data-tab="electricity">Prąd</button>
</div>

<div class="tab-content" id="water-tab">
    <!-- Istniejący dashboard wody -->
</div>

<div class="tab-content" id="gas-tab">
    <!-- NOWY: Dashboard dla gazu -->
    <!-- Podobny do wody, ale używa endpointów /api/gas/* -->
</div>
```

### Endpointy API dla Dashboardu

```python
@app.get("/api/gas/stats")
def get_gas_stats(db: Session = Depends(get_db)):
    """Zwraca statystyki dla dashboardu gazu."""
    stats = {
        "readings_count": db.query(GasReading).count(),
        "invoices_count": db.query(GasInvoice).count(),
        "bills_count": db.query(GasBill).count(),
        "latest_period": None,
        "total_gross_sum": 0,
        # ... podobnie jak get_stats dla wody
    }
    return stats
```

### Parsowanie z Weryfikacją (WYMAGANE)

**WAŻNE:** Przed zapisem faktury do bazy danych, należy wyświetlić sparsowane dane w dashboardzie dla użytkownika do weryfikacji i ewentualnej zmiany.

**Proces:**
1. Użytkownik przesyła fakturę PDF przez dashboard
2. System parsuje fakturę (`GasInvoiceReader.parse_invoice_data`)
3. **Zamiast zapisać od razu**, system zwraca sparsowane dane do dashboardu
4. Dashboard wyświetla formularz z wypełnionymi polami (do weryfikacji)
5. Użytkownik może sprawdzić i zmienić wartości
6. Po zatwierdzeniu (`POST /api/gas/invoices/verify`), faktura jest zapisywana do bazy

**Endpoint weryfikacji:**

```python
@app.post("/api/gas/invoices/verify")
def verify_and_save_gas_invoice(
    invoice_data: dict,  # Sparsowane dane z możliwością edycji
    db: Session = Depends(get_db)
):
    """
    Zapisuje fakturę gazu po weryfikacji przez użytkownika.
    Wywoływane z dashboardu po zatwierdzeniu.
    """
    # Zapis do bazy danych
    pass
```

**Endpoint parsowania (bez zapisu):**

```python
@app.post("/api/gas/invoices/parse")
async def parse_gas_invoice(
    file: UploadFile = File(...)
):
    """
    Parsuje fakturę PDF i zwraca dane do weryfikacji.
    NIE zapisuje do bazy danych!
    """
    # Parsuj i zwróć dane
    pass
```

---

## 📅 Plan Implementacji

### Faza 1: Przygotowanie Bazy Danych

1. **Rozszerzenie modelu `Local`:**
   - [ ] Dodać kolumnę `gas_meter_name`
   - [ ] Utworzyć migrację (lub zaktualizować `init_db`)

2. **Utworzenie tabel dla gazu:**
   - [ ] `gas_readings`
   - [ ] `gas_invoices`
   - [ ] `gas_bills`
   - [ ] Utworzenie modeli SQLAlchemy

### Faza 2: Modele i Manager

3. **Utworzenie modułu `utilities/gas/`:**
   - [ ] `models.py` - Modele GasReading, GasInvoice, GasBill
   - [ ] `manager.py` - GasBillingManager z logiką obliczeń
   - [ ] Implementacja algorytmów (po uzupełnieniu sekcji "Algorytmy")

### Faza 3: Parser Faktur PDF

4. **Utworzenie `utilities/gas/reader.py`:**
   - [ ] GasInvoiceReader z metodą `extract_text_from_pdf`
   - [ ] Implementacja `parse_invoice_data` (po uzupełnieniu sekcji "Parsowanie Faktur PDF")
   - [ ] Testowanie na przykładowych fakturach

### Faza 4: API Endpoints

5. **Utworzenie `api/gas_routes.py`:**
   - [ ] Endpointy dla odczytów (`GET/POST /api/gas/readings/`)
   - [ ] Endpointy dla faktur (`GET/POST /api/gas/invoices/`, `/api/gas/invoices/upload`)
   - [ ] Endpointy dla rachunków (`GET /api/gas/bills/`, `POST /api/gas/bills/generate/{period}`)
   - [ ] Endpoint statystyk (`GET /api/gas/stats`)

6. **Rejestracja w `main.py`:**
   - [ ] Zaimportować `gas_routes`
   - [ ] Zarejestrować router z prefixem `/api/gas`

### Faza 5: Generowanie PDF

7. **Utworzenie `utilities/gas/generator.py`:**
   - [ ] GasBillGenerator z metodą `generate_bill_pdf`
   - [ ] Szablon PDF (po uzupełnieniu sekcji "Generowanie Rachunków PDF")

### Faza 6: Dashboard Frontend

8. **Rozszerzenie `static/dashboard.html`:**
   - [ ] Dodanie zakładki "Gaz"
   - [ ] Implementacja interfejsu dla gazu (podobny do wody)
   - [ ] Integracja z endpointami `/api/gas/*`

### Faza 7: Testy

9. **Testowanie:**
   - [ ] Testy dodawania odczytów
   - [ ] Testy parsowania faktur PDF
   - [ ] Testy generowania rachunków
   - [ ] Testy API endpointów
   - [ ] Testy dashboardu

---

## ✅ Checklist Implementacji

### Przed Rozpoczęciem

- [ ] Przeanalizować przykładowe faktury gazu
- [ ] Określić format numerów faktur gazu
- [ ] Określić strukturę danych w fakturze gazu
- [ ] Określić algorytmy obliczeń (czy takie same jak woda?)
- [ ] Określić szablon rachunku PDF

### Podczas Implementacji

- [ ] Utworzyć modele bazy danych
- [ ] Zaimplementować parser faktur PDF
- [ ] Zaimplementować manager z algorytmami
- [ ] Zaimplementować generator PDF
- [ ] Utworzyć endpointy API
- [ ] Rozszerzyć dashboard

### Po Implementacji

- [ ] Przetestować na rzeczywistych danych
- [ ] Zweryfikować poprawność obliczeń
- [ ] Sprawdzić generowanie PDF
- [ ] Zaktualizować dokumentację

---

## 📌 Notatki Dodatkowe

### Miejsca Do Uzupełnienia

Ten dokument zawiera sekcje oznaczone jako `[DO UZUPEŁNIENIA]`. Przed rozpoczęciem implementacji przez AI, uzupełnij:

1. **Sekcja "Struktura Bazy Danych":**
   - Jednostki pomiaru
   - Struktura liczników
   - Pola kosztów i abonamentów

2. **Sekcja "Parsowanie Faktur PDF":**
   - Format numerów faktur
   - Wzorce regex do parsowania
   - Przykładowe fragmenty faktur

3. **Sekcja "Algorytmy Obliczeń":**
   - Szczegółowe reguły obliczeń
   - Obsługa specjalnych przypadków
   - Logika korekt i kompensacji

4. **Sekcja "Generowanie Rachunków PDF":**
   - Szablon rachunku
   - Lista pól do wyświetlenia

### Przykładowe Faktury

Jeśli masz przykładowe faktury gazu, dodaj tutaj:
- Fragmenty tekstu z faktur (do analizy formatu)
- Przykładowe numery faktur
- Przykładowe wartości (zużycie, koszty, daty)

---

## 🔗 Linki i Referencje

- [ARCHITECTURE_PROPOSALS.md](ARCHITECTURE_PROPOSALS.md) - Propozycje architektury
- [CALCULATION_LOGIC.md](CALCULATION_LOGIC.md) - Logika obliczeń wody (do porównania)
- `meter_manager.py` - Manager dla wody (do porównania)
- `invoice_reader.py` - Parser faktur wody (do porównania)

---

**Status dokumentu:** ⚠️ Szablon - wymaga uzupełnienia przez użytkownika

**Ostatnia aktualizacja:** [DATA]

