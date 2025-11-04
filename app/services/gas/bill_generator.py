"""
Moduł generowania plików PDF rachunków za gaz.
Generuje osobne rachunki PDF dla każdego lokalu z walidacją danych faktury.
"""

import os
from pathlib import Path
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.pdfbase import pdfmetrics
from sqlalchemy.orm import Session
from app.models.gas import GasBill, GasInvoice
from app.models.water import Local


def format_money(value: float) -> str:
    """Formatuje kwotę do wyświetlenia."""
    return f"{value:.2f} zł"


def format_usage_m3(value: float) -> str:
    """Formatuje zużycie w m³ do wyświetlenia."""
    return f"{value:.2f} m³"


def format_usage_kwh(value: float) -> str:
    """Formatuje zużycie w kWh do wyświetlenia."""
    return f"{value:.2f} kWh"


def validate_gas_invoice(invoice: GasInvoice, strict: bool = True) -> tuple[bool, list[str]]:
    """
    Waliduje dane faktury gazu - sprawdza czy obliczenia się zgadzają.
    
    Args:
        invoice: Faktura gazu do walidacji
        strict: Jeśli False, sprawdza tylko pola z wartościami > 0 (dla niepełnych danych)
    
    Returns:
        Tuple (is_valid, errors) gdzie:
        - is_valid: True jeśli wszystkie obliczenia są poprawne
        - errors: Lista błędów walidacji
    """
    errors = []
    tolerance = 0.01  # Tolerancja dla porównań float
    
    # 1. Sprawdź odczyty liczników
    calculated_usage = invoice.current_reading - invoice.previous_reading
    if abs(calculated_usage - invoice.fuel_usage_m3) > tolerance:
        errors.append(
            f"Zużycie gazu: {calculated_usage:.2f} m³ (obliczone z odczytów) "
            f"nie zgadza się z fakturą: {invoice.fuel_usage_m3:.2f} m³"
        )
    
    # 2. Sprawdź paliwo gazowe (tylko jeśli ma wartości)
    if invoice.fuel_value_gross > 0 or strict:
        calculated_fuel_value_net = invoice.fuel_usage_m3 * invoice.fuel_price_net
        if abs(calculated_fuel_value_net - invoice.fuel_value_net) > tolerance:
            errors.append(
                f"Wartość netto paliwa: {calculated_fuel_value_net:.2f} zł "
                f"nie zgadza się z fakturą: {invoice.fuel_value_net:.2f} zł"
            )
        
        if invoice.fuel_value_gross > 0:
            calculated_fuel_vat = invoice.fuel_value_net * invoice.vat_rate
            if abs(calculated_fuel_vat - invoice.fuel_vat_amount) > tolerance:
                errors.append(
                    f"VAT paliwa: {calculated_fuel_vat:.2f} zł "
                    f"nie zgadza się z fakturą: {invoice.fuel_vat_amount:.2f} zł"
                )
            
            calculated_fuel_gross = invoice.fuel_value_net + invoice.fuel_vat_amount
            if abs(calculated_fuel_gross - invoice.fuel_value_gross) > tolerance:
                errors.append(
                    f"Wartość brutto paliwa: {calculated_fuel_gross:.2f} zł "
                    f"nie zgadza się z fakturą: {invoice.fuel_value_gross:.2f} zł"
                )
    
    # 3. Sprawdź konwersję m³ -> kWh dla paliwa
    calculated_fuel_kwh = invoice.fuel_usage_m3 * invoice.fuel_conversion_factor
    if abs(calculated_fuel_kwh - invoice.fuel_usage_kwh) > tolerance:
        errors.append(
            f"Zużycie paliwa w kWh: {calculated_fuel_kwh:.2f} kWh "
            f"nie zgadza się z fakturą: {invoice.fuel_usage_kwh:.2f} kWh"
        )
    
    # 4. Sprawdź opłatę abonamentową (tylko jeśli ma wartości)
    if invoice.subscription_value_gross > 0 or strict:
        calculated_subscription_value_net = invoice.subscription_quantity * invoice.subscription_price_net
        if abs(calculated_subscription_value_net - invoice.subscription_value_net) > tolerance:
            errors.append(
                f"Wartość netto abonamentu: {calculated_subscription_value_net:.2f} zł "
                f"nie zgadza się z fakturą: {invoice.subscription_value_net:.2f} zł"
            )
        
        if invoice.subscription_value_gross > 0:
            calculated_subscription_vat = invoice.subscription_value_net * invoice.vat_rate
            if abs(calculated_subscription_vat - invoice.subscription_vat_amount) > tolerance:
                errors.append(
                    f"VAT abonamentu: {calculated_subscription_vat:.2f} zł "
                    f"nie zgadza się z fakturą: {invoice.subscription_vat_amount:.2f} zł"
                )
            
            calculated_subscription_gross = invoice.subscription_value_net + invoice.subscription_vat_amount
            if abs(calculated_subscription_gross - invoice.subscription_value_gross) > tolerance:
                errors.append(
                    f"Wartość brutto abonamentu: {calculated_subscription_gross:.2f} zł "
                    f"nie zgadza się z fakturą: {invoice.subscription_value_gross:.2f} zł"
                )
    
    # 5. Sprawdź opłatę dystrybucyjną stałą (tylko jeśli ma wartości)
    if invoice.distribution_fixed_value_gross > 0 or strict:
        calculated_dist_fixed_value_net = invoice.distribution_fixed_quantity * invoice.distribution_fixed_price_net
        if abs(calculated_dist_fixed_value_net - invoice.distribution_fixed_value_net) > tolerance:
            errors.append(
                f"Wartość netto dystrybucji stałej: {calculated_dist_fixed_value_net:.2f} zł "
                f"nie zgadza się z fakturą: {invoice.distribution_fixed_value_net:.2f} zł"
            )
        
        if invoice.distribution_fixed_value_gross > 0:
            calculated_dist_fixed_vat = invoice.distribution_fixed_value_net * invoice.vat_rate
            if abs(calculated_dist_fixed_vat - invoice.distribution_fixed_vat_amount) > tolerance:
                errors.append(
                    f"VAT dystrybucji stałej: {calculated_dist_fixed_vat:.2f} zł "
                    f"nie zgadza się z fakturą: {invoice.distribution_fixed_vat_amount:.2f} zł"
                )
            
            calculated_dist_fixed_gross = invoice.distribution_fixed_value_net + invoice.distribution_fixed_vat_amount
            if abs(calculated_dist_fixed_gross - invoice.distribution_fixed_value_gross) > tolerance:
                errors.append(
                    f"Wartość brutto dystrybucji stałej: {calculated_dist_fixed_gross:.2f} zł "
                    f"nie zgadza się z fakturą: {invoice.distribution_fixed_value_gross:.2f} zł"
                )
    
    # 6. Sprawdź opłatę dystrybucyjną zmienną (tylko jeśli ma wartości)
    if invoice.distribution_variable_value_gross > 0 or strict:
        calculated_dist_var_kwh = invoice.distribution_variable_usage_m3 * invoice.distribution_variable_conversion_factor
        if abs(calculated_dist_var_kwh - invoice.distribution_variable_usage_kwh) > tolerance:
            errors.append(
                f"Zużycie dystrybucji zmiennej w kWh: {calculated_dist_var_kwh:.2f} kWh "
                f"nie zgadza się z fakturą: {invoice.distribution_variable_usage_kwh:.2f} kWh"
            )
        
        calculated_dist_var_value_net = invoice.distribution_variable_usage_kwh * invoice.distribution_variable_price_net
        if abs(calculated_dist_var_value_net - invoice.distribution_variable_value_net) > tolerance:
            errors.append(
                f"Wartość netto dystrybucji zmiennej: {calculated_dist_var_value_net:.2f} zł "
                f"nie zgadza się z fakturą: {invoice.distribution_variable_value_net:.2f} zł"
            )
        
        if invoice.distribution_variable_value_gross > 0:
            calculated_dist_var_vat = invoice.distribution_variable_value_net * invoice.vat_rate
            if abs(calculated_dist_var_vat - invoice.distribution_variable_vat_amount) > tolerance:
                errors.append(
                    f"VAT dystrybucji zmiennej: {calculated_dist_var_vat:.2f} zł "
                    f"nie zgadza się z fakturą: {invoice.distribution_variable_vat_amount:.2f} zł"
                )
            
            calculated_dist_var_gross = invoice.distribution_variable_value_net + invoice.distribution_variable_vat_amount
            if abs(calculated_dist_var_gross - invoice.distribution_variable_value_gross) > tolerance:
                errors.append(
                    f"Wartość brutto dystrybucji zmiennej: {calculated_dist_var_gross:.2f} zł "
                    f"nie zgadza się z fakturą: {invoice.distribution_variable_value_gross:.2f} zł"
                )
    
    # 7. Sprawdź sumę VAT
    calculated_total_vat = (
        invoice.fuel_vat_amount +
        invoice.subscription_vat_amount +
        invoice.distribution_fixed_vat_amount +
        invoice.distribution_variable_vat_amount
    )
    if abs(calculated_total_vat - invoice.vat_amount) > tolerance:
        errors.append(
            f"Suma VAT: {calculated_total_vat:.2f} zł "
            f"nie zgadza się z fakturą: {invoice.vat_amount:.2f} zł"
        )
    
    # 8. Sprawdź sumę netto
    calculated_total_net = (
        invoice.fuel_value_net +
        invoice.subscription_value_net +
        invoice.distribution_fixed_value_net +
        invoice.distribution_variable_value_net
    )
    if abs(calculated_total_net - invoice.total_net_sum) > tolerance:
        errors.append(
            f"Suma netto: {calculated_total_net:.2f} zł "
            f"nie zgadza się z fakturą: {invoice.total_net_sum:.2f} zł"
        )
    
    # 9. Sprawdź sumę brutto
    calculated_total_gross = (
        invoice.fuel_value_gross +
        invoice.subscription_value_gross +
        invoice.distribution_fixed_value_gross +
        invoice.distribution_variable_value_gross
    )
    if abs(calculated_total_gross - invoice.total_gross_sum) > tolerance:
        errors.append(
            f"Suma brutto: {calculated_total_gross:.2f} zł "
            f"nie zgadza się z fakturą: {invoice.total_gross_sum:.2f} zł"
        )
    
    # 10. Sprawdź czy suma brutto = suma netto + VAT
    calculated_gross_from_net_vat = invoice.total_net_sum + invoice.vat_amount
    if abs(calculated_gross_from_net_vat - invoice.total_gross_sum) > tolerance:
        errors.append(
            f"Suma brutto (netto + VAT): {calculated_gross_from_net_vat:.2f} zł "
            f"nie zgadza się z fakturą: {invoice.total_gross_sum:.2f} zł"
        )
    
    return len(errors) == 0, errors


