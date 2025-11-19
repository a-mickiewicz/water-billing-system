"""
Generowanie rachunków PDF dla lokali za prąd.
"""

from pathlib import Path
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.pdfbase import pdfmetrics
from sqlalchemy.orm import Session
from app.models.electricity import ElectricityBill
from app.models.water import Local


def format_money(value: float) -> str:
    """Formats amount for display."""
    return f"{value:.2f} zł"


def format_usage(value: float) -> str:
    """Formats consumption for display."""
    return f"{value:.2f} kWh"


def generate_bill_pdf(db: Session, bill: ElectricityBill) -> str:
    """
    Generuje plik PDF rachunku za prąd dla lokalu.
    
    Args:
        db: Sesja bazy danych
        bill: Rachunek prądu
    
    Returns:
        Ścieżka do wygenerowanego pliku PDF
    
    Raises:
        ValueError: Jeśli faktura nie jest przypisana
    """
    # Pobierz fakturę
    invoice = bill.invoice
    if not invoice:
        raise ValueError(f"Rachunek {bill.id} nie ma przypisanej faktury")
    
    # Utwórz folder dla rachunków prądu
    bills_folder = Path("bills/prad")
    bills_folder.mkdir(parents=True, exist_ok=True)
    
    # Nazwa pliku: electricity_bill_2024_10_local_gora.pdf
    filename = f"electricity_bill_{bill.data}_local_{bill.local}.pdf"
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
    story.append(Paragraph("RACHUNEK ZA PRAD", title_style))
    story.append(Paragraph("NA PODSTAWIE FAKTUR (W ZALACZNIKU)", heading_style))
    
    # Dane lokalu
    local_obj = db.query(Local).filter(Local.local == bill.local).first()
    
    # Okres rozliczeniowy
    period_text = bill.data
    if invoice.data_poczatku_okresu and invoice.data_konca_okresu:
        period_start = invoice.data_poczatku_okresu.strftime('%d.%m.%Y')
        period_stop = invoice.data_konca_okresu.strftime('%d.%m.%Y')
        period_text = f"{period_start} - {period_stop}"
    
    # Oblicz całkowite zużycie dla domu (suma wszystkich lokali w tym okresie)
    from app.models.electricity import ElectricityBill as EB
    all_bills_for_period = db.query(EB).filter(EB.data == bill.data).all()
    total_house_usage = sum(b.usage_kwh for b in all_bills_for_period if b.local != 'dom')
    
    data = [
        ['Okres rozliczeniowy:', period_text],
        ['Zuzycie dom:', f"{total_house_usage:.2f} kWh"],
        ['Lokal:', bill.local],
        ['Najemca:', local_obj.tenant if local_obj else '-'],
        ['Numer faktury:', invoice.numer_faktury],
        ['Typ taryfy:', invoice.typ_taryfy],
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
    
    # Zużycie energii
    story.append(Paragraph("ZUZYCIE ENERGII", heading_style))
    
    usage_data = [
        ['', 'Zuzycie (kWh)'],
        ['Zuzycie lacznie:', format_usage(bill.usage_kwh)],
    ]
    
    if bill.usage_kwh_dzienna is not None:
        usage_data.append(['Zuzycie dzienna (I):', format_usage(bill.usage_kwh_dzienna)])
    if bill.usage_kwh_nocna is not None:
        usage_data.append(['Zuzycie nocna (II):', format_usage(bill.usage_kwh_nocna)])
    
    usage_table = Table(usage_data, colWidths=[100*mm, 75*mm])
    usage_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, -1), default_font),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
    ]))
    
    story.append(usage_table)
    story.append(Spacer(1, 5*mm))
    
    # Rozliczenie kosztów
    story.append(Paragraph("ROZLICZENIE KOSZTOW", heading_style))
    
    # Oblicz koszt netto z brutto (zakładając VAT 23%)
    vat_rate = 0.23
    energy_cost_net = bill.energy_cost_gross / (1 + vat_rate)
    distribution_cost_net = bill.distribution_cost_gross / (1 + vat_rate)
    
    # Oblicz opłaty stałe (z total_gross_sum - energy_cost_gross - distribution_cost_gross)
    fixed_fees_gross = bill.total_gross_sum - bill.energy_cost_gross - bill.distribution_cost_gross
    fixed_fees_net = fixed_fees_gross / (1 + vat_rate)
    
    costs_data = [
        ['', 'Netto', 'VAT 23%', 'Brutto'],
        ['Energia elektryczna:', format_money(energy_cost_net), format_money(energy_cost_net * vat_rate), format_money(bill.energy_cost_gross)],
        ['Usluga dystrybucji:', format_money(distribution_cost_net), format_money(distribution_cost_net * vat_rate), format_money(bill.distribution_cost_gross)],
        ['Oplaty stale:', format_money(fixed_fees_net), format_money(fixed_fees_gross - fixed_fees_net), format_money(fixed_fees_gross)],
        ['RAZEM:', format_money(bill.total_net_sum), format_money(bill.total_gross_sum - bill.total_net_sum), format_money(bill.total_gross_sum)],
    ]
    
    costs_table = Table(costs_data, colWidths=[60*mm, 40*mm, 40*mm, 40*mm])
    costs_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, -1), default_font),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('FONTSIZE', (0, 4), (-1, 4), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ROWBACKGROUNDS', (0, 4), (-1, 4), [colors.lightgrey]),
    ]))
    
    story.append(costs_table)
    story.append(Spacer(1, 5*mm))
    
    # Podsumowanie
    story.append(Paragraph("PODSUMOWANIE", heading_style))
    
    total_data = [
        ['Netto lacznie:', format_money(bill.total_net_sum)],
        ['VAT:', '23%'],
        ['Calosc brutto:', format_money(bill.total_gross_sum)],
    ]
    
    total_table = Table(total_data, colWidths=[60*mm, 100*mm])
    total_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, 2), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, -1), default_font),
        ('FONTSIZE', (0, 2), (-1, 2), 11),
        ('FONTSIZE', (0, 0), (-1, 1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 2), (-1, 2), colors.lightgrey),
    ]))
    
    story.append(total_table)
    
    # Generuj PDF
    doc.build(story)
    
    return str(filepath)
