"""
Główny moduł aplikacji FastAPI dla systemu rozliczania rachunków za wodę.
Zawiera endpointy do zarządzania danymi i generowania rachunków.
"""

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional
from pathlib import Path
from datetime import datetime

from db import get_db, init_db
from models import Local, Reading, Invoice, Bill
from invoice_reader import load_invoice_from_pdf
from meter_manager import generate_bills_for_period
from gsheets_integration import import_readings_from_sheets, import_locals_from_sheets, import_invoices_from_sheets
import bill_generator

app = FastAPI(
    title="Water Billing System",
    description="System rozliczania rachunków za wodę i ścieki",
    version="1.0.0"
)


@app.on_event("startup")
def startup_event():
    """Inicjalizuje bazę danych przy starcie aplikacji."""
    init_db()


# ========== ENDPOINTY LOKALI ==========

@app.get("/locals/", response_model=List[dict])
def get_locals(db: Session = Depends(get_db)):
    """Pobiera listę wszystkich lokali."""
    locals_list = db.query(Local).all()
    return [{"id": l.id, "water_meter_name": l.water_meter_name, "tenant": l.tenant, "local": l.local} 
            for l in locals_list]


@app.post("/locals/")
def create_local(water_meter_name: str, tenant: str, local: str, db: Session = Depends(get_db)):
    """Tworzy nowy lokal."""
    new_local = Local(
        water_meter_name=water_meter_name,
        tenant=tenant,
        local=local
    )
    db.add(new_local)
    db.commit()
    db.refresh(new_local)
    return {"id": new_local.id, "message": "Lokal utworzony"}


# ========== ENDPOINTY ODCZYTÓW ==========

@app.get("/readings/", response_model=List[dict])
def get_readings(db: Session = Depends(get_db)):
    """Pobiera listę wszystkich odczytów."""
    readings = db.query(Reading).order_by(desc(Reading.data)).all()
    return [{
        "data": r.data,
        "water_meter_main": r.water_meter_main,
        "water_meter_5": r.water_meter_5,
        "water_meter_5b": r.water_meter_5b
    } for r in readings]


@app.post("/readings/")
def create_reading(
    data: str,
    water_meter_main: float,
    water_meter_5: int,
    water_meter_5b: int,
    db: Session = Depends(get_db)
):
    """Tworzy nowy odczyt liczników."""
    existing = db.query(Reading).filter(Reading.data == data).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Odczyt dla okresu {data} już istnieje")
    
    # Zaokrąglij water_meter_main do 2 miejsc po przecinku
    new_reading = Reading(
        data=data,
        water_meter_main=round(float(water_meter_main), 2),
        water_meter_5=water_meter_5,
        water_meter_5b=water_meter_5b
    )
    db.add(new_reading)
    db.commit()
    db.refresh(new_reading)
    return {"message": "Odczyt utworzony", "data": data}


# ========== ENDPOINTY FAKTUR ==========

@app.get("/invoices/", response_model=List[dict])
def get_invoices(db: Session = Depends(get_db)):
    """Pobiera listę wszystkich faktur."""
    invoices = db.query(Invoice).order_by(desc(Invoice.data)).all()
    return [{
        "id": i.id,
        "data": i.data,
        "invoice_number": i.invoice_number,
        "usage": i.usage,
        "water_cost_m3": i.water_cost_m3,
        "sewage_cost_m3": i.sewage_cost_m3,
        "gross_sum": i.gross_sum
    } for i in invoices]