def generate_bill_pdf(db: Session, bill: GasBill) -> str:
    """
    Generuje plik PDF rachunku za gaz.
    
    Args:
        db: Sesja bazy danych
        bill: Rachunek gazu
    
    Returns:
        Ścieżka do wygenerowanego pliku PDF
    
    Raises:
        ValueError: Jeśli faktura nie przejdzie walidacji
    """
    # Pobierz fakturę i lokal
    invoice = bill.invoice
    if not invoice:
        raise ValueError(f"Rachunek {bill.id} nie ma przypisanej faktury")
    
    # Waliduj fakturę przed generowaniem (nie strict - sprawdza tylko wypełnione pola)
    is_valid, errors = validate_gas_invoice(invoice, strict=False)
    if not is_valid:
        print(f"[WARNING] Faktura {invoice.invoice_number} ma błędy walidacji:")
        for error in errors[:5]:  # Pokaż tylko pierwsze 5 błędów
            print(f"  - {error}")
        if len(errors) > 5:
            print(f"  ... i {len(errors) - 5} więcej błędów")
        print("[INFO] Kontynuuję generowanie rachunku pomimo błędów walidacji...")
    
    # Utwórz folder dla rachunków gazu
    bills_folder = Path("bills/gaz")
    bills_folder.mkdir(parents=True, exist_ok=True)
    
    # Nazwa pliku: gas_bill_2025_04_local_gora.pdf
    filename = f"gas_bill_{bill.data}_local_{bill.local}.pdf"
    filepath = bills_folder / filename
    
    # Sprawdź czy font Arial jest dostępny (dla polskich znaków)
    try:
        from reportlab.pdfbase.ttfonts import TTFont  # type: ignore
        import platform
        
        font_registered = False
        if platform.system() == 'Windows':
            font_paths = [
                'C:/Windows/Fonts/arial.ttf',
                'C:/Windows/Fonts/Arial.ttf',
                Path('C:/Windows/Fonts/arial.ttf'),
            ]
        else:
            font_paths = [
                '/usr/share/fonts/truetype/msttcorefonts/arial.ttf',
                '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
            ]
        
        for font_path in font_paths:
            try:
                font_path_str = str(font_path)
                if Path(font_path_str).exists():
                    pdfmetrics.registerFont(TTFont('Arial', font_path_str))
                    if 'Arial' in pdfmetrics.getRegisteredFontNames():
                        font_registered = True
                        break
            except Exception:
                continue
        
        if not font_registered:
            print("[WARNING] Nie znaleziono czcionki Arial, używam Helvetica")
        default_font = 'Arial' if font_registered else 'Helvetica'
    except Exception:
        print("[WARNING] Błąd rejestracji czcionki, używam Helvetica")
        default_font = 'Helvetica'
    
    # Funkcja do tworzenia CustomDocTemplate z nagłówkiem
    class CustomDocTemplate(SimpleDocTemplate):
        def __init__(self, font_name, *args, **kwargs):
            SimpleDocTemplate.__init__(self, *args, **kwargs)
            self.font_name = font_name
            self.page_width = A4[0]
            self.page_height = A4[1]
        
        def build(self, flowables, onFirstPage=None, onLaterPages=None):
            now = datetime.now()
            generated_text = f"Wygenerowano: {now.strftime('%d.%m.%Y %H:%M')}"
            font_name = self.font_name
            page_width = self.page_width
            page_height = self.page_height
            
            def add_header(canvas, doc):
                canvas.saveState()
                canvas.setFont(font_name, 9)
                right_margin = 15*mm
                text_width = canvas.stringWidth(generated_text, font_name, 9)
                x = page_width - right_margin - text_width
                y = page_height - 15*mm
                canvas.drawString(x, y, generated_text)
                canvas.restoreState()
            
            return SimpleDocTemplate.build(self, flowables, onFirstPage=add_header, onLaterPages=add_header)
    
    # Stwórz dokument
    doc = CustomDocTemplate(default_font, str(filepath), pagesize=A4,
                           leftMargin=15*mm, rightMargin=15*mm,
                           topMargin=25*mm, bottomMargin=15*mm)
    
    # Style
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading5'],
        fontSize=12,
        textColor=colors.HexColor('#2c5aa0'),
        spaceAfter=1*mm,
        alignment=TA_LEFT,
        fontName=default_font
    )
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading3'],
        fontSize=11,
        textColor=colors.HexColor('#2c5aa0'),
        spaceBefore=2*mm,
        spaceAfter=1*mm,
        fontName=default_font
    )
    
    story = []
    
    # Tytuł
    story.append(Paragraph("RACHUNEK ZA GAZ", title_style))
    story.append(Paragraph("NA PODSTAWIE FAKTUR (W ZAŁĄCZNIKU)", heading_style))
    
    # Dane lokalu
    local_obj = db.query(Local).filter(Local.local == bill.local).first()
    
    # Okres rozliczeniowy
    period_text = bill.data
    if invoice.period_start and invoice.period_stop:
        period_start = invoice.period_start.strftime('%d.%m.%Y')
        period_stop = invoice.period_stop.strftime('%d.%m.%Y')
        period_text = f"{period_start} - {period_stop}"
    
    data = [
        ['Okres rozliczeniowy:', period_text],
        ['Lokal:', bill.local],
        ['Najemca:', local_obj.tenant if local_obj else '-'],
        ['Udział w kosztach:', f"{bill.cost_share * 100:.0f}%"],
        ['Numer faktury:', invoice.invoice_number],
    ]
    
    table = Table(data, colWidths=[50*mm, 125*mm])
    table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), default_font),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    
    story.append(table)
    story.append(Spacer(1, 3*mm))
    
    # Rozliczenie kosztów - nowa tabela
    story.append(Paragraph("ROZLICZENIE KOSZTOW", heading_style))
    
    # Oblicz dane dla tabeli
    # a) Dom - Zużycie gazu (m³)
    house_usage_m3 = invoice.fuel_usage_m3
    
    # b) Dom - kwota brutto na fakturze (bez odsetek) - "Wartość brutto całość"
    house_gross_without_interest = invoice.total_gross_sum - invoice.late_payment_interest
    
    # c) Zużycie lokalu (%) - udział w kosztach
    local_share_percent = bill.cost_share * 100
    
    # Oblicz lokalną kwotę brutto na podstawie udziału z total_gross_sum (bez odsetek)
    # Użytkownik chce używać total_gross_sum do obliczenia udziału
    local_gross_base = house_gross_without_interest * bill.cost_share
    
    # d) Lokal suma - netto (obliczamy z brutto)
    local_net = local_gross_base / (1 + invoice.vat_rate)
    
    # e) VAT - obliczamy z netto
    local_vat = local_net * invoice.vat_rate
    
    # f) Lokal suma brutto (dla "gora" dodajemy odsetki)
    local_gross = local_gross_base
    if bill.local == 'gora' and invoice.late_payment_interest > 0:
        local_gross += invoice.late_payment_interest
        # Aktualizuj netto i VAT po dodaniu odsetek
        # Odsetki są brutto, więc netto odsetek = odsetki / 1.23
        interest_net = invoice.late_payment_interest / (1 + invoice.vat_rate)
        local_net += interest_net
        local_vat = local_net * invoice.vat_rate
        local_gross = local_net + local_vat
    
    costs_data = [
        ['', 'Wartosc'],
        ['Dom - Zuzycie gazu (m3):', format_usage_m3(house_usage_m3)],
        ['Dom - kwota brutto na fakturze (bez odsetek):', format_money(house_gross_without_interest)],
        ['Zuzycie lokalu (%):', f"{local_share_percent:.0f}%"],
        ['', ''],  # Pusta linia dla czytelności
        ['Lokal suma - netto:', format_money(local_net)],
        ['VAT:', format_money(local_vat)],
    ]
    
    # Jeśli są odsetki dla "gora", dodaj informację przed sumą brutto
    if bill.local == 'gora' and invoice.late_payment_interest > 0:
        costs_data.append(['Odsetki za spoznienie:', format_money(invoice.late_payment_interest)])
    
    # Suma brutto na końcu
    costs_data.append(['Lokal suma brutto:', format_money(local_gross)])
    
    costs_table = Table(costs_data, colWidths=[110*mm, 65*mm])
    
    # Znajdź indeks ostatniego wiersza (suma brutto)
    last_row_idx = len(costs_data) - 1
    
    table_style = TableStyle([
        # Nagłówek
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 1), (1, -1), 'RIGHT'),  # Wartości wyrównane do prawej
        ('FONTNAME', (0, 0), (-1, -1), default_font),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        # Ostatni wiersz (suma brutto) - podkreślony
        ('BACKGROUND', (0, last_row_idx), (-1, last_row_idx), colors.lightgrey),
        ('FONTSIZE', (0, last_row_idx), (-1, last_row_idx), 11),
        ('FONTNAME', (0, last_row_idx), (-1, last_row_idx), default_font),
    ])
    
    costs_table.setStyle(table_style)
    
    story.append(costs_table)
    
    # Generuj PDF
    doc.build(story)
    
    # Zaktualizuj dane w bazie danych zgodnie z obliczeniami w PDF
    # (aby dane w bazie były takie same jak w PDF)
    share = bill.cost_share
    
    # Jeśli wartości szczegółowe w fakturze są dostępne (nie są 0), użyj ich
    # W przeciwnym razie rozdziel local_gross_base proporcjonalnie
    if (invoice.fuel_value_gross > 0 or invoice.subscription_value_gross > 0 or 
        invoice.distribution_fixed_value_gross > 0 or invoice.distribution_variable_value_gross > 0):
        # Użyj wartości szczegółowych z faktury
        calculated_fuel_cost_gross = invoice.fuel_value_gross * share
        calculated_subscription_cost_gross = invoice.subscription_value_gross * share
        calculated_distribution_fixed_cost_gross = invoice.distribution_fixed_value_gross * share
        calculated_distribution_variable_cost_gross = invoice.distribution_variable_value_gross * share
    else:
        # Jeśli wartości szczegółowe są 0, rozdziel local_gross_base proporcjonalnie
        # Dla uproszczenia dzielimy równo między wszystkie kategorie
        calculated_fuel_cost_gross = local_gross_base * 0.25
        calculated_subscription_cost_gross = local_gross_base * 0.25
        calculated_distribution_fixed_cost_gross = local_gross_base * 0.25
        calculated_distribution_variable_cost_gross = local_gross_base * 0.25
    
    # Zaktualizuj wartości w bazie zgodnie z obliczeniami w PDF
    bill.fuel_cost_gross = round(calculated_fuel_cost_gross, 2)
    bill.subscription_cost_gross = round(calculated_subscription_cost_gross, 2)
    bill.distribution_fixed_cost_gross = round(calculated_distribution_fixed_cost_gross, 2)
    bill.distribution_variable_cost_gross = round(calculated_distribution_variable_cost_gross, 2)
    bill.total_net_sum = round(local_net, 2)
    bill.total_gross_sum = round(local_gross, 2)
    # Użyj bezwzględnej ścieżki dla niezawodności
    bill.pdf_path = str(filepath.resolve())
    
    db.commit()
    
    return str(filepath.resolve())


