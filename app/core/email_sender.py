"""
Moduł wysyłania emaili z backupami bazy danych.
Pliki są szyfrowane przed wysłaniem - tylko aplikacja może je odszyfrować.
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from typing import Optional, List
import os

from app.core.file_encryption import encrypt_file_in_memory
from app.config import settings


def send_backup_email(
    recipient_email: str,
    backup_file_path: str,
    smtp_server: str = None,
    smtp_port: int = 587,
    smtp_user: str = None,
    smtp_password: str = None,
    use_tls: bool = True
) -> bool:
    """
    Wysyła backup bazy danych na email.
    
    Args:
        recipient_email: Email odbiorcy
        backup_file_path: Ścieżka do pliku backupu
        smtp_server: Adres serwera SMTP (domyślnie z zmiennych środowiskowych)
        smtp_port: Port SMTP (domyślnie 587)
        smtp_user: Użytkownik SMTP (domyślnie z zmiennych środowiskowych)
        smtp_password: Hasło SMTP (domyślnie z zmiennych środowiskowych)
        use_tls: Czy używać TLS
    
    Returns:
        True jeśli wysłano pomyślnie, False w przeciwnym razie
    """
    # Pobierz konfigurację z ustawień (Pydantic Settings wczytuje z .env) lub zmiennych środowiskowych
    if smtp_server is None:
        smtp_server = settings.smtp_server or os.getenv("SMTP_SERVER", "smtp.gmail.com")
    if smtp_port is None:
        smtp_port = settings.smtp_port or int(os.getenv("SMTP_PORT", "587"))
    if smtp_user is None:
        smtp_user = settings.smtp_user or os.getenv("SMTP_USER")
    if smtp_password is None:
        smtp_password = settings.smtp_password or os.getenv("SMTP_PASSWORD")
    
    # Usuń spacje z hasła (hasła aplikacji Gmail mogą mieć spacje, ale SMTP ich nie akceptuje)
    if smtp_password:
        smtp_password = smtp_password.replace(" ", "")
    
    if not smtp_user or not smtp_password:
        print("[WARN] Brak konfiguracji SMTP. Ustaw zmienne środowiskowe SMTP_USER i SMTP_PASSWORD")
        print(f"[DEBUG] SMTP_USER z settings: '{settings.smtp_user}'")
        print(f"[DEBUG] SMTP_PASSWORD z settings: {'*' * len(settings.smtp_password) if settings.smtp_password else 'BRAK'}")
        print(f"[DEBUG] SMTP_USER z os.getenv: '{os.getenv('SMTP_USER')}'")
        print(f"[DEBUG] SMTP_PASSWORD z os.getenv: {'*' * len(os.getenv('SMTP_PASSWORD', '')) if os.getenv('SMTP_PASSWORD') else 'BRAK'}")
        print("[INFO] Aby skonfigurować SMTP, dodaj do pliku .env lub ustaw zmienne środowiskowe:")
        print("[INFO]   SMTP_SERVER=smtp.gmail.com (lub inny serwer SMTP)")
        print("[INFO]   SMTP_PORT=587")
        print("[INFO]   SMTP_USER=twoj@email.com")
        print("[INFO]   SMTP_PASSWORD=twoje_haslo_lub_haslo_aplikacji")
        return False
    
    if not os.path.exists(backup_file_path):
        print(f"[ERROR] Plik backupu nie istnieje: {backup_file_path}")
        return False
    
    try:
        # Utwórz wiadomość
        msg = MIMEMultipart()
        msg['From'] = smtp_user
        msg['To'] = recipient_email
        msg['Subject'] = f"Backup bazy danych - {Path(backup_file_path).stem}"
        
        # Treść wiadomości
        body = f"""
Witaj,

W załączniku znajduje się zaszyfrowany backup bazy danych systemu rozliczania rachunków.

⚠️ WAŻNE: Plik jest zaszyfrowany i może być odszyfrowany tylko za pomocą aplikacji.
Aby odszyfrować plik, użyj funkcji deszyfrowania w aplikacji.

Data utworzenia: {Path(backup_file_path).stem.replace('water_billing_backup_', '').replace('_', '-')}

