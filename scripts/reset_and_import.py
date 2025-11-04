"""
Skrypt do resetu bazy danych, importu danych z Google Sheets i generowania rachunków.
Uruchamia pełny proces od początku.
"""

import os
import sys
from pathlib import Path
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, engine, init_db, Base, DATABASE_URL
from app.models.water import Local, Reading, Invoice, Bill
from app.integrations.google_sheets import (
    import_readings_from_sheets,
    import_locals_from_sheets,
    import_invoices_from_sheets
)
from app.services.water import bill_generator


def reset_database():
    """
    Usuwa wszystkie dane z bazy danych i tworzy tabele na nowo.
    """
    print("=" * 60)
    print("🔄 RESET BAZY DANYCH")
    print("=" * 60)
    
    # Sprawdź czy baza istnieje
    db_exists = os.path.exists(DATABASE_URL)
    
    if db_exists:
        print(f"\n📁 Znaleziono bazę danych: {DATABASE_URL}")
        
        # Sprawdź ile rekordów jest w bazie
        db = SessionLocal()
        try:
            locals_count = db.query(Local).count()
            readings_count = db.query(Reading).count()
            invoices_count = db.query(Invoice).count()
            bills_count = db.query(Bill).count()
            
            print(f"\n📊 Stan bazy danych przed resetem:")
            print(f"   - Lokale: {locals_count}")
            print(f"   - Odczyty: {readings_count}")
            print(f"   - Faktury: {invoices_count}")
            print(f"   - Rachunki: {bills_count}")
            
            # Usuń wszystkie rachunki i pliki PDF
            print("\n🗑️  Usuwanie rachunków...")
            bills = db.query(Bill).all()
            pdf_deleted = 0
            for bill in bills:
                if bill.pdf_path and Path(bill.pdf_path).exists():
                    try:
                        Path(bill.pdf_path).unlink()
                        pdf_deleted += 1
                    except Exception as e:
                        print(f"   [UWAGA] Nie udało się usunąć PDF {bill.pdf_path}: {e}")
                db.delete(bill)
            
            print(f"   ✓ Usunięto {len(bills)} rachunków (w tym {pdf_deleted} plików PDF)")
            
            # Usuń wszystkie rekordy z tabel
            print("\n🗑️  Usuwanie danych z tabel...")
            db.query(Bill).delete()
            db.query(Invoice).delete()
            db.query(Reading).delete()
            db.query(Local).delete()
            db.commit()
            print("   ✓ Wyczyszczono wszystkie tabele")
            
        except Exception as e:
            db.rollback()
            print(f"\n❌ Błąd podczas czyszczenia bazy: {e}")
            raise
        finally:
            db.close()
    else:
        print(f"\n📁 Baza danych nie istnieje, będzie utworzona: {DATABASE_URL}")
    
    # Usuń plik bazy danych i utwórz na nowo
    if db_exists:
        # Poczekaj chwilę, aby upewnić się, że wszystkie połączenia są zamknięte
        import time
        time.sleep(0.5)
        
        try:
            # Zamknij silnik, aby zwolnić plik
            engine.dispose()
            
            # Teraz usuń plik
            if os.path.exists(DATABASE_URL):
                os.remove(DATABASE_URL)
                print(f"\n🗑️  Usunięto plik bazy danych")
        except PermissionError as e:
            print(f"\n❌ Błąd uprawnień - plik bazy danych może być używany przez inną aplikację")
            print(f"   Zamknij inne instancje aplikacji i spróbuj ponownie.")
            raise
        except Exception as e:
            print(f"\n❌ Nie udało się usunąć pliku bazy danych: {e}")
            print("   Próbuję kontynuować...")
    
    # Inicjalizuj bazę od nowa
    print("\n🔨 Tworzenie nowych tabel...")
    try:
        init_db()
        print("   ✓ Baza danych zresetowana pomyślnie")
    except Exception as e:
        print(f"\n❌ Błąd podczas tworzenia tabel: {e}")
        raise
    
    print("\n" + "=" * 60)


