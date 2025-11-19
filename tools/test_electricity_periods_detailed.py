"""
Szczegółowy test wyłaniania okresów z faktury.
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import SessionLocal
from app.models.electricity_invoice import (
    ElectricityInvoice,
    ElectricityInvoiceOplataDystrybucyjna,
    ElectricityInvoiceSprzedazEnergii,
    ElectricityInvoiceRozliczenieOkres
)
from sqlalchemy import desc


def test_invoice_details():
    """Sprawdź szczegóły faktury."""
    db = SessionLocal()
    
    try:
        print("=" * 80)
        print("SZCZEGÓŁOWA ANALIZA FAKTURY")
        print("=" * 80)
        
        # Znajdź fakturę
        invoice = db.query(ElectricityInvoice).order_by(desc(ElectricityInvoice.data_poczatku_okresu)).first()
        
        if not invoice:
            print("[ERROR] Brak faktur!")
            return
        
        print(f"\nFaktura: {invoice.numer_faktury}")
        print(f"Okres: {invoice.data_poczatku_okresu} - {invoice.data_konca_okresu}")
        print(f"Typ taryfy: {invoice.typ_taryfy}")
        
        # Sprawdź rozliczenie_okresy
        print("\n" + "-" * 80)
        print("ROZLICZENIE_OKRESY:")
        print("-" * 80)
        
        rozliczenie_okresy = db.query(ElectricityInvoiceRozliczenieOkres).filter(
            ElectricityInvoiceRozliczenieOkres.invoice_id == invoice.id
        ).order_by(ElectricityInvoiceRozliczenieOkres.numer_okresu).all()
        
        if rozliczenie_okresy:
            print(f"Znaleziono {len(rozliczenie_okresy)} okresów:")
            for okres in rozliczenie_okresy:
                print(f"  Okres {okres.numer_okresu}: data_okresu = {okres.data_okresu}")
        else:
            print("Brak rozliczenie_okresy")
        
        # Sprawdź opłaty dystrybucyjne
        print("\n" + "-" * 80)
        print("OPŁATY DYSTRYBUCYJNE:")
        print("-" * 80)
        
        oplaty = db.query(ElectricityInvoiceOplataDystrybucyjna).filter(
            ElectricityInvoiceOplataDystrybucyjna.invoice_id == invoice.id
        ).order_by(ElectricityInvoiceOplataDystrybucyjna.data).all()
        
        if oplaty:
            print(f"Znaleziono {len(oplaty)} opłat:")
            unique_dates = sorted(set(o.data for o in oplaty if o.data))
            print(f"Unikalne daty: {unique_dates}")
            
            for date_val in unique_dates[:3]:  # Pokaż pierwsze 3
                print(f"\n  Data: {date_val}")
                oplaty_for_date = [o for o in oplaty if o.data == date_val]
                for o in oplaty_for_date[:5]:  # Pokaż pierwsze 5
                    print(f"    {o.typ_oplaty}: {o.jednostka}, cena={o.cena}, strefa={o.strefa}")
        else:
            print("Brak opłat dystrybucyjnych")
        
        # Sprawdź sprzedaż energii
        print("\n" + "-" * 80)
        print("SPRZEDAŻ ENERGII:")
        print("-" * 80)
        
        sprzedaz = db.query(ElectricityInvoiceSprzedazEnergii).filter(
            ElectricityInvoiceSprzedazEnergii.invoice_id == invoice.id
        ).order_by(ElectricityInvoiceSprzedazEnergii.data).all()
        
        if sprzedaz:
            print(f"Znaleziono {len(sprzedaz)} pozycji sprzedaży:")
            for s in sprzedaz[:5]:  # Pokaż pierwsze 5
                print(f"  data={s.data}, strefa={s.strefa}, ilosc={s.ilosc_kwh}, cena={s.cena_za_kwh}, naleznosc={s.naleznosc}")
        else:
            print("Brak sprzedaży energii")
        
    except Exception as e:
        print(f"\n[ERROR] Błąd: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    test_invoice_details()

