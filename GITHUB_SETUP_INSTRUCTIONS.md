# 📝 Instrukcje przygotowania projektu na GitHub

Ten plik zawiera kroki, które **TY** musisz wykonać, aby przygotować projekt do publikacji.

## ✅ Co zostało już zrobione automatycznie

- ✅ Profesjonalny README.md z sekcjami dla rekruterów
- ✅ QUICKSTART.md - szybki przewodnik testowania
- ✅ LICENSE (MIT)
- ✅ .gitignore z odpowiednimi wykluczeniami
- ✅ Dokumentacja w kodzie

## 🔧 Co musisz zrobić SAM

### 1. Screenshoty Dashboardu

**Gdzie:** Dodaj screenshoty do README.md w sekcji "📸 Screenshoty Dashboardu"

**Jak to zrobić:**
1. Uruchom aplikację: `python main.py`
2. Otwórz: http://localhost:8000/dashboard
3. Zrób screenshoty:
   - Główny widok dashboardu (statystyki + zakładki)
   - Zakładka "Lokale" z formularzem
   - Zakładka "Faktury" z listą
   - Zakładka "Rachunki" z wygenerowanymi rachunkami

4. Zapisz jako:
   - `docs/screenshots/dashboard-main.png`
   - `docs/screenshots/dashboard-locals.png`
   - `docs/screenshots/dashboard-invoices.png`
   - `docs/screenshots/dashboard-bills.png`

5. Dodaj do README.md w sekcji screenshotów:
   ```markdown
   ![Dashboard Main](docs/screenshots/dashboard-main.png)
   ![Dashboard Locals](docs/screenshots/dashboard-locals.png)
   ```

**Alternatywa:** Możesz użyć narzędzi typu [Carbon](https://carbon.now.sh/) do ładnych screenshotów kodu.

### 2. Aktualizacja Linków w README.md

**Znajdź w README.md i zamień:**
```markdown
# ZAMIEŃ:
git clone https://github.com/your-username/water-billing.git

# NA:
git clone https://github.com/TWOJA-NAZWA-UZYTKOWNIKA/water-billing.git
```

**Zamień również:**
- `your-username` → Twoja nazwa użytkownika GitHub
- Wszystkie linki do Issues/PR

### 3. (Opcjonalnie) Dodaj Badge'e Technologii

Możesz dodać więcej badge'ów w README.md:
```markdown
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
```

### 4. Sprawdź czy wszystko jest w .gitignore

Upewnij się, że następujące pliki **NIE** są w repozytorium:
- `water_billing.db` (baza danych)
- `credentials.json` (Google credentials)
- `venv/` (środowisko wirtualne)
- `*.pdf` w folderach `invoices_raw/` i `bills/`

**Sprawdź:**
```bash
git status
```

### 5. Przygotuj Repozytorium na GitHub

```bash
# 1. Inicjalizuj git (jeśli jeszcze nie)
git init

# 2. Dodaj wszystkie pliki (gitignore zadba o wykluczenia)
git add .

# 3. Sprawdź co zostanie dodane (NIE powinno być: .db, credentials, venv, PDF)
git status

# 4. Pierwszy commit
git commit -m "Initial commit: Water Billing System"

# 5. Stwórz repozytorium na GitHub (przez web interface)

# 6. Dodaj remote i push
git remote add origin https://github.com/TWOJA-NAZWA/water-billing.git
git branch -M main
git push -u origin main
```

### 6. (Opcjonalnie) GitHub Pages dla Live Demo

Jeśli chcesz pokazać dashboard online:

1. Utwórz branch `gh-pages`
2. Użyj GitHub Actions lub innego hostingu
3. Dodaj link do README: `🌐 Live Demo: https://your-username.github.io/water-billing`

**UWAGA:** Dashboard wymaga backend API, więc nie zadziała statycznie. Możesz użyć:
- Heroku (darmowe)
- Railway.app
- Render.com

### 7. Dodaj Topics na GitHub

Po opublikowaniu repozytorium, dodaj topics:
- `python`
- `fastapi`
- `sqlalchemy`
- `billing-system`
- `pdf-parsing`
- `rest-api`
- `dashboard`

### 8. (Opcjonalnie) GitHub Actions CI/CD

Możesz dodać `.github/workflows/ci.yml`:

```yaml
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
      - name: Run tests (jeśli masz)
        run: |
          pytest
```

## 📋 Checklist przed publikacją

- [ ] Screenshoty dodane do README
- [ ] Linki w README zaktualizowane (your-username → twoja nazwa)
- [ ] `.gitignore` sprawdzony - wrażliwe pliki nie są commitowane
- [ ] Repozytorium utworzone na GitHub
- [ ] Kod zcommitowany i wypushowany
- [ ] README wygląda dobrze na GitHub (sprawdź podgląd)
- [ ] Topics dodane do repozytorium
- [ ] Opis repozytorium uzupełniony (krótki opis w settings)

## 🎯 Co warto dodać w przyszłości

1. **Testy jednostkowe** - pytest
2. **Docker** - Dockerfile dla łatwego uruchomienia
3. **GitHub Actions** - Automatyczne testy
4. **Dokumentacja API** - Może eksport z Swagger do static site
5. **Więcej przykładów** - Screenshoty różnych scenariuszy

## 🔍 Finalna weryfikacja

Przed pokazaniem rekruterom:

1. **Sprawdź jako gość:**
   - Otwórz repozytorium w trybie incognito
   - Czy wszystko jest czytelne?
   - Czy instrukcje są jasne?

2. **Test instalacji:**
   - Sklonuj repozytorium do nowego folderu
   - Wykonaj kroki z QUICKSTART.md
   - Czy wszystko działa?

3. **Przeczytaj README jako rekruter:**
   - Czy rozumiesz co robi projekt?
   - Czy widzisz jakie umiejętności demonstruje?
   - Czy możesz szybko przetestować?

## 💡 Wskazówki

- **Czysty kod:** Upewnij się, że kod jest czytelny i dobrze skomentowany
- **Dokumentacja:** Im więcej, tym lepiej - rekruterzy to docenią
- **Przykłady:** Pokaż różne scenariusze użycia
- **Wizualizacja:** Screenshoty mówią więcej niż 1000 słów

---

**Gotowe?** Czas pokazać światu swój projekt! 🚀