def import_data_from_sheets(credentials_path: str, spreadsheet_id: str):
    """
    Importuje wszystkie dane z Google Sheets (odczyty, lokale, faktury).
    
    Args:
        credentials_path: Ścieżka do pliku JSON z poświadczeniami Google Service Account
        spreadsheet_id: ID arkusza Google Sheets
    """
    print("\n" + "=" * 60)
    print("📥 IMPORT DANYCH Z GOOGLE SHEETS")
    print("=" * 60)
    
    db = SessionLocal()
    try:
        # 1. Import lokali
        print("\n1️⃣  Import lokali...")
        result_locals = import_locals_from_sheets(
            db=db,
            credentials_path=credentials_path,
            spreadsheet_id=spreadsheet_id,
            sheet_name="Lokale"
        )
        print(f"   ✓ Zaimportowano: {result_locals['imported']}")
        print(f"   ⏭️  Pominięto: {result_locals['skipped']}")
        if result_locals['errors']:
            print(f"   ❌ Błędy: {len(result_locals['errors'])}")
            for error in result_locals['errors']:
                print(f"      - {error}")
        
        # 2. Import odczytów
        print("\n2️⃣  Import odczytów...")
        result_readings = import_readings_from_sheets(
            db=db,
            credentials_path=credentials_path,
            spreadsheet_id=spreadsheet_id,
            sheet_name="Odczyty"
        )
        print(f"   ✓ Zaimportowano: {result_readings['imported']}")
        print(f"   ⏭️  Pominięto: {result_readings['skipped']}")
        if result_readings['errors']:
            print(f"   ❌ Błędy: {len(result_readings['errors'])}")
            for error in result_readings['errors']:
                print(f"      - {error}")
        
        # 3. Import faktur
        print("\n3️⃣  Import faktur...")
        result_invoices = import_invoices_from_sheets(
            db=db,
            credentials_path=credentials_path,
            spreadsheet_id=spreadsheet_id,
            sheet_name="Faktury"
        )
        print(f"   ✓ Zaimportowano: {result_invoices['imported']}")
        print(f"   ⏭️  Pominięto: {result_invoices['skipped']}")
        if result_invoices['errors']:
            print(f"   ❌ Błędy: {len(result_invoices['errors'])}")
            for error in result_invoices['errors']:
                print(f"      - {error}")
        
        # Podsumowanie
        print("\n" + "-" * 60)
        print("📊 PODSUMOWANIE IMPORTU:")
        print(f"   Lokale: {result_locals['imported']} zaimportowano, {result_locals['skipped']} pominięto")
        print(f"   Odczyty: {result_readings['imported']} zaimportowano, {result_readings['skipped']} pominięto")
        print(f"   Faktury: {result_invoices['imported']} zaimportowano, {result_invoices['skipped']} pominięto")
        
    except Exception as e:
        db.rollback()
        print(f"\n❌ Błąd podczas importu: {e}")
        raise
    finally:
        db.close()
    
    print("\n" + "=" * 60)


def generate_all_bills():
    """
    Generuje wszystkie możliwe rachunki dla wszystkich okresów.
    """
    print("\n" + "=" * 60)
    print("🧾 GENEROWANIE RACHUNKÓW")
    print("=" * 60)
    
    db = SessionLocal()
    try:
        result = bill_generator.generate_all_possible_bills(db)
        
        print(f"\n📊 WYNIKI GENEROWANIA:")
        print(f"   Okresów przetworzonych: {result.get('periods_processed', 0)}")
        print(f"   Rachunków wygenerowanych: {result.get('bills_generated', 0)}")
        print(f"   Plików PDF wygenerowanych: {result.get('pdfs_generated', 0)}")
        
        if result.get('errors'):
            print(f"\n❌ Błędy ({len(result['errors'])}):")
            for error in result['errors']:
                print(f"   - {error}")
        
        if result.get('processed_periods'):
            print(f"\n✓ Przetworzone okresy: {', '.join(result['processed_periods'])}")
        
    except Exception as e:
        print(f"\n❌ Błąd podczas generowania rachunków: {e}")
        raise
    finally:
        db.close()
    
    print("\n" + "=" * 60)


