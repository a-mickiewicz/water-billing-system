"""
Narzędzie do analizy faktur za prąd (Enea).
Parsuje faktury na tekst i wyświetla je do porównania.
"""

import sys
import os
from pathlib import Path
import pdfplumber

# Dodaj ścieżkę do projektu
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Wyciąga tekst z pliku PDF - wszystkie strony i wszystkie znaki.
    
    Args:
        pdf_path: Ścieżka do pliku PDF
    
    Returns:
        Wszystki tekst z pliku PDF
    """
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages, 1):
                page_text = page.extract_text() or ""
                
                # Spróbuj też wyciągnąć tabele
                try:
                    tables = page.extract_tables()
                    if tables:
                        for table in tables:
                            for row in table:
                                if row:
                                    row_text = " ".join([str(cell) if cell else "" for cell in row])
                                    page_text += " " + row_text
                except Exception:
                    pass
                
                text += page_text + "\n"
        
    except Exception as e:
        print(f"Błąd przy wczytywaniu PDF {pdf_path}: {e}")
        return ""
    return text


def analyze_invoice(pdf_path: str, invoice_name: str, output_dir: Path):
    """Analizuje pojedynczą fakturę i zapisuje jej tekst do pliku."""
    print(f"\nPrzetwarzanie: {invoice_name}")
    
    # Wczytaj tekst
    text = extract_text_from_pdf(pdf_path)
    
    if not text:
        print(f"  BLAD - Nie udalo sie wczytac tekstu z PDF")
        return None
    
    # Utwórz nazwę pliku wyjściowego (zmień .pdf na .txt)
    output_filename = invoice_name.replace(".pdf", ".txt")
    output_path = output_dir / output_filename
    
    # Zapisz tekst do pliku
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(f"FAKTURA: {invoice_name}\n")
            f.write(f"Plik źródłowy: {pdf_path}\n")
            f.write("="*100 + "\n\n")
            f.write(text)
        
        print(f"  OK - Zapisano do: {output_path}")
        print(f"    Dlugosc tekstu: {len(text)} znakow, linii: {len(text.splitlines())}")
        return output_path
    except Exception as e:
        print(f"  BLAD przy zapisie: {e}")
        return None


def main():
    """Główna funkcja - analizuje wszystkie faktury za prąd."""
    # Ścieżka do katalogu z fakturami
    invoices_dir = Path("invoices_raw/electricity")
    
    if not invoices_dir.exists():
        print(f"BLAD - Katalog nie istnieje: {invoices_dir}")
        print("   Upewnij sie, ze jestes w katalogu glownym projektu.")
        sys.exit(1)
    
    # Utwórz katalog na sparsowane pliki tekstowe
    output_dir = invoices_dir / "parsed"
    output_dir.mkdir(exist_ok=True)
    
    # Znajdź wszystkie pliki PDF
    pdf_files = sorted(invoices_dir.glob("*.pdf"))
    
    if not pdf_files:
        print(f"BLAD - Nie znaleziono plikow PDF w katalogu: {invoices_dir}")
        sys.exit(1)
    
    print(f"Znaleziono {len(pdf_files)} faktur za prąd:")
    for pdf_file in pdf_files:
        print(f"  - {pdf_file.name}")
    
    print(f"\nSparsowany tekst zostanie zapisany w: {output_dir}")
    print("="*100)
    
    # Analizuj każdą fakturę
    saved_files = []
    for pdf_file in pdf_files:
        output_path = analyze_invoice(str(pdf_file), pdf_file.name, output_dir)
        if output_path:
            saved_files.append(output_path)
    
    print("\n" + "="*100)
    print("KONIEC ANALIZY")
    print("="*100)
    print(f"\nZapisano {len(saved_files)} plikow tekstowych:")
    for saved_file in saved_files:
        print(f"  - {saved_file}")
    print(f"\nKatalog z plikami: {output_dir}")
    print("\nPrzeanalizuj pliki tekstowe i określ:")
    print("  1. Jakie pola są wspólne dla wszystkich faktur?")
    print("  2. Jakie pola różnią się między fakturami?")
    print("  3. Jakie dane powinniśmy wyciągać z faktur?")


if __name__ == "__main__":
    main()

