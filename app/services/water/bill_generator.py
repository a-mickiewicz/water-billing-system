
"""
PDF bill generation module for units.
Creates PDF files with bills in bills/ folder.
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
from app.models.water import Bill, Local


def format_money(value: float) -> str:
    """Formats amount for display."""
    return f"{value:.2f} zł"


def format_usage(value: float) -> str:
    """Formats consumption for display."""
    return f"{value:.2f} m³"


def generate_bill_pdf(db: Session, bill: Bill) -> str:
    """
    Generates PDF file with bill.
    
    Args:
        db: Database session
        bill: Bill to generate
    
    Returns:
        Path to generated PDF file
    """
    # Determine file path
    bills_folder = Path("bills/woda")
    bills_folder.mkdir(parents=True, exist_ok=True)
    
    # Filename: bill_2025_02_local_gora.pdf
    filename = f"bill_{bill.data}_local_{bill.local}.pdf"
    filepath = bills_folder / filename
    
    # Check if Arial font is available (for Polish characters)
    try:
        from reportlab.pdfbase.ttfonts import TTFont  # type: ignore
        import platform
        
        font_registered = False
        if platform.system() == 'Windows':
            # On Windows, check standard Arial locations
            font_paths = [
                'C:/Windows/Fonts/arial.ttf',
                'C:/Windows/Fonts/Arial.ttf',
                Path('C:/Windows/Fonts/arial.ttf'),  # Try also as Path
            ]
        else:
            # On other systems try standard locations
            font_paths = [
                '/usr/share/fonts/truetype/msttcorefonts/arial.ttf',
                '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
            ]
        
        for font_path in font_paths:
            try:
                font_path_str = str(font_path)
                if Path(font_path_str).exists():
                    pdfmetrics.registerFont(TTFont('Arial', font_path_str))
                    # Check if font was registered
                    if 'Arial' in pdfmetrics.getRegisteredFontNames():
                        font_registered = True
                        print(f"[OK] Registered Arial font from: {font_path_str}")
                        break
            except Exception as e:
                print(f"[DEBUG] Failed to register font from {font_path}: {e}")
                continue
        
        if not font_registered:
            print("[WARNING] Arial font not found, using Helvetica (may lack Polish characters)")
        default_font = 'Arial' if font_registered else 'Helvetica'
    except Exception as e:
        # If font is not available, use default Helvetica
        print(f"[WARNING] Font registration error: {e}, using Helvetica")
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
    
    # Tytuł (bez polskich liter)
    story.append(Paragraph("RACHUNEK ZA WODE I SCIEKI", title_style))
    story.append(Paragraph("NA PODSTAWIE FAKTUR (W ZAŁĄCZNIKU)", heading_style))
    # Dane lokalu
    local_obj = db.query(Local).filter(Local.local == bill.local).first()
    
    # Okres rozliczeniowy - pobierz z faktury
    period_text = bill.data
    if bill.invoice and bill.invoice.period_start and bill.invoice.period_stop:
        period_start = bill.invoice.period_start.strftime('%d.%m.%Y')
        period_stop = bill.invoice.period_stop.strftime('%d.%m.%Y')
        period_text = f"{period_start} - {period_stop}"
    
    # Oblicz całkowite zużycie dla domu (suma wszystkich lokali w tym okresie)
    all_bills_for_period = db.query(Bill).filter(Bill.data == bill.data).all()
    total_house_usage = sum(b.usage_m3 for b in all_bills_for_period)
    
    data = [
        ['Okres rozliczeniowy:', period_text],
        ['Zuzycie dom:', f"{total_house_usage:.2f} m3"],
        ['Lokal:', bill.local],
        ['Najemca:', local_obj.tenant if local_obj else '-'],
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
    
    # Koszty - przestrukturyzowana tabela
    story.append(Paragraph("ROZLICZENIE KOSZTOW", heading_style))
    
    if bill.invoice:
        invoice = bill.invoice
        # Oblicz całkowitą kwotę abonamentu (łącznie dla wszystkich lokali)
        # IMPORTANT: water_subscr_cost and sewage_subscr_cost are already TOTAL sums from all positions
        # (each position: quantity × price, then all positions are summed)
        # We do NOT multiply by nr_of_subscription - it's already the total sum!
        total_abonament_water = invoice.water_subscr_cost
        total_abonament_sewage = invoice.sewage_subscr_cost
        
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
            ['', 'Zużycie', 'Cena jednostkowa', 'Łączny koszt'],
            ['Woda:', format_usage(bill.usage_m3), '', format_money(bill.cost_water)],
            ['Scieki:', format_usage(bill.usage_m3), '', format_money(bill.cost_sewage)],
            ['Koszt zuzycia woda/scieki lacznie', '', '', format_money(bill.cost_usage_total)],
            ['Abonament', '', '', format_money(bill.abonament_total)],
        ]
    
    costs_table = Table(costs_data, colWidths=[60*mm, 30*mm, 40*mm, 30*mm])
    costs_table.setStyle(TableStyle([
        # Nagłówek
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (2, 1), (3, -1), 'RIGHT'),  # Cena i koszt wyrównane do prawej
        ('FONTNAME', (0, 0), (-1, -1), default_font),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        # Wiersze sum
        ('ROWBACKGROUNDS', (0, 3), (-1, 3), [colors.lightgrey]),
        ('ROWBACKGROUNDS', (0, 6), (-1, 6), [colors.lightgrey]),
    ]))
    
    story.append(costs_table)
    story.append(Spacer(1, 5*mm))
    
    # Podsumowanie (zamiast SUMA KOŃCOWA)
    story.append(Paragraph("PODSUMOWANIE", heading_style))
    
    total_data = [
        ['Netto Lacznie:', format_money(bill.net_sum)],
        ['VAT:', '8%'],
        ['Calosc brutto:', format_money(bill.gross_sum)],
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
        bills_folder = Path("bills/woda")
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


def generate_all_possible_bills(db: Session) -> dict:
    """
    Generuje wszystkie możliwe rachunki dla wszystkich okresów,
    które mają faktury i odczyty.
    
    Args:
        db: Sesja bazy danych
    
    Returns:
        Słownik ze statystykami generowania
    """
    from app.models.water import Invoice, Reading
    from app.services.water.meter_manager import generate_bills_for_period
    from sqlalchemy import distinct
    
    # Pobierz wszystkie okresy z faktur
    periods_with_invoices = db.query(distinct(Invoice.data)).all()
    periods_with_invoices = [p[0] for p in periods_with_invoices]
    
    # Pobierz okresy z odczytów
    periods_with_readings = db.query(distinct(Reading.data)).all()
    periods_with_readings = [p[0] for p in periods_with_readings]
    
    # Okresy które mają zarówno faktury jak i odczyty
    valid_periods = [p for p in periods_with_invoices if p in periods_with_readings]
    
    if not valid_periods:
        return {
            "message": "Brak okresów z fakturami i odczytami",
            "periods_processed": 0,
            "bills_generated": 0,
            "pdfs_generated": 0,
            "errors": []
        }
    
    bills_generated_count = 0
    pdfs_generated_count = 0
    errors = []
    processed_periods = []
    
    # Dla każdego okresu, sprawdź czy są rachunki, jeśli nie - wygeneruj
    for period in sorted(valid_periods):
        try:
            existing_bills = db.query(Bill).filter(Bill.data == period).first()
            
            if not existing_bills:
                # Wygeneruj rachunki dla tego okresu
                try:
                    bills = generate_bills_for_period(db, period)
                    bills_generated_count += len(bills)
                    print(f"[OK] Wygenerowano {len(bills)} rachunków dla okresu {period}")
                    processed_periods.append(period)
                except Exception as e:
                    error_msg = f"Błąd generowania rachunków dla {period}: {str(e)}"
                    errors.append(error_msg)
                    print(f"[ERROR] {error_msg}")
                    continue
        except Exception as e:
            error_msg = f"Błąd sprawdzania rachunków dla {period}: {str(e)}"
            errors.append(error_msg)
            print(f"[ERROR] {error_msg}")
            continue
    
    # Teraz wygeneruj PDF dla wszystkich rachunków bez PDF
    all_bills = db.query(Bill).all()
    for bill in all_bills:
        if not bill.pdf_path:
            try:
                bills_folder = Path("bills")
                filename = f"bill_{bill.data}_local_{bill.local}.pdf"
                filepath = bills_folder / filename
                
                if not filepath.exists():
                    pdf_path = generate_bill_pdf(db, bill)
                    bill.pdf_path = pdf_path
                    db.commit()
                    pdfs_generated_count += 1
                    print(f"[OK] Wygenerowano PDF: {filename}")
            except Exception as e:
                error_msg = f"Błąd generowania PDF dla rachunku {bill.id} ({bill.data}, {bill.local}): {str(e)}"
                errors.append(error_msg)
                print(f"[ERROR] {error_msg}")
    
    return {
        "message": "Zakończono generowanie wszystkich możliwych rachunków",
        "valid_periods": len(valid_periods),
        "periods_processed": len(processed_periods),
        "bills_generated": bills_generated_count,
        "pdfs_generated": pdfs_generated_count,
        "processed_periods": processed_periods,
        "errors": errors
    }


if __name__ == "__main__":
    from db import SessionLocal
    
    db = SessionLocal()
    try:
        print("=" * 50)
        print("Generowanie wszystkich możliwych rachunków...")
        print("=" * 50)
        
        result = generate_all_possible_bills(db)
        
        print("\n" + "=" * 50)
        print("PODSUMOWANIE:")
        print("=" * 50)
        print(f"Znaleziono okresów: {result['valid_periods']}")
        print(f"Przetworzono okresów: {result['periods_processed']}")
        print(f"Wygenerowano rachunków: {result['bills_generated']}")
        print(f"Wygenerowano plików PDF: {result['pdfs_generated']}")
        
        if result['processed_periods']:
            print(f"\nPrzetworzone okresy: {', '.join(result['processed_periods'])}")
        
        if result['errors']:
            print(f"\n⚠️  Błędy ({len(result['errors'])}):")
            for error in result['errors']:
                print(f"  - {error}")
        else:
            print("\n✓ Wszystko zakończone pomyślnie!")
    finally:
        db.close()