@app.post("/invoices/")
def create_invoice(
    data: str,
    usage: float,
    water_cost_m3: float,
    sewage_cost_m3: float,
    nr_of_subscription: int,
    water_subscr_cost: float,
    sewage_subscr_cost: float,
    vat: float,
    period_start: str,
    period_stop: str,
    invoice_number: str,
    gross_sum: float,
    db: Session = Depends(get_db)
):
    """Dodaje fakturę ręcznie do bazy danych.
    Może być wiele faktur dla tego samego okresu (data) w przypadku podwyżki kosztów."""
    
    # Konwertuj daty
    try:
        period_start_date = datetime.strptime(period_start, "%Y-%m-%d").date()
        period_stop_date = datetime.strptime(period_stop, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Nieprawidłowy format daty. Użyj YYYY-MM-DD")
    
    # Zaokrąglij wszystkie wartości Float do 2 miejsc po przecinku
    # Stwórz nową fakturę
    new_invoice = Invoice(
        data=data,
        usage=round(float(usage), 2),
        water_cost_m3=round(float(water_cost_m3), 2),
        sewage_cost_m3=round(float(sewage_cost_m3), 2),
        nr_of_subscription=nr_of_subscription,
        water_subscr_cost=round(float(water_subscr_cost), 2),
        sewage_subscr_cost=round(float(sewage_subscr_cost), 2),
        vat=round(float(vat), 2),
        period_start=period_start_date,
        period_stop=period_stop_date,
        invoice_number=invoice_number,
        gross_sum=round(float(gross_sum), 2)
    )
    
    db.add(new_invoice)
    db.commit()
    db.refresh(new_invoice)
    
    return {
        "message": "Faktura dodana",
        "id": new_invoice.id,
        "invoice_number": new_invoice.invoice_number,
        "data": new_invoice.data
    }


@app.post("/invoices/upload")
async def upload_invoice(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Wczytuje fakturę PDF z pliku."""
    # Zapisuj plik tymczasowo
    upload_folder = Path("invoices_raw")
    upload_folder.mkdir(exist_ok=True)
    
    file_path = upload_folder / file.filename
    
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    # Wczytaj fakturę
    invoice = load_invoice_from_pdf(db, str(file_path))
    
    if not invoice:
        raise HTTPException(status_code=400, detail="Nie udało się wczytać faktury")
    
    return {"message": "Faktura wczytana", "invoice_number": invoice.invoice_number}


# ========== ENDPOINTY RACHUNKÓW ==========

@app.get("/bills/", response_model=List[dict])
def get_bills(db: Session = Depends(get_db)):
    """Pobiera listę wszystkich rachunków."""
    bills = db.query(Bill).order_by(desc(Bill.data)).all()
    return [{
        "id": b.id,
        "data": b.data,
        "local": b.local,
        "usage_m3": b.usage_m3,
        "cost_water": b.cost_water,
        "cost_sewage": b.cost_sewage,
        "abonament_total": b.abonament_total,
        "net_sum": b.net_sum,
        "gross_sum": b.gross_sum,
        "pdf_path": b.pdf_path
    } for b in bills]


@app.get("/bills/period/{period}", response_model=List[dict])
def get_bills_for_period(period: str, db: Session = Depends(get_db)):
    """Pobiera rachunki dla danego okresu."""
    bills = db.query(Bill).filter(Bill.data == period).all()
    return [{
        "id": b.id,
        "data": b.data,
        "local": b.local,
        "usage_m3": b.usage_m3,
        "gross_sum": b.gross_sum
    } for b in bills]


@app.post("/bills/generate/{period}")
def generate_bills(period: str, db: Session = Depends(get_db)):
    """
    Generuje rachunki dla danego okresu.
    Wymaga obecności faktury i odczytów dla tego okresu.
    """
    try:
        # Sprawdź czy rachunki już istnieją
        existing = db.query(Bill).filter(Bill.data == period).first()
        if existing:
            return {"message": f"Rachunki dla okresu {period} już istnieją. Użyj /bills/regenerate/{period}"}
        
        # Wygeneruj rachunki
        bills = generate_bills_for_period(db, period)
        
        # Wygeneruj pliki PDF
        pdf_files = bill_generator.generate_all_bills_for_period(db, period)
        
        return {
            "message": "Rachunki wygenerowane",
            "period": period,
            "bills_count": len(bills),
            "pdf_files": pdf_files
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/bills/regenerate/{period}")
def regenerate_bills(period: str, db: Session = Depends(get_db)):
    """Ponownie generuje rachunki i pliki PDF dla danego okresu."""
    # Usuń stare rachunki
    bills = db.query(Bill).filter(Bill.data == period).all()
    for bill in bills:
        # Usuń plik PDF jeśli istnieje
        if bill.pdf_path and Path(bill.pdf_path).exists():
            Path(bill.pdf_path).unlink()
        db.delete(bill)
    db.commit()
    
    try:
        # Wygeneruj nowe rachunki
        bills = generate_bills_for_period(db, period)
        
        # Wygeneruj pliki PDF
        pdf_files = bill_generator.generate_all_bills_for_period(db, period)
        
        return {
            "message": "Rachunki ponownie wygenerowane",
            "period": period,
            "bills_count": len(bills),
            "pdf_files": pdf_files
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/bills/generate-all")
def generate_all_bills(db: Session = Depends(get_db)):
    """
    Generuje wszystkie możliwe rachunki dla wszystkich okresów,
    które mają faktury i odczyty.
    Generuje TYLKO brakujące rachunki (nie usuwa istniejących).
    """
    try:
        result = bill_generator.generate_all_possible_bills(db)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Błąd generowania rachunków: {str(e)}")


@app.post("/bills/regenerate-all")
def regenerate_all_bills(db: Session = Depends(get_db)):
    """
    Regeneruje WSZYSTKIE rachunki - usuwa istniejące i generuje na nowo.
    Użyj tego endpointu po zmianach w logice obliczeń (np. poprawkach błędów).
    
    Wykonuje:
    1. Usuwa wszystkie istniejące rachunki z bazy danych
    2. Usuwa wszystkie pliki PDF rachunków
    3. Generuje wszystkie możliwe rachunki dla okresów z fakturami i odczytami
    4. Generuje pliki PDF dla wszystkich wygenerowanych rachunków
    """
    try:
        # 1. Usuń wszystkie istniejące rachunki
        all_bills = db.query(Bill).all()
        deleted_count = 0
        
        for bill in all_bills:
            # Usuń plik PDF jeśli istnieje
            if bill.pdf_path and Path(bill.pdf_path).exists():
                try:
                    Path(bill.pdf_path).unlink()
                except Exception as e:
                    print(f"[WARNING] Nie udalo sie usunac pliku {bill.pdf_path}: {e}")
            db.delete(bill)
            deleted_count += 1
        
        db.commit()
        
        if deleted_count > 0:
            print(f"[INFO] Usunieto {deleted_count} istniejących rachunków")
        
        # 2. Wygeneruj wszystkie rachunki na nowo
        result = bill_generator.generate_all_possible_bills(db)
        
        return {
            "message": "Wszystkie rachunki zregenerowane",
            "deleted_bills": deleted_count,
            "regenerated_periods": result.get("periods_processed", 0),
            "bills_generated": result.get("bills_generated", 0),
            "pdfs_generated": result.get("pdfs_generated", 0),
            "errors": result.get("errors", []),
            "processed_periods": result.get("processed_periods", [])
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Błąd regenerowania rachunków: {str(e)}")


@app.get("/bills/download/{bill_id}")
def download_bill(bill_id: int, db: Session = Depends(get_db)):
    """Pobiera plik PDF rachunku."""
    bill = db.query(Bill).filter(Bill.id == bill_id).first()
    
    if not bill:
        raise HTTPException(status_code=404, detail="Rachunek nie znaleziony")
    
    if not bill.pdf_path or not Path(bill.pdf_path).exists():
        # Wygeneruj plik jeśli nie istnieje
        bill.pdf_path = bill_generator.generate_bill_pdf(db, bill)
        db.commit()
    
    return FileResponse(bill.pdf_path, media_type="application/pdf")


@app.delete("/bills/{bill_id}")
def delete_bill(bill_id: int, db: Session = Depends(get_db)):
    """Usuwa pojedynczy rachunek po ID."""
    bill = db.query(Bill).filter(Bill.id == bill_id).first()
    
    if not bill:
        raise HTTPException(status_code=404, detail="Rachunek nie znaleziony")
    
    # Usuń plik PDF jeśli istnieje
    if bill.pdf_path and Path(bill.pdf_path).exists():
        Path(bill.pdf_path).unlink()
    
    db.delete(bill)
    db.commit()
    
    return {
        "message": "Rachunek usunięty",
        "id": bill_id,
        "period": bill.data,
        "local": bill.local
    }


@app.delete("/bills/period/{period}")
def delete_bills_for_period(period: str, db: Session = Depends(get_db)):
    """Usuwa wszystkie rachunki dla danego okresu."""
    bills = db.query(Bill).filter(Bill.data == period).all()
    
    if not bills:
        return {"message": f"Brak rachunków dla okresu {period}", "deleted_count": 0}
    
    deleted_ids = []
    for bill in bills:
        # Usuń plik PDF jeśli istnieje
        if bill.pdf_path and Path(bill.pdf_path).exists():
            Path(bill.pdf_path).unlink()
        
        deleted_ids.append(bill.id)
        db.delete(bill)
    
    db.commit()
    
    return {
        "message": f"Usunięto {len(bills)} rachunków dla okresu {period}",
        "period": period,
        "deleted_count": len(bills),
        "deleted_ids": deleted_ids
    }


@app.delete("/bills/")
def delete_all_bills(db: Session = Depends(get_db)):
    """Usuwa wszystkie rachunki z bazy danych."""
    bills = db.query(Bill).all()
    
    if not bills:
        return {"message": "Brak rachunków w bazie", "deleted_count": 0}
    
    deleted_count = 0
    for bill in bills:
        # Usuń plik PDF jeśli istnieje
        if bill.pdf_path and Path(bill.pdf_path).exists():
            Path(bill.pdf_path).unlink()
        
        db.delete(bill)
        deleted_count += 1
    
    db.commit()
    
    return {
        "message": f"Usunięto wszystkie rachunki ({deleted_count})",
        "deleted_count": deleted_count
    }


# ========== ENDPOINTY GOOGLE SHEETS ==========

@app.post("/import/readings")
def import_readings(
    credentials_path: str,
    spreadsheet_id: str,
    sheet_name: str = "Odczyty",
    db: Session = Depends(get_db)
):
    """
    Importuje odczyty liczników z Google Sheets.
    
    Wymaga:
    - credentials_path: Ścieżka do pliku JSON z poświadczeniami Google Service Account
    - spreadsheet_id: ID arkusza (z URL: https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit)
    - sheet_name: Nazwa arkusza (domyślnie "Odczyty")
    """
    try:
        result = import_readings_from_sheets(
            db=db,
            credentials_path=credentials_path,
            spreadsheet_id=spreadsheet_id,
            sheet_name=sheet_name
        )
        return {
            "message": "Import zakończony",
            "imported": result["imported"],
            "skipped": result["skipped"],
            "errors": result["errors"],
            "total": result["total"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Błąd importu: {str(e)}")


@app.post("/import/locals")
def import_locals(
    credentials_path: str,
    spreadsheet_id: str,
    sheet_name: str = "Lokale",
    db: Session = Depends(get_db)
):
    """
    Importuje lokale z Google Sheets.
    
    Wymaga:
    - credentials_path: Ścieżka do pliku JSON z poświadczeniami Google Service Account
    - spreadsheet_id: ID arkusza
    - sheet_name: Nazwa arkusza (domyślnie "Lokale")
    """
    try:
        result = import_locals_from_sheets(
            db=db,
            credentials_path=credentials_path,
            spreadsheet_id=spreadsheet_id,
            sheet_name=sheet_name
        )
        return {
            "message": "Import zakończony",
            "imported": result["imported"],
            "skipped": result["skipped"],
            "errors": result["errors"],
            "total": result["total"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Błąd importu: {str(e)}")


@app.post("/import/invoices")
def import_invoices(
    credentials_path: str,
    spreadsheet_id: str,
    sheet_name: str = "Faktury",
    db: Session = Depends(get_db)
):
    """
    Importuje faktury z Google Sheets.
    
    Wymaga:
    - credentials_path: Ścieżka do pliku JSON z poświadczeniami Google Service Account
    - spreadsheet_id: ID arkusza
    - sheet_name: Nazwa arkusza (domyślnie "Faktury")
    """
    try:
        result = import_invoices_from_sheets(
            db=db,
            credentials_path=credentials_path,
            spreadsheet_id=spreadsheet_id,
            sheet_name=sheet_name
        )
        return {
            "message": "Import zakończony",
            "imported": result["imported"],
            "skipped": result["skipped"],
            "errors": result["errors"],
            "total": result["total"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Błąd importu: {str(e)}")


# ========== ENDPOINTY POMOCNICZE ==========

@app.get("/")
def root():
    """Strona główna z dokumentacją API."""
    return {
        "message": "Water Billing System API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "locals": "/locals/",
            "readings": "/readings/",
            "invoices": "/invoices/",
            "create_invoice": "POST /invoices/ (ręczne dodawanie)",
            "upload_invoice": "POST /invoices/upload (z pliku PDF)",
            "bills": "/bills/",
            "generate_bills": "/bills/generate/{period}",
            "regenerate_bills": "POST /bills/regenerate/{period} (ponownie generuje dla okresu)",
            "generate_all_bills": "POST /bills/generate-all (generuje tylko brakujące)",
            "regenerate_all_bills": "POST /bills/regenerate-all (usuwa wszystkie i generuje na nowo)",
            "download_bill": "/bills/download/{bill_id}",
            "delete_bill": "DELETE /bills/{bill_id}",
            "delete_period_bills": "DELETE /bills/period/{period}",
            "delete_all_bills": "DELETE /bills/",
            "import_readings": "POST /import/readings (z Google Sheets)",
            "import_locals": "POST /import/locals (z Google Sheets)",
            "import_invoices": "POST /import/invoices (z Google Sheets)"
        }
    }


@app.post("/load_sample_data")
def load_sample_data(db: Session = Depends(get_db)):
    """Ładuje przykładowe dane do bazy."""
    # Sprawdź czy dane już istnieją
    if db.query(Local).first():
        return {"message": "Dane już istnieją w bazie"}
    
    # Dodaj lokale
    locals_data = [
        Local(water_meter_name="water_meter_5", tenant="Jan Kowalski", local="gora"),
        Local(water_meter_name="water_meter_5b", tenant="Anna Nowak", local="gabinet"),
        Local(water_meter_name="water_meter_5a", tenant="Piotr Wiśniewski", local="dol"),
    ]
    
    for local in locals_data:
        db.add(local)
    
    db.commit()
    
    return {"message": "Przykładowe dane załadowane (tylko lokale)"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

