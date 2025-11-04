"""
Główny moduł aplikacji FastAPI dla systemu rozliczania rachunków za wodę.
Zawiera endpointy do zarządzania danymi i generowania rachunków.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Body
from typing import Dict, Any, List, Optional
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from pathlib import Path
from datetime import datetime

from app.core.database import get_db, init_db
from app.models.water import Local, Reading, Invoice, Bill
from app.services.water.invoice_reader import load_invoice_from_pdf
from app.services.water.meter_manager import generate_bills_for_period
from app.integrations.google_sheets import import_readings_from_sheets, import_locals_from_sheets, import_invoices_from_sheets
from app.services.water import bill_generator
from app.api.routes.gas import router as gas_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Zarządzanie cyklem życia aplikacji - inicjalizacja i zamknięcie."""
    # Startup - inicjalizacja bazy danych
    init_db()
    yield
    # Shutdown - tutaj można dodać czyszczenie zasobów jeśli potrzeba


app = FastAPI(
    title="Water Billing System",
    description="System rozliczania rachunków za wodę i ścieki",
    version="1.0.0",
    lifespan=lifespan
)

# CORS dla frontendu
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # W produkcji ograniczyć do konkretnych domen
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serwowanie plików statycznych
static_dir = Path("app/static")
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Rejestracja routerów dla mediów
app.include_router(gas_router)  # /api/gas/*


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


@app.delete("/locals/{local_id}")
def delete_local(local_id: int, db: Session = Depends(get_db)):
    """Usuwa lokal po ID. Usuwa również wszystkie powiązane rachunki."""
    local = db.query(Local).filter(Local.id == local_id).first()
    
    if not local:
        raise HTTPException(status_code=404, detail="Lokal nie znaleziony")
    
    # Usuń wszystkie rachunki powiązane z tym lokalem
    bills = db.query(Bill).filter(Bill.local_id == local_id).all()
    for bill in bills:
        # Usuń plik PDF jeśli istnieje
        if bill.pdf_path and Path(bill.pdf_path).exists():
            Path(bill.pdf_path).unlink()
        db.delete(bill)
    
    # Usuń również rachunki gazu
    from app.models.gas import GasBill
    gas_bills = db.query(GasBill).filter(GasBill.local_id == local_id).all()
    for gas_bill in gas_bills:
        if gas_bill.pdf_path and Path(gas_bill.pdf_path).exists():
            Path(gas_bill.pdf_path).unlink()
        db.delete(gas_bill)
    
    db.delete(local)
    db.commit()
    
    return {
        "message": "Lokal usunięty",
        "id": local_id,
        "water_meter_name": local.water_meter_name,
        "deleted_bills_count": len(bills) + len(gas_bills)
    }


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


@app.get("/readings/{period}")
def get_reading(period: str, db: Session = Depends(get_db)):
    """Pobiera pojedynczy odczyt po okresie."""
    reading = db.query(Reading).filter(Reading.data == period).first()
    
    if not reading:
        raise HTTPException(status_code=404, detail="Odczyt nie znaleziony")
    
    return {
        "data": reading.data,
        "water_meter_main": reading.water_meter_main,
        "water_meter_5": reading.water_meter_5,
        "water_meter_5b": reading.water_meter_5b
    }


@app.put("/readings/{period}")
def update_reading(
    period: str,
    water_meter_main: float,
    water_meter_5: int,
    water_meter_5b: int,
    db: Session = Depends(get_db)
):
    """Aktualizuje odczyt po okresie."""
    reading = db.query(Reading).filter(Reading.data == period).first()
    
    if not reading:
        raise HTTPException(status_code=404, detail="Odczyt nie znaleziony")
    
    reading.water_meter_main = round(float(water_meter_main), 2)
    reading.water_meter_5 = int(water_meter_5)
    reading.water_meter_5b = int(water_meter_5b)
    
    db.commit()
    db.refresh(reading)
    
    return {
        "message": "Odczyt zaktualizowany",
        "data": reading.data
    }


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


@app.delete("/readings/{period}")
def delete_reading(period: str, db: Session = Depends(get_db)):
    """Usuwa odczyt dla danego okresu. Usuwa również wszystkie rachunki dla tego okresu."""
    reading = db.query(Reading).filter(Reading.data == period).first()
    
    if not reading:
        raise HTTPException(status_code=404, detail=f"Odczyt dla okresu {period} nie znaleziony")
    
    # Usuń wszystkie rachunki dla tego okresu
    bills = db.query(Bill).filter(Bill.reading_id == period).all()
    deleted_bills_count = 0
    for bill in bills:
        # Usuń plik PDF jeśli istnieje
        if bill.pdf_path and Path(bill.pdf_path).exists():
            Path(bill.pdf_path).unlink()
        db.delete(bill)
        deleted_bills_count += 1
    
    db.delete(reading)
    db.commit()
    
    return {
        "message": f"Odczyt dla okresu {period} usunięty",
        "period": period,
        "deleted_bills_count": deleted_bills_count
    }


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


