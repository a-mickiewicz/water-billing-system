# Instrukcja publikacji na GitHub

## Krok 1: Utwórz repozytorium na GitHub

1. Przejdź na https://github.com
2. Kliknij **"New repository"** lub **"+"** → **"New repository"**
3. Wypełnij:
   - **Repository name:** `water-billing-system`
   - **Description:** `System rozliczania rachunków za wodę i ścieki dla trzech lokali`
   - **Public** lub **Private** (wybierz według preferencji)
   - **NIE** zaznaczaj "Initialize this repository with a README" (już masz pliki)
4. Kliknij **"Create repository"**

## Krok 2: Podłącz lokalne repozytorium do GitHub

### Opcja A: Nowe repozytorium

```bash
git remote add origin https://github.com/TWOJA-NAZWA/water-billing-system.git
git branch -M main
git push -u origin main
```

### Opcja B: Istniejące repozytorium

```bash
git remote add origin https://github.com/TWOJA-NAZWA/water-billing-system.git
git branch -M main
git push -u origin master
```

**Uwaga:** Zamień `TWOJA-NAZWA` na swoją nazwę użytkownika GitHub!

## Alternatywnie: Użyj GitHub CLI (jeśli zainstalowane)

```bash
gh auth login
gh repo create water-billing-system --public --source=. --remote=origin --push
```

## Sprawdzenie

Po udanym push, sprawdź repozytorium pod adresem:
https://github.com/TWOJA-NAZWA/water-billing-system

## Co nie zostało dodane do Git?

Pliki wykluczone przez `.gitignore`:
- `venv/` - środowisko wirtualne Python
- `*.db` - baza danych SQLite
- `invoices_raw/*.pdf` - faktury PDF
- `bills/*.pdf` - wygenerowane rachunki PDF
- `__pycache__/` - pliki cache Python

**To jest poprawne zachowanie** - te pliki nie powinny być w repozytorium.



