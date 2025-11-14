"""
Weryfikuje parsowanie faktury i obliczenia.
"""

from app.core.database import SessionLocal, init_db
from app.models.water import Invoice
from app.services.water.invoice_reader import extract_text_from_pdf, parse_invoice_data
import re

def verify_invoice(invoice_number: str):
    init_db()
    db = SessionLocal()
    
    try:
        invoice = db.query(Invoice).filter(Invoice.invoice_number == invoice_number).first()
        if not invoice:
            print(f"[BLAD] Nie znaleziono faktury {invoice_number}")
            return
        
        # Znajdz plik PDF
        from app.config import settings
        import os
        from pathlib import Path
        
        invoices_dir = Path(settings.invoices_raw_dir)
        pdf_files = list(invoices_dir.glob("**/*.pdf"))
        
        pdf_path = None
        for pdf_file in pdf_files:
            text = extract_text_from_pdf(str(pdf_file))
            if invoice_number in text:
                pdf_path = pdf_file
                break
        
        if not pdf_path:
            print(f"[BLAD] Nie znaleziono pliku PDF dla faktury {invoice_number}")
            return
        
        print("=" * 80)
        print(f"WERYFIKACJA PARSOWANIA FAKTURY: {invoice_number}")
        print("=" * 80)
        
        # Wczytaj tekst z PDF
        text = extract_text_from_pdf(str(pdf_path))
        
        # Sprawdz pozycje wody
        print("\n1. POZYCJE WODY W FAKTURZE:")
        items_section = re.search(r'(?:Pozycje|Pozycja|Woda|Ścieki).*?(?:Wartość\s+Netto|Razem|Suma|VAT)', text, re.IGNORECASE | re.DOTALL)
        search_text = items_section.group(0) if items_section else text
        
        water_pattern = r'Woda\s+m3\s+(\d+[.,]\d+)\s+(\d+[.,]\d+)\s+(\d+[.,]\d+)\s+\d+%?'
        water_matches = re.findall(water_pattern, search_text, re.IGNORECASE)
        
        if water_matches:
            total_water_usage = 0.0
            total_water_value = 0.0
            
            for i, match in enumerate(water_matches, 1):
                usage = float(match[0].replace(',', '.'))
                price = float(match[1].replace(',', '.'))
                value = float(match[2].replace(',', '.'))
                total_water_usage += usage
                total_water_value += value
                
                print(f"   Pozycja {i}:")
                print(f"     Ilosc: {usage} m3")
                print(f"     Cena: {price} zl/m3")
                print(f"     Wartosc netto: {value} zl")
                print(f"     Weryfikacja: {usage} × {price} = {usage * price:.2f} zl")
            
            avg_water_price = total_water_value / total_water_usage if total_water_usage > 0 else 0.0
            print(f"\n   SUMA:")
            print(f"     Ilosc: {total_water_usage} m3")
            print(f"     Wartosc netto: {total_water_value} zl")
            print(f"     Srednia wazona cena: {avg_water_price:.2f} zl/m3")
            print(f"\n   W BAZIE:")
            print(f"     Ilosc: {invoice.usage} m3")
            print(f"     Cena: {invoice.water_cost_m3} zl/m3")
            print(f"     ROZNICA ceny: {abs(avg_water_price - invoice.water_cost_m3):.4f} zl/m3")
        
        # Sprawdz pozycje sciekow
        print("\n2. POZYCJE SCIEKOW W FAKTURZE:")
        sewage_pattern = r'Ścieki\s+m3\s+(\d+[.,]\d+)\s+(\d+[.,]\d+)\s+(\d+[.,]\d+)\s+\d+%?'
        sewage_matches = re.findall(sewage_pattern, search_text, re.IGNORECASE)
        
        if sewage_matches:
            total_sewage_usage = 0.0
            total_sewage_value = 0.0
            
            for i, match in enumerate(sewage_matches, 1):
                usage = float(match[0].replace(',', '.'))
                price = float(match[1].replace(',', '.'))
                value = float(match[2].replace(',', '.'))
                total_sewage_usage += usage
                total_sewage_value += value
                
                print(f"   Pozycja {i}:")
                print(f"     Ilosc: {usage} m3")
                print(f"     Cena: {price} zl/m3")
                print(f"     Wartosc netto: {value} zl")
                print(f"     Weryfikacja: {usage} × {price} = {usage * price:.2f} zl")
            
            avg_sewage_price = total_sewage_value / total_sewage_usage if total_sewage_usage > 0 else 0.0
            print(f"\n   SUMA:")
            print(f"     Ilosc: {total_sewage_usage} m3")
            print(f"     Wartosc netto: {total_sewage_value} zl")
            print(f"     Srednia wazona cena: {avg_sewage_price:.2f} zl/m3")
            print(f"\n   W BAZIE:")
            print(f"     Cena: {invoice.sewage_cost_m3} zl/m3")
            print(f"     ROZNICA ceny: {abs(avg_sewage_price - invoice.sewage_cost_m3):.4f} zl/m3")
        
        # Sprawdz abonament
        print("\n3. ABONAMENT W FAKTURZE:")
        
        # Szukaj wszystkich wzorcow abonamentu
        abonament_patterns = [
            (r'Abonament\s+Woda\s+szt\.\s+(\d+[.,]\d+)\s+(\d+[.,]\d+)\s+(\d+[.,]\d+)', "Abonament Woda szt."),
            (r'Abonament\s+(?:za\s+)?wod[ęy]\s+(\d+)\s+(\d+[.,]\d+)\s+(\d+[.,]\d+)', "Abonament za wodę"),
            (r'Abonament\s+wodny\s+(\d+)\s+(\d+[.,]\d+)\s+(\d+[.,]\d+)', "Abonament wodny"),
            (r'wod[ęy].*?x\s*(\d+)[,\s]+(\d+[.,]\d+)', "woda x ilość cena"),
        ]
        
        print("   Szukanie wzorcow abonamentu wody:")
        for pattern, desc in abonament_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                print(f"     Wzorzec '{desc}': znaleziono {len(matches)} dopasowan")
                for match in matches:
                    print(f"       {match}")
        
        # Szukaj w formacie "x1, 13,37" lub "x1 13,37"
        x_format = re.findall(r'wod[ęy].*?x\s*(\d+)[,\s]+(\d+[.,]\d+)', text, re.IGNORECASE)
        if x_format:
            print(f"\n   Format 'x ilość, cena': {x_format}")
            for qty, price in x_format:
                qty_val = int(qty)
                price_val = float(price.replace(',', '.'))
                print(f"     Ilość: {qty_val}, Cena: {price_val} zl, Wartość: {qty_val * price_val:.2f} zl")
        
        print(f"\n   W BAZIE:")
        print(f"     Abonament wody: {invoice.water_subscr_cost} zl")
        print(f"     Abonament sciekow: {invoice.sewage_subscr_cost} zl")
        print(f"     Liczba abonamentow: {invoice.nr_of_subscription}")
        
        # Wyswietl fragment tekstu z abonamentem
        abonament_section = re.search(r'abonament.*?(?:wod|ściek).*?(\d+[.,]\d+)', text, re.IGNORECASE | re.DOTALL)
        if abonament_section:
            print(f"\n   Fragment tekstu z abonamentem:")
            print(f"     {abonament_section.group(0)[:200]}")
    
    finally:
        db.close()

if __name__ == "__main__":
    import sys
    invoice_number = sys.argv[1] if len(sys.argv) > 1 else "FRP/25/02/022549"
    verify_invoice(invoice_number)

