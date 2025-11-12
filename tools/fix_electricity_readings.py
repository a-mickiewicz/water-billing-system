"""
Skrypt do identyfikacji i poprawy błędnie zapisanych odczytów w tabeli electricity_invoice_odczyty.

Problem: Wartości z kropkami jako separatorami tysięcy (np. "24.320") były błędnie parsowane jako "24".
Skrypt pomaga zidentyfikować i poprawić takie wartości.
"""

import sys
from pathlib import Path

# Dodaj główny katalog projektu do ścieżki
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import SessionLocal
from app.models.electricity_invoice import ElectricityInvoice, ElectricityInvoiceOdczyt


def parse_int_value_fixed(value):
    """Poprawiona funkcja parsująca wartości całkowite z formatu polskiego."""
    if value is None or value == '':
        return None
    
    # Jeśli wartość jest już liczbą, zwróć ją
    if isinstance(value, (int, float)):
        return int(value)
    
    value_str = str(value).strip()
    
    # Jeśli wartość zawiera kropki, sprawdź czy są to separatory tysięcy
    if '.' in value_str:
        # Jeśli jest też przecinek, to kropki są separatorami tysięcy
        if ',' in value_str:
            # Format: "24.320,50" -> usuń kropki -> "24320,50" -> zamień przecinek -> "24320.50"
            value_str = value_str.replace('.', '').replace(',', '.')
        else:
            # Tylko kropki - sprawdź czy to separator tysięcy (3 cyfry po kropce)
            parts = value_str.split('.')
            if len(parts) == 2 and len(parts[1]) == 3:
                # Format: "24.320" -> separator tysięcy -> usuń kropki
                value_str = value_str.replace('.', '')
            # W przeciwnym razie kropka jest separatorem dziesiętnym (zostaw)
    elif ',' in value_str:
        # Tylko przecinek - zamień na kropkę (separator dziesiętny)
        value_str = value_str.replace(',', '.')
    
    try:
        return int(float(value_str))
    except (ValueError, AttributeError, TypeError):
        return None


def identify_suspicious_readings(db):
    """Identyfikuje odczyty z podejrzanie małymi wartościami."""
    print("=== IDENTYFIKACJA PODEJRZANYCH ODCZYTÓW ===\n")
    
    all_readings = db.query(ElectricityInvoiceOdczyt).all()
    suspicious = []
    
    for reading in all_readings:
        issues = []
        
        # Sprawdź biezacy_odczyt - jeśli < 100, to prawdopodobnie błąd
        if reading.biezacy_odczyt < 100:
            issues.append(f"biezacy_odczyt={reading.biezacy_odczyt} (podejrzanie mały)")
        
        # Sprawdź poprzedni_odczyt - jeśli < 100, to prawdopodobnie błąd
        if reading.poprzedni_odczyt < 100:
            issues.append(f"poprzedni_odczyt={reading.poprzedni_odczyt} (podejrzanie mały)")
        
        # Sprawdź ilosc_kwh - jeśli bardzo mała w stosunku do różnicy odczytów
        if reading.biezacy_odczyt > 0 and reading.poprzedni_odczyt > 0:
            roznica_odczytow = reading.biezacy_odczyt - reading.poprzedni_odczyt
            obliczona_ilosc = roznica_odczytow * reading.mnozna
            
            # Jeśli obliczona ilość jest znacznie większa niż zapisana, to prawdopodobnie błąd
            if obliczona_ilosc > reading.ilosc_kwh * 10 and reading.ilosc_kwh < 1000:
                issues.append(f"ilosc_kwh={reading.ilosc_kwh} (obliczona: {obliczona_ilosc:.0f})")
        
        # Sprawdź razem_kwh - jeśli bardzo mała
        if reading.razem_kwh < 100 and reading.ilosc_kwh > 0:
            issues.append(f"razem_kwh={reading.razem_kwh} (podejrzanie mały)")
        
        if issues:
            invoice = db.query(ElectricityInvoice).filter(
                ElectricityInvoice.id == reading.invoice_id
            ).first()
            
            suspicious.append({
                'reading': reading,
                'invoice': invoice,
                'issues': issues
            })
    
    return suspicious


