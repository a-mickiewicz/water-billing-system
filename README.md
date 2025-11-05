# 💧⚡ Water & Gas Billing System

> **Profesjonalny system rozliczania rachunków za wodę, ścieki i gaz z nowoczesnym interfejsem webowym i REST API**

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green.svg)](https://fastapi.tiangolo.com/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-orange.svg)](https://www.sqlalchemy.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 🎯 O Projekcie

Water & Gas Billing System to kompleksowe rozwiązanie do automatycznego rozliczania rachunków za wodę, ścieki i gaz dla budynku z wieloma lokalami. System automatycznie przetwarza faktury PDF, obsługuje odczyty liczników, oblicza koszty dla każdego lokalu i generuje profesjonalne rachunki PDF.

### 🔥 Obsługiwane Media

- 💧 **Woda i Ścieki** - Pełna obsługa rozliczeń z odczytami liczników, kompensacjami i rozkładem abonamentów
- 🔥 **Gaz** - Rozliczenia gazu z konwersją m³ na kWh, obsługą dystrybucji i rozkładem kosztów

### ✨ Kluczowe Funkcje

- 🎨 **Nowoczesny Dashboard Webowy** - Intuicyjny interfejs do zarządzania danymi dla wszystkich mediów
- 📄 **Automatyczne Parsowanie Faktur PDF** - Wczytywanie faktur od dostawcy mediów (woda, gaz)
- 💰 **Inteligentne Rozliczanie** - Obsługa wielu faktur dla jednego okresu (zmiana stawek)
- 📊 **REST API** - Pełna dokumentacja w Swagger UI z endpointami dla wody i gazu
- 📑 **Generowanie PDF** - Automatyczne tworzenie rachunków dla lokali
- 🔗 **Integracja Google Sheets** - Import danych z arkuszy kalkulacyjnych
- 🧮 **Średnie Ważone Kosztów** - Automatyczne przeliczanie przy zmianie stawek
- ⚡ **Modularna Architektura** - Oddzielne serwisy dla każdego medium, łatwe rozszerzanie

## 🚀 Quick Start

### Wymagania

- Python 3.11+
- pip (Python package manager)

### Instalacja w 3 krokach

```bash
# 1. Sklonuj repozytorium
git clone https://github.com/your-username/water-billing.git
cd water-billing

# 2. Utwórz i aktywuj środowisko wirtualne
python -m venv venv

# Windows
.\venv\Scripts\activate

# Linux/Mac
source venv/bin/activate

# 3. Zainstaluj zależności i uruchom
pip install -r requirements.txt
python main.py
```

### 🎮 Pierwszy test (3 minuty)

Po uruchomieniu aplikacji (`python main.py`):

1. **Otwórz dashboard:** http://localhost:8000/dashboard
2. **Dodaj przykładowe dane:** Kliknij w zakładce "Faktury" → "Wczytaj PDF" lub użyj endpoint:
   ```bash
   curl -X POST "http://localhost:8000/load_sample_data"
   ```
3. **Przetestuj API:** http://localhost:8000/docs (interaktywna dokumentacja Swagger)

**Więcej szczegółów:** Zobacz [QUICKSTART.md](QUICKSTART.md)

## 📸 Screenshoty Dashboardu

> 💡 **Wskazówka dla rekruterów:** Dashboard zawiera nowoczesny interfejs z zakładkami, statystykami i formularzami. Możesz go zobaczyć po uruchomieniu aplikacji.

### Główne Sekcje Dashboardu:
- 📊 **Statystyki** - Karty z podsumowaniem danych dla wszystkich mediów
- 🏠 **Lokale** - Zarządzanie lokalizacjami i najemcami
- 📈 **Odczyty** - Wprowadzanie odczytów liczników (woda)
- 📄 **Faktury** - Wczytywanie faktur PDF lub ręczne dodawanie (woda i gaz)
- 💰 **Rachunki** - Generowanie i pobieranie rachunków PDF (woda i gaz)

## 🛠 Technologie i Umiejętności

Projekt demonstruje znajomość:

### Backend
- **FastAPI** - Nowoczesny framework REST API z automatyczną dokumentacją
- **SQLAlchemy ORM** - Zaawansowane zarządzanie bazą danych
- **SQLite** - Baza danych
- **Pydantic** - Walidacja danych (integracja z FastAPI)

### Frontend
- **HTML5/CSS3/JavaScript (Vanilla)** - Responsywny dashboard bez frameworków
- **REST API Integration** - Komunikacja z backendem przez Fetch API
- **CORS Middleware** - Konfiguracja cross-origin requests

### Przetwarzanie Danych
- **pdfplumber** - Parsowanie faktur PDF
- **reportlab** - Generowanie dokumentów PDF
- **Algorytmy biznesowe** - Średnie ważone, kompensacja różnic pomiarowych

### Integracje
- **Google Sheets API** - Import danych z arkuszy kalkulacyjnych
- **OAuth2 Service Account** - Bezpieczne połączenie z Google API

### Architektura
- **Modularna Struktura** - Oddzielne serwisy dla każdego medium (water/, gas/)
- **RESTful API Design** - RESTful endpoints z właściwą strukturą
- **Dependency Injection** - FastAPI dependencies pattern
- **Separation of Concerns** - Oddzielenie logiki biznesowej od API
- **Database Migrations** - Zarządzanie schematem bazy danych
- **Router Pattern** - Oddzielne routery dla każdego medium (/api/gas/*)

## 📁 Struktura Projektu

```
water_billing/
├── main.py                 # FastAPI aplikacja - główny entry point
├── app/
│   ├── api/
│   │   └── routes/
│   │       └── gas.py      # Endpointy API dla gazu (/api/gas/*)
│   ├── core/
│   │   └── database.py     # Konfiguracja bazy danych SQLAlchemy
│   ├── models/
│   │   ├── water.py        # Modele ORM dla wody (Local, Reading, Invoice, Bill)
│   │   └── gas.py          # Modele ORM dla gazu (GasInvoice, GasBill)
│   ├── services/
│   │   ├── water/
│   │   │   ├── invoice_reader.py    # Parsowanie faktur PDF (woda)
│   │   │   ├── meter_manager.py     # Logika obliczania rozliczeń (woda)
│   │   │   └── bill_generator.py    # Generowanie rachunków PDF (woda)
│   │   └── gas/
│   │       ├── invoice_reader.py     # Parsowanie faktur PDF (gaz)
│   │       ├── manager.py            # Logika obliczania rozliczeń (gaz)
│   │       └── bill_generator.py     # Generowanie rachunków PDF (gaz)
│   ├── integrations/
│   │   └── google_sheets.py          # Integracja z Google Sheets
│   └── static/
│       └── dashboard.html            # Interfejs webowy (HTML/JS/CSS)
├── migrations/
│   └── versions/                     # Migracje bazy danych
├── tests/                            # Testy jednostkowe
├── docs/                             # Dokumentacja projektu
│   ├── CALCULATION_LOGIC.md          # Dokumentacja algorytmu rozliczania
│   ├── API_EXAMPLES.md               # Przykłady użycia API
│   ├── GOOGLE_SHEETS_SETUP.md        # Instrukcja integracji Google Sheets
│   └── QUICKSTART.md                 # Szybki przewodnik testowania
├── tools/                            # Narzędzia pomocnicze
├── scripts/                          # Skrypty zarządzania
└── requirements.txt                  # Zależności Python
```

## 📖 Dokumentacja

### Dla Rekruterów / Developerów

- **[QUICKSTART.md](QUICKSTART.md)** - Szybki start i testowanie (5 minut)
- **[CALCULATION_LOGIC.md](CALCULATION_LOGIC.md)** - Szczegółowa logika obliczania
- **[API_EXAMPLES.md](API_EXAMPLES.md)** - Przykłady użycia API
- **Swagger UI** - http://localhost:8000/docs (po uruchomieniu)

### Dla Użytkowników

- **[GOOGLE_SHEETS_SETUP.md](GOOGLE_SHEETS_SETUP.md)** - Konfiguracja integracji Google Sheets

## 🎯 Przykładowe Scenariusze Użycia

### 1. Pełny Workflow - Od Faktury do Rachunku

```bash
# 1. Dodaj lokale
curl -X POST "http://localhost:8000/load_sample_data"

# 2. Dodaj odczyt liczników
curl -X POST "http://localhost:8000/readings/" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "data=2025-02&water_meter_main=150.5&water_meter_5=45.0&water_meter_5b=38.0"

# 3. Wczytaj fakturę (przez dashboard lub API)
curl -X POST "http://localhost:8000/invoices/upload" \
  -F "file=@invoices_raw/invoice.pdf"

# 4. Wygeneruj rachunki
curl -X POST "http://localhost:8000/bills/generate/2025-02"

# 5. Pobierz rachunek PDF
curl -X GET "http://localhost:8000/bills/download/1" -o bill.pdf
```

### 2. Obsługa Zmiany Stawki w Połowie Okresu

System obsługuje sytuację, gdy okres rozliczeniowy ma kilka faktur z różnymi stawkami:

```bash
# Faktura 1: Stara stawka (10 zł/m³)
curl -X POST "http://localhost:8000/invoices/" \
  -d "data=2025-02&usage=20&water_cost_m3=10.00&..." \
  -d "period_start=2025-01-01&period_stop=2025-01-31"

# Faktura 2: Nowa stawka (12 zł/m³) - TEN SAM OKRES "2025-02"
curl -X POST "http://localhost:8000/invoices/" \
  -d "data=2025-02&usage=25&water_cost_m3=12.00&..." \
  -d "period_start=2025-02-01&period_stop=2025-02-28"

# System automatycznie obliczy średnią ważoną: (10×20 + 12×25)/45 = 11.11 zł/m³
```

## 🧪 Testowanie

### Interaktywne API (Swagger UI)
```
http://localhost:8000/docs
```
- Przetestuj wszystkie endpointy bezpośrednio w przeglądarce
- Pełna dokumentacja z przykładami

### Dashboard Webowy
```
http://localhost:8000/dashboard
```
- Dodawanie danych przez formularze
- Wczytywanie faktur PDF
- Generowanie rachunków
- Pobieranie PDF

## 📊 API Endpoints

### 💧 Woda i Ścieki

#### Lokale
- `GET /locals/` - Lista wszystkich lokali
- `POST /locals/` - Dodaj nowy lokal
- `DELETE /locals/{local_id}` - Usuń lokal

#### Odczyty
- `GET /readings/` - Lista wszystkich odczytów
- `GET /readings/{period}` - Pobierz odczyt dla okresu
- `POST /readings/` - Dodaj odczyt liczników
- `PUT /readings/{period}` - Aktualizuj odczyt
- `DELETE /readings/{period}` - Usuń odczyt

#### Faktury
- `GET /invoices/` - Lista wszystkich faktur
- `GET /invoices/{invoice_id}` - Pobierz fakturę po ID
- `POST /invoices/` - Dodaj fakturę ręcznie
- `POST /invoices/parse` - Parsuj fakturę PDF (bez zapisu)
- `POST /invoices/verify` - Zapisuje fakturę po weryfikacji
- `POST /invoices/upload` - Wczytaj fakturę z pliku PDF (deprecated)
- `PUT /invoices/{invoice_id}` - Aktualizuj fakturę
- `DELETE /invoices/{invoice_id}` - Usuń fakturę

#### Rachunki
- `GET /bills/` - Lista wszystkich rachunków
- `GET /bills/{bill_id}` - Pobierz rachunek po ID
- `GET /bills/period/{period}` - Rachunki dla konkretnego okresu
- `POST /bills/generate/{period}` - Generuj rachunki dla okresu
- `POST /bills/regenerate/{period}` - Regeneruj rachunki
- `POST /bills/generate-all` - Generuj wszystkie możliwe rachunki
- `POST /bills/regenerate-all` - Regeneruj wszystkie rachunki
- `GET /bills/download/{bill_id}` - Pobierz rachunek PDF
- `PUT /bills/{bill_id}` - Aktualizuj rachunek
- `DELETE /bills/{bill_id}` - Usuń rachunek
- `DELETE /bills/period/{period}` - Usuń rachunki dla okresu

### 🔥 Gaz

#### Faktury
- `GET /api/gas/invoices/` - Lista wszystkich faktur gazu
- `GET /api/gas/invoices/{invoice_id}` - Pobierz fakturę gazu po ID
- `POST /api/gas/invoices/` - Dodaj fakturę gazu ręcznie
- `POST /api/gas/invoices/parse` - Parsuj fakturę PDF gazu (bez zapisu)
- `POST /api/gas/invoices/verify` - Zapisuje fakturę gazu po weryfikacji
- `PUT /api/gas/invoices/{invoice_id}` - Aktualizuj fakturę gazu
- `DELETE /api/gas/invoices/{invoice_id}` - Usuń fakturę gazu

#### Rachunki
- `GET /api/gas/bills/` - Lista wszystkich rachunków gazu
- `GET /api/gas/bills/{bill_id}` - Pobierz rachunek gazu po ID
- `GET /api/gas/bills/period/{period}` - Rachunki gazu dla konkretnego okresu
- `POST /api/gas/bills/generate/{period}` - Generuj rachunki gazu dla okresu
- `POST /api/gas/bills/generate-pdf/{period}` - Generuj PDF dla istniejących rachunków
- `POST /api/gas/bills/regenerate/{period}` - Regeneruj rachunki gazu
- `GET /api/gas/bills/download/{bill_id}` - Pobierz rachunek PDF gazu
- `PUT /api/gas/bills/{bill_id}` - Aktualizuj rachunek gazu
- `DELETE /api/gas/bills/{bill_id}` - Usuń rachunek gazu

#### Statystyki
- `GET /api/gas/stats` - Statystyki dla gazu

### Integracje
- `POST /import/readings` - Import odczytów z Google Sheets
- `POST /import/locals` - Import lokali z Google Sheets
- `POST /import/invoices` - Import faktur z Google Sheets

### Statystyki
- `GET /api/stats` - Statystyki dla dashboardu (woda)

## 🔒 Bezpieczeństwo

- ✅ Wszystkie wrażliwe dane (credentials, baza danych) są w `.gitignore`
- ✅ Brak hardcoded secrets w kodzie
- ✅ CORS skonfigurowany (można dostosować dla produkcji)
- ✅ Walidacja danych przez FastAPI/Pydantic

**Raport bezpieczeństwa:** [security_check_report.md](security_check_report.md)

## 🎓 Co Można Zobaczyć w Projekcie

Dla rekruterów - demonstracja umiejętności:

### Backend Development
- ✅ RESTful API design
- ✅ Dependency Injection pattern
- ✅ Database ORM (SQLAlchemy)
- ✅ File processing (PDF parsing)
- ✅ Document generation (PDF reports)
- ✅ Error handling i walidacja

### Frontend Development
- ✅ Responsywny design (mobile-friendly)
- ✅ Vanilla JavaScript (bez frameworków)
- ✅ REST API integration
- ✅ Form validation
- ✅ User experience design

### Business Logic
- ✅ Złożone algorytmy obliczeniowe
- ✅ Obsługa edge cases (wymiana liczników, kompensacje)
- ✅ Średnie ważone przy wielu fakturach
- ✅ Korekty różnic pomiarowych

### Code Quality
- ✅ Modularna struktura kodu (app/services/water/, app/services/gas/)
- ✅ Separation of concerns
- ✅ Dokumentacja kodu
- ✅ Type hints (Python)
- ✅ Clean code principles
- ✅ Router pattern dla różnych mediów
- ✅ Wielokrotne użycie komponentów (shared models, database)

## 🤝 Kontrybucja

Projekt jest otwarty na sugestie i poprawki! Jeśli masz pomysł na ulepszenie:

1. Fork repozytorium
2. Utwórz branch dla swojej funkcji (`git checkout -b feature/amazing-feature`)
3. Commit zmiany (`git commit -m 'Add amazing feature'`)
4. Push do brancha (`git push origin feature/amazing-feature`)
5. Otwórz Pull Request

## 📝 Roadmap

- [x] Obsługa gazu (rozliczenia, faktury, rachunki)
- [x] Modularna architektura (app/services/*)
- [ ] Testy jednostkowe (pytest)
- [ ] Docker containerization
- [ ] CI/CD pipeline (GitHub Actions)
- [ ] Export danych do Excel
- [ ] Email notifications
- [ ] Multi-tenant support
- [ ] Obsługa prądu (elektryczność)

## 📄 Licencja

Ten projekt jest dostępny na licencji MIT. Zobacz plik [LICENSE](LICENSE) dla szczegółów.

## 👤 Autor

Projekt stworzony w celach demonstracyjnych umiejętności programowania.

---

⭐ **Jeśli projekt Ci się podoba, zostaw gwiazdkę!** ⭐

**Pytania?** Otwórz [Issue](https://github.com/a-mickiewicz/water-billing/issues) na GitHub.
