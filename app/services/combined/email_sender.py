"""
Moduł wysyłania rachunków łączonych na email.
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from typing import Optional, List
import os

from app.config import settings
from app.models.combined import CombinedBill
from app.models.water import Local


def send_combined_bill_email(
    recipient_email: str,
    bill: CombinedBill,
    pdf_path: str,
    smtp_server: str = None,
    smtp_port: int = 587,
    smtp_user: str = None,
    smtp_password: str = None,
    use_tls: bool = True
) -> bool:
    """
    Wysyła rachunek łączony na email.
    
    Args:
        recipient_email: Email odbiorcy
        bill: Rachunek łączony
        pdf_path: Ścieżka do pliku PDF
        smtp_server: Adres serwera SMTP (domyślnie z zmiennych środowiskowych)
        smtp_port: Port SMTP (domyślnie 587)
        smtp_user: Użytkownik SMTP (domyślnie z zmiennych środowiskowych)
        smtp_password: Hasło SMTP (domyślnie z zmiennych środowiskowych)
        use_tls: Czy używać TLS
    
    Returns:
        True jeśli wysłano pomyślnie, False w przeciwnym razie
    """
    # Pobierz konfigurację z ustawień
    if smtp_server is None:
        smtp_server = settings.smtp_server or os.getenv("SMTP_SERVER", "smtp.gmail.com")
    if smtp_port is None:
        smtp_port = settings.smtp_port or int(os.getenv("SMTP_PORT", "587"))
    if smtp_user is None:
        smtp_user = settings.smtp_user or os.getenv("SMTP_USER")
    if smtp_password is None:
        smtp_password = settings.smtp_password or os.getenv("SMTP_PASSWORD")
    
    # Usuń spacje z hasła
    if smtp_password:
        smtp_password = smtp_password.replace(" ", "")
    
    if not smtp_user or not smtp_password:
        print("[ERROR] Brak konfiguracji SMTP. Ustaw SMTP_USER i SMTP_PASSWORD w zmiennych środowiskowych lub pliku .env")
        return False
    
    if not Path(pdf_path).exists():
        print(f"[ERROR] Plik PDF nie istnieje: {pdf_path}")
        return False
    
    try:
        # Utwórz wiadomość
        msg = MIMEMultipart()
        msg['From'] = smtp_user
        msg['To'] = recipient_email
        msg['Subject'] = f"Rachunek za media - {bill.period_start} do {bill.period_end} - Lokal {bill.local}"
        
        # Treść wiadomości
        local_name = bill.local_obj.tenant if bill.local_obj and bill.local_obj.tenant else bill.local
        period_text = f"{bill.period_start} do {bill.period_end}"
        
        body = f"""
Witaj {local_name},

W załączeniu przesyłamy rachunek za media za okres {period_text}.

Szczegóły:
- Lokal: {bill.local}
- Okres rozliczeniowy: {period_text}
- Suma netto: {bill.total_net_sum:.2f} zł
- Suma brutto: {bill.total_gross_sum:.2f} zł
- Data wygenerowania: {bill.generated_date.strftime('%d.%m.%Y')}

Rachunek zawiera rozliczenie za:
- Wodę i ścieki
- Gaz
- Prąd

W razie pytań prosimy o kontakt.

Pozdrawiamy,
System rozliczania rachunków
        """
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        # Załącz plik PDF
        with open(pdf_path, "rb") as attachment:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(attachment.read())
        
        encoders.encode_base64(part)
        part.add_header(
            'Content-Disposition',
            f'attachment; filename= {Path(pdf_path).name}'
        )
        msg.attach(part)
        
        # Wyślij email
        print(f"[INFO] Próba połączenia z SMTP: {smtp_server}:{smtp_port}")
        server = smtplib.SMTP(smtp_server, smtp_port)
        
        if use_tls:
            print("[INFO] Włączanie TLS...")
            server.starttls()
        
        print("[INFO] Logowanie do serwera SMTP...")
        server.login(smtp_user, smtp_password)
        print("[INFO] Zalogowano pomyślnie")
        
        print(f"[INFO] Wysyłanie rachunku na email: {recipient_email}")
        text = msg.as_string()
        server.sendmail(smtp_user, recipient_email, text)
        server.quit()
        
        print(f"[OK] Wysłano rachunek na email: {recipient_email}")
        return True
        
    except smtplib.SMTPAuthenticationError as e:
        print(f"[ERROR] Błąd autentykacji SMTP: {str(e)}")
        return False
    except smtplib.SMTPException as e:
        print(f"[ERROR] Błąd SMTP: {str(e)}")
        return False
    except Exception as e:
        print(f"[ERROR] Błąd wysyłania email: {str(e)}")
        import traceback
        print(f"[ERROR] Szczegóły: {traceback.format_exc()}")
        return False