@app.post("/invoices/parse")
async def parse_invoice(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Parsuje fakturę PDF i zwraca dane do weryfikacji.
    NIE zapisuje do bazy danych!
    """
    from invoice_reader import extract_text_from_pdf, parse_invoice_data
    from datetime import datetime
    import os
    
    # Zapisuj plik tymczasowo
    upload_folder = Path("invoices_raw")
    upload_folder.mkdir(exist_ok=True)
    
    file_path = upload_folder / file.filename
    
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    # Wczytaj tekst z PDF
    text = extract_text_from_pdf(str(file_path))
    if not text:
        raise HTTPException(status_code=400, detail="Nie udało się wczytać tekstu z pliku PDF")
    
    # Parsuj dane z faktury
    invoice_data = parse_invoice_data(text)
    
    if not invoice_data:
        raise HTTPException(status_code=400, detail="Nie udało się sparsować danych z faktury")
    
    # Określ okres rozliczeniowy
    period = None
    if '_extracted_period' in invoice_data:
        period = invoice_data['_extracted_period']
    else:
        # Próbuj wyciągnąć z nazwy pliku
        from invoice_reader import parse_period_from_filename
        period = parse_period_from_filename(os.path.basename(file_path))
        if not period and 'period_start' in invoice_data:
            period_start = invoice_data['period_start']
            if isinstance(period_start, datetime):
                period = f"{period_start.year}-{period_start.month:02d}"
    
    # Dodaj okres do danych
    if period:
        invoice_data['data'] = period
    
    # Konwertuj daty na stringi (dla JSON)
    if 'period_start' in invoice_data and isinstance(invoice_data['period_start'], datetime):
        invoice_data['period_start'] = invoice_data['period_start'].strftime('%Y-%m-%d')
    if 'period_stop' in invoice_data and isinstance(invoice_data['period_stop'], datetime):
        invoice_data['period_stop'] = invoice_data['period_stop'].strftime('%Y-%m-%d')
    
    # Usuń pomocnicze pola które nie są potrzebne w formularzu
    invoice_data.pop('_extracted_period', None)
    invoice_data.pop('meter_readings', None)
    
    return invoice_data


@app.post("/invoices/upload")
async def upload_invoice(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Wczytuje fakturę PDF z pliku (DEPRECATED - użyj /invoices/parse + /invoices/verify)."""
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


@app.post("/invoices/verify")
def verify_and_save_invoice(
    invoice_data: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db)
):
    """
    Zapisuje fakturę po weryfikacji przez użytkownika.
    Wywoływane z dashboardu po zatwierdzeniu.
    """
    from datetime import datetime
    
    # Walidacja wymaganych pól
    required_fields = ['data', 'usage', 'water_cost_m3', 'sewage_cost_m3', 
                      'nr_of_subscription', 'water_subscr_cost', 'sewage_subscr_cost',
                      'vat', 'period_start', 'period_stop', 'invoice_number', 'gross_sum']
    
    missing_fields = [field for field in required_fields if field not in invoice_data]
    if missing_fields:
        raise HTTPException(status_code=400, detail=f"Brakuje wymaganych pól: {', '.join(missing_fields)}")
    
    # Konwertuj daty
    try:
        period_start_date = datetime.strptime(invoice_data['period_start'], "%Y-%m-%d").date()
        period_stop_date = datetime.strptime(invoice_data['period_stop'], "%Y-%m-%d").date()
    except (ValueError, TypeError) as e:
        raise HTTPException(status_code=400, detail=f"Nieprawidłowy format daty: {e}")
    
    # Zaokrąglij wszystkie wartości Float do 2 miejsc po przecinku
    new_invoice = Invoice(
        data=invoice_data['data'],
        usage=round(float(invoice_data['usage']), 2),
        water_cost_m3=round(float(invoice_data['water_cost_m3']), 2),
        sewage_cost_m3=round(float(invoice_data['sewage_cost_m3']), 2),
        nr_of_subscription=int(invoice_data['nr_of_subscription']),
        water_subscr_cost=round(float(invoice_data['water_subscr_cost']), 2),
        sewage_subscr_cost=round(float(invoice_data['sewage_subscr_cost']), 2),
        vat=round(float(invoice_data['vat']), 2),
        period_start=period_start_date,
        period_stop=period_stop_date,
        invoice_number=invoice_data['invoice_number'],
        gross_sum=round(float(invoice_data['gross_sum']), 2)
    )
    
    db.add(new_invoice)
    db.commit()
    db.refresh(new_invoice)
    
    return {
        "message": "Faktura zapisana",
        "id": new_invoice.id,
        "invoice_number": new_invoice.invoice_number,
        "data": new_invoice.data
    }


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


