"""
Generowanie PDF rachunków łączonych (wszystkie media).
"""

from datetime import datetime, date
from pathlib import Path
from typing import Optional
from sqlalchemy.orm import Session

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from app.models.combined import CombinedBill
from app.models.water import Bill, Invoice as WaterInvoice, Reading as WaterReading
from app.models.gas import GasBill, GasInvoice
from app.models.electricity import ElectricityBill
from app.models.electricity_invoice import ElectricityInvoice
from app.services.electricity.cost_calculator import calculate_kwh_cost
from app.services.electricity.manager import ElectricityBillingManager


def get_font():
    """Pobiera dostępną czcionkę z polskimi znakami."""
    try:
        import platform
        
        font_registered = False
        if platform.system() == 'Windows':
            font_paths = [
                'C:/Windows/Fonts/arial.ttf',
                'C:/Windows/Fonts/Arial.ttf',
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
        
        return 'Arial' if font_registered else 'Helvetica'
    except Exception:
        return 'Helvetica'


def generate_combined_bill_pdf(db: Session, combined_bill: CombinedBill) -> str:
    """
    Generuje plik PDF rachunku łączonego (wszystkie media).
    
    Args:
        db: Sesja bazy danych
        combined_bill: Rachunek łączony
    
    Returns:
        Ścieżka do wygenerowanego pliku PDF
    """
    # Utwórz folder dla rachunków łączonych
    bills_folder = Path("bills/combined")
    bills_folder.mkdir(parents=True, exist_ok=True)
    
    # Nazwa pliku: combined_bill_2025-01_2025-02_local_gora.pdf
    filename = f"combined_bill_{combined_bill.period_start}_{combined_bill.period_end}_local_{combined_bill.local}.pdf"
    filepath = bills_folder / filename
    
    # Pobierz czcionkę
    default_font = get_font()
    
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
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.HexColor('#2c5aa0'),
        spaceAfter=3*mm,
        alignment=1,  # CENTER
        fontName=default_font
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading3'],
        fontSize=12,
        textColor=colors.HexColor('#2c5aa0'),
        spaceBefore=4*mm,
        spaceAfter=2*mm,
        fontName=default_font
    )
    
    subheading_style = ParagraphStyle(
        'CustomSubHeading',
        parent=styles['Heading4'],
        fontSize=11,
        textColor=colors.HexColor('#2c5aa0'),
        spaceBefore=2*mm,
        spaceAfter=1*mm,
        fontName=default_font
    )
    
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=10,
        fontName=default_font
    )
    
    story = []
    
    # Tytuł
    story.append(Paragraph("RACHUNEK ZA MEDIA", title_style))
    story.append(Spacer(1, 2*mm))
    
    # Dane lokalu
    local_obj = combined_bill.local_obj
    period_text = f"{combined_bill.period_start} do {combined_bill.period_end}"
    
    data = [
        ['Lokal:', local_obj.local if local_obj else combined_bill.local],
        ['Rachunek za media za okres:', period_text],
        ['Data wygenerowania:', combined_bill.generated_date.strftime('%d.%m.%Y')],
    ]
    
    table = Table(data, colWidths=[60*mm, 125*mm])
    table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), default_font),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(table)
    story.append(Spacer(1, 5*mm))
    
    # ========== I. PRĄD ==========
    story.append(Paragraph("I. PRĄD", heading_style))
    story.append(Spacer(1, 2*mm))
    
    # Pobierz wszystkie rachunki prądu z obu miesięcy
    from app.models.electricity import ElectricityBill
    electricity_bills = db.query(ElectricityBill).filter(
        ElectricityBill.data.in_([combined_bill.period_start, combined_bill.period_end]),
        ElectricityBill.local == combined_bill.local
    ).all()
    
    if electricity_bills:
        # Sumuj zużycie i koszty z obu miesięcy
        total_usage_kwh = sum(b.usage_kwh for b in electricity_bills)
        total_net = sum(b.total_net_sum for b in electricity_bills)
        total_gross = sum(b.total_gross_sum for b in electricity_bills)
        
        # Użyj pierwszego rachunku do szczegółów (odczyty, faktura)
        electricity_bill = electricity_bills[0]
        # Pobierz odczyt
        reading = electricity_bill.reading
        previous_reading = None
        if reading:
            # Znajdź poprzedni odczyt
            from app.models.electricity import ElectricityReading
            all_readings = db.query(ElectricityReading).order_by(ElectricityReading.data).all()
            for i, r in enumerate(all_readings):
                if r.id == reading.id and i > 0:
                    previous_reading = all_readings[i - 1]
                    break
        
        # Zużycie kWh
        story.append(Paragraph("ZUŻYCIE KWH:", subheading_style))
        
        usage_data = []
        if reading:
            if combined_bill.local == 'gora':
                current_reading = reading.odczyt_gora if hasattr(reading, 'odczyt_gora') else 0
                prev_reading = previous_reading.odczyt_gora if previous_reading and hasattr(previous_reading, 'odczyt_gora') else 0
            elif combined_bill.local == 'dol':
                current_reading = reading.odczyt_dol if hasattr(reading, 'odczyt_dol') else 0
                prev_reading = previous_reading.odczyt_dol if previous_reading and hasattr(previous_reading, 'odczyt_dol') else 0
            else:  # gabinet
                current_reading = reading.odczyt_gabinet if hasattr(reading, 'odczyt_gabinet') else 0
                prev_reading = previous_reading.odczyt_gabinet if previous_reading and hasattr(previous_reading, 'odczyt_gabinet') else 0
            
            usage_data = [
                ['Odczyty licznika:', f"{current_reading:.2f}"],
                ['Poprzedni odczyt:', f"{prev_reading:.2f}"],
                ['Zużycie:', f"{total_usage_kwh:.2f} kWh"],
            ]
        else:
            usage_data = [
                ['Zużycie:', f"{total_usage_kwh:.2f} kWh"],
            ]
        
        usage_table = Table(usage_data, colWidths=[60*mm, 125*mm])
        usage_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), default_font),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))
        story.append(usage_table)
        story.append(Spacer(1, 2*mm))
        
        # 1. Należność za energię czynną, opłata jakościowa, zmienna sieciowa, kogeneracyjna
        story.append(Paragraph("1. NALEŻNOŚĆ ZA ENERGIĘ CZYNNĄ, OPŁATA JAKOŚCIOWA, ZMIENNA SIECIOWA, KOGENERACYJNA - ŁĄCZNIE (PROPORCJONALNIE DO ZUŻYCIA ENERGII)", subheading_style))
        
        # Oblicz koszt 1 kWh
        invoice = electricity_bill.invoice
        if invoice:
            koszty_kwh = calculate_kwh_cost(invoice.id, db)
            
            # Pobierz szczegóły obliczeń
            manager = ElectricityBillingManager()
            from app.services.electricity.calculator import calculate_all_usage
            if reading and previous_reading:
                usage_data_dict = calculate_all_usage(reading, previous_reading)
            else:
                usage_data_dict = {}
            
            # Oblicz szczegóły dla lokalu
            if combined_bill.local == 'gora':
                local_usage = usage_data_dict.get('gora', {}).get('zuzycie_gora_lacznie', total_usage_kwh)
            elif combined_bill.local == 'dol':
                local_usage = usage_data_dict.get('dol', {}).get('zuzycie_dol_lacznie', total_usage_kwh)
            else:
                local_usage = usage_data_dict.get('gabinet', {}).get('zuzycie_gabinet', total_usage_kwh)
            
            # Oblicz koszt za 1 kWh (średnia ważona dla dwutaryfowej lub całodobowa)
            if invoice.typ_taryfy == "DWUTARYFOWA" and "DZIENNA" in koszty_kwh and "NOCNA" in koszty_kwh:
                koszt_dzienna = koszty_kwh["DZIENNA"].get("suma", 0)
                koszt_nocna = koszty_kwh["NOCNA"].get("suma", 0)
                cena_1kwh = round(koszt_dzienna * 0.7 + koszt_nocna * 0.3, 4)
                obliczenia_text = f"Średnia ważona: {koszt_dzienna:.4f} × 0.7 + {koszt_nocna:.4f} × 0.3 = {cena_1kwh:.4f} zł/kWh"
            elif "CAŁODOBOWA" in koszty_kwh:
                cena_1kwh = koszty_kwh["CAŁODOBOWA"].get("suma", 0)
                obliczenia_text = f"Cena całodobowa: {cena_1kwh:.4f} zł/kWh"
            else:
                cena_1kwh = 0
                obliczenia_text = "Brak danych"
            
            energy_cost_details = [
                ['Zużycie prądu:', f"{electricity_bill.usage_kwh:.2f} kWh"],
                ['Cena za 1 kWh (obliczana z pokrywania się okresów faktury i okresów rozliczeniowych):', f"{cena_1kwh:.4f} zł/kWh"],
                ['Obliczenia:', obliczenia_text],
            ]
        else:
            energy_cost_details = [
                ['Zużycie prądu:', f"{electricity_bill.usage_kwh:.2f} kWh"],
                ['Cena za 1 kWh:', "Brak danych"],
            ]
        
        energy_table = Table(energy_cost_details, colWidths=[100*mm, 85*mm])
        energy_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), default_font),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        story.append(energy_table)
        story.append(Spacer(1, 2*mm))
        
        # 2. Opłata stała sieciowa, abonamentowa, przejściowa
        story.append(Paragraph("2. OPŁATA STAŁA SIECIOWA, ABONAMENTOWA, PRZEJŚCIOWA (OBLICZANA Z POKRYWANIA SIĘ OKRESÓW FAKTURY I OKRESÓW ROZLICZENIOWYCH)", subheading_style))
        story.append(Paragraph("Opłaty stałe są już uwzględnione w kosztach dystrybucji.", normal_style))
        story.append(Spacer(1, 2*mm))
        
        # 3. Koszty łącznie
        story.append(Paragraph("3. KOSZTY ŁĄCZNIE (1.+2.):", subheading_style))
        costs_table = Table([
            ['Netto:', f"{total_net:.2f} zł"],
            ['Brutto:', f"{total_gross:.2f} zł"],
        ], colWidths=[60*mm, 125*mm])
        costs_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), default_font),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))
        story.append(costs_table)
    else:
        story.append(Paragraph("Brak danych o rachunku za prąd", normal_style))
    
    story.append(Spacer(1, 5*mm))
    
    # ========== II. WODA I ŚCIEKI ==========
    story.append(Paragraph("II. WODA I ŚCIEKI", heading_style))
    story.append(Spacer(1, 2*mm))
    
    # Pobierz wszystkie rachunki wody z obu miesięcy
    from app.models.water import Bill
    water_bills = db.query(Bill).filter(
        Bill.data.in_([combined_bill.period_start, combined_bill.period_end]),
        Bill.local == combined_bill.local
    ).all()
    
    if water_bills:
        # Sumuj zużycie i koszty z obu miesięcy
        total_usage_m3 = sum(b.usage_m3 for b in water_bills)
        total_net = sum(b.net_sum for b in water_bills)
        total_gross = sum(b.gross_sum for b in water_bills)
        total_cost_water = sum(b.cost_water for b in water_bills)
        total_cost_sewage = sum(b.cost_sewage for b in water_bills)
        total_abonament_water = sum(b.abonament_water_share for b in water_bills)
        total_abonament_sewage = sum(b.abonament_sewage_share for b in water_bills)
        
        # Użyj pierwszego rachunku do szczegółów (odczyty, faktura)
        water_bill = water_bills[0]
        # Odczyty
        reading = water_bill.reading
        previous_reading = None
        if reading:
            from app.models.water import Reading
            all_readings = db.query(Reading).order_by(Reading.data).all()
            for i, r in enumerate(all_readings):
                if r.data == reading.data and i > 0:
                    previous_reading = all_readings[i - 1]
                    break
        
        reading_data = []
        if reading and previous_reading:
            if combined_bill.local == 'gora':
                current_reading = reading.water_meter_5
                prev_reading = previous_reading.water_meter_5
            elif combined_bill.local == 'gabinet':
                current_reading = reading.water_meter_5a
                prev_reading = previous_reading.water_meter_5a
            else:  # dol
                current_reading = reading.water_meter_main - (reading.water_meter_5 + reading.water_meter_5a)
                prev_reading = previous_reading.water_meter_main - (previous_reading.water_meter_5 + previous_reading.water_meter_5a)
            
            reading_data = [
                ['Odczyty licznika:', f"{current_reading:.2f} m³"],
                ['Poprzedni odczyt:', f"{prev_reading:.2f} m³"],
                ['Zużycie:', f"{total_usage_m3:.2f} m³"],
            ]
        else:
            reading_data = [
                ['Zużycie:', f"{total_usage_m3:.2f} m³"],
            ]
        
        reading_table = Table(reading_data, colWidths=[60*mm, 125*mm])
        reading_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), default_font),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))
        story.append(reading_table)
        story.append(Spacer(1, 2*mm))
        
        # 1. Woda
        story.append(Paragraph("1. WODA", subheading_style))
        invoice = water_bill.invoice
        if invoice:
            water_details = [
                ['Zużycie:', f"{total_usage_m3:.2f} m³"],
                ['Cena za 1 m³:', f"{invoice.water_cost_m3:.4f} zł/m³"],
                ['Koszt wody:', f"{total_cost_water:.2f} zł"],
                ['Abonament (1/3):', f"{total_abonament_water:.2f} zł"],
            ]
        else:
            water_details = [
                ['Koszt wody:', f"{total_cost_water:.2f} zł"],
            ]
        
        water_table = Table(water_details, colWidths=[60*mm, 125*mm])
        water_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), default_font),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))
        story.append(water_table)
        story.append(Spacer(1, 2*mm))
        
        # 2. Ścieki
        story.append(Paragraph("2. ŚCIEKI", subheading_style))
        if invoice:
            sewage_details = [
                ['Zużycie:', f"{total_usage_m3:.2f} m³"],
                ['Cena za 1 m³:', f"{invoice.sewage_cost_m3:.4f} zł/m³"],
                ['Koszt ścieków:', f"{total_cost_sewage:.2f} zł"],
                ['Abonament (1/3):', f"{total_abonament_sewage:.2f} zł"],
            ]
        else:
            sewage_details = [
                ['Koszt ścieków:', f"{total_cost_sewage:.2f} zł"],
            ]
        
        sewage_table = Table(sewage_details, colWidths=[60*mm, 125*mm])
        sewage_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), default_font),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))
        story.append(sewage_table)
        story.append(Spacer(1, 2*mm))
        
        # 3. Koszty łącznie
        story.append(Paragraph("3. KOSZTY ŁĄCZNIE (1.+2.):", subheading_style))
        water_costs_table = Table([
            ['Netto:', f"{total_net:.2f} zł"],
            ['Brutto:', f"{total_gross:.2f} zł"],
        ], colWidths=[60*mm, 125*mm])
        water_costs_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), default_font),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))
        story.append(water_costs_table)
    else:
        story.append(Paragraph("Brak danych o rachunku za wodę i ścieki", normal_style))
    
    story.append(Spacer(1, 5*mm))
    
    # ========== III. GAZ ==========
    story.append(Paragraph("III. GAZ", heading_style))
    story.append(Spacer(1, 2*mm))
    
    # Pobierz wszystkie rachunki gazu z obu miesięcy
    from app.models.gas import GasBill
    gas_bills = db.query(GasBill).filter(
        GasBill.data.in_([combined_bill.period_start, combined_bill.period_end]),
        GasBill.local == combined_bill.local
    ).all()
    
    if gas_bills:
        # Sumuj koszty z obu miesięcy
        total_net = sum(b.total_net_sum for b in gas_bills)
        total_gross = sum(b.total_gross_sum for b in gas_bills)
        total_fuel = sum(b.fuel_cost_gross for b in gas_bills)
        total_subscription = sum(b.subscription_cost_gross for b in gas_bills)
        total_dist_fixed = sum(b.distribution_fixed_cost_gross for b in gas_bills)
        total_dist_variable = sum(b.distribution_variable_cost_gross for b in gas_bills)
        
        # Użyj pierwszego rachunku do szczegółów (faktura, udział)
        gas_bill = gas_bills[0]
        # Odczyty (gaz nie ma odczytów w bazie, więc pokazujemy tylko koszty)
        story.append(Paragraph("Odczyty licznika:", subheading_style))
        story.append(Paragraph("Dane z faktury gazu", normal_style))
        story.append(Spacer(1, 2*mm))
        
        # Szczegóły obliczeń
        story.append(Paragraph("Szczegóły obliczeń:", subheading_style))
        invoice = gas_bill.invoice
        if invoice:
            # Proporcje
            share = gas_bill.cost_share
            share_percent = int(share * 100)
            
            gas_details = [
                ['Udział lokalu:', f"{share_percent}%"],
                ['Koszt paliwa gazowego:', f"{total_fuel:.2f} zł"],
                ['Opłata abonamentowa:', f"{total_subscription:.2f} zł"],
                ['Opłata dystrybucyjna stała:', f"{total_dist_fixed:.2f} zł"],
                ['Opłata dystrybucyjna zmienna:', f"{total_dist_variable:.2f} zł"],
            ]
        else:
            gas_details = [
                ['Koszt brutto:', f"{total_gross:.2f} zł"],
            ]
        
        gas_table = Table(gas_details, colWidths=[60*mm, 125*mm])
        gas_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), default_font),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))
        story.append(gas_table)
        story.append(Spacer(1, 2*mm))
        
        # Koszty łącznie
        story.append(Paragraph("Koszty łącznie:", subheading_style))
        gas_costs_table = Table([
            ['Netto:', f"{total_net:.2f} zł"],
            ['Brutto:', f"{total_gross:.2f} zł"],
        ], colWidths=[60*mm, 125*mm])
        gas_costs_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), default_font),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))
        story.append(gas_costs_table)
    else:
        story.append(Paragraph("Brak danych o rachunku za gaz", normal_style))
    
    # Generuj PDF
    doc.build(story)
    
    return str(filepath.resolve())

