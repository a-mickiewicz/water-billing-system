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
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
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
    
    # Stwórz dokument
    doc = SimpleDocTemplate(str(filepath), pagesize=A4)
    
    # Style
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#1a5490'),
        spaceAfter=30,
        alignment=TA_CENTER
    )
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=12,
        textColor=colors.HexColor('#2c5aa0'),
        spaceBefore=10,
        spaceAfter=5
    )
    
    story = []
    
    # Tytuł
    story.append(Paragraph("RACHUNEK ZA WODĘ I ŚCIEKI", title_style))
    story.append(Spacer(1, 10*mm))
    
    # Dane lokalu
    local_obj = db.query(Local).filter(Local.local == bill.local).first()
    
    data = [
        ['Okres rozliczeniowy:', bill.data],
        ['Lokal:', bill.local],
        ['Najemca:', local_obj.tenant if local_obj else '-'],
        ['Licznik:', bill.reading_value, 'm³'],
    ]
    
    table = Table(data, colWidths=[60*mm, 80*mm, 30*mm])
    table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
    ]))
    
    story.append(table)
    story.append(Spacer(1, 15*mm))
    
    # Zużycie
    story.append(Paragraph("<b>ZUŻYCIE</b>", heading_style))
    
    usage_data = [
        ['Stan obecny:', format_usage(bill.reading_value)],
        ['Zużycie:', format_usage(bill.usage_m3)],
    ]
    
    usage_table = Table(usage_data, colWidths=[80*mm, 50*mm])
    usage_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
    ]))
    
    story.append(usage_table)
    story.append(Spacer(1, 15*mm))
    
    # Koszty
    story.append(Paragraph("<b>ROZLICZENIE KOSZTÓW</b>", heading_style))
    
    if bill.invoice:
        invoice = bill.invoice
        costs_data = [
            ['', 'Cena jednostkowa', 'Zużycie', 'Wartość'],
            ['Woda:', format_money(invoice.water_cost_m3), format_usage(bill.usage_m3), format_money(bill.cost_water)],
            ['Ścieki:', format_money(invoice.sewage_cost_m3), format_usage(bill.usage_m3), format_money(bill.cost_sewage)],
            ['', '', '', ''],
            ['Razem zużycie:', '', '', format_money(bill.cost_usage_total)],
            ['', '', '', ''],
            ['Abonament (woda):', '', '', format_money(bill.abonament_water_share)],
            ['Abonament (ścieki):', '', '', format_money(bill.abonament_sewage_share)],
            ['Razem abonament:', '', '', format_money(bill.abonament_total)],
        ]
    else:
        costs_data = [
            ['Woda:', '', format_usage(bill.usage_m3), format_money(bill.cost_water)],
            ['Ścieki:', '', format_usage(bill.usage_m3), format_money(bill.cost_sewage)],
            ['Razem zużycie:', '', '', format_money(bill.cost_usage_total)],
            ['Abonament:', '', '', format_money(bill.abonament_total)],
        ]
    
    costs_table = Table(costs_data, colWidths=[50*mm, 40*mm, 40*mm, 50*mm])
    costs_table.setStyle(TableStyle([
        # Nagłówek
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (3, 1), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        # Sumy
        ('FONTNAME', (0, 4), (-1, -1), 'Helvetica-Bold'),
    ]))
    
    story.append(costs_table)
    story.append(Spacer(1, 15*mm))
    
    # Suma końcowa
    story.append(Paragraph("<b>SUMA KOŃCOWA</b>", heading_style))
    
    total_data = [
        ['Suma netto:', format_money(bill.net_sum)],
        ['VAT:', '8%'],
        ['Suma brutto:', format_money(bill.gross_sum)],
    ]
    
    total_table = Table(total_data, colWidths=[60*mm, 80*mm])
    total_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 2), (1, 2), 'RIGHT'),
        ('FONTNAME', (0, 2), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 2), (-1, -1), 12),
        ('FONTSIZE', (0, 0), (-1, 1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 2), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 2), (-1, -1), colors.lightgrey),
    ]))
    
    story.append(total_table)
    story.append(Spacer(1, 20*mm))
    
    # Stopka
    now = datetime.now()
    story.append(Paragraph(f"Wygenerowano: {now.strftime('%d.%m.%Y %H:%M')}", styles['Normal']))
    
    # Generuj PDF
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