@app.get("/invoices/{invoice_id}")
def get_invoice(invoice_id: int, db: Session = Depends(get_db)):
    """Pobiera pojedynczą fakturę po ID."""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    
    if not invoice:
        raise HTTPException(status_code=404, detail="Faktura nie znaleziona")
    
    return {
        "id": invoice.id,
        "data": invoice.data,
        "usage": invoice.usage,
        "water_cost_m3": invoice.water_cost_m3,
        "sewage_cost_m3": invoice.sewage_cost_m3,
        "nr_of_subscription": invoice.nr_of_subscription,
        "water_subscr_cost": invoice.water_subscr_cost,
        "sewage_subscr_cost": invoice.sewage_subscr_cost,
        "vat": invoice.vat,
        "period_start": invoice.period_start.isoformat() if invoice.period_start else None,
        "period_stop": invoice.period_stop.isoformat() if invoice.period_stop else None,
        "invoice_number": invoice.invoice_number,
        "gross_sum": invoice.gross_sum
    }


@app.put("/invoices/{invoice_id}")
def update_invoice(
    invoice_id: int,
    invoice_data: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db)
):
    """Aktualizuje fakturę po ID."""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    
    if not invoice:
        raise HTTPException(status_code=404, detail="Faktura nie znaleziona")
    
    # Konwertuj daty jeśli są podane
    if 'period_start' in invoice_data:
        try:
            invoice_data['period_start'] = datetime.strptime(invoice_data['period_start'], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Nieprawidłowy format daty period_start")
    
    if 'period_stop' in invoice_data:
        try:
            invoice_data['period_stop'] = datetime.strptime(invoice_data['period_stop'], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Nieprawidłowy format daty period_stop")
    
    # Aktualizuj pola
    for key, value in invoice_data.items():
        if hasattr(invoice, key):
            if isinstance(value, float):
                value = round(value, 2)
            setattr(invoice, key, value)
    
    db.commit()
    db.refresh(invoice)
    
    return {
        "message": "Faktura zaktualizowana",
        "id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "data": invoice.data
    }


@app.delete("/invoices/{invoice_id}")
def delete_invoice(invoice_id: int, db: Session = Depends(get_db)):
    """Usuwa fakturę po ID. Usuwa również wszystkie rachunki dla okresu tej faktury."""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    
    if not invoice:
        raise HTTPException(status_code=404, detail="Faktura nie znaleziona")
    
    period = invoice.data
    
    # Usuń wszystkie rachunki dla tego okresu (może być wiele faktur dla tego samego okresu)
    # Sprawdź czy są jeszcze inne faktury dla tego okresu
    other_invoices = db.query(Invoice).filter(
        Invoice.data == period,
        Invoice.id != invoice_id
    ).count()
    
    deleted_bills_count = 0
    if other_invoices == 0:
        # Jeśli to ostatnia faktura dla tego okresu, usuń wszystkie rachunki
        bills = db.query(Bill).filter(Bill.data == period).all()
        for bill in bills:
            # Usuń plik PDF jeśli istnieje
            if bill.pdf_path and Path(bill.pdf_path).exists():
                Path(bill.pdf_path).unlink()
            db.delete(bill)
            deleted_bills_count += 1
    
    db.delete(invoice)
    db.commit()
    
    return {
        "message": "Faktura usunięta",
        "id": invoice_id,
        "invoice_number": invoice.invoice_number,
        "period": period,
        "deleted_bills_count": deleted_bills_count
    }


# ========== ENDPOINTY RACHUNKÓW ==========

@app.get("/bills/", response_model=List[dict])
def get_bills(db: Session = Depends(get_db)):
    """Pobiera listę wszystkich rachunków."""
    bills = db.query(Bill).order_by(desc(Bill.data)).all()
    return [{
        "id": b.id,
        "data": b.data,
        "local": b.local,
        "reading_value": b.reading_value,
        "usage_m3": b.usage_m3,
        "cost_water": b.cost_water,
        "cost_sewage": b.cost_sewage,
        "cost_usage_total": b.cost_usage_total,
        "abonament_water_share": b.abonament_water_share,
        "abonament_sewage_share": b.abonament_sewage_share,
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


@app.get("/bills/{bill_id}")
def get_bill(bill_id: int, db: Session = Depends(get_db)):
    """Pobiera pojedynczy rachunek po ID."""
    bill = db.query(Bill).filter(Bill.id == bill_id).first()
    
    if not bill:
        raise HTTPException(status_code=404, detail="Rachunek nie znaleziony")
    
    return {
        "id": bill.id,
        "data": bill.data,
        "local": bill.local,
        "reading_value": bill.reading_value,
        "usage_m3": bill.usage_m3,
        "cost_water": bill.cost_water,
        "cost_sewage": bill.cost_sewage,
        "cost_usage_total": bill.cost_usage_total,
        "abonament_water_share": bill.abonament_water_share,
        "abonament_sewage_share": bill.abonament_sewage_share,
        "abonament_total": bill.abonament_total,
        "net_sum": bill.net_sum,
        "gross_sum": bill.gross_sum,
        "pdf_path": bill.pdf_path
    }


@app.put("/bills/{bill_id}")
def update_bill(
    bill_id: int,
    bill_data: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db)
):
    """Aktualizuje rachunek po ID."""
    bill = db.query(Bill).filter(Bill.id == bill_id).first()
    
    if not bill:
        raise HTTPException(status_code=404, detail="Rachunek nie znaleziony")
    
    # Aktualizuj pola
    for key, value in bill_data.items():
        if hasattr(bill, key):
            if isinstance(value, float):
                value = round(value, 2)
            setattr(bill, key, value)
    
    db.commit()
    db.refresh(bill)
    
    return {
        "message": "Rachunek zaktualizowany",
        "id": bill.id,
        "data": bill.data,
        "local": bill.local
    }


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

@app.get("/", response_class=HTMLResponse)
def root():
    """Strona główna - dashboard."""
    dashboard_path = static_dir / "dashboard.html"
    if dashboard_path.exists():
        return dashboard_path.read_text(encoding="utf-8")
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Water Billing System</title>
        <meta charset="utf-8">
    </head>
    <body>
        <h1>Water Billing System API</h1>
        <p>Dokumentacja API: <a href="/docs">/docs</a></p>
        <p>Dashboard: <a href="/dashboard">/dashboard</a></p>
    </body>
    </html>
    """


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    """Dashboard aplikacji."""
    dashboard_path = static_dir / "dashboard.html"
    if dashboard_path.exists():
        return dashboard_path.read_text(encoding="utf-8")
    return "<h1>Dashboard nie znaleziony. Sprawdź folder static/</h1>"


@app.get("/api/stats")
def get_stats(db: Session = Depends(get_db)):
    """Zwraca statystyki dla dashboardu."""
    stats = {
        "locals_count": db.query(Local).count(),
        "readings_count": db.query(Reading).count(),
        "invoices_count": db.query(Invoice).count(),
        "bills_count": db.query(Bill).count(),
        "latest_period": None,
        "total_gross_sum": 0,
        "periods_with_bills": [],
        "available_periods": []
    }
    
    # Najnowszy okres
    latest_reading = db.query(Reading).order_by(desc(Reading.data)).first()
    if latest_reading:
        stats["latest_period"] = latest_reading.data
    
    # Suma brutto wszystkich rachunków
    total_sum = db.query(func.sum(Bill.gross_sum)).scalar()
    if total_sum:
        stats["total_gross_sum"] = float(total_sum)
    
    # Okresy z rachunkami
    periods = db.query(Bill.data).distinct().order_by(desc(Bill.data)).all()
    stats["periods_with_bills"] = [p[0] for p in periods[:10]]  # Ostatnie 10
    
    # Dostępne okresy (mające zarówno faktury jak i odczyty)
    reading_periods = set(r.data for r in db.query(Reading.data).distinct().all())
    invoice_periods = set(i.data for i in db.query(Invoice.data).distinct().all())
    stats["available_periods"] = sorted(reading_periods & invoice_periods, reverse=True)
    
    return stats


@app.post("/load_sample_data")
def load_sample_data(db: Session = Depends(get_db)):
    """Ładuje przykładowe dane do bazy."""
    # Sprawdź czy dane już istnieją
    if db.query(Local).first():
        return {"message": "Dane już istnieją w bazie"}
    
    # Dodaj lokale
    locals_data = [
        Local(water_meter_name="water_meter_5", tenant="Jan Kowalski", local="gora"),
        Local(water_meter_name="water_meter_5b", tenant="Mikołaj", local="dol"),
        Local(water_meter_name="water_meter_5a", tenant="Bartek", local="gabinet"),
    ]
    
    for local in locals_data:
        db.add(local)
    
    db.commit()
    
    return {"message": "Przykładowe dane załadowane (tylko lokale)"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

