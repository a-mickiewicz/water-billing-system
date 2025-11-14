"""
Sprawdza obsługę wartości dziesiętnych w zużyciu wody/ścieków i różnice w sumach.
"""

from app.core.database import SessionLocal, init_db
from app.models.water import Invoice, Bill
from app.services.water.invoice_reader import parse_invoice_data, extract_text_from_pdf

def check_invoice_float_handling(invoice_number: str):
    init_db()
    db = SessionLocal()
    
    try:
        print("=" * 80)
        print(f"ANALIZA FAKTURY: {invoice_number}")
        print("=" * 80)
        
        # Znajdz fakture w bazie
        invoice = db.query(Invoice).filter(Invoice.invoice_number == invoice_number).first()
        if not invoice:
            print(f"[BLAD] Nie znaleziono faktury {invoice_number} w bazie")
            return
        
        print(f"\n1. DANE Z BAZY:")
        print(f"   Suma brutto faktury: {invoice.gross_sum} zl")
        print(f"   Zuzycie: {invoice.usage} m3")
        print(f"   Cena wody: {invoice.water_cost_m3} zl/m3")
        print(f"   Cena sciekow: {invoice.sewage_cost_m3} zl/m3")
        print(f"   Abonament wody: {invoice.water_subscr_cost} zl")
        print(f"   Abonament sciekow: {invoice.sewage_subscr_cost} zl")
        
        # Sprawdz rachunki
        bills = db.query(Bill).filter(Bill.invoice_id == invoice.id).all()
        print(f"\n2. RACHUNKI DLA LOKALI:")
        total_gross = 0.0
        for bill in bills:
            print(f"   {bill.local}:")
            print(f"     Zuzycie: {bill.usage_m3} m3")
            print(f"     Suma brutto: {bill.gross_sum} zl")
            total_gross += bill.gross_sum
        
        print(f"\n   SUMA BRUTTO Z RACHUNKOW: {total_gross:.2f} zl")
        print(f"   SUMA BRUTTO Z FAKTURY: {invoice.gross_sum:.2f} zl")
        print(f"   ROZNICA: {abs(total_gross - invoice.gross_sum):.2f} zl")
        
        # Sprawdz szczegoly obliczen
        print(f"\n3. SZCZEGOLY OBLICZEN:")
        for bill in bills:
            print(f"\n   {bill.local}:")
            print(f"     Zuzycie: {bill.usage_m3} m3")
            print(f"     Koszt wody: {bill.cost_water} zl ({bill.usage_m3} × {invoice.water_cost_m3})")
            print(f"     Koszt sciekow: {bill.cost_sewage} zl ({bill.usage_m3} × {invoice.sewage_cost_m3})")
            print(f"     Koszt zuzycia: {bill.cost_usage_total} zl")
            print(f"     Abonament: {bill.abonament_total} zl")
            print(f"     Suma netto: {bill.net_sum} zl")
            print(f"     VAT ({invoice.vat * 100:.1f}%): {bill.net_sum * invoice.vat:.2f} zl")
            print(f"     Suma brutto: {bill.gross_sum} zl")
            print(f"     Weryfikacja: {bill.net_sum * (1 + invoice.vat):.2f} zl")
        
        # Sprawdz parsowanie faktury z PDF
        print(f"\n4. PARSOWANIE Z PDF:")
        pdf_files = [
            f"invoices_raw/FVSP_{invoice_number.replace('/', '_')}.pdf",
            f"invoices_raw/{invoice_number.replace('/', '_')}.pdf"
        ]
        
        pdf_path = None
        for pdf_file in pdf_files:
            try:
                import os
                if os.path.exists(pdf_file):
                    pdf_path = pdf_file
                    break
            except:
                pass
        
        if pdf_path:
            print(f"   Znaleziono plik: {pdf_path}")
            text = extract_text_from_pdf(pdf_path)
            data = parse_invoice_data(text)
            
            if data:
                print(f"   Zuzycie z PDF: {data.get('usage')} m3")
                print(f"   Cena wody z PDF: {data.get('water_cost_m3')} zl/m3")
                print(f"   Cena sciekow z PDF: {data.get('sewage_cost_m3')} zl/m3")
                
                # Sprawdz czy sa pozycje z wartosciami dziesietnymi
                import re
                water_matches = re.findall(r'Woda\s+m3\s+(\d+[.,]\d+)\s+(\d+[.,]\d+)\s+(\d+[.,]\d+)', text, re.IGNORECASE)
                if water_matches:
                    print(f"\n   POZYCJE WODY W PDF:")
                    total_usage = 0.0
                    for i, match in enumerate(water_matches, 1):
                        usage = float(match[0].replace(',', '.'))
                        total_usage += usage
                        print(f"     Pozycja {i}: {usage} m3")
                    print(f"     SUMA: {total_usage} m3")
                    print(f"     W bazie: {invoice.usage} m3")
                    print(f"     ROZNICA: {abs(total_usage - invoice.usage):.4f} m3")
        else:
            print(f"   [INFO] Nie znaleziono pliku PDF")
    
    finally:
        db.close()

if __name__ == "__main__":
    import sys
    invoice_number = sys.argv[1] if len(sys.argv) > 1 else "FRP/24/02/008566"
    check_invoice_float_handling(invoice_number)

