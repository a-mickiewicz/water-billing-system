# 💧 Water Billing System

System rozliczania rachunków za wodę i ścieki dla budynku z trzema lokalami.

## 📋 Opis projektu

Aplikacja automatycznie rozlicza rachunki za wodę i ścieki na podstawie:
- Faktur od dostawcy mediów (PDF)
- Odczyty stanów liczników
- Algorytm rozliczania dla trzech lokali

## 🚀 Technologie

- **Python 3.11+**
- **FastAPI** - API RESTful
- **SQLAlchemy** - ORM
- **SQLite** - baza danych
- **pdfplumber** - parsowanie faktur PDF
- **reportlab** - generowanie rachunków PDF

## 📦 Instalacja

### 1. Aktywuj środowisko wirtualne

```bash
# Windows
.\venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 2. Zainstaluj zależności

```bash
pip install -r requirements.txt
```

### 3. Inicjalizuj bazę danych

```bash
python db.py
```

## 🏃 Uruchomienie

```bash
python main.py
```

Lub z uvicorn:

```bash
uvicorn main:app --reload
```

Aplikacja będzie dostępna pod adresem: http://localhost:8000

Dokumentacja API (Swagger): http://localhost:8000/docs

## 📁 Struktura projektu

```
water_billing/
├── main.py                 # FastAPI aplikacja
├── db.py                   # Konfiguracja bazy danych
├── models.py               # Modele SQLAlchemy
├── invoice_reader.py       # Parsowanie faktur PDF
├── meter_manager.py        # Logika rozliczeń
├── bill_generator.py       # Generowanie rachunków PDF
├── requirements.txt        # Zależności Python
├── invoices_raw/           # Folder z faktrami PDF (wejście)
├── bills/                  # Folder z wygenerowanymi rachunkami (wyjście)
└── water_billing.db       # Baza danych SQLite
```

## 🧑‍💻 Podstawowe użycie

### 1. Dodaj dane o lokalach

```bash
curl -X POST "http://localhost:8000/locals/?water_meter_name=water_meter_5&tenant=Jan+Kowalski&local=gora"
```

Lub użyj endpoint `/load_sample_data`:

```bash
curl -X POST "http://localhost:8000/load_sample_data"
```

### 2. Dodaj odczyt liczników

```bash
curl -X POST "http://localhost:8000/readings/" \
  -H "Content-Type: application/json" \
  -d '{
    "data": "2025-02",
    "water_meter_main": 150.5,
    "water_meter_5": 45.0,
    "water_meter_5b": 38.0
  }'
```

### 3. Dodaj fakturę

**Opcja A: Wczytaj fakturę PDF**

```bash
# Wklej fakturę PDF do folderu invoices_raw/
# Albo użyj endpointa:
curl -X POST "http://localhost:8000/invoices/upload" \
  -F "file=@invoices_raw/invoice__2025_02.pdf"
```

**Opcja B: Dodaj fakturę ręcznie**

```bash
curl -X POST "http://localhost:8000/invoices/" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "data=2025-02" \
  -d "usage=45.5" \
  -d "water_cost_m3=15.20" \
  -d "sewage_cost_m3=12.50" \
  -d "nr_of_subscription=2" \
  -d "water_subscr_cost=18.50" \
  -d "sewage_subscr_cost=16.00" \
  -d "vat=0.08" \
  -d "period_start=2025-01-01" \
  -d "period_stop=2025-02-28" \
  -d "invoice_number=FV-2025-002" \
  -d "gross_sum=1560.50"
```

### 4. Wygeneruj rachunki

```bash
curl -X POST "http://localhost:8000/bills/generate/2025-02"
```

### 5. Pobierz rachunek PDF

```bash
curl -X GET "http://localhost:8000/bills/download/1" -o bill.pdf
```

## 📊 API Endpoints

### Lokale
- `GET /locals/` - Lista lokali
- `POST /locals/` - Dodaj lokal

### Odczyty
- `GET /readings/` - Lista odczytów
- `POST /readings/` - Dodaj odczyt

### Faktury
- `GET /invoices/` - Lista faktur
- `POST /invoices/` - Dodaj fakturę ręcznie
- `POST /invoices/upload` - Wczytaj fakturę PDF

### Rachunki
- `GET /bills/` - Lista rachunków
- `GET /bills/period/{period}` - Rachunki dla okresu
- `POST /bills/generate/{period}` - Generuj rachunki
- `POST /bills/regenerate/{period}` - Ponownie generuj rachunki
- `GET /bills/download/{bill_id}` - Pobierz PDF
- `DELETE /bills/{bill_id}` - Usuń pojedynczy rachunek
- `DELETE /bills/period/{period}` - Usuń rachunki dla okresu
- `DELETE /bills/` - Usuń wszystkie rachunki

## 📝 Liczniki

Projekt obsługuje 3 lokale z licznikami:

1. **gora** - `water_meter_5`
2. **gabinet** - `water_meter_5b`
3. **dol** - `water_meter_5a` (obliczany: main - (5 + 5b))

## 💰 Algorytm rozliczania

### Obliczanie zużycia

**Zużycie wody jest obliczane jako różnica między obecnym a poprzednim odczytem licznika.**

Dla każdego lokalu:

```
Zużycie = obecny_odczyt - poprzedni_odczyt
```

**Przykład:**
- Poprzedni odczyt: 45 m³
- Obecny odczyt: 60 m³  
- **Zużycie: 15 m³**

### Koszty

```
Koszt wody = Zużycie * cena wody za m³
Koszt ścieków = Zużycie * cena ścieków za m³
Abonament = (abonament_woda + abonament_ścieki) / 3
Suma końcowa = Koszt wody + Koszt ścieków + Abonament
```

**Więcej szczegółów:** Zobacz [CALCULATION_LOGIC.md](CALCULATION_LOGIC.md)

## ⚠️ Funkcje

- Automatyczne wczytywanie faktur PDF
- **Obsługa wielu faktur dla jednego okresu** (podwyżka kosztów)
- Kompensacja różnic pomiarowych
- Generowanie rachunków PDF
- Historia wszystkich rozliczeń w bazie danych
- Możliwość ponownego wygenerowania rachunków
- Średnie ważone koszty przy wielu fakturach

## 🧪 Testowanie

Aby przetestować aplikację, użyj narzędzia Swagger UI:
http://localhost:8000/docs

## 📄 Licencja

MIT

