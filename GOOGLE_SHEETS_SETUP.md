# 🔗 Integracja z Google Sheets - Instrukcja krok po kroku

Ten przewodnik pomoże Ci skonfigurować połączenie z Google Sheets, aby móc importować dane bezpośrednio do bazy danych.

## 📋 Krok 1: Utworzenie konta serwisowego Google Cloud

1. **Przejdź do Google Cloud Console**
   - Odwiedź: https://console.cloud.google.com/
   - Zaloguj się na swoje konto Google

2. **Utwórz nowy projekt (lub wybierz istniejący)**
   - Kliknij na rozwijaną listę projektów u góry
   - Kliknij "New Project"
   - Wprowadź nazwę projektu (np. "Water Billing")
   - Kliknij "Create"

3. **Włącz API Google Sheets i Drive**
   - W menu po lewej wybierz "APIs & Services" > "Library"
   - Wyszukaj "Google Sheets API" i kliknij "Enable"
   - Wyszukaj "Google Drive API" i kliknij "Enable"

## 📋 Krok 2: Utworzenie konta serwisowego

1. **Przejdź do Service Accounts**
   - W menu wybierz "APIs & Services" > "Credentials"
   - Kliknij "Create Credentials" > "Service Account"

2. **Skonfiguruj konto serwisowe**
   - Wprowadź nazwę (np. "water-billing-service")
   - Kliknij "Create and Continue"
   - Opcjonalnie: Dodaj rolę (nie jest wymagane)
   - Kliknij "Done"

3. **Pobierz klucz JSON**
   - Kliknij na utworzone konto serwisowe
   - Przejdź do zakładki "Keys"
   - Kliknij "Add Key" > "Create new key"
   - Wybierz format "JSON"
   - Kliknij "Create"
   - Plik JSON zostanie automatycznie pobrany - **zachowaj go w bezpiecznym miejscu!**

## 📋 Krok 3: Przygotowanie arkusza Google Sheets

1. **Utwórz nowy arkusz Google Sheets**
   - Przejdź do: https://sheets.google.com
   - Utwórz nowy arkusz

2. **Udostępnij arkusz kontu serwisowemu**
   - Kliknij przycisk "Share" (Udostępnij) w prawym górnym rogu
   - W polu "Add people and groups" wklej **email z pliku JSON** (znajdziesz go w polu `client_email`)
   - Nadaj uprawnienie "Editor" (Edytor)
   - Kliknij "Send"

3. **Pobierz ID arkusza z URL**
   - URL arkusza wygląda tak: `https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit`
   - Skopiuj `SPREADSHEET_ID` (długi ciąg znaków między `/d/` a `/edit`) 

## 📋 Krok 4: Przygotowanie danych w Google Sheets

### ⚠️ Ważne: Formatowanie arkusza

**NIE MUSISZ zamieniać danych na tabelę Google Sheets!** Wystarczy zwykły arkusz z nagłówkami.

**Jak przygotować arkusz:**
1. **Pierwszy wiersz** - nagłówki kolumn (nazwy dokładnie jak w przykładach poniżej)
2. **Kolejne wiersze** - dane, każdy wiersz to jeden rekord
3. **Ważne:** Nazwy kolumn w pierwszym wierszu muszą być dokładnie takie jak w przykładach (wielkość liter ma znaczenie!)
4. **Nie** używaj funkcji "Zamień na tabelę" - zwykły arkusz wystarczy

**Przykład poprawnego formatowania:**

```
| data      | water_meter_main | water_meter_5 | water_meter_5b |
|-----------|------------------|---------------|----------------|
| 2025-02   | 150.5            | 45            | 38             |
| 2025-03   | 165.2            | 52            | 42             |
```

To wszystko! System automatycznie rozpozna pierwszy wiersz jako nagłówki i zaimportuje dane z kolejnych wierszy.

**Wizualny przykład jak to wygląda w Google Sheets:**

```
┌─────────┬──────────────────┬───────────────┬───────────────┐
│   A     │        B         │       C       │       D       │
├─────────┼──────────────────┼───────────────┼───────────────┤
│ data    │ water_meter_main │ water_meter_5 │ water_meter_5b│ ← Wiersz 1: NAGŁÓWKI
├─────────┼──────────────────┼───────────────┼───────────────┤
│ 2025-02 │ 150.5            │ 45            │ 38             │ ← Wiersz 2: DANE
├─────────┼──────────────────┼───────────────┼───────────────┤
│ 2025-03 │ 165.2            │ 52            │ 42             │ ← Wiersz 3: DANE
└─────────┴──────────────────┴───────────────┴───────────────┘
```