Pozdrawiam,
System rozliczania rachunków
        """
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        # Zaszyfruj plik przed wysłaniem
        try:
            encrypted_data = encrypt_file_in_memory(backup_file_path)
            
            # Utwórz nazwę pliku z rozszerzeniem .encrypted
            original_filename = Path(backup_file_path).name
            encrypted_filename = f"{original_filename}.encrypted"
            
            # Załącz zaszyfrowany plik
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(encrypted_data)
            
            encoders.encode_base64(part)
            part.add_header(
                'Content-Disposition',
                f'attachment; filename= {encrypted_filename}'
            )
            msg.attach(part)
            
        except Exception as e:
            print(f"[ERROR] Błąd szyfrowania pliku przed wysłaniem: {str(e)}")
            raise
        
        # Wyślij email
        print(f"[INFO] Próba połączenia z SMTP: {smtp_server}:{smtp_port}")
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.set_debuglevel(1)  # Włącz debugowanie SMTP
        
        if use_tls:
            print("[INFO] Włączanie TLS...")
            server.starttls()
        
        print("[INFO] Logowanie do serwera SMTP...")
        server.login(smtp_user, smtp_password)
        print("[INFO] Zalogowano pomyślnie")
        
        print(f"[INFO] Wysyłanie emaila do: {recipient_email}")
        text = msg.as_string()
        server.sendmail(smtp_user, recipient_email, text)
        server.quit()
        
        print(f"[OK] Wysłano backup na email: {recipient_email}")
        return True
        
    except smtplib.SMTPAuthenticationError as e:
        print(f"[ERROR] Błąd autentykacji SMTP: {str(e)}")
        print(f"[ERROR] Sprawdź czy:")
        print(f"[ERROR]   1. Hasło aplikacji jest poprawne (bez spacji)")
        print(f"[ERROR]   2. Włączona jest weryfikacja dwuetapowa w Gmail")
        print(f"[ERROR]   3. Używasz hasła aplikacji, nie hasła konta Gmail")
        return False
    except smtplib.SMTPException as e:
        print(f"[ERROR] Błąd SMTP: {str(e)}")
        return False
    except Exception as e:
        print(f"[ERROR] Błąd wysyłania email: {str(e)}")
        print(f"[ERROR] Typ błędu: {type(e).__name__}")
        import traceback
        print(f"[ERROR] Szczegóły: {traceback.format_exc()}")
        return False


def send_backup_to_user_email(
    user_email: str,
    backup_file_path: str = None
) -> bool:
    """
    Wysyła backup na email użytkownika.
    Jeśli backup_file_path nie jest podany, używa najnowszego backupu okresowego.
    
    Args:
        user_email: Email użytkownika
        backup_file_path: Ścieżka do pliku backupu (opcjonalnie)
    
    Returns:
        True jeśli wysłano pomyślnie, False w przeciwnym razie
    """
    from app.core.backup import get_latest_backup
    
    if backup_file_path is None:
        backup_file_path = get_latest_backup(backup_type="period")
        if backup_file_path is None:
            print("[ERROR] Brak dostępnego backupu do wysłania")
            return False
    
    return send_backup_email(recipient_email=user_email, backup_file_path=backup_file_path)


def send_password_reset_code(
    recipient_email: str,
    reset_code: str,
    smtp_server: str = None,
    smtp_port: int = 587,
    smtp_user: str = None,
    smtp_password: str = None,
    use_tls: bool = True
) -> bool:
    """
    Wysyła kod resetujący hasło na email.
    
    Args:
        recipient_email: Email odbiorcy
        reset_code: Kod resetujący (6 cyfr)
        smtp_server: Adres serwera SMTP (domyślnie z zmiennych środowiskowych)
        smtp_port: Port SMTP (domyślnie 587)
        smtp_user: Użytkownik SMTP (domyślnie z zmiennych środowiskowych)
        smtp_password: Hasło SMTP (domyślnie z zmiennych środowiskowych)
        use_tls: Czy używać TLS
    
    Returns:
        True jeśli wysłano pomyślnie, False w przeciwnym razie
    """
    # Pobierz konfigurację z ustawień (Pydantic Settings wczytuje z .env) lub zmiennych środowiskowych
    if smtp_server is None:
        smtp_server = settings.smtp_server or os.getenv("SMTP_SERVER", "smtp.gmail.com")
    if smtp_port is None:
        smtp_port = settings.smtp_port or int(os.getenv("SMTP_PORT", "587"))
    if smtp_user is None:
        smtp_user = settings.smtp_user or os.getenv("SMTP_USER")
    if smtp_password is None:
        smtp_password = settings.smtp_password or os.getenv("SMTP_PASSWORD")
    
    # Usuń spacje z hasła (hasła aplikacji Gmail mogą mieć spacje, ale SMTP ich nie akceptuje)
    if smtp_password:
        smtp_password = smtp_password.replace(" ", "")
    
    if not smtp_user or not smtp_password:
        print("[WARN] Brak konfiguracji SMTP. Ustaw zmienne środowiskowe SMTP_USER i SMTP_PASSWORD")
        print(f"[DEBUG] SMTP_USER z settings: '{settings.smtp_user}'")
        print(f"[DEBUG] SMTP_PASSWORD z settings: {'*' * len(settings.smtp_password) if settings.smtp_password else 'BRAK'}")
        print(f"[DEBUG] SMTP_USER z os.getenv: '{os.getenv('SMTP_USER')}'")
        print(f"[DEBUG] SMTP_PASSWORD z os.getenv: {'*' * len(os.getenv('SMTP_PASSWORD', '')) if os.getenv('SMTP_PASSWORD') else 'BRAK'}")
        print("[INFO] Aby skonfigurować SMTP, dodaj do pliku .env lub ustaw zmienne środowiskowe:")
        print("[INFO]   SMTP_SERVER=smtp.gmail.com (lub inny serwer SMTP)")
        print("[INFO]   SMTP_PORT=587")
        print("[INFO]   SMTP_USER=twoj@email.com")
        print("[INFO]   SMTP_PASSWORD=twoje_haslo_lub_haslo_aplikacji")
        return False
    
    try:
        # Utwórz wiadomość
        msg = MIMEMultipart()
        msg['From'] = smtp_user
        msg['To'] = recipient_email
        msg['Subject'] = "Kod resetujący hasło - System rozliczania rachunków"
        
        # Treść wiadomości
        body = f"""