def print_suspicious_readings(suspicious):
    """Wyświetla listę podejrzanych odczytów."""
    if not suspicious:
        print("Nie znaleziono podejrzanych odczytów.")
        return
    
    print(f"Znaleziono {len(suspicious)} podejrzanych odczytów:\n")
    
    for idx, item in enumerate(suspicious, 1):
        reading = item['reading']
        invoice = item['invoice']
        issues = item['issues']
        
        print(f"{idx}. Odczyt ID: {reading.id}")
        print(f"   Faktura: {invoice.numer_faktury if invoice else 'BRAK'} (ID: {reading.invoice_id})")
        print(f"   Typ energii: {reading.typ_energii}, Strefa: {reading.strefa or 'całodobowa'}")
        print(f"   Data odczytu: {reading.data_odczytu}")
        print(f"   Bieżący odczyt: {reading.biezacy_odczyt}")
        print(f"   Poprzedni odczyt: {reading.poprzedni_odczyt}")
        print(f"   Mnożna: {reading.mnozna}")
        print(f"   Ilość kWh: {reading.ilosc_kwh}")
        print(f"   Razem kWh: {reading.razem_kwh}")
        print(f"   Problemy: {', '.join(issues)}")
        print()


def fix_readings_from_invoice_data(db, suspicious):
    """Próbuje poprawić odczyty na podstawie oryginalnych danych z faktury."""
    print("=== PRÓBA POPRAWY ODCZYTÓW ===\n")
    
    fixed_count = 0
    
    for item in suspicious:
        reading = item['reading']
        invoice = item['invoice']
        
        if not invoice:
            print(f"Odczyt ID {reading.id}: Brak faktury, pomijam.")
            continue
        
        # Szukaj ścieżki do PDF w powiązanych rachunkach (ElectricityBill)
        from app.models.electricity import ElectricityBill
        bill = db.query(ElectricityBill).filter(
            ElectricityBill.invoice_id == invoice.id
        ).first()
        
        pdf_path = None
        if bill and bill.pdf_path:
            pdf_path = Path(bill.pdf_path)
        else:
            # Spróbuj znaleźć PDF w folderze invoices_raw/electricity na podstawie numeru faktury
            invoices_folder = Path("invoices_raw/electricity")
            if invoices_folder.exists():
                # Szukaj pliku PDF z numerem faktury w nazwie
                invoice_number_clean = invoice.numer_faktury.replace('/', '_').replace('\\', '_')
                for pdf_file in invoices_folder.glob(f"*{invoice_number_clean}*.pdf"):
                    pdf_path = pdf_file
                    break
                # Jeśli nie znaleziono, spróbuj szukać po dacie
                if not pdf_path:
                    date_str = invoice.data_poczatku_okresu.strftime("%Y-%m")
                    for pdf_file in invoices_folder.glob(f"*{date_str}*.pdf"):
                        pdf_path = pdf_file
                        break
        
        if not pdf_path:
            print(f"Odczyt ID {reading.id}: Brak ścieżki do PDF faktury, pomijam.")
            continue
        
        if not pdf_path.exists():
            print(f"Odczyt ID {reading.id}: Plik PDF nie istnieje: {pdf_path}, pomijam.")
            continue
        
        try:
            from app.services.electricity.invoice_reader import extract_text_from_pdf, parse_invoice_data
            
            text = extract_text_from_pdf(str(pdf_path))
            if not text:
                print(f"Odczyt ID {reading.id}: Nie udało się odczytać tekstu z PDF, pomijam.")
                continue
            
            invoice_data = parse_invoice_data(text)
            
            if not invoice_data or 'odczyty' not in invoice_data:
                print(f"Odczyt ID {reading.id}: Nie udało się odczytać danych z PDF, pomijam.")
                continue
            
            # Znajdź odpowiedni odczyt w danych z PDF
            for odczyt_data in invoice_data['odczyty']:
                # Sprawdź czy to ten sam odczyt (typ energii, strefa, data)
                typ_match = (odczyt_data.get('typ') == 'pobrana' and reading.typ_energii == 'POBRANA') or \
                           (odczyt_data.get('typ') == 'oddana' and reading.typ_energii == 'ODDANA')
                
                if not typ_match:
                    continue
                
                strefa_match = False
                if reading.strefa:
                    strefa_match = odczyt_data.get('strefa', '').upper() == reading.strefa.upper()
                else:
                    strefa_match = odczyt_data.get('strefa') is None or odczyt_data.get('strefa') == ''
                
                if not strefa_match:
                    continue
                
                # Parsuj wartości z oryginalnych danych
                biezacy_fixed = parse_int_value_fixed(odczyt_data.get('biezace'))
                poprzedni_fixed = parse_int_value_fixed(odczyt_data.get('poprzednie'))
                ilosc_fixed = parse_int_value_fixed(odczyt_data.get('ilosc'))
                razem_fixed = parse_int_value_fixed(odczyt_data.get('razem'))
                
                # Sprawdź czy wartości się różnią
                if (biezacy_fixed and biezacy_fixed != reading.biezacy_odczyt) or \
                   (poprzedni_fixed and poprzedni_fixed != reading.poprzedni_odczyt) or \
                   (ilosc_fixed and ilosc_fixed != reading.ilosc_kwh) or \
                   (razem_fixed and razem_fixed != reading.razem_kwh):
                    
                    print(f"Odczyt ID {reading.id}: Znaleziono poprawne wartości w PDF")
                    print(f"  Bieżący: {reading.biezacy_odczyt} -> {biezacy_fixed}")
                    print(f"  Poprzedni: {reading.poprzedni_odczyt} -> {poprzedni_fixed}")
                    print(f"  Ilość kWh: {reading.ilosc_kwh} -> {ilosc_fixed}")
                    print(f"  Razem kWh: {reading.razem_kwh} -> {razem_fixed}")
                    
                    # Zaktualizuj wartości
                    if biezacy_fixed:
                        reading.biezacy_odczyt = biezacy_fixed
                    if poprzedni_fixed:
                        reading.poprzedni_odczyt = poprzedni_fixed
                    if ilosc_fixed:
                        reading.ilosc_kwh = ilosc_fixed
                    if razem_fixed:
                        reading.razem_kwh = razem_fixed
                    
                    fixed_count += 1
                    break
        
        except Exception as e:
            print(f"Odczyt ID {reading.id}: Błąd przy odczycie z PDF: {e}, pomijam.")
            continue
    
    if fixed_count > 0:
        db.commit()
        print(f"\nPoprawiono {fixed_count} odczytów.")
    else:
        print("\nNie udało się automatycznie poprawić żadnych odczytów.")
        print("Możesz poprawić je ręcznie w interfejsie użytkownika.")


def main():
    """Główna funkcja skryptu."""
    db = SessionLocal()
    
    try:
        # Identyfikuj podejrzane odczyty
        suspicious = identify_suspicious_readings(db)
        
        # Wyświetl listę
        print_suspicious_readings(suspicious)
        
        if not suspicious:
            print("Wszystkie odczyty wyglądają poprawnie!")
            return
        
        # Zapytaj użytkownika czy chce poprawić
        print("\nCzy chcesz spróbować automatycznie poprawić odczyty na podstawie danych z PDF?")
        print("(Wymaga dostępności plików PDF faktur)")
        response = input("Tak/Nie (t/n): ").strip().lower()
        
        if response in ['t', 'tak', 'y', 'yes']:
            fix_readings_from_invoice_data(db, suspicious)
        else:
            print("\nPominięto automatyczną poprawę.")
            print("Możesz poprawić odczyty ręcznie w interfejsie użytkownika.")
    
    finally:
        db.close()


if __name__ == "__main__":
    main()