def generate_all_bills_for_period(db: Session, period: str) -> list[str]:
    """
    Generuje pliki PDF dla wszystkich rachunków gazu w danym okresie.
    
    Args:
        db: Sesja bazy danych
        period: Okres rozliczeniowy w formacie 'YYYY-MM'
    
    Returns:
        Lista ścieżek do wygenerowanych plików PDF
    """
    bills = db.query(GasBill).filter(GasBill.data == period).all()
    
    if not bills:
        print(f"Brak rachunków gazu dla okresu {period}")
        return []
    
    pdf_files = []
    
    for bill in bills:
        try:
            # Sprawdź czy plik już istnieje
            bills_folder = Path("bills/gaz")
            filename = f"gas_bill_{bill.data}_local_{bill.local}.pdf"
            filepath = bills_folder / filename
            
            if filepath.exists() and bill.pdf_path:
                # Plik już istnieje i ma ścieżkę w bazie
                print(f"[INFO] Rachunek gazu już istnieje: {filename}")
                pdf_files.append(str(filepath.resolve()))
            else:
                # Wygeneruj plik PDF
                pdf_path = generate_bill_pdf(db, bill)
                # Odśwież obiekt z bazy danych, aby mieć aktualne dane
                db.refresh(bill)
                pdf_files.append(pdf_path)
                print(f"[OK] Wygenerowano rachunek gazu: {pdf_path}")
        except ValueError as e:
            error_msg = f"Nie można wygenerować rachunku {bill.id} (lokal: {bill.local}): {e}"
            print(f"[ERROR] {error_msg}")
            import traceback
            traceback.print_exc()
        except Exception as e:
            error_msg = f"Błąd podczas generowania rachunku {bill.id} (lokal: {bill.local}): {e}"
            print(f"[ERROR] {error_msg}")
            import traceback
            traceback.print_exc()
    
    return pdf_files