**Tips:**
- Możesz sformatować nagłówki jako pogrubione, ale nie jest to wymagane
- Możesz dodać kolorowanie, ale to też nie jest konieczne
- Wartości numeryczne możesz wpisać bezpośrednio jako liczby (Google Sheets automatycznie je rozpozna)
- Wartości tekstowe (np. `data`, `invoice_number`) możesz wpisać jako tekst lub liczby - system je przekonwertuje

### Arkusz "Odczyty"

Utwórz arkusz o nazwie **"Odczyty"** z następującymi kolumnami (w pierwszym wierszu):

| data      | water_meter_main | water_meter_5 | water_meter_5b |
|-----------|------------------|---------------|----------------|
| 2025-02   | 150.5            | 45            | 38             |
| 2025-03   | 165.2            | 52            | 42             |

**Format kolumny `data`:** `YYYY-MM` (np. `2025-02`)

### Arkusz "Lokale"

Utwórz arkusz o nazwie **"Lokale"** z następującymi kolumnami:

| water_meter_name | tenant         | local   |
|------------------|----------------|---------|
| water_meter_5    | Jan Kowalski   | gora    |
| water_meter_5b   | Mikołaj        | dol    |
| water_meter_5a   | Bartek         | gabinet |

### Arkusz "Faktury"

Utwórz arkusz o nazwie **"Faktury"** z następującymi kolumnami:

| data   | usage | water_cost_m3 | sewage_cost_m3 | nr_of_subscription | water_subscr_cost | sewage_subscr_cost | vat  | period_start | period_stop | invoice_number | gross_sum |
|--------|-------|---------------|----------------|-------------------|-------------------|-------------------|------|--------------|-------------|----------------|-----------|
| 2025-02| 45.5  | 15.20         | 12.50          | 2                 | 18.50             | 16.00             | 0.08 | 2025-01-01   | 2025-02-28  | FV-2025-002    | 1560.50   |

**Format dat:**
- `data`: `YYYY-MM`
- `period_start`, `period_stop`: `YYYY-MM-DD`
- `vat`: wartość numeryczna (np. 0.08 dla 8%)

## 📋 Krok 5: Instalacja zależności

Zainstaluj wymagane biblioteki:

```bash
# Aktywuj środowisko wirtualne (jeśli nie jest aktywne)
.\venv\Scripts\activate  # Windows
# lub
source venv/bin/activate  # Linux/Mac

# Zainstaluj zależności
pip install -r requirements.txt
```

## 📋 Krok 6: Użycie API do importu danych

### Import odczytów

**Jeśli plik credentials.json jest w głównym katalogu:**
```bash
curl -X POST "http://localhost:8000/import/readings" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "credentials_path=credentials.json" \
  -d "spreadsheet_id=TU_WKLEJ_SPREADSHEET_ID" \
  -d "sheet_name=Odczyty"
```

**Lub jeśli plik ma inną nazwę (np. z nazwą projektu):**
```bash
curl -X POST "http://localhost:8000/import/readings" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "credentials_path=water-billing-476608-533d44cc7f53.json" \
  -d "spreadsheet_id=TU_WKLEJ_SPREADSHEET_ID" \
  -d "sheet_name=Odczyty"
```

**Jeśli plik jest w folderze config/:**
```bash
curl -X POST "http://localhost:8000/import/readings" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "credentials_path=config/credentials.json" \
  -d "spreadsheet_id=TU_WKLEJ_SPREADSHEET_ID" \
  -d "sheet_name=Odczyty"
```

### Import lokali

```bash
curl -X POST "http://localhost:8000/import/locals" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "credentials_path=credentials.json" \
  -d "spreadsheet_id=TU_WKLEJ_SPREADSHEET_ID" \
  -d "sheet_name=Lokale"
```

### Import faktur

```bash
curl -X POST "http://localhost:8000/import/invoices" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "credentials_path=credentials.json" \
  -d "spreadsheet_id=TU_WKLEJ_SPREADSHEET_ID" \
  -d "sheet_name=Faktury"
```

**💡 Tip:** Ścieżka może być względna (np. `credentials.json`) lub bezwzględna (np. `E:\IT\_RACHUNKI_ROZLICZENIA_\water_billing\credentials.json`). Zawsze używaj względnej ścieżki - jest bezpieczniejsza i bardziej przenośna.

### Użycie przez Swagger UI

