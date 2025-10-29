"""
Moduł generowania rachunków PDF dla lokali.
Tworzy pliki PDF z rachunkami w folderze bills/.
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
from models import Bill, Local


def format_money(value: float) -> str:
    """Formatuje kwotę do wyświetlenia."""
    return f"{value:.2f} zł"


def format_usage(value: float) -> str:
    """Formatuje zużycie do wyświetlenia."""
    return f"{value:.2f} m³"


def generate_bill_pdf(db: Session, bill: Bill) -> str:
    """
    Generuje plik PDF z rachunkiem.
    
    Args:
        db: Sesja bazy danych
        bill: Rachunek do wygenerowania
    
    Returns:
        Ścieżka do wygenerowanego pliku PDF
    """
    # Ustal ścieżkę pliku
    bills_folder = Path("bills")
    bills_folder.mkdir(exist_ok=True)
    
    # Nazwa pliku: bill_2025_02_local_gora.pdf
    filename = f"bill_{bill.data}_local_{bill.local}.pdf"
    filepath = bills_folder / filename
    
    # Sprawdź czy font DejaVuSans jest dostępny (dla polskich znaków)
    try:
        from reportlab.pdfbase.ttf import TTFont  # type: ignore
        import platform
        
        font_registered = False
        if platform.system() == 'Windows':
            # W Windows, sprawdź standardowe lokalizacje
            font_paths = [
                ('C:/Windows/Fonts/dejavu/DejaVuSans.ttf', 'C:/Windows/Fonts/dejavu/DejaVuSans-Bold.ttf'),
                ('C:/Windows/Fonts/DejaVuSans.ttf', 'C:/Windows/Fonts/DejaVuSans-Bold.ttf'),
            ]
        else:
            font_paths = [
                ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'),
            ]
        
        for regular_path, bold_path in font_paths:
            try:
                if Path(regular_path).exists() and Path(bold_path).exists():
                    pdfmetrics.registerFont(TTFont('DejaVuSans', regular_path))
                    pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', bold_path))
                    font_registered = True
                    break
            except:
                continue
        default_font = 'DejaVuSans' if font_registered else 'Helvetica'
        default_font_bold = 'DejaVuSans-Bold' if font_registered else 'Helvetica-Bold'
    except Exception:
        # Jeśli font nie jest dostępny, użyj domyślnego Helvetica
        default_font = 'Helvetica'
        default_font_bold = 'Helvetica-Bold'
    
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
                # Oblicz pozycję uwzględniając marginesy
                right_margin = 15*mm  # Zgodnie z rightMargin w CustomDocTemplate
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
    
    # Użyj fontu z polskimi znakami jeśli dostępny
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.HexColor('#1a5490'),
        spaceAfter=6*mm,
        alignment=TA_CENTER,
        fontName=default_font_bold
    )
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=11,
        textColor=colors.HexColor('#2c5aa0'),
        spaceBefore=5*mm,
        spaceAfter=3*mm,
        fontName=default_font_bold
    )
    
    story = []
    
    # Tytuł (bez polskich liter)
    story.append(Paragraph("RACHUNEK ZA WODE I SCIEKI", title_style))
    
    # Dane lokalu
    local_obj = db.query(Local).filter(Local.local == bill.local).first()
    
    # Okres rozliczeniowy - pobierz z faktury
    period_text = bill.data
    if bill.invoice and bill.invoice.period_start and bill.invoice.period_stop:
        period_start = bill.invoice.period_start.strftime('%d.%m.%Y')
        period_stop = bill.invoice.period_stop.strftime('%d.%m.%Y')
        period_text = f"{period_start} - {period_stop}"
    
    data = [
        ['Okres rozliczeniowy:', period_text],
        ['Lokal:', bill.local],
        ['Najemca:', local_obj.tenant if local_obj else '-'],
    ]
    
    table = Table(data, colWidths=[50*mm, 120*mm])
    table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), default_font_bold),
        ('FONTNAME', (1, 0), (-1, -1), default_font),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    
    story.append(table)
    story.append(Spacer(1, 5*mm))
    
    # Koszty - przestrukturyzowana tabela
    story.append(Paragraph("<b>ROZLICZENIE KOSZTOW</b>", heading_style))
    
    if bill.invoice:
        invoice = bill.invoice
        # Oblicz całkowitą kwotę abonamentu (łącznie dla wszystkich lokali)
        # Abonament z faktury to: water_subscr_cost * nr_of_subscription (łącznie dla wszystkich lokali)
        total_abonament_water = invoice.water_subscr_cost * invoice.nr_of_subscription
        total_abonament_sewage = invoice.sewage_subscr_cost * invoice.nr_of_subscription
        
        costs_data = [
            ['', 'Zuzycie', 'Cena jednostkowa', 'Laczny koszt'],
            ['Woda:', format_usage(bill.usage_m3), format_money(invoice.water_cost_m3), format_money(bill.cost_water)],
            ['Scieki:', format_usage(bill.usage_m3), format_money(invoice.sewage_cost_m3), format_money(bill.cost_sewage)],
            ['Koszt zuzycia woda/scieki lacznie', '', '', format_money(bill.cost_usage_total)],
            ['Woda abonament', '1/3', format_money(total_abonament_water), format_money(bill.abonament_water_share)],
            ['Scieki abonament', '1/3', format_money(total_abonament_sewage), format_money(bill.abonament_sewage_share)],
            ['Abonament lacznie', '', '', format_money(bill.abonament_total)],
        ]
    else:
        costs_data = [
            ['', 'Zuzycie', 'Cena jednostkowa', 'Laczny koszt'],
            ['Woda:', format_usage(bill.usage_m3), '', format_money(bill.cost_water)],
            ['Scieki:', format_usage(bill.usage_m3), '', format_money(bill.cost_sewage)],
            ['Koszt zuzycia woda/scieki lacznie', '', '', format_money(bill.cost_usage_total)],
            ['Abonament', '', '', format_money(bill.abonament_total)],
        ]
    
    costs_table = Table(costs_data, colWidths=[60*mm, 30*mm, 40*mm, 40*mm])
    costs_table.setStyle(TableStyle([
        # Nagłówek
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (2, 1), (3, -1), 'RIGHT'),  # Cena i koszt wyrównane do prawej
        ('FONTNAME', (0, 0), (-1, 0), default_font_bold),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        # Wiersze sum
        ('FONTNAME', (0, 3), (-1, -1), default_font_bold),
        ('ROWBACKGROUNDS', (0, 3), (-1, 3), [colors.lightgrey]),
        ('ROWBACKGROUNDS', (0, 6), (-1, 6), [colors.lightgrey]),
    ]))
    
    story.append(costs_table)
    story.append(Spacer(1, 5*mm))
    
    # Podsumowanie (zamiast SUMA KOŃCOWA)
    story.append(Paragraph("<b>PODSUMOWANIE</b>", heading_style))
    
    total_data = [
        ['Netto Lacznie:', format_money(bill.net_sum)],
        ['VAT:', '8%'],
        ['Calosc brutto:', format_money(bill.gross_sum)],
    ]
    
    total_table = Table(total_data, colWidths=[50*mm, 80*mm])
    total_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, 2), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, -1), default_font_bold),
        ('FONTSIZE', (0, 2), (-1, 2), 11),
        ('FONTSIZE', (0, 0), (-1, 1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 2), (-1, 2), colors.lightgrey),
    ]))
    
    story.append(total_table)
    
    # Generuj PDF - "Wygenerowano" jest dodawane w CustomDocTemplate
    doc.build(story)
    
    return str(filepath)


def generate_all_bills_for_period(db: Session, period: str) -> list[str]:
    """
    Generuje wszystkie rachunki PDF dla danego okresu.
    
    Args:
        db: Sesja bazy danych
        period: Okres rozliczeniowy
    
    Returns:
        Lista ścieżek do wygenerowanych plików
    """
    bills = db.query(Bill).filter(Bill.data == period).all()
    
    if not bills:
        print(f"Brak rachunków dla okresu {period}")
        return []
    
    generated_files = []
    
    for bill in bills:
        # Sprawdź czy plik już istnieje
        bills_folder = Path("bills")
        filename = f"bill_{bill.data}_local_{bill.local}.pdf"
        filepath = bills_folder / filename
        
        if filepath.exists():
            print(f"Rachunek już istnieje: {filename}")
        else:
            pdf_path = generate_bill_pdf(db, bill)
            
            # Zaktualizuj ścieżkę w bazie
            bill.pdf_path = pdf_path
            db.commit()
            
            print(f"[OK] Wygenerowano: {filename}")
        
        generated_files.append(str(filepath))
    
    return generated_files


if __name__ == "__main__":
    from db import SessionLocal
    from models import Bill
    
    db = SessionLocal()
    try:
        bills = db.query(Bill).all()
        print(f"Znaleziono {len(bills)} rachunków")
        
        for bill in bills:
            if not bill.pdf_path:
                generate_bill_pdf(db, bill)
                print(f"Wygenerowano rachunek dla {bill.local}")
    finally:
        db.close()

