# 🚀 Quick Start Guide

Szybki przewodnik dla rekruterów i developerów - uruchom aplikację w 5 minut!

## 📋 Wymagania

- Python 3.11 lub nowszy
- pip (zazwyczaj instalowany z Pythonem)

## ⚡ Szybka Instalacja

### Krok 1: Sklonuj i przejdź do projektu

```bash
git clone https://github.com/your-username/water-billing.git
cd water-billing
```

### Krok 2: Utwórz środowisko wirtualne

```bash
# Windows
python -m venv venv
.\venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### Krok 3: Zainstaluj zależności

```bash
pip install -r requirements.txt
```

### Krok 4: Uruchom aplikację

```bash
python main.py
```

Aplikacja uruchomi się na: **http://localhost:8000**

## 🎮 Szybki Test (2 minuty)

### 1. Otwórz Dashboard

Przejdź do: **http://localhost:8000/dashboard**

Zobaczysz:
- Karty ze statystykami
- Zakładki: Lokale, Odczyty, Faktury, Rachunki
- Formularze do dodawania danych

### 2. Załaduj Przykładowe Dane

**Opcja A: Przez Dashboard**
- Kliknij zakładkę "Lokale"
- Uzupełnij formularz i kliknij "Dodaj lokal"

**Opcja B: Przez API (curl)**
```bash
curl -X POST "http://localhost:8000/load_sample_data"
```

**Opcja C: Przez Swagger UI**
1. Przejdź do: http://localhost:8000/docs
2. Znajdź endpoint `POST /load_sample_data`
3. Kliknij "Try it out" → "Execute"

### 3. Dodaj Odczyt Liczników

**Przez Dashboard:**
- Kliknij zakładkę "Odczyty"
- Wypełnij formularz:
  - Okres: `2025-02`
  - Licznik główny: `150.5`
  - Licznik 5: `45.0`
  - Licznik 5b: `38.0`
- Kliknij "Dodaj odczyt"

**Przez API:**
```bash
curl -X POST "http://localhost:8000/readings/" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "data=2025-02" \
  -d "water_meter_main=150.5" \
  -d "water_meter_5=45.0" \
  -d "water_meter_5b=38.0"
```

### 4. Dodaj Fakturę

**Przez Dashboard:**
- Kliknij zakładkę "Faktury"
- Wypełnij formularz "Dodaj ręcznie":
  - Okres: `2025-02`
  - Zużycie: `45.5`
  - Koszt wody za m³: `15.20`
  - Koszt ścieków za m³: `12.50`
  - Numer faktury: `FV-2025-002`
  - Data początku: `2025-01-01`
  - Data końca: `2025-02-28`
  - Pozostałe pola według faktury
- Kliknij "Dodaj fakturę"

### 5. Wygeneruj Rachunki

**Przez Dashboard:**
- Kliknij zakładkę "Rachunki"
- Wpisz okres: `2025-02`
- Kliknij "Generuj rachunki"

**Przez API:**
```bash
curl -X POST "http://localhost:8000/bills/generate/2025-02"
```

### 6. Pobierz Rachunek PDF

**Przez Dashboard:**
- W zakładce "Rachunki" zobaczysz listę rachunków
- Kliknij "Pobierz PDF" przy wybranym rachunku

**Przez API:**
```bash
curl -X GET "http://localhost:8000/bills/download/1" -o bill.pdf
```

## 🔍 Co Przetestować

### 1. Dashboard Webowy
- ✅ Responsywny design (zmień rozmiar okna)
- ✅ Formularze z walidacją
- ✅ Automatyczne odświeżanie statystyk
- ✅ Listy danych w tabelach

### 2. REST API (Swagger UI)
- Otwórz: http://localhost:8000/docs
- Przetestuj endpointy:
  - `GET /locals/` - Pobierz lokale
  - `GET /readings/` - Pobierz odczyty
  - `GET /invoices/` - Pobierz faktury
  - `GET /bills/` - Pobierz rachunki
  - `GET /api/stats` - Statystyki

### 3. Obsługa Wielu Faktur
Przetestuj scenariusz zmiany stawki w połowie okresu:

```bash
# Faktura 1 - Stara stawka
curl -X POST "http://localhost:8000/invoices/" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "data=2025-02" \
  -d "usage=20" \
  -d "water_cost_m3=10.00" \
  -d "sewage_cost_m3=8.00" \
  -d "nr_of_subscription=1" \
  -d "water_subscr_cost=15.00" \
  -d "sewage_subscr_cost=12.00" \
  -d "vat=0.08" \
  -d "period_start=2025-01-01" \
  -d "period_stop=2025-01-31" \
  -d "invoice_number=FV-001" \
  -d "gross_sum=400.00"

# Faktura 2 - Nowa stawka (TEN SAM OKRES "2025-02")
curl -X POST "http://localhost:8000/invoices/" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "data=2025-02" \
  -d "usage=25" \
  -d "water_cost_m3=12.00" \
  -d "sewage_cost_m3=10.00" \
  -d "nr_of_subscription=1" \
  -d "water_subscr_cost=15.00" \
  -d "sewage_subscr_cost=12.00" \
  -d "vat=0.08" \
  -d "period_start=2025-02-01" \
  -d "period_stop=2025-02-28" \
  -d "invoice_number=FV-002" \
  -d "gross_sum=550.00"

# Wygeneruj rachunki - system użyje średniej ważonej
curl -X POST "http://localhost:8000/bills/generate/2025-02"
```

## 📊 Sprawdź Statystyki

```bash
curl http://localhost:8000/api/stats
```

Otrzymasz JSON z:
- Liczbą lokali, odczytów, faktur, rachunków
- Sumą brutto wszystkich rachunków
- Dostępnymi okresami do generowania

## 🐛 Rozwiązywanie Problemów

### Problem: "Module not found"
```bash
# Upewnij się, że środowisko wirtualne jest aktywne
# Windows: .\venv\Scripts\activate
# Linux/Mac: source venv/bin/activate

# Zainstaluj ponownie zależności
pip install -r requirements.txt
```

### Problem: "Port 8000 already in use"
```bash
# Zmień port w main.py lub użyj:
uvicorn main:app --port 8001
```

### Problem: "Database not initialized"
```bash
# Baza tworzy się automatycznie przy starcie
# Jeśli potrzeba ręcznie:
python db.py
```

## 📚 Co Dalej?

- Przeczytaj [README.md](README.md) - Pełna dokumentacja
- Zobacz [CALCULATION_LOGIC.md](CALCULATION_LOGIC.md) - Logika obliczania
- Sprawdź [API_EXAMPLES.md](API_EXAMPLES.md) - Więcej przykładów API

## 💡 Wskazówki dla Rekruterów

1. **Zobacz kod źródłowy:**
   - `main.py` - Struktura API i endpointy
   - `meter_manager.py` - Logika biznesowa
   - `static/dashboard.html` - Frontend

2. **Przetestuj różne scenariusze:**
   - Dodaj kilka faktur dla jednego okresu
   - Wygeneruj rachunki
   - Pobierz PDF

3. **Sprawdź dokumentację:**
   - Swagger UI (http://localhost:8000/docs)
   - Kod zawiera docstrings

---

**Czas potrzebny:** ~5 minut  
**Poziom trudności:** ⭐ Easy