1. Uruchom aplikację: `python main.py`
2. Przejdź do: http://localhost:8000/docs
3. Znajdź endpointy `/import/readings`, `/import/locals`, `/import/invoices`
4. Kliknij "Try it out"
5. Wypełnij wymagane pola:
   - `credentials_path`: ścieżka do pliku JSON (np. `credentials.json` lub `water-billing-476608-533d44cc7f53.json`)
     - Jeśli plik jest w głównym katalogu: `credentials.json`
     - Jeśli plik jest w folderze config: `config/credentials.json`
     - Możesz użyć pełnej nazwy pliku jeśli ma inną nazwę (z Google Cloud Console)
   - `spreadsheet_id`: ID arkusza z Google Sheets
   - `sheet_name`: nazwa arkusza (opcjonalnie, domyślnie "Odczyty"/"Lokale"/"Faktury")
6. Kliknij "Execute"

## 🔒 Bezpieczeństwo i umiejscowienie pliku credentials.json

### 📁 Gdzie umieścić plik credentials.json?

**Rekomendowane rozwiązanie: W głównym katalogu projektu**

1. **Umieść plik w głównym katalogu projektu** (tam gdzie jest `main.py`):
   ```
   water_billing/
   ├── main.py
   ├── credentials.json          ← Tutaj!
   ├── gsheets_integration.py
   └── ...
   ```

2. **Użyj prostej ścieżki** w API:
   - `credentials_path=credentials.json` (względna ścieżka)
   - `credentials_path=water-billing-476608-533d44cc7f53.json` (jeśli plik ma inną nazwę)

**Alternatywne rozwiązanie: Folder `config/` (bardziej zorganizowane)**

1. **Utwórz folder `config/` w głównym katalogu**:
   ```
   water_billing/
   ├── main.py
   ├── config/
   │   └── credentials.json      ← Tutaj!
   └── ...
   ```

2. **Użyj ścieżki z folderem** w API:
   - `credentials_path=config/credentials.json`

### ⚠️ WAŻNE - Bezpieczeństwo:

- ✅ Plik `credentials.json` jest już w `.gitignore` - **nie zostanie wysłany na GitHub**
- ✅ Wszystkie pliki z `credentials` w nazwie są ignorowane
- ✅ Folder `config/` również jest w `.gitignore` (jeśli używasz tej opcji)
- ⚠️ **NIE** commit'uj pliku `credentials.json` do repozytorium Git!
- ⚠️ Przechowuj plik JSON w bezpiecznym miejscu (zawsze w katalogu projektu)
- ⚠️ Nie udostępniaj go publicznie

### 📝 Sprawdzenie, czy plik jest bezpieczny

Aby upewnić się, że plik nie zostanie wysłany na GitHub:

```bash
# Sprawdź status git - plik NIE powinien być widoczny
git status

# Jeśli widzisz plik credentials.json na liście, to znaczy że .gitignore nie działa poprawnie
```

Jeśli plik jest widoczny, upewnij się że:
1. Plik `.gitignore` zawiera `credentials.json`
2. Plik nie został dodany do Git przed dodaniem do `.gitignore`

Jeśli plik był już wcześniej dodany do Git, usuń go:
```bash
git rm --cached credentials.json
git commit -m "Remove credentials.json from tracking"
```

## 📝 Przykład struktury pliku credentials.json

Plik JSON powinien wyglądać mniej więcej tak:

```json
{
  "type": "service_account",
  "project_id": "your-project-id",
  "private_key_id": "key-id",
  "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",
  "client_email": "water-billing-service@your-project.iam.gserviceaccount.com",
  "client_id": "123456789",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/..."
}
```

## ❓ Rozwiązywanie problemów

### Błąd: "The caller does not have permission"
- Upewnij się, że udostępniłeś arkusz kontu serwisowemu (email z pliku JSON)
- Sprawdź czy konto serwisowe ma uprawnienia "Editor"

### Błąd: "Worksheet not found"
- Sprawdź czy nazwa arkusza jest dokładnie taka sama jak w Google Sheets
- Nazwa jest case-sensitive (wrażliwa na wielkość liter)

### Błąd: "Invalid credentials"
- Sprawdź czy ścieżka do pliku JSON jest prawidłowa
- Sprawdź czy plik JSON nie jest uszkodzony
- Upewnij się, że pobrałeś klucz JSON z Google Cloud Console

### Import pomija wszystkie wiersze
- Sprawdź czy pierwszy wiersz arkusza zawiera nagłówki kolumn
- Sprawdź czy nazwy kolumn są dokładnie takie jak w przykładach powyżej
- Sprawdź czy dane w arkuszach są poprawnie sformatowane

## 📚 Dodatkowe informacje

- Wszystkie endpointy importu zwracają informacje o liczbie zaimportowanych, pominiętych i błędnych rekordów
- Rekordy z duplikatami są automatycznie pomijane (nie są nadpisywane)
- Możesz importować dane wielokrotnie - system nie zaimportuje duplikatów

