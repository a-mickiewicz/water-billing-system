# Konfiguracja SMTP dla wysyłania emaili

Aby móc wysyłać kody resetujące hasło na email, musisz skonfigurować ustawienia SMTP.

## Sposób 1: Plik .env (Zalecane)

Utwórz plik `.env` w głównym katalogu projektu z następującą zawartością:

```env
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=twoj@email.com
SMTP_PASSWORD=twoje_haslo_lub_haslo_aplikacji
```

## Sposób 2: Zmienne środowiskowe systemowe

Ustaw zmienne środowiskowe w systemie:

**Windows (PowerShell):**
```powershell
$env:SMTP_SERVER="smtp.gmail.com"
$env:SMTP_PORT="587"
$env:SMTP_USER="twoj@email.com"
$env:SMTP_PASSWORD="twoje_haslo"
```

**Linux/Mac:**
```bash
export SMTP_SERVER=smtp.gmail.com
export SMTP_PORT=587
export SMTP_USER=twoj@email.com
export SMTP_PASSWORD=twoje_haslo
```

## Konfiguracja dla Gmail

Jeśli używasz Gmail:

1. **Włącz 2-etapową weryfikację** w ustawieniach konta Google
2. **Wygeneruj hasło aplikacji:**
   - Przejdź do: https://myaccount.google.com/apppasswords
   - Wybierz "Aplikacja" i "Poczta"
   - Wygeneruj hasło i użyj go jako `SMTP_PASSWORD`

3. Ustawienia w `.env`:
```env
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=twoj@gmail.com
SMTP_PASSWORD=wygenerowane_haslo_aplikacji
```

## Konfiguracja dla innych dostawców

### Outlook/Hotmail:
```env
SMTP_SERVER=smtp-mail.outlook.com
SMTP_PORT=587
SMTP_USER=twoj@outlook.com
SMTP_PASSWORD=twoje_haslo
```

### Inne serwery SMTP:
Sprawdź dokumentację swojego dostawcy poczty email dla właściwych ustawień SMTP.

## Lokalne środowisko (bez SMTP)

Jeśli nie skonfigurujesz SMTP, kod resetujący hasło zostanie:
- Wyświetlony w konsoli serwera
- Zapisany w pliku `password_reset_code.txt` w głównym katalogu projektu

**Uwaga:** Plik `password_reset_code.txt` zawiera wrażliwe dane - nie commituj go do repozytorium!

