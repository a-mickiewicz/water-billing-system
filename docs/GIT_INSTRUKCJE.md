# Instrukcje Git - Zabezpieczanie zmian i przeglądanie historii

## 1. Zabezpieczenie istniejących zmian (Commit)

### Krok 1: Sprawdź status zmian
```bash
git status
```

### Krok 2: Dodaj pliki do staging area
```bash
# Dodaj wszystkie zmodyfikowane pliki
git add .

# LUB dodaj konkretne pliki
git add docs/WERYFIKACJA_FAKTURY_2024_02_04.md
git add tools/verify_invoice_calculation.py
```

### Krok 3: Utwórz commit z opisem zmian
```bash
git commit -m "feat: weryfikacja faktury P/23666363/0002/24 z poprawioną logiką obliczeń

- Dodano skrypt weryfikacyjny verify_invoice_calculation.py
- Dodano dokumentację weryfikacji faktury
- Uwzględniono ujemne zużycie w obliczeniach
- Przeliczono fakturę zgodnie z poprawioną logiką overlapping periods"
```

### Krok 4: Wyślij zmiany do zdalnego repozytorium (opcjonalnie)
```bash
git push origin main
```

## 2. Przeglądanie historii commitów

### Wyświetl listę commitów (krótka wersja)
```bash
git log --oneline -20
```

### Wyświetl szczegółową historię
```bash
git log
```

### Wyświetl historię z grafem
```bash
git log --oneline --graph --all -20
```

### Wyświetl zmiany w konkretnym commicie
```bash
git show <hash_commita>
# Przykład:
git show 1199934
```

### Wyświetl zmiany między commitami
```bash
git diff <hash1> <hash2>
# Przykład:
git diff 04f8c7c 1199934
```

## 3. Przełączanie się między commitami

### Sprawdź aktualny commit
```bash
git log --oneline -1
```

### Przełącz się do konkretnego commita (tylko do przeglądania)
```bash
git checkout <hash_commita>
# Przykład:
git checkout 04f8c7c
```

**UWAGA:** To przełączy Cię w tryb "detached HEAD". Możesz przeglądać kod, ale nie powinieneś wprowadzać zmian.

### Wróć do najnowszego commita na branchu main
```bash
git checkout main
```

### Lub użyj skrótu
```bash
git checkout -
```

## 4. Bezpieczne przeglądanie starego kodu (bez przełączania)

### Wyświetl zawartość pliku z konkretnego commita
```bash
git show <hash>:<ścieżka_do_pliku>
# Przykład:
git show 04f8c7c:app/services/electricity/manager.py
```

### Porównaj plik między commitami
```bash
git diff <hash1> <hash2> -- <ścieżka_do_pliku>
# Przykład:
git diff 04f8c7c 1199934 -- app/services/electricity/manager.py
```

### Wyświetl listę plików zmienionych w commicie
```bash
git show --name-only <hash>
```

### Wyświetl statystyki zmian
```bash
git show --stat <hash>
```

## 5. Tworzenie brancha do eksperymentów

Jeśli chcesz bezpiecznie eksperymentować ze starym kodem:

### Utwórz nowy branch z konkretnego commita
```bash
git checkout -b eksperyment-stary-kod <hash_commita>
# Przykład:
git checkout -b eksperyment-stary-kod 04f8c7c
```

### Wróć do main
```bash
git checkout main
```

### Usuń branch eksperymentalny (jeśli nie jest potrzebny)
```bash
git branch -d eksperyment-stary-kod
```

## 6. Stash - tymczasowe zapisanie zmian

Jeśli masz niezapisane zmiany i chcesz przełączyć się do innego commita:

### Zapisz zmiany tymczasowo
```bash
git stash
```

### Przełącz się do innego commita
```bash
git checkout <hash>
```

### Wróć i przywróć zmiany
```bash
git checkout main
git stash pop
```

### Wyświetl listę zapisanych stashów
```bash
git stash list
```

## 7. Przydatne aliasy Git (opcjonalnie)

Możesz dodać do `~/.gitconfig` lub `.git/config`:

```ini
[alias]
    hist = log --oneline --graph --all -20
    last = log -1 HEAD
    visual = !gitk
    unstage = reset HEAD --
    st = status
    co = checkout
    br = branch
    ci = commit
```

## 8. Przykładowy workflow

### Scenariusz: Chcesz przejrzeć kod z commita sprzed 3 commitów

```bash
# 1. Zabezpiecz obecne zmiany
git add .
git commit -m "WIP: zmiany przed przeglądaniem historii"

# 2. Sprawdź historię
git log --oneline -10

# 3. Przełącz się do starego commita (tylko do przeglądania)
git checkout <hash_starego_commita>

# 4. Przejrzyj kod (możesz otworzyć pliki w edytorze)

# 5. Wróć do najnowszego commita
git checkout main

# 6. Jeśli chcesz zobaczyć różnice
git diff <hash_stary> <hash_nowy> -- app/services/electricity/manager.py
```

## 9. Najważniejsze komendy - szybka ściąga

| Komenda | Opis |
|---------|------|
| `git status` | Sprawdź status zmian |
| `git add .` | Dodaj wszystkie zmiany |
| `git commit -m "opis"` | Utwórz commit |
| `git log --oneline -10` | Pokaż ostatnie 10 commitów |
| `git checkout <hash>` | Przełącz się do commita (tylko przeglądanie) |
| `git checkout main` | Wróć do najnowszego commita |
| `git show <hash>` | Pokaż szczegóły commita |
| `git diff <hash1> <hash2>` | Porównaj dwa commity |
| `git stash` | Zapisz zmiany tymczasowo |
| `git stash pop` | Przywróć zapisane zmiany |

## 10. Bezpieczeństwo

### Zawsze przed przełączeniem się do starego commita:

1. **Zapisz zmiany:**
   ```bash
   git add .
   git commit -m "Zapis przed przeglądaniem historii"
   ```

2. **LUB użyj stash:**
   ```bash
   git stash
   ```

3. **Sprawdź, że jesteś na właściwym branchu:**
   ```bash
   git branch
   ```

### Jeśli przypadkowo wprowadzisz zmiany w trybie detached HEAD:

```bash
# Utwórz branch z tych zmian (jeśli są ważne)
git checkout -b zapisane-zmiany

# LUB odrzuć zmiany i wróć do main
git checkout main
```

## 11. Przykład: Przejrzyj kod z commita "992cb95"

```bash
# 1. Sprawdź co to za commit
git show 992cb95 --stat

# 2. Zobacz zmiany w konkretnym pliku
git show 992cb95:app/services/electricity/manager.py

# 3. LUB przełącz się do tego commita (tylko przeglądanie)
git checkout 992cb95

# 4. Przejrzyj kod w edytorze

# 5. Wróć do main
git checkout main
```