def main():
    """
    Główna funkcja - wykonuje pełny reset i import.
    """
    print("\n" + "=" * 60)
    print("💧 WATER BILLING SYSTEM - RESET I IMPORT")
    print("=" * 60)
    
    # Sprawdź argumenty
    if len(sys.argv) < 3:
        print("\n❌ BŁĄD: Brakuje wymaganych argumentów!")
        print("\nUżycie:")
        print(f"  python {sys.argv[0]} <credentials_path> <spreadsheet_id>")
        print("\nPrzykłady:")
        print(f"  python {sys.argv[0]} credentials.json SPREADSHEET_ID")
        print(f"  python {sys.argv[0]} .\\credentials.json SPREADSHEET_ID")
        print(f"  python {sys.argv[0]} config/credentials.json SPREADSHEET_ID")
        print("\nGdzie:")
        print("  - credentials_path: Ścieżka do pliku JSON z poświadczeniami Google Service Account")
        print("  - spreadsheet_id: ID arkusza Google Sheets (z URL: https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit)")
        sys.exit(1)
    
    credentials_path = sys.argv[1]
    spreadsheet_id = sys.argv[2]
    
    # Normalizuj ścieżkę - usuń prefiksy .\ lub ./ jeśli są obecne
    credentials_path = credentials_path.strip()
    if credentials_path.startswith('.\\') or credentials_path.startswith('./'):
        # Usuń prefiks .\ lub ./
        credentials_path = credentials_path[2:]
    
    # Jeśli ścieżka jest względna, przekonwertuj na bezwzględną
    if not os.path.isabs(credentials_path):
        credentials_path = os.path.normpath(os.path.join(os.getcwd(), credentials_path))
    else:
        credentials_path = os.path.normpath(credentials_path)
    
    # Sprawdź czy plik credentials istnieje
    if not os.path.exists(credentials_path):
        print(f"\n❌ BŁĄD: Plik credentials nie został znaleziony!")
        print(f"   Szukana ścieżka: {credentials_path}")
        print(f"   Obecny katalog roboczy: {os.getcwd()}")
        print(f"\n   Sprawdź czy:")
        print(f"   1. Plik credentials.json istnieje w tym katalogu")
        print(f"   2. Ścieżka jest prawidłowa")
        print(f"   3. Używasz poprawnej nazwy pliku")
        
        # Spróbuj znaleźć możliwe pliki credentials
        current_dir = os.getcwd()
        possible_files = [f for f in os.listdir(current_dir) if 'credential' in f.lower() and f.endswith('.json')]
        if possible_files:
            print(f"\n   Znalezione pliki credentials w katalogu:")
            for f in possible_files:
                print(f"      - {f}")
        
        sys.exit(1)
    
    print(f"\n📁 Ścieżka credentials: {credentials_path}")
    print(f"📋 Spreadsheet ID: {spreadsheet_id}")
    
    # Sprawdź czy plik jest prawidłowym JSON
    try:
        import json
        with open(credentials_path, 'r', encoding='utf-8') as f:
            creds_data = json.load(f)
            if 'type' not in creds_data or creds_data.get('type') != 'service_account':
                print(f"\n⚠️  UWAGA: Plik credentials może nie być poprawnym plikiem Service Account")
            else:
                print(f"   ✓ Plik credentials jest poprawny (Service Account)")
    except json.JSONDecodeError as e:
        print(f"\n❌ BŁĄD: Plik credentials nie jest prawidłowym JSON!")
        print(f"   Szczegóły: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n⚠️  Nie można zweryfikować pliku credentials: {e}")
    
    # Potwierdzenie
    print("\n⚠️  UWAGA: Ta operacja usunie wszystkie dane z bazy danych!")
    response = input("Czy kontynuować? (tak/nie): ").strip().lower()
    
    if response not in ['tak', 't', 'yes', 'y']:
        print("\n❌ Operacja anulowana przez użytkownika.")
        sys.exit(0)
    
    try:
        # 1. Reset bazy danych
        reset_database()
        
        # 2. Import danych z Google Sheets
        import_data_from_sheets(credentials_path, spreadsheet_id)
        
        # 3. Generowanie rachunków
        generate_all_bills()
        
        print("\n" + "=" * 60)
        print("✅ OPERACJA ZAKOŃCZONA POMYŚLNIE!")
        print("=" * 60)
        print("\nMożesz teraz:")
        print("  - Uruchomić aplikację: python run.py")
        print("  - Otworzyć dokumentację API: http://localhost:8000/docs")
        print("  - Sprawdzić wygenerowane rachunki w folderze bills/")
        print("\n")
        
    except Exception as e:
        print("\n" + "=" * 60)
        print("❌ BŁĄD PODCZAS WYKONYWANIA OPERACJI")
        print("=" * 60)
        print(f"\nSzczegóły błędu:")
        print(f"  {type(e).__name__}: {e}")
        print("\nStack trace:")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

