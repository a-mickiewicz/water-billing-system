"""
Skrypt testowy do sprawdzania wykrywania duplikatów faktur.
Wczytuje tę samą fakturę dwukrotnie, aby sprawdzić czy duplikat zostanie wykryty.
"""

from app.core.database import SessionLocal, init_db
from app.services.water.invoice_reader import load_invoice_from_pdf
from pathlib import Path


def test_duplicate_detection(pdf_path: str):
    """
    Testuje wykrywanie duplikatów faktur.
    
    Args:
        pdf_path: Ścieżka do pliku PDF z fakturą
    """
    # Inicjalizuj bazę danych
    init_db()
    
    db = SessionLocal()
    try:
        print("=" * 80)
        print("TEST WYKRYWANIA DUPLIKATÓW FAKTUR")
        print("=" * 80)
        
        print(f"\n📄 Testowanie pliku: {pdf_path}")
        
        # Pierwsza próba wczytania faktury
        print("\n" + "-" * 80)
        print("1️⃣ PIERWSZE WCZYTYWANIE FAKTURY")
        print("-" * 80)
        invoice1 = load_invoice_from_pdf(db, pdf_path)
        
        if invoice1:
            print(f"\n✅ Faktura wczytana pomyślnie!")
            print(f"   Numer faktury: {invoice1.invoice_number}")
            print(f"   Okres: {invoice1.data}")
            print(f"   Suma brutto: {invoice1.gross_sum} zł")
            print(f"   ID w bazie: {invoice1.id}")
        else:
            print("\n❌ Nie udało się wczytać faktury")
            return
        
        # Druga próba wczytania tej samej faktury
        print("\n" + "-" * 80)
        print("2️⃣ DRUGIE WCZYTYWANIE TEJ SAMEJ FAKTURY (test duplikatu)")
        print("-" * 80)
        invoice2 = load_invoice_from_pdf(db, pdf_path)
        
        if invoice2:
            print(f"\n📊 PORÓWNANIE:")
            print(f"   ID pierwszej faktury: {invoice1.id}")
            print(f"   ID drugiej faktury: {invoice2.id}")
            
            if invoice1.id == invoice2.id:
                print(f"\n✅ SUKCES: Funkcja wykryła duplikat i zwróciła istniejącą fakturę!")
                print(f"   Nie utworzono duplikatu w bazie danych.")
            else:
                print(f"\n⚠️ UWAGA: Zwrócono różne faktury (może być problem z duplikatami)")
        else:
            print("\n❌ Nie udało się wczytać faktury drugi raz")
        
        # Sprawdź ile faktur jest w bazie dla tego okresu i numeru
        print("\n" + "-" * 80)
        print("3️⃣ WERYFIKACJA W BAZIE DANYCH")
        print("-" * 80)
        
        from app.models.water import Invoice
        
        count = db.query(Invoice).filter(
            Invoice.invoice_number == invoice1.invoice_number,
            Invoice.data == invoice1.data
        ).count()
        
        print(f"Liczba faktur w bazie dla numeru '{invoice1.invoice_number}' i okresu '{invoice1.data}': {count}")
        
        if count == 1:
            print("✅ OK: W bazie jest dokładnie jedna faktura (brak duplikatów)")
        elif count > 1:
            print(f"⚠️ UWAGA: W bazie jest {count} faktur (możliwe duplikaty)")
            all_invoices = db.query(Invoice).filter(
                Invoice.invoice_number == invoice1.invoice_number,
                Invoice.data == invoice1.data
            ).all()
            
            print("\nLista wszystkich faktur:")
            for i, inv in enumerate(all_invoices, 1):
                print(f"  {i}. ID: {inv.id}, Suma brutto: {inv.gross_sum} zł")
        else:
            print("❌ BŁĄD: Nie znaleziono żadnych faktur w bazie")
        
        print("\n" + "=" * 80)
        print("TEST ZAKOŃCZONY")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ BŁĄD podczas testu: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


def main():
    """Główna funkcja."""
    import sys
    
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
    else:
        # Domyślny plik
        pdf_path = "invoices_raw/invoice_2023_12.pdf"
    
    if not Path(pdf_path).exists():
        print(f"❌ BŁĄD: Plik nie istnieje: {pdf_path}")
        print("\nUżycie:")
        print("  python test_duplicates.py [ścieżka_do_pdf]")
        print("\nPrzykład:")
        print("  python test_duplicates.py invoices_raw/invoice_2023_12.pdf")
        return
    
    test_duplicate_detection(pdf_path)


if __name__ == "__main__":
    main()