Witaj,

Otrzymaliśmy żądanie resetu hasła dla Twojego konta w systemie rozliczania rachunków.

Twój kod resetujący hasło to: {reset_code}

⚠️ WAŻNE:
- Kod jest ważny przez 15 minut
- Kod może być użyty tylko raz
- Jeśli nie prosiłeś o reset hasła, zignoruj tę wiadomość

Aby zresetować hasło:
1. Wróć do aplikacji
2. Wybierz opcję "Nie pamiętam hasła"
3. Wprowadź ten kod
4. Ustaw nowe hasło

Pozdrawiam,
System rozliczania rachunków
        """
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        # Wyślij email
        print(f"[INFO] Próba połączenia z SMTP: {smtp_server}:{smtp_port}")
        print(f"[INFO] Użytkownik SMTP: {smtp_user}")
        
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.set_debuglevel(1)  # Włącz debugowanie SMTP
        
        if use_tls:
            print("[INFO] Włączanie TLS...")
            server.starttls()
        
        print("[INFO] Logowanie do serwera SMTP...")
        server.login(smtp_user, smtp_password)
        print("[INFO] Zalogowano pomyślnie")
        
        print(f"[INFO] Wysyłanie emaila do: {recipient_email}")
        text = msg.as_string()
        server.sendmail(smtp_user, recipient_email, text)
        server.quit()
        
        print(f"[OK] Wysłano kod resetujący hasło na email: {recipient_email}")
        return True
        
    except smtplib.SMTPAuthenticationError as e:
        print(f"[ERROR] Błąd autentykacji SMTP: {str(e)}")
        print(f"[ERROR] Sprawdź czy:")
        print(f"[ERROR]   1. Hasło aplikacji jest poprawne (bez spacji)")
        print(f"[ERROR]   2. Włączona jest weryfikacja dwuetapowa w Gmail")
        print(f"[ERROR]   3. Używasz hasła aplikacji, nie hasła konta Gmail")
        return False
    except smtplib.SMTPException as e:
        print(f"[ERROR] Błąd SMTP: {str(e)}")
        return False
    except Exception as e:
        print(f"[ERROR] Błąd wysyłania email z kodem resetującym: {str(e)}")
        print(f"[ERROR] Typ błędu: {type(e).__name__}")
        import traceback
        print(f"[ERROR] Szczegóły: {traceback.format_exc()}")
        return False
