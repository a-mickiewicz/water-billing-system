"""
API endpoints for electricity billing.
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Body
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from typing import List, Optional, Dict, Any
from datetime import datetime, date
from pathlib import Path
from pydantic import BaseModel

from app.core.database import get_db
from app.models.electricity import ElectricityReading, ElectricityBill
from app.models.electricity_invoice import (
    ElectricityInvoice,
    ElectricityInvoiceBlankiet,
    ElectricityInvoiceOdczyt,
    ElectricityInvoiceSprzedazEnergii,
    ElectricityInvoiceOplataDystrybucyjna,
    ElectricityInvoiceRozliczenieOkres
)
from app.models.water import Local
from app.services.electricity.manager import ElectricityBillingManager
from app.services.electricity.calculator import calculate_all_usage, get_previous_reading
from app.services.electricity.cost_calculator import calculate_kwh_cost, calculate_kwh_cost_for_blankiet
from app.services.electricity.invoice_reader import (
    extract_text_from_pdf,
    parse_invoice_data,
    load_invoice_from_pdf,
    save_invoice_after_verification
)

router = APIRouter(prefix="/api/electricity", tags=["electricity"])


class ElectricityReadingCreate(BaseModel):
    """Model for creating electricity reading."""
    data: str
    data_odczytu_licznika: Optional[str] = None  # Format: 'YYYY-MM-DD'
    is_main_meter_single_tariff: bool = False
    main_reading: Optional[float] = None
    main_reading_t1: Optional[float] = None
    main_reading_t2: Optional[float] = None
    is_dol_meter_single_tariff: bool = False
    dol_reading: Optional[float] = None
    dol_reading_t1: Optional[float] = None
    dol_reading_t2: Optional[float] = None
    gabinet_reading: float = 0.0
    local_id: Optional[int] = None


@router.get("/readings")
def get_readings(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Gets list of electricity meter readings."""
    readings = db.query(ElectricityReading).order_by(desc(ElectricityReading.data)).offset(skip).limit(limit).all()
    
    # Map field names from database to format expected by dashboard
    result = []
    for r in readings:
        # Safe value conversion
        main_reading = None
        if r.odczyt_dom is not None:
            try:
                main_reading = float(r.odczyt_dom)
            except (ValueError, TypeError):
                main_reading = None
        
        main_reading_t1 = None
        if r.odczyt_dom_I is not None:
            try:
                main_reading_t1 = float(r.odczyt_dom_I)
            except (ValueError, TypeError):
                main_reading_t1 = None
        
        main_reading_t2 = None
        if r.odczyt_dom_II is not None:
            try:
                main_reading_t2 = float(r.odczyt_dom_II)
            except (ValueError, TypeError):
                main_reading_t2 = None
        
        dol_reading = None
        if r.odczyt_dol is not None:
            try:
                dol_reading = float(r.odczyt_dol)
            except (ValueError, TypeError):
                dol_reading = None
        
        dol_reading_t1 = None
        if r.odczyt_dol_I is not None:
            try:
                dol_reading_t1 = float(r.odczyt_dol_I)
            except (ValueError, TypeError):
                dol_reading_t1 = None
        
        dol_reading_t2 = None
        if r.odczyt_dol_II is not None:
            try:
                dol_reading_t2 = float(r.odczyt_dol_II)
            except (ValueError, TypeError):
                dol_reading_t2 = None
        
        gabinet_reading = 0.0
        if r.odczyt_gabinet is not None:
            try:
                gabinet_reading = float(r.odczyt_gabinet)
            except (ValueError, TypeError):
                gabinet_reading = 0.0
        
        result.append({
            "id": r.id,
            "data": r.data,
            "data_odczytu_licznika": r.data_odczytu_licznika.isoformat() if r.data_odczytu_licznika else None,
            "is_main_meter_single_tariff": bool(r.licznik_dom_jednotaryfowy),
            "main_reading": main_reading,
            "main_reading_t1": main_reading_t1,
            "main_reading_t2": main_reading_t2,
            "is_dol_meter_single_tariff": bool(r.licznik_dol_jednotaryfowy),
            "dol_reading": dol_reading,
            "dol_reading_t1": dol_reading_t1,
            "dol_reading_t2": dol_reading_t2,
            "gabinet_reading": gabinet_reading,
            "is_flagged": bool(r.is_flagged) if hasattr(r, 'is_flagged') else False
        })
    
    return result


@router.get("/readings/{data}/usage")
def get_usage(
    data: str,
    db: Session = Depends(get_db)
):
    """Gets calculated consumption for given period."""
    reading = db.query(ElectricityReading).filter(
        ElectricityReading.data == data
    ).first()
    
    if not reading:
        raise HTTPException(status_code=404, detail=f"No reading for period {data}")
    
    previous = get_previous_reading(db, data)
    usage = calculate_all_usage(reading, previous)
    
    return usage


@router.get("/readings/{data}")
def get_reading(
    data: str,
    db: Session = Depends(get_db)
):
    """Gets reading for specific period."""
    reading = db.query(ElectricityReading).filter(
        ElectricityReading.data == data
    ).first()
    
    if not reading:
        raise HTTPException(status_code=404, detail=f"No reading for period {data}")
    
    # Map field names from database to format expected by dashboard
    return {
        "id": reading.id,
        "data": reading.data,
        "data_odczytu_licznika": reading.data_odczytu_licznika.isoformat() if reading.data_odczytu_licznika else None,
        "is_main_meter_single_tariff": bool(reading.licznik_dom_jednotaryfowy),
        "main_reading": float(reading.odczyt_dom) if reading.odczyt_dom is not None else None,
        "main_reading_t1": float(reading.odczyt_dom_I) if reading.odczyt_dom_I is not None else None,
        "main_reading_t2": float(reading.odczyt_dom_II) if reading.odczyt_dom_II is not None else None,
        "is_dol_meter_single_tariff": bool(reading.licznik_dol_jednotaryfowy),
        "dol_reading": float(reading.odczyt_dol) if reading.odczyt_dol is not None else None,
        "dol_reading_t1": float(reading.odczyt_dol_I) if reading.odczyt_dol_I is not None else None,
        "dol_reading_t2": float(reading.odczyt_dol_II) if reading.odczyt_dol_II is not None else None,
        "gabinet_reading": float(reading.odczyt_gabinet) if reading.odczyt_gabinet is not None else 0.0,
        "is_flagged": bool(reading.is_flagged) if hasattr(reading, 'is_flagged') else False
    }


@router.put("/readings/{data}")
def update_reading(
    data: str,
    reading_data: ElectricityReadingCreate,
    db: Session = Depends(get_db)
):
    """Updates reading for given period."""
    reading = db.query(ElectricityReading).filter(
        ElectricityReading.data == data
    ).first()
    
    if not reading:
        raise HTTPException(status_code=404, detail=f"No reading for period {data}")
    
    # Map field names from dashboard to database names
    licznik_dom_jednotaryfowy = reading_data.is_main_meter_single_tariff
    odczyt_dom = reading_data.main_reading
    odczyt_dom_I = reading_data.main_reading_t1
    odczyt_dom_II = reading_data.main_reading_t2
    
    licznik_dol_jednotaryfowy = reading_data.is_dol_meter_single_tariff
    odczyt_dol = reading_data.dol_reading
    odczyt_dol_I = reading_data.dol_reading_t1
    odczyt_dol_II = reading_data.dol_reading_t2
    
    odczyt_gabinet = reading_data.gabinet_reading or 0.0
    
    # Validate data
    if licznik_dom_jednotaryfowy:
        if odczyt_dom is None:
            raise HTTPException(status_code=400, detail="Brak odczytu_dom dla licznika jednotaryfowego")
        if odczyt_dom_I is not None or odczyt_dom_II is not None:
            raise HTTPException(status_code=400, detail="Nie można podać odczytów I/II dla licznika jednotaryfowego")
    else:
        if odczyt_dom_I is None or odczyt_dom_II is None:
            raise HTTPException(status_code=400, detail="Brak odczytów I/II dla licznika dwutaryfowego")
        if odczyt_dom is not None:
            raise HTTPException(status_code=400, detail="Nie można podać odczytu_dom dla licznika dwutaryfowego")
    
    if licznik_dol_jednotaryfowy:
        if odczyt_dol is None:
            raise HTTPException(status_code=400, detail="Brak odczytu_dol dla licznika jednotaryfowego")
        if odczyt_dol_I is not None or odczyt_dol_II is not None:
            raise HTTPException(status_code=400, detail="Nie można podać odczytów I/II dla licznika jednotaryfowego")
    else:
        if odczyt_dol_I is None or odczyt_dol_II is None:
            raise HTTPException(status_code=400, detail="Brak odczytów I/II dla licznika dwutaryfowego")
        if odczyt_dol is not None:
            raise HTTPException(status_code=400, detail="Nie można podać odczytu_dol dla licznika dwutaryfowego")
    
    # Convert data_odczytu_licznika from string to date
    data_odczytu_licznika = None
    if reading_data.data_odczytu_licznika:
        try:
            data_odczytu_licznika = datetime.strptime(reading_data.data_odczytu_licznika, '%Y-%m-%d').date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Nieprawidłowy format daty odczytu licznika. Oczekiwany format: YYYY-MM-DD")
    
    # Update reading
    reading.licznik_dom_jednotaryfowy = licznik_dom_jednotaryfowy
    reading.odczyt_dom = odczyt_dom
    reading.odczyt_dom_I = odczyt_dom_I
    reading.odczyt_dom_II = odczyt_dom_II
    reading.licznik_dol_jednotaryfowy = licznik_dol_jednotaryfowy
    reading.odczyt_dol = odczyt_dol
    reading.odczyt_dol_I = odczyt_dol_I
    reading.odczyt_dol_II = odczyt_dol_II
    reading.odczyt_gabinet = odczyt_gabinet
    reading.data_odczytu_licznika = data_odczytu_licznika
    
    db.commit()
    db.refresh(reading)
    
    # Return updated reading in format expected by dashboard
    return {
        "id": reading.id,
        "data": reading.data,
        "data_odczytu_licznika": reading.data_odczytu_licznika.isoformat() if reading.data_odczytu_licznika else None,
        "is_main_meter_single_tariff": bool(reading.licznik_dom_jednotaryfowy),
        "main_reading": float(reading.odczyt_dom) if reading.odczyt_dom is not None else None,
        "main_reading_t1": float(reading.odczyt_dom_I) if reading.odczyt_dom_I is not None else None,
        "main_reading_t2": float(reading.odczyt_dom_II) if reading.odczyt_dom_II is not None else None,
        "is_dol_meter_single_tariff": bool(reading.licznik_dol_jednotaryfowy),
        "dol_reading": float(reading.odczyt_dol) if reading.odczyt_dol is not None else None,
        "dol_reading_t1": float(reading.odczyt_dol_I) if reading.odczyt_dol_I is not None else None,
        "dol_reading_t2": float(reading.odczyt_dol_II) if reading.odczyt_dol_II is not None else None,
        "gabinet_reading": float(reading.odczyt_gabinet) if reading.odczyt_gabinet is not None else 0.0,
        "is_flagged": bool(reading.is_flagged) if hasattr(reading, 'is_flagged') else False
    }


@router.delete("/readings/{data}")
def delete_reading(
    data: str,
    db: Session = Depends(get_db)
):
    """Usuwa odczyt dla danego okresu. Usuwa również wszystkie rachunki dla tego okresu."""
    reading = db.query(ElectricityReading).filter(
        ElectricityReading.data == data
    ).first()
    
    if not reading:
        raise HTTPException(status_code=404, detail=f"Brak odczytu dla okresu {data}")
    
    # Usuń wszystkie rachunki dla tego okresu
    bills = db.query(ElectricityBill).filter(ElectricityBill.data == data).all()
    deleted_bills_count = len(bills)
    
    for bill in bills:
        # Delete PDF file if exists
        if hasattr(bill, 'pdf_path') and bill.pdf_path:
            from pathlib import Path
            if Path(bill.pdf_path).exists():
                Path(bill.pdf_path).unlink()
        db.delete(bill)
    
    db.delete(reading)
    db.commit()
    
    return {
        "message": f"Odczyt dla okresu {data} został usunięty",
        "deleted_bills_count": deleted_bills_count
    }


@router.put("/readings/{data}/flag")
def toggle_reading_flag(
    data: str,
    flag_data: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db)
):
    """Przełącza flagę dla odczytu prądu."""
    reading = db.query(ElectricityReading).filter(
        ElectricityReading.data == data
    ).first()
    
    if not reading:
        raise HTTPException(status_code=404, detail=f"Brak odczytu dla okresu {data}")
    
    # Pobierz wartość flagi z request body (domyślnie True jeśli nie podano)
    is_flagged = flag_data.get('is_flagged', True)
    
    # Zaktualizuj flagę
    if hasattr(reading, 'is_flagged'):
        reading.is_flagged = bool(is_flagged)
    else:
        raise HTTPException(status_code=500, detail="Kolumna is_flagged nie istnieje w modelu")
    
    db.commit()
    db.refresh(reading)
    
    return {
        "message": f"Flaga odczytu dla okresu {data} została zaktualizowana",
        "data": reading.data,
        "is_flagged": bool(reading.is_flagged)
    }


@router.post("/readings")
def create_reading(
    reading_data: ElectricityReadingCreate,
    db: Session = Depends(get_db)
):
    """
    Tworzy nowy odczyt liczników prądu.
    
    Akceptuje dane w formacie JSON z mapowaniem nazw pól:
    - data: Data w formacie 'YYYY-MM'
    - is_main_meter_single_tariff (licznik_dom_jednotaryfowy): True jeśli licznik główny jest jednotaryfowy
    - main_reading (odczyt_dom): Odczyt licznika głównego (jednotaryfowy)
    - main_reading_t1 (odczyt_dom_I): Odczyt licznika głównego - taryfa I (dwutaryfowy)
    - main_reading_t2 (odczyt_dom_II): Odczyt licznika głównego - taryfa II (dwutaryfowy)
    - is_dol_meter_single_tariff (licznik_dol_jednotaryfowy): True jeśli podlicznik DÓŁ jest jednotaryfowy
    - dol_reading (odczyt_dol): Odczyt podlicznika DÓŁ (jednotaryfowy)
    - dol_reading_t1 (odczyt_dol_I): Odczyt podlicznika DÓŁ - taryfa I (dwutaryfowy)
    - dol_reading_t2 (odczyt_dol_II): Odczyt podlicznika DÓŁ - taryfa II (dwutaryfowy)
    - gabinet_reading (odczyt_gabinet): Odczyt podlicznika GABINET (zawsze jednotaryfowy)
    """
    # Map field names from dashboard to database names
    data = reading_data.data
    
    licznik_dom_jednotaryfowy = reading_data.is_main_meter_single_tariff
    odczyt_dom = reading_data.main_reading
    odczyt_dom_I = reading_data.main_reading_t1
    odczyt_dom_II = reading_data.main_reading_t2
    
    licznik_dol_jednotaryfowy = reading_data.is_dol_meter_single_tariff
    odczyt_dol = reading_data.dol_reading
    odczyt_dol_I = reading_data.dol_reading_t1
    odczyt_dol_II = reading_data.dol_reading_t2
    
    odczyt_gabinet = reading_data.gabinet_reading or 0.0
    
    # Convert data_odczytu_licznika from string to date
    data_odczytu_licznika = None
    if reading_data.data_odczytu_licznika:
        try:
            data_odczytu_licznika = datetime.strptime(reading_data.data_odczytu_licznika, '%Y-%m-%d').date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Nieprawidłowy format daty odczytu licznika. Oczekiwany format: YYYY-MM-DD")
    
    # Check if reading already exists
    existing = db.query(ElectricityReading).filter(
        ElectricityReading.data == data
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail=f"Odczyt dla okresu {data} już istnieje")
    
    # Validate data
    if licznik_dom_jednotaryfowy:
        if odczyt_dom is None:
            raise HTTPException(status_code=400, detail="Brak odczytu_dom dla licznika jednotaryfowego")
        if odczyt_dom_I is not None or odczyt_dom_II is not None:
            raise HTTPException(status_code=400, detail="Nie można podać odczytów I/II dla licznika jednotaryfowego")
    else:
        if odczyt_dom_I is None or odczyt_dom_II is None:
            raise HTTPException(status_code=400, detail="Brak odczytów I/II dla licznika dwutaryfowego")
        if odczyt_dom is not None:
            raise HTTPException(status_code=400, detail="Nie można podać odczytu_dom dla licznika dwutaryfowego")
    
    if licznik_dol_jednotaryfowy:
        if odczyt_dol is None:
            raise HTTPException(status_code=400, detail="Brak odczytu_dol dla licznika jednotaryfowego")
        if odczyt_dol_I is not None or odczyt_dol_II is not None:
            raise HTTPException(status_code=400, detail="Nie można podać odczytów I/II dla licznika jednotaryfowego")
    else:
        if odczyt_dol_I is None or odczyt_dol_II is None:
            raise HTTPException(status_code=400, detail="Brak odczytów I/II dla licznika dwutaryfowego")
        if odczyt_dol is not None:
            raise HTTPException(status_code=400, detail="Nie można podać odczytu_dol dla licznika dwutaryfowego")
    
    # Create reading
    reading = ElectricityReading(
        data=data,
        data_odczytu_licznika=data_odczytu_licznika,
        licznik_dom_jednotaryfowy=licznik_dom_jednotaryfowy,
        odczyt_dom=odczyt_dom,
        odczyt_dom_I=odczyt_dom_I,
        odczyt_dom_II=odczyt_dom_II,
        licznik_dol_jednotaryfowy=licznik_dol_jednotaryfowy,
        odczyt_dol=odczyt_dol,
        odczyt_dol_I=odczyt_dol_I,
        odczyt_dol_II=odczyt_dol_II,
        odczyt_gabinet=odczyt_gabinet
    )
    
    db.add(reading)
    db.commit()
    db.refresh(reading)
    
    return reading


@router.get("/invoices")
def get_invoices(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Gets list of electricity invoices."""
    invoices = db.query(ElectricityInvoice).offset(skip).limit(limit).all()
    return invoices


@router.get("/invoices/{data}")
def get_invoice(
    data: str,
    db: Session = Depends(get_db)
):
    """Gets invoice for specific period."""
    invoice = db.query(ElectricityInvoice).filter(
        ElectricityInvoice.data == data
    ).first()
    
    if not invoice:
        raise HTTPException(status_code=404, detail=f"Brak faktury dla okresu {data}")
    
    return invoice


@router.post("/invoices")
def create_invoice(
    data: str,
    invoice_number: str,
    period_start: str,
    period_stop: str,
    usage_kwh: float,
    energy_price_net: float,
    energy_value_net: float,
    energy_vat_amount: float,
    energy_value_gross: float,
    distribution_fees_net: float = 0.0,
    distribution_fees_vat: float = 0.0,
    distribution_fees_gross: float = 0.0,
    vat_rate: float = 0.23,
    vat_amount: float = 0.0,
    total_net_sum: float = 0.0,
    total_gross_sum: float = 0.0,
    amount_to_pay: float = 0.0,
    payment_due_date: str = "",
    db: Session = Depends(get_db)
):
    """Creates new electricity invoice."""
    # Check if invoice already exists
    existing = db.query(ElectricityInvoice).filter(
        ElectricityInvoice.data == data,
        ElectricityInvoice.invoice_number == invoice_number
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Faktura już istnieje")
    
    # Parsuj daty
    period_start_date = datetime.strptime(period_start, "%Y-%m-%d").date()
    period_stop_date = datetime.strptime(period_stop, "%Y-%m-%d").date()
    payment_due_date_obj = datetime.strptime(payment_due_date, "%Y-%m-%d").date() if payment_due_date else period_stop_date
    
    invoice = ElectricityInvoice(
        data=data,
        invoice_number=invoice_number,
        period_start=period_start_date,
        period_stop=period_stop_date,
        usage_kwh=usage_kwh,
        energy_price_net=energy_price_net,
        energy_value_net=energy_value_net,
        energy_vat_amount=energy_vat_amount,
        energy_value_gross=energy_value_gross,
        distribution_fees_net=distribution_fees_net,
        distribution_fees_vat=distribution_fees_vat,
        distribution_fees_gross=distribution_fees_gross,
        vat_rate=vat_rate,
        vat_amount=vat_amount,
        total_net_sum=total_net_sum,
        total_gross_sum=total_gross_sum,
        amount_to_pay=amount_to_pay,
        payment_due_date=payment_due_date_obj
    )
    
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    
    return invoice


@router.post("/invoices/parse")
async def parse_invoice(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Parsuje fakturę PDF i zwraca dane do weryfikacji.
    NIE zapisuje do bazy danych!
    """
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
    
    # Konwertuj daty na stringi (dla JSON)
    if 'period_start' in invoice_data and isinstance(invoice_data['period_start'], datetime):
        invoice_data['period_start'] = invoice_data['period_start'].strftime('%Y-%m-%d')
    if 'period_stop' in invoice_data and isinstance(invoice_data['period_stop'], datetime):
        invoice_data['period_stop'] = invoice_data['period_stop'].strftime('%Y-%m-%d')
    if 'payment_due_date' in invoice_data and isinstance(invoice_data['payment_due_date'], datetime):
        invoice_data['payment_due_date'] = invoice_data['payment_due_date'].strftime('%Y-%m-%d')
    
    # Remove helper fields that are not needed in the form
    invoice_data.pop('_raw_data', None)
    invoice_data.pop('_file_path', None)
    invoice_data.pop('_file_name', None)
    
    return invoice_data


@router.post("/invoices/verify")
def verify_and_save_invoice(
    invoice_data: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db)
):
    """
    Zapisuje fakturę po weryfikacji przez użytkownika.
    Wywoływane z dashboardu po zatwierdzeniu.
    """
    # Walidacja wymaganych pól
    required_fields = ['data', 'invoice_number', 'period_start', 'period_stop', 
                      'usage_kwh', 'energy_price_net', 'energy_value_net', 
                      'energy_vat_amount', 'energy_value_gross', 'total_net_sum',
                      'total_gross_sum', 'amount_to_pay', 'payment_due_date']
    
    missing_fields = [field for field in required_fields if field not in invoice_data]
    if missing_fields:
        raise HTTPException(status_code=400, detail=f"Brakuje wymaganych pól: {', '.join(missing_fields)}")
    
    # Konwertuj daty
    try:
        period_start_date = datetime.strptime(invoice_data['period_start'], "%Y-%m-%d").date()
        period_stop_date = datetime.strptime(invoice_data['period_stop'], "%Y-%m-%d").date()
        payment_due_date = datetime.strptime(invoice_data['payment_due_date'], "%Y-%m-%d").date()
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"Błędny format daty: {e}")
    
    # Przygotuj dane do zapisu
    invoice_dict = {
        'data': invoice_data['data'],
        'invoice_number': invoice_data['invoice_number'],
        'period_start': period_start_date,
        'period_stop': period_stop_date,
        'usage_kwh': float(invoice_data.get('usage_kwh', 0)),
        'energy_price_net': float(invoice_data.get('energy_price_net', 0)),
        'energy_value_net': float(invoice_data.get('energy_value_net', 0)),
        'energy_vat_amount': float(invoice_data.get('energy_vat_amount', 0)),
        'energy_value_gross': float(invoice_data.get('energy_value_gross', 0)),
        'distribution_fees_net': float(invoice_data.get('distribution_fees_net', 0)),
        'distribution_fees_vat': float(invoice_data.get('distribution_fees_vat', 0)),
        'distribution_fees_gross': float(invoice_data.get('distribution_fees_gross', 0)),
        'vat_rate': float(invoice_data.get('vat_rate', 0.23)),
        'vat_amount': float(invoice_data.get('vat_amount', 0)),
        'total_net_sum': float(invoice_data.get('total_net_sum', 0)),
        'total_gross_sum': float(invoice_data.get('total_gross_sum', 0)),
        'amount_to_pay': float(invoice_data.get('amount_to_pay', 0)),
        'payment_due_date': payment_due_date
    }
    
    # Save invoice
    try:
        invoice = save_invoice_after_verification(db, invoice_dict)
        return {
            "message": "Faktura zapisana pomyślnie",
            "invoice_id": invoice.id,
            "invoice_number": invoice.invoice_number
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/bills/")
def get_bills(
    skip: int = 0,
    limit: int = 100,
    data: Optional[str] = None,
    local: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Pobiera listę rachunków za prąd z kosztem 1 kWh."""
    query = db.query(ElectricityBill)
    
    if data:
        query = query.filter(ElectricityBill.data == data)
    if local:
        query = query.filter(ElectricityBill.local == local)
    
    bills = query.offset(skip).limit(limit).all()
    
    # Dodaj koszt 1 kWh dla każdego rachunku
    result = []
    for bill in bills:
        bill_dict = {
            "id": bill.id,
            "data": bill.data,
            "local": bill.local,
            "reading_id": bill.reading_id,
            "invoice_id": bill.invoice_id,
            "local_id": bill.local_id,
            "usage_kwh": bill.usage_kwh,
            "usage_kwh_dzienna": bill.usage_kwh_dzienna,
            "usage_kwh_nocna": bill.usage_kwh_nocna,
            "energy_cost_gross": bill.energy_cost_gross,
            "distribution_cost_gross": bill.distribution_cost_gross,
            "total_net_sum": bill.total_net_sum,
            "total_gross_sum": bill.total_gross_sum,
            "pdf_path": bill.pdf_path,
        }
        
        # Oblicz koszt 1 kWh dla faktury
        if bill.invoice_id:
            koszty_kwh = calculate_kwh_cost(bill.invoice_id, db)
            
            # Find blankiet for bill period
            from app.services.electricity.manager import ElectricityBillingManager
            manager = ElectricityBillingManager()
            blankiet = manager.find_blankiet_for_period(db, bill.invoice_id, bill.data)
            
            # Get invoice to check tariff type
            invoice = db.query(ElectricityInvoice).filter(ElectricityInvoice.id == bill.invoice_id).first()
            
            if invoice:
                if invoice.typ_taryfy == "DWUTARYFOWA":
                    bill_dict["koszt_1kwh_dzienna"] = round(koszty_kwh.get("DZIENNA", {}).get("suma", 0), 4) if "DZIENNA" in koszty_kwh else None
                    bill_dict["koszt_1kwh_nocna"] = round(koszty_kwh.get("NOCNA", {}).get("suma", 0), 4) if "NOCNA" in koszty_kwh else None
                    bill_dict["koszt_1kwh_calodobowa"] = None
                elif invoice.typ_taryfy == "CAŁODOBOWA":
                    bill_dict["koszt_1kwh_dzienna"] = None
                    bill_dict["koszt_1kwh_nocna"] = None
                    bill_dict["koszt_1kwh_calodobowa"] = round(koszty_kwh.get("CAŁODOBOWA", {}).get("suma", 0), 4) if "CAŁODOBOWA" in koszty_kwh else None
                
                # Add invoice and blankiet information
                bill_dict["numer_faktury"] = invoice.numer_faktury
                # Billing period as invoice start and end dates
                if invoice.data_poczatku_okresu and invoice.data_konca_okresu:
                    bill_dict["okres_rozliczeniowy"] = f"{invoice.data_poczatku_okresu.strftime('%d.%m.%Y')} - {invoice.data_konca_okresu.strftime('%d.%m.%Y')}"
                else:
                    bill_dict["okres_rozliczeniowy"] = bill.data
                if blankiet:
                    bill_dict["blankiet_numer"] = blankiet.numer_blankietu
                    bill_dict["blankiet_poczatek"] = blankiet.poczatek_podokresu.isoformat() if blankiet.poczatek_podokresu else None
                    bill_dict["blankiet_koniec"] = blankiet.koniec_podokresu.isoformat() if blankiet.koniec_podokresu else None
        
        result.append(bill_dict)
    
    return result


@router.post("/generate-bills")
def generate_bills(
    data: str,
    db: Session = Depends(get_db)
):
    """Generuje rachunki dla wszystkich lokali w danym okresie."""
    manager = ElectricityBillingManager()
    
    try:
        bills = manager.generate_bills_for_period(db, data)
        
        # Sprawdź czy okres jest w pełni rozliczony i wykonaj backup jeśli tak
        from app.core.billing_period import handle_period_settlement
        settlement_result = handle_period_settlement(db, data)
        
        response = {
            "message": f"Wygenerowano {len(bills)} rachunków dla okresu {data}",
            "bills_count": len(bills)
        }
        
        if settlement_result.get("is_fully_settled"):
            response["settlement"] = settlement_result
        
        return response
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/bills/regenerate/{period}")
def regenerate_bills(period: str, db: Session = Depends(get_db)):
    """Regeneruje rachunki prądu dla danego okresu."""
    manager = ElectricityBillingManager()
    
    # Usuń stare rachunki dla tego okresu
    bills = db.query(ElectricityBill).filter(ElectricityBill.data == period).all()
    for bill in bills:
        # Usuń plik PDF jeśli istnieje
        if bill.pdf_path and Path(bill.pdf_path).exists():
            try:
                Path(bill.pdf_path).unlink()
            except Exception:
                pass  # Ignoruj błędy usuwania plików
        db.delete(bill)
    db.commit()
    
    try:
        # Wygeneruj nowe rachunki
        bills = manager.generate_bills_for_period(db, period)
        
        # Sprawdź czy okres jest w pełni rozliczony i wykonaj backup jeśli tak
        from app.core.billing_period import handle_period_settlement
        settlement_result = handle_period_settlement(db, period)
        
        response = {
            "message": "Rachunki prądu zregenerowane",
            "period": period,
            "bills_count": len(bills)
        }
        
        if settlement_result.get("is_fully_settled"):
            response["settlement"] = settlement_result
        
        return response
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/bills/{bill_id}")
def get_bill(bill_id: int, db: Session = Depends(get_db)):
    """Pobiera rachunek po ID."""
    bill = db.query(ElectricityBill).filter(ElectricityBill.id == bill_id).first()
    
    if not bill:
        raise HTTPException(status_code=404, detail="Rachunek nie znaleziony")
    
    bill_dict = {
        "id": bill.id,
        "data": bill.data,
        "local": bill.local,
        "reading_id": bill.reading_id,
        "invoice_id": bill.invoice_id,
        "local_id": bill.local_id,
        "usage_kwh": bill.usage_kwh,
        "usage_kwh_dzienna": bill.usage_kwh_dzienna,
        "usage_kwh_nocna": bill.usage_kwh_nocna,
        "energy_cost_gross": bill.energy_cost_gross,
        "distribution_cost_gross": bill.distribution_cost_gross,
        "total_net_sum": bill.total_net_sum,
        "total_gross_sum": bill.total_gross_sum,
        "pdf_path": bill.pdf_path,
    }
    
    # Dodaj informacje o fakturze
    if bill.invoice_id:
        invoice = db.query(ElectricityInvoice).filter(ElectricityInvoice.id == bill.invoice_id).first()
        if invoice:
            bill_dict["numer_faktury"] = invoice.numer_faktury
            bill_dict["typ_taryfy"] = invoice.typ_taryfy
    
    return bill_dict


@router.put("/bills/{bill_id}")
def update_bill(
    bill_id: int,
    bill_data: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db)
):
    """Aktualizuje rachunek po ID."""
    bill = db.query(ElectricityBill).filter(ElectricityBill.id == bill_id).first()
    
    if not bill:
        raise HTTPException(status_code=404, detail="Rachunek nie znaleziony")
    
    # Update fields
    updatable_fields = [
        'usage_kwh', 'usage_kwh_dzienna', 'usage_kwh_nocna',
        'energy_cost_gross', 'distribution_cost_gross',
        'total_net_sum', 'total_gross_sum', 'pdf_path'
    ]
    
    for key, value in bill_data.items():
        if key in updatable_fields and hasattr(bill, key):
            if isinstance(value, (int, float)) and value is not None:
                value = round(float(value), 4)
            setattr(bill, key, value)
    
    db.commit()
    db.refresh(bill)
    
    return {
        "message": "Rachunek zaktualizowany",
        "id": bill.id,
        "data": bill.data,
        "local": bill.local
    }


@router.post("/bills/generate-pdf/{bill_id}")
def generate_bill_pdf_endpoint(bill_id: int, db: Session = Depends(get_db)):
    """Generuje plik PDF dla konkretnego rachunku prądu."""
    from app.services.electricity.bill_generator import generate_bill_pdf
    
    bill = db.query(ElectricityBill).filter(ElectricityBill.id == bill_id).first()
    
    if not bill:
        raise HTTPException(status_code=404, detail="Rachunek nie znaleziony")
    
    try:
        pdf_path = generate_bill_pdf(db, bill)
        bill.pdf_path = pdf_path
        db.commit()
        
        return {
            "message": "Plik PDF został wygenerowany",
            "bill_id": bill_id,
            "pdf_path": pdf_path
        }
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"[ERROR] Błąd podczas generowania PDF dla rachunku {bill_id}: {e}")
        print(error_details)
        raise HTTPException(status_code=500, detail=f"Nie można wygenerować pliku PDF: {str(e)}")


@router.get("/bills/download/{bill_id}")
def download_bill(bill_id: int, db: Session = Depends(get_db)):
    """Pobiera plik PDF rachunku prądu. Generuje PDF jeśli nie istnieje."""
    bill = db.query(ElectricityBill).filter(ElectricityBill.id == bill_id).first()
    
    if not bill:
        raise HTTPException(status_code=404, detail="Rachunek nie znaleziony")
    
    # Jeśli plik PDF nie istnieje, wygeneruj go
    if not bill.pdf_path or not Path(bill.pdf_path).exists():
        try:
            from app.services.electricity.bill_generator import generate_bill_pdf
            pdf_path = generate_bill_pdf(db, bill)
            bill.pdf_path = pdf_path
            db.commit()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Nie można wygenerować pliku PDF: {str(e)}")
    
    return FileResponse(bill.pdf_path, media_type="application/pdf")


@router.delete("/bills/{bill_id}")
def delete_bill(bill_id: int, db: Session = Depends(get_db)):
    """Usuwa pojedynczy rachunek po ID."""
    from pathlib import Path
    
    bill = db.query(ElectricityBill).filter(ElectricityBill.id == bill_id).first()
    
    if not bill:
        raise HTTPException(status_code=404, detail="Rachunek nie znaleziony")
    
    # Delete PDF file if exists
    if bill.pdf_path and Path(bill.pdf_path).exists():
        try:
            Path(bill.pdf_path).unlink()
        except Exception:
            pass  # Ignore file deletion errors
    
    period = bill.data
    local = bill.local
    
    db.delete(bill)
    db.commit()
    
    return {
        "message": "Rachunek usunięty",
        "id": bill_id,
        "period": period,
        "local": local
    }


@router.delete("/bills")
def delete_all_bills(db: Session = Depends(get_db)):
    """Usuwa wszystkie rachunki prądu."""
    from pathlib import Path
    
    bills = db.query(ElectricityBill).all()
    deleted_count = len(bills)
    
    # Usuń pliki PDF jeśli istnieją
    for bill in bills:
        if bill.pdf_path and Path(bill.pdf_path).exists():
            try:
                Path(bill.pdf_path).unlink()
            except Exception:
                pass  # Ignore file deletion errors
    
    # Usuń wszystkie rachunki z bazy
    for bill in bills:
        db.delete(bill)
    
    db.commit()
    
    return {
        "message": f"Usunięto {deleted_count} rachunków",
        "deleted_count": deleted_count
    }


@router.get("/stats")
def get_electricity_stats(db: Session = Depends(get_db)):
    """Returns statistics for electricity dashboard."""
    stats = {
        "readings_count": db.query(ElectricityReading).count(),
        "invoices_count": db.query(ElectricityInvoice).count(),
        "bills_count": db.query(ElectricityBill).count(),
        "latest_period": None,
        "total_gross_sum": 0,
        "available_periods": []
    }
    
    # Latest period from readings
    latest_reading = db.query(ElectricityReading).order_by(desc(ElectricityReading.data)).first()
    if latest_reading:
        stats["latest_period"] = latest_reading.data
    
    # Total gross sum of all bills
    total_sum = db.query(func.sum(ElectricityBill.total_gross_sum)).scalar()
    if total_sum:
        stats["total_gross_sum"] = float(total_sum)
    
    # Periods with bills
    periods = db.query(ElectricityBill.data).distinct().order_by(desc(ElectricityBill.data)).all()
    stats["available_periods"] = [p[0] for p in periods[:10]]  # Last 10
    
    return stats


@router.get("/available-periods")
def get_available_periods(db: Session = Depends(get_db)):
    """
    Returns periods available for bill generation (having both invoices and readings).
    """
    from datetime import datetime, date
    
    # Get periods from readings
    reading_periods = set()
    readings = db.query(ElectricityReading.data).distinct().all()
    for r in readings:
        reading_periods.add(r.data)
    
    # Get all months from invoice periods and check if they have readings
    available_periods = set()
    invoices = db.query(ElectricityInvoice).all()
    
    for invoice in invoices:
        # For each month in invoice period
        start = invoice.data_poczatku_okresu
        end = invoice.data_konca_okresu
        
        # Ensure start is the first day of the month
        period_start = start.replace(day=1) if start.day != 1 else start
        
        # Iterate through all months in invoice period
        current = period_start
        while current <= end:
            period_str = current.strftime('%Y-%m')
            
            # Check if there is a reading for this period
            if period_str in reading_periods:
                available_periods.add(period_str)
            
            # Move to next month
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1, day=1)
            else:
                current = current.replace(month=current.month + 1, day=1)
    
    # Available periods are those that have both readings and invoices
    available = sorted(available_periods, reverse=True)
    
    # Get all periods from invoices (for debugging)
    all_invoice_periods = set()
    for invoice in invoices:
        start = invoice.data_poczatku_okresu.replace(day=1) if invoice.data_poczatku_okresu.day != 1 else invoice.data_poczatku_okresu
        end = invoice.data_konca_okresu
        current = start
        while current <= end:
            all_invoice_periods.add(current.strftime('%Y-%m'))
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1, day=1)
            else:
                current = current.replace(month=current.month + 1, day=1)
    
    # Periods from invoices but without readings (for diagnostics)
    periods_without_readings = sorted(all_invoice_periods - reading_periods, reverse=True)
    
    # Get periods that already have bills generated
    bills = db.query(ElectricityBill.data).distinct().all()
    periods_with_bills = {bill.data for bill in bills}
    
    # Separate available periods into those with and without bills
    available_without_bills = [p for p in available if p not in periods_with_bills]
    available_with_bills = [p for p in available if p in periods_with_bills]
    
    return {
        "available_periods": available,
        "available_periods_without_bills": sorted(available_without_bills, reverse=True),
        "available_periods_with_bills": sorted(available_with_bills, reverse=True),
        "all_reading_periods": sorted(reading_periods, reverse=True),
        "all_invoice_periods": sorted(all_invoice_periods, reverse=True),
        "periods_without_readings": periods_without_readings,
        "diagnostics": {
            "total_invoices": len(invoices),
            "total_readings": len(readings),
            "available_count": len(available),
            "available_without_bills_count": len(available_without_bills),
            "available_with_bills_count": len(available_with_bills),
            "missing_readings_count": len(periods_without_readings)
        }
    }


# ============================================================================
# NOWE ENDPOINTY DLA SZCZEGÓŁOWYCH FAKTUR (zgodnie ze schematem)
# ============================================================================

@router.get("/invoices-detailed/")
def get_invoices_detailed(
    skip: int = 0,
    limit: int = 100,
    rok: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Pobiera listę szczegółowych faktur prądu."""
    query = db.query(ElectricityInvoice)
    
    if rok:
        query = query.filter(ElectricityInvoice.rok == rok)
    
    invoices = query.order_by(desc(ElectricityInvoice.rok), desc(ElectricityInvoice.data_poczatku_okresu)).offset(skip).limit(limit).all()
    
    result = []
    for inv in invoices:
        # Oblicz koszt 1 kWh dla tej faktury
        koszty_kwh = calculate_kwh_cost(inv.id, db)
        
        # Określ główny koszt (dzienna dla dwutaryfowej, całodobowa dla całodobowej)
        glowny_koszt = None
        if inv.typ_taryfy == "DWUTARYFOWA":
            if "DZIENNA" in koszty_kwh:
                glowny_koszt = koszty_kwh["DZIENNA"]["suma"]
        elif inv.typ_taryfy == "CAŁODOBOWA":
            if "CAŁODOBOWA" in koszty_kwh:
                glowny_koszt = koszty_kwh["CAŁODOBOWA"]["suma"]
        
        # Jeśli nie ma głównego kosztu, użyj pierwszej dostępnej strefy
        if glowny_koszt is None and koszty_kwh:
            glowny_koszt = list(koszty_kwh.values())[0]["suma"]
        
        # Przygotuj koszty dla wyświetlenia
        koszt_dzienna = None
        koszt_nocna = None
        koszt_calodobowa = None
        
        if "DZIENNA" in koszty_kwh:
            koszt_dzienna = round(koszty_kwh["DZIENNA"]["suma"], 4)
        if "NOCNA" in koszty_kwh:
            koszt_nocna = round(koszty_kwh["NOCNA"]["suma"], 4)
        if "CAŁODOBOWA" in koszty_kwh:
            koszt_calodobowa = round(koszty_kwh["CAŁODOBOWA"]["suma"], 4)
        
        result.append({
            "id": inv.id,
            "rok": inv.rok,
            "numer_faktury": inv.numer_faktury,
            "data_wystawienia": inv.data_wystawienia.isoformat() if inv.data_wystawienia else None,
            "data_poczatku_okresu": inv.data_poczatku_okresu.isoformat() if inv.data_poczatku_okresu else None,
            "data_konca_okresu": inv.data_konca_okresu.isoformat() if inv.data_konca_okresu else None,
            "naleznosc_za_okres": float(inv.naleznosc_za_okres),
            "wynik_rozliczenia": float(inv.wynik_rozliczenia),
            "saldo_z_rozliczenia": float(inv.saldo_z_rozliczenia),
            "zuzycie_kwh": inv.zuzycie_kwh,
            "ogolem_sprzedaz_energii": float(inv.ogolem_sprzedaz_energii),
            "ogolem_usluga_dystrybucji": float(inv.ogolem_usluga_dystrybucji),
            "grupa_taryfowa": inv.grupa_taryfowa,
            "typ_taryfy": inv.typ_taryfy,
            "do_zaplaty": float(inv.do_zaplaty),
            "koszt_1kwh_dzienna": koszt_dzienna,
            "koszt_1kwh_nocna": koszt_nocna,
            "koszt_1kwh_calodobowa": koszt_calodobowa,
            "koszty_kwh_szczegolowe": koszty_kwh,
            "is_flagged": bool(inv.is_flagged) if hasattr(inv, 'is_flagged') else False,
        })
    
    return result


@router.get("/invoices-detailed/{invoice_id}")
def get_invoice_detailed(
    invoice_id: int,
    db: Session = Depends(get_db)
):
    """Pobiera szczegółową fakturę z wszystkimi danymi."""
    invoice = db.query(ElectricityInvoice).filter(ElectricityInvoice.id == invoice_id).first()
    
    if not invoice:
        raise HTTPException(status_code=404, detail=f"Faktura o ID {invoice_id} nie istnieje")
    
    # Get all related data
    blankiety = db.query(ElectricityInvoiceBlankiet).filter(
        ElectricityInvoiceBlankiet.invoice_id == invoice_id
    ).all()
    
    odczyty = db.query(ElectricityInvoiceOdczyt).filter(
        ElectricityInvoiceOdczyt.invoice_id == invoice_id
    ).all()
    
    sprzedaz = db.query(ElectricityInvoiceSprzedazEnergii).filter(
        ElectricityInvoiceSprzedazEnergii.invoice_id == invoice_id
    ).all()
    
    oplaty = db.query(ElectricityInvoiceOplataDystrybucyjna).filter(
        ElectricityInvoiceOplataDystrybucyjna.invoice_id == invoice_id
    ).all()
    
    okresy = db.query(ElectricityInvoiceRozliczenieOkres).filter(
        ElectricityInvoiceRozliczenieOkres.invoice_id == invoice_id
    ).all()
    
    return {
        "invoice": {
            "id": invoice.id,
            "rok": invoice.rok,
            "numer_faktury": invoice.numer_faktury,
            "data_wystawienia": invoice.data_wystawienia.isoformat() if invoice.data_wystawienia else None,
            "data_poczatku_okresu": invoice.data_poczatku_okresu.isoformat() if invoice.data_poczatku_okresu else None,
            "data_konca_okresu": invoice.data_konca_okresu.isoformat() if invoice.data_konca_okresu else None,
            "naleznosc_za_okres": float(invoice.naleznosc_za_okres),
            "wartosc_prognozy": float(invoice.wartosc_prognozy),
            "faktury_korygujace": float(invoice.faktury_korygujace),
            "odsetki": float(invoice.odsetki),
            "wynik_rozliczenia": float(invoice.wynik_rozliczenia),
            "kwota_nadplacona": float(invoice.kwota_nadplacona),
            "saldo_z_rozliczenia": float(invoice.saldo_z_rozliczenia),
            "niedoplata_nadplata": float(invoice.niedoplata_nadplata),
            "energia_do_akcyzy_kwh": invoice.energia_do_akcyzy_kwh,
            "akcyza": float(invoice.akcyza),
            "do_zaplaty": float(invoice.do_zaplaty),
            "zuzycie_kwh": invoice.zuzycie_kwh,
            "ogolem_sprzedaz_energii": float(invoice.ogolem_sprzedaz_energii),
            "ogolem_usluga_dystrybucji": float(invoice.ogolem_usluga_dystrybucji),
            "grupa_taryfowa": invoice.grupa_taryfowa,
            "typ_taryfy": invoice.typ_taryfy,
            "energia_lacznie_zuzyta_w_roku_kwh": invoice.energia_lacznie_zuzyta_w_roku_kwh,
            "is_flagged": bool(invoice.is_flagged) if hasattr(invoice, 'is_flagged') else False,
        },
        "blankiety": [
            {
                "id": b.id,
                "numer_blankietu": b.numer_blankietu,
                "poczatek_podokresu": b.poczatek_podokresu.isoformat() if b.poczatek_podokresu else None,
                "koniec_podokresu": b.koniec_podokresu.isoformat() if b.koniec_podokresu else None,
                "ilosc_dzienna_kwh": b.ilosc_dzienna_kwh,
                "ilosc_nocna_kwh": b.ilosc_nocna_kwh,
                "ilosc_calodobowa_kwh": b.ilosc_calodobowa_kwh,
                "kwota_brutto": float(b.kwota_brutto),
                "akcyza": float(b.akcyza),
                "energia_do_akcyzy_kwh": b.energia_do_akcyzy_kwh,
                "nadplata_niedoplata": float(b.nadplata_niedoplata),
                "odsetki": float(b.odsetki),
                "termin_platnosci": b.termin_platnosci.isoformat() if b.termin_platnosci else None,
                "do_zaplaty": float(b.do_zaplaty),
            } for b in blankiety
        ],
        "odczyty": [
            {
                "id": o.id,
                "typ_energii": o.typ_energii,
                "strefa": o.strefa,
                "data_odczytu": o.data_odczytu.isoformat() if o.data_odczytu else None,
                "biezacy_odczyt": o.biezacy_odczyt,
                "poprzedni_odczyt": o.poprzedni_odczyt,
                "mnozna": o.mnozna,
                "ilosc_kwh": o.ilosc_kwh,
                "straty_kwh": o.straty_kwh,
                "razem_kwh": o.razem_kwh,
            } for o in odczyty
        ],
        "sprzedaz_energii": [
            {
                "id": s.id,
                "data": s.data.isoformat() if s.data else None,
                "strefa": s.strefa,
                "ilosc_kwh": s.ilosc_kwh,
                "cena_za_kwh": float(s.cena_za_kwh),
                "naleznosc": float(s.naleznosc),
                "vat_procent": float(s.vat_procent),
            } for s in sprzedaz
        ],
        "oplaty_dystrybucyjne": [
            {
                "id": op.id,
                "typ_oplaty": op.typ_oplaty,
                "strefa": op.strefa,
                "jednostka": op.jednostka,
                "data": op.data.isoformat() if op.data else None,
                "ilosc_kwh": op.ilosc_kwh,
                "ilosc_miesiecy": op.ilosc_miesiecy,
                "wspolczynnik": float(op.wspolczynnik) if op.wspolczynnik else None,
                "cena": float(op.cena),
                "naleznosc": float(op.naleznosc),
                "vat_procent": float(op.vat_procent),
            } for op in oplaty
        ],
        "rozliczenie_okresy": [
            {
                "id": r.id,
                "data_okresu": r.data_okresu.isoformat() if r.data_okresu else None,
                "numer_okresu": r.numer_okresu,
            } for r in okresy
        ],
    }


@router.post("/invoices-detailed/parse")
async def parse_invoice_detailed(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Parsuje szczegółową fakturę PDF i zwraca dane do weryfikacji.
    NIE zapisuje do bazy danych!
    """
    # Zapisuj plik tymczasowo
    upload_folder = Path("invoices_raw/electricity")
    upload_folder.mkdir(parents=True, exist_ok=True)
    
    file_path = upload_folder / file.filename
    
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    # Wczytaj tekst z PDF
    text = extract_text_from_pdf(str(file_path))
    if not text:
        raise HTTPException(status_code=400, detail="Nie udało się wczytać tekstu z pliku PDF")
    
    # Parsuj dane z faktury (użyj istniejącej funkcji, ale później rozszerzymy)
    invoice_data = parse_invoice_data(text)
    
    if not invoice_data:
        raise HTTPException(status_code=400, detail="Nie udało się sparsować danych z faktury")
    
    # Konwertuj daty na stringi (dla JSON) - obsługa zarówno datetime jak i date
    from datetime import date as date_type
    if 'period_start' in invoice_data:
        if isinstance(invoice_data['period_start'], (datetime, date_type)):
            invoice_data['period_start'] = invoice_data['period_start'].strftime('%Y-%m-%d')
    if 'period_stop' in invoice_data:
        if isinstance(invoice_data['period_stop'], (datetime, date_type)):
            invoice_data['period_stop'] = invoice_data['period_stop'].strftime('%Y-%m-%d')
    if 'data_poczatku_okresu' in invoice_data:
        if isinstance(invoice_data['data_poczatku_okresu'], (datetime, date_type)):
            invoice_data['data_poczatku_okresu'] = invoice_data['data_poczatku_okresu'].strftime('%Y-%m-%d')
    if 'data_konca_okresu' in invoice_data:
        if isinstance(invoice_data['data_konca_okresu'], (datetime, date_type)):
            invoice_data['data_konca_okresu'] = invoice_data['data_konca_okresu'].strftime('%Y-%m-%d')
    if 'data_wystawienia' in invoice_data:
        if isinstance(invoice_data['data_wystawienia'], (datetime, date_type)):
            invoice_data['data_wystawienia'] = invoice_data['data_wystawienia'].strftime('%Y-%m-%d')
    if 'payment_due_date' in invoice_data:
        if isinstance(invoice_data['payment_due_date'], (datetime, date_type)):
            invoice_data['payment_due_date'] = invoice_data['payment_due_date'].strftime('%Y-%m-%d')
    
    # Usuń pomocnicze pola
    invoice_data.pop('_raw_data', None)
    invoice_data.pop('_file_path', None)
    invoice_data.pop('_file_name', None)
    
    return invoice_data


@router.post("/invoices-detailed/verify")
def verify_and_save_invoice_detailed(
    invoice_data: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db)
):
    """
    Zapisuje szczegółową fakturę po weryfikacji przez użytkownika.
    Wywoływane z dashboardu po zatwierdzeniu.
    """
    try:
        # Walidacja wymaganych pól
        required_fields = [
            'rok', 'numer_faktury', 'data_wystawienia', 'data_poczatku_okresu', 'data_konca_okresu',
            'naleznosc_za_okres', 'wartosc_prognozy', 'faktury_korygujace', 'odsetki',
            'wynik_rozliczenia', 'kwota_nadplacona', 'saldo_z_rozliczenia', 'niedoplata_nadplata',
            'energia_do_akcyzy_kwh', 'akcyza', 'do_zaplaty', 'zuzycie_kwh',
            'ogolem_sprzedaz_energii', 'ogolem_usluga_dystrybucji', 'grupa_taryfowa', 'typ_taryfy',
            'energia_lacznie_zuzyta_w_roku_kwh'
        ]
        
        missing_fields = [field for field in required_fields if field not in invoice_data or invoice_data.get(field) is None or invoice_data.get(field) == '']
        if missing_fields:
            raise HTTPException(status_code=400, detail=f"Brakuje wymaganych pól: {', '.join(missing_fields)}")
        
            # Sprawdź czy faktura już istnieje
        existing = db.query(ElectricityInvoice).filter(
            ElectricityInvoice.numer_faktury == invoice_data['numer_faktury'],
            ElectricityInvoice.rok == invoice_data['rok']
        ).first()
        
        if existing:
            raise HTTPException(status_code=400, detail=f"Faktura {invoice_data['numer_faktury']} dla roku {invoice_data['rok']} już istnieje")
        
        # Konwertuj daty - obsługa pustych dat
        # Data wystawienia - jeśli pusta, użyj daty początku okresu
        data_wystawienia_str = invoice_data.get('data_wystawienia', '').strip()
        if data_wystawienia_str:
            data_wystawienia = datetime.strptime(data_wystawienia_str, "%Y-%m-%d").date()
        else:
            # Spróbuj użyć data_poczatku_okresu
            data_poczatku_str = invoice_data.get('data_poczatku_okresu', '').strip()
            if data_poczatku_str:
                data_wystawienia = datetime.strptime(data_poczatku_str, "%Y-%m-%d").date()
            else:
                raise HTTPException(status_code=400, detail="Brak daty wystawienia lub daty początku okresu")
        
        # Data początku okresu
        data_poczatku_str = invoice_data.get('data_poczatku_okresu', '').strip()
        if not data_poczatku_str:
            raise HTTPException(status_code=400, detail="Brak daty początku okresu")
        data_poczatku_okresu = datetime.strptime(data_poczatku_str, "%Y-%m-%d").date()
        
        # Data końca okresu
        data_konca_str = invoice_data.get('data_konca_okresu', '').strip()
        if not data_konca_str:
            raise HTTPException(status_code=400, detail="Brak daty końca okresu")
        data_konca_okresu = datetime.strptime(data_konca_str, "%Y-%m-%d").date()
        
            # Utwórz fakturę
        invoice = ElectricityInvoice(
            rok=int(invoice_data['rok']),
            numer_faktury=invoice_data['numer_faktury'],
            data_wystawienia=data_wystawienia,
            data_poczatku_okresu=data_poczatku_okresu,
            data_konca_okresu=data_konca_okresu,
            naleznosc_za_okres=float(invoice_data['naleznosc_za_okres']),
            wartosc_prognozy=float(invoice_data['wartosc_prognozy']),
            faktury_korygujace=float(invoice_data['faktury_korygujace']),
            odsetki=float(invoice_data['odsetki']),
            wynik_rozliczenia=float(invoice_data['wynik_rozliczenia']),
            kwota_nadplacona=float(invoice_data['kwota_nadplacona']),
            saldo_z_rozliczenia=float(invoice_data['saldo_z_rozliczenia']),
            niedoplata_nadplata=float(invoice_data['niedoplata_nadplata']),
            energia_do_akcyzy_kwh=int(invoice_data['energia_do_akcyzy_kwh']),
            akcyza=float(invoice_data['akcyza']),
            do_zaplaty=float(invoice_data['do_zaplaty']),
            zuzycie_kwh=int(invoice_data['zuzycie_kwh']),
            ogolem_sprzedaz_energii=float(invoice_data['ogolem_sprzedaz_energii']),
            ogolem_usluga_dystrybucji=float(invoice_data['ogolem_usluga_dystrybucji']),
            grupa_taryfowa=invoice_data['grupa_taryfowa'],
            typ_taryfy=invoice_data['typ_taryfy'],
            energia_lacznie_zuzyta_w_roku_kwh=int(invoice_data['energia_lacznie_zuzyta_w_roku_kwh'])
        )
        
        db.add(invoice)
        db.flush()  # Flush aby uzyskać invoice.id
        
        # Funkcje pomocnicze do parsowania wartości
        def parse_value(data_dict, key, default=0.0):
            """
            Parsuje wartość numeryczną z formatu polskiego.
            Dla małych wartości (< 10) bez kropek, przecinek jest separatorem dziesiętnym.
            Dla większych wartości z kropkami, kropki są separatorami tysięcy.
            Jeśli wartość jest już float, zwraca ją bez parsowania.
            """
            if key in data_dict and data_dict[key] is not None and data_dict[key] != '':
                try:
                    # Jeśli wartość jest już float, zwróć ją bez parsowania
                    if isinstance(data_dict[key], (int, float)):
                        return float(data_dict[key])
                    
                    value_str = str(data_dict[key]).strip()
                    # Jeśli wartość zawiera kropki, to są to separatory tysięcy
                    if '.' in value_str:
                        # Format: "1.234,56" -> usuń kropki -> "1234,56" -> zamień przecinek -> "1234.56"
                        return float(value_str.replace('.', '').replace(',', '.'))
                    else:
                        # Jeśli nie ma kropek, przecinek jest separatorem dziesiętnym
                        # Format: "0,3640" -> zamień przecinek -> "0.3640"
                        return float(value_str.replace(',', '.'))
                except (ValueError, AttributeError, TypeError):
                    pass
            return default
        
        def parse_int_value(data_dict, key, default=0):
            """Parsuje wartość całkowitą z formatu polskiego."""
            if key in data_dict and data_dict[key] is not None and data_dict[key] != '':
                try:
                    # Jeśli wartość jest już liczbą, zwróć ją jako int
                    if isinstance(data_dict[key], (int, float)):
                        return int(data_dict[key])
                    
                    value_str = str(data_dict[key]).strip()
                    
                    # Jeśli wartość zawiera kropki, sprawdź czy są to separatory tysięcy
                    if '.' in value_str:
                        # Jeśli jest też przecinek, to kropki są separatorami tysięcy
                        if ',' in value_str:
                            # Format: "24.320,50" -> usuń kropki -> "24320,50" -> zamień przecinek -> "24320.50"
                            value_str = value_str.replace('.', '').replace(',', '.')
                        else:
                            # Tylko kropki - sprawdź czy to separatory tysięcy
                            # W formacie polskim separatory tysięcy to kropki, a każda grupa ma 3 cyfry
                            # Format: "24.320" lub "1.234.567" -> wszystkie kropki to separatory tysięcy
                            parts = value_str.split('.')
                            # Jeśli wszystkie części po pierwszej mają 3 cyfry, to są to separatory tysięcy
                            if len(parts) > 1 and all(len(part) == 3 for part in parts[1:]):
                                # Format: "24.320" lub "1.234.567" -> usuń wszystkie kropki
                                value_str = value_str.replace('.', '')
                            # W przeciwnym razie kropka jest separatorem dziesiętnym (zostaw)
                    elif ',' in value_str:
                        # Tylko przecinek - zamień na kropkę (separator dziesiętny)
                        value_str = value_str.replace(',', '.')
                    
                    return int(float(value_str))
                except (ValueError, AttributeError, TypeError):
                    pass
            return default
        
        # Zapisz blankiety
        if 'blankiety' in invoice_data and invoice_data['blankiety']:
            for blankiet_data in invoice_data['blankiety']:
                # Pomiń "Ogółem" jeśli jest
                if blankiet_data.get('ogolem'):
                    continue
                
                # Parsuj daty
                poczatek_podokresu = None
                koniec_podokresu = None
                termin_platnosci = None
                
                # Parsuj daty - obsługa zarówno ISO (YYYY-MM-DD) jak i DD/MM/YYYY
                if blankiet_data.get('okres_od'):
                    try:
                        date_str = blankiet_data['okres_od']
                        if '/' in date_str:
                            poczatek_podokresu = datetime.strptime(date_str, "%d/%m/%Y").date()
                        else:
                            poczatek_podokresu = datetime.strptime(date_str, "%Y-%m-%d").date()
                    except (ValueError, KeyError):
                        pass
                
                if blankiet_data.get('okres_do'):
                    try:
                        date_str = blankiet_data['okres_do']
                        if '/' in date_str:
                            koniec_podokresu = datetime.strptime(date_str, "%d/%m/%Y").date()
                        else:
                            koniec_podokresu = datetime.strptime(date_str, "%Y-%m-%d").date()
                    except (ValueError, KeyError):
                        pass
                
                if blankiet_data.get('termin_platnosci'):
                    try:
                        date_str = blankiet_data['termin_platnosci']
                        if '/' in date_str:
                            termin_platnosci = datetime.strptime(date_str, "%d/%m/%Y").date()
                        else:
                            termin_platnosci = datetime.strptime(date_str, "%Y-%m-%d").date()
                    except (ValueError, KeyError):
                        pass
                
                # Określ ilości energii - dla taryfy dwutaryfowej: ilosc_d i ilosc_c
                # Dla taryfy całodobowej: może być jedna wartość w polu ilosc_calodobowa
                ilosc_dzienna = parse_int_value(blankiet_data, 'ilosc_d') if blankiet_data.get('ilosc_d') else None
                ilosc_nocna = parse_int_value(blankiet_data, 'ilosc_c') if blankiet_data.get('ilosc_c') else None
                ilosc_calodobowa = None
                
                # Jeśli typ taryfy to całodobowa, sprawdź ilosc_calodobowa (z parsera) lub ilosc_c (fallback)
                if invoice.typ_taryfy == "CAŁODOBOWA":
                    if blankiet_data.get('ilosc_calodobowa'):
                        ilosc_calodobowa = parse_int_value(blankiet_data, 'ilosc_calodobowa')
                    elif blankiet_data.get('ilosc_c'):
                        ilosc_calodobowa = parse_int_value(blankiet_data, 'ilosc_c')
                    ilosc_dzienna = None
                    ilosc_nocna = None
                
                blankiet = ElectricityInvoiceBlankiet(
                    invoice_id=invoice.id,
                    rok=invoice.rok,
                    numer_blankietu=blankiet_data.get('nr_blankietu', ''),
                    poczatek_podokresu=poczatek_podokresu,
                    koniec_podokresu=koniec_podokresu,
                    ilosc_dzienna_kwh=ilosc_dzienna,
                    ilosc_nocna_kwh=ilosc_nocna,
                    ilosc_calodobowa_kwh=ilosc_calodobowa,
                    kwota_brutto=parse_value(blankiet_data, 'kwota_brutto', 0.0),
                    akcyza=parse_value(blankiet_data, 'akcyza', 0.0),
                    energia_do_akcyzy_kwh=parse_int_value(blankiet_data, 'energia_do_akcyzy', 0),
                    nadplata_niedoplata=parse_value(blankiet_data, 'nadplata_niedoplata', 0.0),
                    odsetki=parse_value(blankiet_data, 'odsetki', 0.0),
                    termin_platnosci=termin_platnosci if termin_platnosci else data_konca_okresu,
                    do_zaplaty=parse_value(blankiet_data, 'do_zaplaty', 0.0)
                )
                db.add(blankiet)
        
        # Zapisz odczyty
        if 'odczyty' in invoice_data and invoice_data['odczyty']:
            # Użyj set do deduplikacji odczytów w ramach tej faktury (typ_energii, strefa)
            # Dla nowej faktury nie sprawdzamy bazy - tylko deduplikujemy w danych wejściowych
            seen_odczyty = set()
            for odczyt_data in invoice_data['odczyty']:
                # Parsuj datę - obsługa zarówno ISO (YYYY-MM-DD) jak i DD/MM/YYYY
                data_odczytu = None
                if odczyt_data.get('data'):
                    try:
                        date_str = odczyt_data['data']
                        if '/' in date_str:
                            data_odczytu = datetime.strptime(date_str, "%d/%m/%Y").date()
                        else:
                            data_odczytu = datetime.strptime(date_str, "%Y-%m-%d").date()
                    except (ValueError, KeyError):
                        pass
                
                if not data_odczytu:
                    continue
                
                # Określ typ energii i strefę
                typ_energii = "POBRANA" if odczyt_data.get('typ') == 'pobrana' else "ODDANA"
                strefa = None
                if odczyt_data.get('strefa'):
                    strefa_str = odczyt_data['strefa'].upper()
                    if strefa_str in ['DZIENNA', 'NOCNA']:
                        strefa = strefa_str
                
                # Jeśli typ taryfy to całodobowa, strefa = NULL
                if invoice.typ_taryfy == "CAŁODOBOWA":
                    strefa = None
                
                # Sprawdź czy już przetworzyliśmy ten odczyt w ramach tej faktury (deduplikacja)
                # Używamy typ_energii, strefa i data_odczytu, aby umożliwić wiele okresów dla tej samej strefy
                odczyt_key = (typ_energii, strefa, data_odczytu)
                if odczyt_key in seen_odczyty:
                    # Pomiń duplikat - już mamy odczyt z tym typem energii, strefą i datą dla tej faktury
                    continue
                seen_odczyty.add(odczyt_key)
                
                # Utwórz nowy odczyt (dla nowej faktury zawsze tworzymy nowe odczyty)
                odczyt = ElectricityInvoiceOdczyt(
                    invoice_id=invoice.id,
                    rok=invoice.rok,
                    typ_energii=typ_energii,
                    strefa=strefa,
                    data_odczytu=data_odczytu,
                    biezacy_odczyt=parse_int_value(odczyt_data, 'biezace', 0),
                    poprzedni_odczyt=parse_int_value(odczyt_data, 'poprzednie', 0),
                    mnozna=parse_int_value(odczyt_data, 'mnozna', 1),
                    ilosc_kwh=parse_int_value(odczyt_data, 'ilosc', 0),
                    straty_kwh=parse_int_value(odczyt_data, 'straty', 0),
                    razem_kwh=parse_int_value(odczyt_data, 'razem', 0)
                )
                db.add(odczyt)
        
        # Zapisz sprzedaż energii
        if 'sprzedaz_energii' in invoice_data and invoice_data['sprzedaz_energii']:
            for sprzedaz_data in invoice_data['sprzedaz_energii']:
                # Pomiń upusty (będą zapisane jako osobne pozycje jeśli potrzebne)
                if sprzedaz_data.get('typ') == 'upust':
                    continue
                
                # Parsuj datę (jeśli jest) - obsługa zarówno ISO (YYYY-MM-DD) jak i DD/MM/YYYY
                data_sprzedazy = None
                if sprzedaz_data.get('data'):
                    try:
                        date_str = sprzedaz_data['data']
                        if '/' in date_str:
                            data_sprzedazy = datetime.strptime(date_str, "%d/%m/%Y").date()
                        else:
                            data_sprzedazy = datetime.strptime(date_str, "%Y-%m-%d").date()
                    except (ValueError, KeyError):
                        pass
                
                # Określ strefę
                strefa = None
                if sprzedaz_data.get('strefa'):
                    strefa_str = sprzedaz_data['strefa'].upper()
                    if strefa_str in ['DZIENNA', 'NOCNA']:
                        strefa = strefa_str
                
                # Jeśli typ taryfy to całodobowa, strefa = NULL
                if invoice.typ_taryfy == "CAŁODOBOWA":
                    strefa = None
                
                # Określ ilość kWh
                ilosc_kwh = 0
                if 'ilosc_kwh' in sprzedaz_data:
                    ilosc_kwh = parse_int_value(sprzedaz_data, 'ilosc_kwh', 0)
                elif 'ilosc' in sprzedaz_data:
                    ilosc_kwh = parse_int_value(sprzedaz_data, 'ilosc', 0)
                
                sprzedaz = ElectricityInvoiceSprzedazEnergii(
                    invoice_id=invoice.id,
                    rok=invoice.rok,
                    data=data_sprzedazy,
                    strefa=strefa,
                    ilosc_kwh=ilosc_kwh,
                    cena_za_kwh=parse_value(sprzedaz_data, 'cena', 0.0),
                    naleznosc=parse_value(sprzedaz_data, 'naleznosc', 0.0),
                    vat_procent=parse_value(sprzedaz_data, 'vat', 23.0)
                )
                db.add(sprzedaz)
        
        # Zapisz opłaty dystrybucyjne
        if 'oplaty_dystrybucyjne' in invoice_data and invoice_data['oplaty_dystrybucyjne']:
            for oplata_data in invoice_data['oplaty_dystrybucyjne']:
                # Parsuj datę - obsługa zarówno ISO (YYYY-MM-DD) jak i DD/MM/YYYY
                data_oplaty = None
                if oplata_data.get('data'):
                    try:
                        date_str = oplata_data['data']
                        if '/' in date_str:
                            data_oplaty = datetime.strptime(date_str, "%d/%m/%Y").date()
                        else:
                            data_oplaty = datetime.strptime(date_str, "%Y-%m-%d").date()
                    except (ValueError, KeyError):
                        pass
                
                if not data_oplaty:
                    # Jeśli nie ma daty, użyj daty początku okresu
                    data_oplaty = data_poczatku_okresu
                
                # Określ strefę
                strefa = None
                if oplata_data.get('strefa'):
                    strefa_str = oplata_data['strefa'].upper()
                    if strefa_str in ['DZIENNA', 'NOCNA']:
                        strefa = strefa_str
                
                # Jeśli typ taryfy to całodobowa, strefa = NULL
                if invoice.typ_taryfy == "CAŁODOBOWA":
                    strefa = None
                
                # Określ jednostkę i ilości
                jednostka = oplata_data.get('jednostka', 'kWh')
                ilosc_kwh = None
                ilosc_miesiecy = None
                wspolczynnik = None
                
                if jednostka == 'kWh':
                    if 'ilosc_kwh' in oplata_data:
                        ilosc_kwh = parse_int_value(oplata_data, 'ilosc_kwh', 0)
                    elif 'ilosc' in oplata_data:
                        ilosc_kwh = parse_int_value(oplata_data, 'ilosc', 0)
                elif jednostka == 'zł/mc':
                    if 'ilosc_miesiecy' in oplata_data:
                        ilosc_miesiecy = parse_value(oplata_data, 'ilosc_miesiecy', 0.0)  # Float, bo może być np. 4,9333
                    elif 'ilosc' in oplata_data:
                        ilosc_miesiecy = parse_value(oplata_data, 'ilosc', 0.0)
                
                # Współczynnik (dla opłaty stałej sieciowej)
                if 'wspolczynnik1' in oplata_data:
                    wspolczynnik = parse_value(oplata_data, 'wspolczynnik1', 0.0)
                elif 'wspolczynnik' in oplata_data:
                    wspolczynnik = parse_value(oplata_data, 'wspolczynnik', 0.0)
                
                oplata = ElectricityInvoiceOplataDystrybucyjna(
                    invoice_id=invoice.id,
                    rok=invoice.rok,
                    typ_oplaty=oplata_data.get('nazwa', ''),
                    strefa=strefa,
                    jednostka=jednostka,
                    data=data_oplaty,
                    ilosc_kwh=ilosc_kwh,
                    ilosc_miesiecy=ilosc_miesiecy,
                    wspolczynnik=wspolczynnik,
                    cena=parse_value(oplata_data, 'cena', 0.0),
                    naleznosc=parse_value(oplata_data, 'naleznosc', 0.0),
                    vat_procent=parse_value(oplata_data, 'vat', 23.0)
                )
                db.add(oplata)
        
        # Zapisz rozliczenie okresów - jeśli są w invoice_data
        if 'rozliczenie_okresy' in invoice_data and invoice_data['rozliczenie_okresy']:
            for okres_data in invoice_data['rozliczenie_okresy']:
                data_okresu = None
                if okres_data.get('data_okresu'):
                    try:
                        date_str = okres_data['data_okresu']
                        if '/' in date_str:
                            data_okresu = datetime.strptime(date_str, "%d/%m/%Y").date()
                        else:
                            data_okresu = datetime.strptime(date_str, "%Y-%m-%d").date()
                    except (ValueError, KeyError):
                        pass
                
                if data_okresu:
                    rozliczenie_okres = ElectricityInvoiceRozliczenieOkres(
                        invoice_id=invoice.id,
                        rok=invoice.rok,
                        data_okresu=data_okresu,
                        numer_okresu=okres_data.get('numer_okresu', 1)
                    )
                    db.add(rozliczenie_okres)
        elif 'blankiety' in invoice_data and invoice_data['blankiety']:
            # Fallback: generuj z blankietów jeśli nie ma rozliczenie_okresy
            okres_num = 1
            for blankiet_data in invoice_data['blankiety']:
                # Pomiń "Ogółem"
                if blankiet_data.get('ogolem'):
                    continue
                
                # Parsuj datę okresu (użyj końca podokresu)
                data_okresu = None
                if blankiet_data.get('okres_do'):
                    try:
                        date_str = blankiet_data['okres_do']
                        if '/' in date_str:
                            data_okresu = datetime.strptime(date_str, "%d/%m/%Y").date()
                        else:
                            data_okresu = datetime.strptime(date_str, "%Y-%m-%d").date()
                    except (ValueError, KeyError):
                        pass
                
                if data_okresu:
                    rozliczenie_okres = ElectricityInvoiceRozliczenieOkres(
                        invoice_id=invoice.id,
                        rok=invoice.rok,
                        data_okresu=data_okresu,
                        numer_okresu=okres_num
                    )
                    db.add(rozliczenie_okres)
                    okres_num += 1
        
        db.commit()
        db.refresh(invoice)
        
        return {
            "message": "Faktura zapisana pomyślnie ze wszystkimi szczegółami",
            "invoice_id": invoice.id,
            "invoice_number": invoice.numer_faktury,
            "rok": invoice.rok
        }
    except Exception as e:
        db.rollback()
        import traceback
        error_details = traceback.format_exc()
        print(f"Błąd zapisywania faktury: {error_details}")
        raise HTTPException(status_code=500, detail=f"Błąd zapisywania faktury: {str(e)}")


@router.put("/invoices-detailed/{invoice_id}")
def update_invoice_detailed(
    invoice_id: int,
    invoice_data: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db)
):
    """
    Aktualizuje szczegółową fakturę.
    """
    # Find invoice
    invoice = db.query(ElectricityInvoice).filter(ElectricityInvoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Faktura nie znaleziona")
    
    # Konwertuj daty - obsługa pustych dat
    try:
        from datetime import datetime
        
        # Data wystawienia
        data_wystawienia_str = invoice_data.get('data_wystawienia', '').strip()
        if data_wystawienia_str:
            data_wystawienia = datetime.strptime(data_wystawienia_str, "%Y-%m-%d").date()
        else:
            data_wystawienia = invoice.data_wystawienia
        
        # Data początku okresu
        data_poczatku_str = invoice_data.get('data_poczatku_okresu', '').strip()
        if data_poczatku_str:
            data_poczatku_okresu = datetime.strptime(data_poczatku_str, "%Y-%m-%d").date()
        else:
            data_poczatku_okresu = invoice.data_poczatku_okresu
        
        # Data końca okresu
        data_konca_str = invoice_data.get('data_konca_okresu', '').strip()
        if data_konca_str:
            data_konca_okresu = datetime.strptime(data_konca_str, "%Y-%m-%d").date()
        else:
            data_konca_okresu = invoice.data_konca_okresu
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Błędny format daty: {e}")
    
    # Update main invoice fields
    invoice.rok = int(invoice_data.get('rok', invoice.rok))
    invoice.numer_faktury = invoice_data.get('numer_faktury', invoice.numer_faktury)
    invoice.data_wystawienia = data_wystawienia
    invoice.data_poczatku_okresu = data_poczatku_okresu
    invoice.data_konca_okresu = data_konca_okresu
    invoice.naleznosc_za_okres = float(invoice_data.get('naleznosc_za_okres', invoice.naleznosc_za_okres))
    invoice.wartosc_prognozy = float(invoice_data.get('wartosc_prognozy', invoice.wartosc_prognozy))
    invoice.faktury_korygujace = float(invoice_data.get('faktury_korygujace', invoice.faktury_korygujace))
    invoice.odsetki = float(invoice_data.get('odsetki', invoice.odsetki))
    invoice.wynik_rozliczenia = float(invoice_data.get('wynik_rozliczenia', invoice.wynik_rozliczenia))
    invoice.kwota_nadplacona = float(invoice_data.get('kwota_nadplacona', invoice.kwota_nadplacona))
    invoice.saldo_z_rozliczenia = float(invoice_data.get('saldo_z_rozliczenia', invoice.saldo_z_rozliczenia))
    invoice.niedoplata_nadplata = float(invoice_data.get('niedoplata_nadplata', invoice.niedoplata_nadplata))
    invoice.energia_do_akcyzy_kwh = int(invoice_data.get('energia_do_akcyzy_kwh', invoice.energia_do_akcyzy_kwh))
    invoice.akcyza = float(invoice_data.get('akcyza', invoice.akcyza))
    invoice.do_zaplaty = float(invoice_data.get('do_zaplaty', invoice.do_zaplaty))
    invoice.zuzycie_kwh = int(invoice_data.get('zuzycie_kwh', invoice.zuzycie_kwh))
    invoice.ogolem_sprzedaz_energii = float(invoice_data.get('ogolem_sprzedaz_energii', invoice.ogolem_sprzedaz_energii))
    invoice.ogolem_usluga_dystrybucji = float(invoice_data.get('ogolem_usluga_dystrybucji', invoice.ogolem_usluga_dystrybucji))
    invoice.grupa_taryfowa = invoice_data.get('grupa_taryfowa', invoice.grupa_taryfowa)
    invoice.typ_taryfy = invoice_data.get('typ_taryfy', invoice.typ_taryfy)
    invoice.energia_lacznie_zuzyta_w_roku_kwh = int(invoice_data.get('energia_lacznie_zuzyta_w_roku_kwh', invoice.energia_lacznie_zuzyta_w_roku_kwh))
    
    db.flush()
    
    # Funkcje pomocnicze do parsowania wartości
    def parse_value(data_dict, key, default=0.0):
        """
        Parsuje wartość numeryczną z formatu polskiego.
        Dla małych wartości (< 10) bez kropek, przecinek jest separatorem dziesiętnym.
        Dla większych wartości z kropkami, kropki są separatorami tysięcy.
        Jeśli wartość jest już float, zwraca ją bez parsowania.
        """
        if key in data_dict and data_dict[key] is not None and data_dict[key] != '':
            try:
                # Jeśli wartość jest już float, zwróć ją bez parsowania
                if isinstance(data_dict[key], (int, float)):
                    return float(data_dict[key])
                
                value_str = str(data_dict[key]).strip()
                # Jeśli wartość zawiera kropki, to są to separatory tysięcy
                if '.' in value_str:
                    # Format: "1.234,56" -> usuń kropki -> "1234,56" -> zamień przecinek -> "1234.56"
                    return float(value_str.replace('.', '').replace(',', '.'))
                else:
                    # Jeśli nie ma kropek, przecinek jest separatorem dziesiętnym
                    # Format: "0,3640" -> zamień przecinek -> "0.3640"
                    return float(value_str.replace(',', '.'))
            except (ValueError, AttributeError, TypeError):
                pass
        return default
    
    def parse_int_value(data_dict, key, default=0):
        """Parsuje wartość całkowitą z formatu polskiego."""
        if key in data_dict and data_dict[key] is not None and data_dict[key] != '':
            try:
                # Jeśli wartość jest już liczbą, zwróć ją jako int
                if isinstance(data_dict[key], (int, float)):
                    return int(data_dict[key])
                
                value_str = str(data_dict[key]).strip()
                
                # Jeśli wartość zawiera kropki, sprawdź czy są to separatory tysięcy
                if '.' in value_str:
                    # Jeśli jest też przecinek, to kropki są separatorami tysięcy
                    if ',' in value_str:
                        # Format: "24.320,50" -> usuń kropki -> "24320,50" -> zamień przecinek -> "24320.50"
                        value_str = value_str.replace('.', '').replace(',', '.')
                    else:
                        # Tylko kropki - sprawdź czy to separatory tysięcy
                        # W formacie polskim separatory tysięcy to kropki, a każda grupa ma 3 cyfry
                        # Format: "24.320" lub "1.234.567" -> wszystkie kropki to separatory tysięcy
                        parts = value_str.split('.')
                        # Jeśli wszystkie części po pierwszej mają 3 cyfry, to są to separatory tysięcy
                        if len(parts) > 1 and all(len(part) == 3 for part in parts[1:]):
                            # Format: "24.320" lub "1.234.567" -> usuń wszystkie kropki
                            value_str = value_str.replace('.', '')
                        # W przeciwnym razie kropka jest separatorem dziesiętnym (zostaw)
                elif ',' in value_str:
                    # Tylko przecinek - zamień na kropkę (separator dziesiętny)
                    value_str = value_str.replace(',', '.')
                
                return int(float(value_str))
            except (ValueError, AttributeError, TypeError):
                pass
        return default
    
    # Usuń stare szczegółowe dane i dodaj nowe (jeśli są w invoice_data)
    if 'blankiety' in invoice_data and invoice_data['blankiety']:
        # Usuń stare blankiety
        db.query(ElectricityInvoiceBlankiet).filter(ElectricityInvoiceBlankiet.invoice_id == invoice_id).delete()
        
        # Dodaj nowe blankiety (ten sam kod co w verify_and_save_invoice_detailed)
        for blankiet_data in invoice_data['blankiety']:
            if blankiet_data.get('ogolem'):
                continue
            
            poczatek_podokresu = None
            koniec_podokresu = None
            termin_platnosci = None
            
            # Parsuj daty - obsługa zarówno ISO (YYYY-MM-DD) jak i DD/MM/YYYY
            if blankiet_data.get('okres_od'):
                try:
                    date_str = blankiet_data['okres_od']
                    if '/' in date_str:
                        poczatek_podokresu = datetime.strptime(date_str, "%d/%m/%Y").date()
                    else:
                        poczatek_podokresu = datetime.strptime(date_str, "%Y-%m-%d").date()
                except (ValueError, KeyError):
                    pass
            
            if blankiet_data.get('okres_do'):
                try:
                    date_str = blankiet_data['okres_do']
                    if '/' in date_str:
                        koniec_podokresu = datetime.strptime(date_str, "%d/%m/%Y").date()
                    else:
                        koniec_podokresu = datetime.strptime(date_str, "%Y-%m-%d").date()
                except (ValueError, KeyError):
                    pass
            
            if blankiet_data.get('termin_platnosci'):
                try:
                    date_str = blankiet_data['termin_platnosci']
                    if '/' in date_str:
                        termin_platnosci = datetime.strptime(date_str, "%d/%m/%Y").date()
                    else:
                        termin_platnosci = datetime.strptime(date_str, "%Y-%m-%d").date()
                except (ValueError, KeyError):
                    pass
            
            ilosc_dzienna = parse_int_value(blankiet_data, 'ilosc_d') if blankiet_data.get('ilosc_d') else None
            ilosc_nocna = parse_int_value(blankiet_data, 'ilosc_c') if blankiet_data.get('ilosc_c') else None
            ilosc_calodobowa = None
            
            # Jeśli typ taryfy to całodobowa, sprawdź ilosc_calodobowa (z parsera) lub ilosc_c (fallback)
            if invoice.typ_taryfy == "CAŁODOBOWA":
                if blankiet_data.get('ilosc_calodobowa'):
                    ilosc_calodobowa = parse_int_value(blankiet_data, 'ilosc_calodobowa')
                elif blankiet_data.get('ilosc_c'):
                    ilosc_calodobowa = parse_int_value(blankiet_data, 'ilosc_c')
                ilosc_dzienna = None
                ilosc_nocna = None
            
            blankiet = ElectricityInvoiceBlankiet(
                invoice_id=invoice.id,
                rok=invoice.rok,
                numer_blankietu=blankiet_data.get('nr_blankietu', ''),
                poczatek_podokresu=poczatek_podokresu,
                koniec_podokresu=koniec_podokresu,
                ilosc_dzienna_kwh=ilosc_dzienna,
                ilosc_nocna_kwh=ilosc_nocna,
                ilosc_calodobowa_kwh=ilosc_calodobowa,
                kwota_brutto=parse_value(blankiet_data, 'kwota_brutto', 0.0),
                akcyza=parse_value(blankiet_data, 'akcyza', 0.0),
                energia_do_akcyzy_kwh=parse_int_value(blankiet_data, 'energia_do_akcyzy', 0),
                nadplata_niedoplata=parse_value(blankiet_data, 'nadplata_niedoplata', 0.0),
                odsetki=parse_value(blankiet_data, 'odsetki', 0.0),
                termin_platnosci=termin_platnosci or data_konca_okresu,
                do_zaplaty=parse_value(blankiet_data, 'do_zaplaty', 0.0)
            )
            db.add(blankiet)
    
    # Podobnie dla pozostałych tabel (odczyty, sprzedaż, opłaty, rozliczenie okresów)
    # Dla uproszczenia, jeśli są dane w invoice_data, usuń stare i dodaj nowe
    if 'odczyty' in invoice_data and invoice_data['odczyty']:
        db.query(ElectricityInvoiceOdczyt).filter(ElectricityInvoiceOdczyt.invoice_id == invoice_id).delete()
        for odczyt_data in invoice_data['odczyty']:
            data_odczytu = None
            if odczyt_data.get('data'):
                try:
                    date_str = odczyt_data['data']
                    if '/' in date_str:
                        data_odczytu = datetime.strptime(date_str, "%d/%m/%Y").date()
                    else:
                        data_odczytu = datetime.strptime(date_str, "%Y-%m-%d").date()
                except (ValueError, KeyError):
                    pass
            
            if not data_odczytu:
                continue
            
            typ_energii = "POBRANA" if odczyt_data.get('typ') == 'pobrana' else "ODDANA"
            strefa = None
            if odczyt_data.get('strefa'):
                strefa_str = odczyt_data['strefa'].upper()
                if strefa_str in ['DZIENNA', 'NOCNA']:
                    strefa = strefa_str
            
            if invoice.typ_taryfy == "CAŁODOBOWA":
                strefa = None
            
            odczyt = ElectricityInvoiceOdczyt(
                invoice_id=invoice.id,
                rok=invoice.rok,
                typ_energii=typ_energii,
                strefa=strefa,
                data_odczytu=data_odczytu,
                biezacy_odczyt=parse_int_value(odczyt_data, 'biezace', 0),
                poprzedni_odczyt=parse_int_value(odczyt_data, 'poprzednie', 0),
                mnozna=parse_int_value(odczyt_data, 'mnozna', 1),
                ilosc_kwh=parse_int_value(odczyt_data, 'ilosc', 0),
                straty_kwh=parse_int_value(odczyt_data, 'straty', 0),
                razem_kwh=parse_int_value(odczyt_data, 'razem', 0)
            )
            db.add(odczyt)
    
    if 'sprzedaz_energii' in invoice_data and invoice_data['sprzedaz_energii']:
        db.query(ElectricityInvoiceSprzedazEnergii).filter(ElectricityInvoiceSprzedazEnergii.invoice_id == invoice_id).delete()
        for sprzedaz_data in invoice_data['sprzedaz_energii']:
            if sprzedaz_data.get('typ') == 'upust':
                continue
            
            data_sprzedazy = None
            if sprzedaz_data.get('data'):
                try:
                    date_str = sprzedaz_data['data']
                    if '/' in date_str:
                        data_sprzedazy = datetime.strptime(date_str, "%d/%m/%Y").date()
                    else:
                        data_sprzedazy = datetime.strptime(date_str, "%Y-%m-%d").date()
                except (ValueError, KeyError):
                    pass
            
            strefa = None
            if sprzedaz_data.get('strefa'):
                strefa_str = sprzedaz_data['strefa'].upper()
                if strefa_str in ['DZIENNA', 'NOCNA']:
                    strefa = strefa_str
            
            if invoice.typ_taryfy == "CAŁODOBOWA":
                strefa = None
            
            ilosc_kwh = 0
            if 'ilosc_kwh' in sprzedaz_data:
                ilosc_kwh = parse_int_value(sprzedaz_data, 'ilosc_kwh', 0)
            elif 'ilosc' in sprzedaz_data:
                ilosc_kwh = parse_int_value(sprzedaz_data, 'ilosc', 0)
            
            sprzedaz = ElectricityInvoiceSprzedazEnergii(
                invoice_id=invoice.id,
                rok=invoice.rok,
                data=data_sprzedazy,
                strefa=strefa,
                ilosc_kwh=ilosc_kwh,
                cena_za_kwh=parse_value(sprzedaz_data, 'cena', 0.0),
                naleznosc=parse_value(sprzedaz_data, 'naleznosc', 0.0),
                vat_procent=parse_value(sprzedaz_data, 'vat', 23.0)
            )
            db.add(sprzedaz)
    
    if 'oplaty_dystrybucyjne' in invoice_data and invoice_data['oplaty_dystrybucyjne']:
        db.query(ElectricityInvoiceOplataDystrybucyjna).filter(ElectricityInvoiceOplataDystrybucyjna.invoice_id == invoice_id).delete()
        for oplata_data in invoice_data['oplaty_dystrybucyjne']:
            data_oplaty = None
            if oplata_data.get('data'):
                try:
                    date_str = oplata_data['data']
                    if '/' in date_str:
                        data_oplaty = datetime.strptime(date_str, "%d/%m/%Y").date()
                    else:
                        data_oplaty = datetime.strptime(date_str, "%Y-%m-%d").date()
                except (ValueError, KeyError):
                    pass
            
            if not data_oplaty:
                data_oplaty = data_poczatku_okresu
            
            strefa = None
            if oplata_data.get('strefa'):
                strefa_str = oplata_data['strefa'].upper()
                if strefa_str in ['DZIENNA', 'NOCNA']:
                    strefa = strefa_str
            
            if invoice.typ_taryfy == "CAŁODOBOWA":
                strefa = None
            
            jednostka = oplata_data.get('jednostka', 'kWh')
            ilosc_kwh = None
            ilosc_miesiecy = None
            wspolczynnik = None
            
            if jednostka == 'kWh':
                if 'ilosc_kwh' in oplata_data:
                    ilosc_kwh = parse_int_value(oplata_data, 'ilosc_kwh', 0)
                elif 'ilosc' in oplata_data:
                    ilosc_kwh = parse_int_value(oplata_data, 'ilosc', 0)
            elif jednostka == 'zł/mc':
                if 'ilosc_miesiecy' in oplata_data:
                    ilosc_miesiecy = parse_value(oplata_data, 'ilosc_miesiecy', 0.0)  # Float, bo może być np. 4,9333
                elif 'ilosc' in oplata_data:
                    ilosc_miesiecy = parse_value(oplata_data, 'ilosc', 0.0)
            
            if 'wspolczynnik1' in oplata_data:
                wspolczynnik = parse_value(oplata_data, 'wspolczynnik1', 0.0)
            elif 'wspolczynnik' in oplata_data:
                wspolczynnik = parse_value(oplata_data, 'wspolczynnik', 0.0)
            
            oplata = ElectricityInvoiceOplataDystrybucyjna(
                invoice_id=invoice.id,
                rok=invoice.rok,
                typ_oplaty=oplata_data.get('nazwa', ''),
                strefa=strefa,
                jednostka=jednostka,
                data=data_oplaty,
                ilosc_kwh=ilosc_kwh,
                ilosc_miesiecy=ilosc_miesiecy,
                wspolczynnik=wspolczynnik,
                cena=parse_value(oplata_data, 'cena', 0.0),
                naleznosc=parse_value(oplata_data, 'naleznosc', 0.0),
                vat_procent=parse_value(oplata_data, 'vat', 23.0)
            )
            db.add(oplata)
    
    # Rozliczenie okresów - jeśli są w invoice_data
    if 'rozliczenie_okresy' in invoice_data and invoice_data['rozliczenie_okresy']:
        db.query(ElectricityInvoiceRozliczenieOkres).filter(ElectricityInvoiceRozliczenieOkres.invoice_id == invoice_id).delete()
        for okres_data in invoice_data['rozliczenie_okresy']:
            data_okresu = None
            if okres_data.get('data_okresu'):
                try:
                    date_str = okres_data['data_okresu']
                    if '/' in date_str:
                        data_okresu = datetime.strptime(date_str, "%d/%m/%Y").date()
                    else:
                        data_okresu = datetime.strptime(date_str, "%Y-%m-%d").date()
                except (ValueError, KeyError):
                    pass
            
            if data_okresu:
                rozliczenie_okres = ElectricityInvoiceRozliczenieOkres(
                    invoice_id=invoice.id,
                    rok=invoice.rok,
                    data_okresu=data_okresu,
                    numer_okresu=okres_data.get('numer_okresu', 1)
                )
                db.add(rozliczenie_okres)
    elif 'blankiety' in invoice_data and invoice_data['blankiety']:
        # Fallback: generuj z blankietów jeśli nie ma rozliczenie_okresy
        db.query(ElectricityInvoiceRozliczenieOkres).filter(ElectricityInvoiceRozliczenieOkres.invoice_id == invoice_id).delete()
        okres_num = 1
        for blankiet_data in invoice_data['blankiety']:
            if blankiet_data.get('ogolem') or not blankiet_data.get('okres_do'):
                continue
            
            data_okresu = None
            if blankiet_data.get('okres_do'):
                try:
                    date_str = blankiet_data['okres_do']
                    if '/' in date_str:
                        data_okresu = datetime.strptime(date_str, "%d/%m/%Y").date()
                    else:
                        data_okresu = datetime.strptime(date_str, "%Y-%m-%d").date()
                except (ValueError, KeyError):
                    pass
            
            if data_okresu:
                rozliczenie_okres = ElectricityInvoiceRozliczenieOkres(
                    invoice_id=invoice.id,
                    rok=invoice.rok,
                    data_okresu=data_okresu,
                    numer_okresu=okres_num
                )
                db.add(rozliczenie_okres)
                okres_num += 1
    
    db.commit()
    db.refresh(invoice)
    
    return {
        "message": "Faktura zaktualizowana pomyślnie",
        "invoice_id": invoice.id,
        "invoice_number": invoice.numer_faktury,
        "rok": invoice.rok
    }


@router.put("/invoices-detailed/{invoice_id}/flag")
def toggle_invoice_flag(
    invoice_id: int,
    flag_data: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db)
):
    """Przełącza flagę dla faktury prądu."""
    invoice = db.query(ElectricityInvoice).filter(ElectricityInvoice.id == invoice_id).first()
    
    if not invoice:
        raise HTTPException(status_code=404, detail=f"Faktura o ID {invoice_id} nie istnieje")
    
    # Pobierz wartość flagi z request body (domyślnie True jeśli nie podano)
    is_flagged = flag_data.get('is_flagged', True)
    
    # Zaktualizuj flagę
    if hasattr(invoice, 'is_flagged'):
        invoice.is_flagged = bool(is_flagged)
    else:
        raise HTTPException(status_code=500, detail="Kolumna is_flagged nie istnieje w modelu")
    
    db.commit()
    db.refresh(invoice)
    
    return {
        "message": f"Flaga faktury {invoice.numer_faktury} została zaktualizowana",
        "invoice_id": invoice.id,
        "invoice_number": invoice.numer_faktury,
        "is_flagged": bool(invoice.is_flagged)
    }


@router.delete("/invoices-detailed/{invoice_id}")
def delete_invoice_detailed(
    invoice_id: int,
    db: Session = Depends(get_db)
):
    """
    Usuwa szczegółową fakturę wraz ze wszystkimi powiązanymi danymi.
    """
    invoice = db.query(ElectricityInvoice).filter(ElectricityInvoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Faktura nie znaleziona")
    
    invoice_number = invoice.numer_faktury
    invoice_rok = invoice.rok
    
    # Usuń fakturę (cascade usunie wszystkie powiązane dane dzięki relacjom)
    db.delete(invoice)
    db.commit()
    
    return {
        "message": f"Faktura {invoice_number} dla roku {invoice_rok} została usunięta",
        "invoice_id": invoice_id
    }


# ============================================================================
# ENDPOINTY DO EDYCJI/USUWANIA POJEDYNCZYCH REKORDÓW Z TABEL SZCZEGÓŁOWYCH
# ============================================================================

@router.put("/invoices-detailed/blankiety/{blankiet_id}")
def update_blankiet(
    blankiet_id: int,
    blankiet_data: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db)
):
    """Aktualizuje blankiet prognozowy."""
    blankiet = db.query(ElectricityInvoiceBlankiet).filter(ElectricityInvoiceBlankiet.id == blankiet_id).first()
    if not blankiet:
        raise HTTPException(status_code=404, detail="Blankiet nie znaleziony")
    
    from datetime import datetime
    
    # Parsuj daty
    if blankiet_data.get('poczatek_podokresu'):
        blankiet.poczatek_podokresu = datetime.strptime(blankiet_data['poczatek_podokresu'], "%Y-%m-%d").date()
    if blankiet_data.get('koniec_podokresu'):
        blankiet.koniec_podokresu = datetime.strptime(blankiet_data['koniec_podokresu'], "%Y-%m-%d").date()
    if blankiet_data.get('termin_platnosci'):
        blankiet.termin_platnosci = datetime.strptime(blankiet_data['termin_platnosci'], "%Y-%m-%d").date()
    
    # Update fields
    if 'numer_blankietu' in blankiet_data:
        blankiet.numer_blankietu = blankiet_data['numer_blankietu']
    if 'ilosc_dzienna_kwh' in blankiet_data:
        blankiet.ilosc_dzienna_kwh = blankiet_data['ilosc_dzienna_kwh']
    if 'ilosc_nocna_kwh' in blankiet_data:
        blankiet.ilosc_nocna_kwh = blankiet_data['ilosc_nocna_kwh']
    if 'ilosc_calodobowa_kwh' in blankiet_data:
        blankiet.ilosc_calodobowa_kwh = blankiet_data['ilosc_calodobowa_kwh']
    if 'kwota_brutto' in blankiet_data:
        blankiet.kwota_brutto = float(blankiet_data['kwota_brutto'])
    if 'akcyza' in blankiet_data:
        blankiet.akcyza = float(blankiet_data['akcyza'])
    if 'energia_do_akcyzy_kwh' in blankiet_data:
        blankiet.energia_do_akcyzy_kwh = int(blankiet_data['energia_do_akcyzy_kwh'])
    if 'nadplata_niedoplata' in blankiet_data:
        blankiet.nadplata_niedoplata = float(blankiet_data['nadplata_niedoplata'])
    if 'odsetki' in blankiet_data:
        blankiet.odsetki = float(blankiet_data['odsetki'])
    if 'do_zaplaty' in blankiet_data:
        blankiet.do_zaplaty = float(blankiet_data['do_zaplaty'])
    
    db.commit()
    db.refresh(blankiet)
    return {"message": "Blankiet zaktualizowany", "blankiet_id": blankiet.id}


@router.delete("/invoices-detailed/blankiety/{blankiet_id}")
def delete_blankiet(blankiet_id: int, db: Session = Depends(get_db)):
    """Usuwa blankiet prognozowy."""
    blankiet = db.query(ElectricityInvoiceBlankiet).filter(ElectricityInvoiceBlankiet.id == blankiet_id).first()
    if not blankiet:
        raise HTTPException(status_code=404, detail="Blankiet nie znaleziony")
    db.delete(blankiet)
    db.commit()
    return {"message": "Blankiet usunięty", "blankiet_id": blankiet_id}


@router.put("/invoices-detailed/odczyty/{odczyt_id}")
def update_odczyt(
    odczyt_id: int,
    odczyt_data: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db)
):
    """Aktualizuje odczyt licznika."""
    odczyt = db.query(ElectricityInvoiceOdczyt).filter(ElectricityInvoiceOdczyt.id == odczyt_id).first()
    if not odczyt:
        raise HTTPException(status_code=404, detail="Odczyt nie znaleziony")
    
    from datetime import datetime
    
    if odczyt_data.get('data_odczytu'):
        odczyt.data_odczytu = datetime.strptime(odczyt_data['data_odczytu'], "%Y-%m-%d").date()
    if 'typ_energii' in odczyt_data:
        odczyt.typ_energii = odczyt_data['typ_energii']
    if 'strefa' in odczyt_data:
        odczyt.strefa = odczyt_data['strefa'] if odczyt_data['strefa'] else None
    if 'biezacy_odczyt' in odczyt_data:
        odczyt.biezacy_odczyt = int(odczyt_data['biezacy_odczyt'])
    if 'poprzedni_odczyt' in odczyt_data:
        odczyt.poprzedni_odczyt = int(odczyt_data['poprzedni_odczyt'])
    if 'mnozna' in odczyt_data:
        odczyt.mnozna = int(odczyt_data['mnozna'])
    if 'ilosc_kwh' in odczyt_data:
        odczyt.ilosc_kwh = int(odczyt_data['ilosc_kwh'])
    if 'straty_kwh' in odczyt_data:
        odczyt.straty_kwh = int(odczyt_data['straty_kwh'])
    if 'razem_kwh' in odczyt_data:
        odczyt.razem_kwh = int(odczyt_data['razem_kwh'])
    
    db.commit()
    db.refresh(odczyt)
    return {"message": "Odczyt zaktualizowany", "odczyt_id": odczyt.id}


@router.delete("/invoices-detailed/odczyty/{odczyt_id}")
def delete_odczyt(odczyt_id: int, db: Session = Depends(get_db)):
    """Usuwa odczyt licznika."""
    odczyt = db.query(ElectricityInvoiceOdczyt).filter(ElectricityInvoiceOdczyt.id == odczyt_id).first()
    if not odczyt:
        raise HTTPException(status_code=404, detail="Odczyt nie znaleziony")
    db.delete(odczyt)
    db.commit()
    return {"message": "Odczyt usunięty", "odczyt_id": odczyt_id}


@router.put("/invoices-detailed/sprzedaz/{sprzedaz_id}")
def update_sprzedaz(
    sprzedaz_id: int,
    sprzedaz_data: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db)
):
    """Aktualizuje pozycję sprzedaży energii."""
    sprzedaz = db.query(ElectricityInvoiceSprzedazEnergii).filter(ElectricityInvoiceSprzedazEnergii.id == sprzedaz_id).first()
    if not sprzedaz:
        raise HTTPException(status_code=404, detail="Pozycja sprzedaży nie znaleziona")
    
    from datetime import datetime
    
    if sprzedaz_data.get('data'):
        sprzedaz.data = datetime.strptime(sprzedaz_data['data'], "%Y-%m-%d").date()
    if 'strefa' in sprzedaz_data:
        sprzedaz.strefa = sprzedaz_data['strefa'] if sprzedaz_data['strefa'] else None
    if 'ilosc_kwh' in sprzedaz_data:
        sprzedaz.ilosc_kwh = int(sprzedaz_data['ilosc_kwh'])
    if 'cena_za_kwh' in sprzedaz_data:
        sprzedaz.cena_za_kwh = float(sprzedaz_data['cena_za_kwh'])
    if 'naleznosc' in sprzedaz_data:
        sprzedaz.naleznosc = float(sprzedaz_data['naleznosc'])
    if 'vat_procent' in sprzedaz_data:
        sprzedaz.vat_procent = float(sprzedaz_data['vat_procent'])
    
    db.commit()
    db.refresh(sprzedaz)
    return {"message": "Pozycja sprzedaży zaktualizowana", "sprzedaz_id": sprzedaz.id}


@router.delete("/invoices-detailed/sprzedaz/{sprzedaz_id}")
def delete_sprzedaz(sprzedaz_id: int, db: Session = Depends(get_db)):
    """Usuwa pozycję sprzedaży energii."""
    sprzedaz = db.query(ElectricityInvoiceSprzedazEnergii).filter(ElectricityInvoiceSprzedazEnergii.id == sprzedaz_id).first()
    if not sprzedaz:
        raise HTTPException(status_code=404, detail="Pozycja sprzedaży nie znaleziona")
    db.delete(sprzedaz)
    db.commit()
    return {"message": "Pozycja sprzedaży usunięta", "sprzedaz_id": sprzedaz_id}


@router.put("/invoices-detailed/oplaty/{oplata_id}")
def update_oplata(
    oplata_id: int,
    oplata_data: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db)
):
    """Aktualizuje opłatę dystrybucyjną."""
    oplata = db.query(ElectricityInvoiceOplataDystrybucyjna).filter(ElectricityInvoiceOplataDystrybucyjna.id == oplata_id).first()
    if not oplata:
        raise HTTPException(status_code=404, detail="Opłata nie znaleziona")
    
    from datetime import datetime
    
    if oplata_data.get('data'):
        oplata.data = datetime.strptime(oplata_data['data'], "%Y-%m-%d").date()
    if 'typ_oplaty' in oplata_data:
        oplata.typ_oplaty = oplata_data['typ_oplaty']
    if 'strefa' in oplata_data:
        oplata.strefa = oplata_data['strefa'] if oplata_data['strefa'] else None
    if 'jednostka' in oplata_data:
        oplata.jednostka = oplata_data['jednostka']
    if 'ilosc_kwh' in oplata_data:
        oplata.ilosc_kwh = oplata_data['ilosc_kwh'] if oplata_data['ilosc_kwh'] else None
    if 'ilosc_miesiecy' in oplata_data:
        oplata.ilosc_miesiecy = oplata_data['ilosc_miesiecy'] if oplata_data['ilosc_miesiecy'] else None
    if 'wspolczynnik' in oplata_data:
        oplata.wspolczynnik = float(oplata_data['wspolczynnik']) if oplata_data['wspolczynnik'] else None
    if 'cena' in oplata_data:
        oplata.cena = float(oplata_data['cena'])
    if 'naleznosc' in oplata_data:
        oplata.naleznosc = float(oplata_data['naleznosc'])
    if 'vat_procent' in oplata_data:
        oplata.vat_procent = float(oplata_data['vat_procent'])
    
    db.commit()
    db.refresh(oplata)
    return {"message": "Opłata zaktualizowana", "oplata_id": oplata.id}


@router.delete("/invoices-detailed/oplaty/{oplata_id}")
def delete_oplata(oplata_id: int, db: Session = Depends(get_db)):
    """Usuwa opłatę dystrybucyjną."""
    oplata = db.query(ElectricityInvoiceOplataDystrybucyjna).filter(ElectricityInvoiceOplataDystrybucyjna.id == oplata_id).first()
    if not oplata:
        raise HTTPException(status_code=404, detail="Opłata nie znaleziona")
    db.delete(oplata)
    db.commit()
    return {"message": "Opłata usunięta", "oplata_id": oplata_id}


@router.put("/invoices-detailed/rozliczenie-okresy/{okres_id}")
def update_rozliczenie_okres(
    okres_id: int,
    okres_data: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db)
):
    """Aktualizuje rozliczenie okresu."""
    okres = db.query(ElectricityInvoiceRozliczenieOkres).filter(ElectricityInvoiceRozliczenieOkres.id == okres_id).first()
    if not okres:
        raise HTTPException(status_code=404, detail="Okres nie znaleziony")
    
    from datetime import datetime
    
    if okres_data.get('data_okresu'):
        okres.data_okresu = datetime.strptime(okres_data['data_okresu'], "%Y-%m-%d").date()
    if 'numer_okresu' in okres_data:
        okres.numer_okresu = int(okres_data['numer_okresu'])
    
    db.commit()
    db.refresh(okres)
    return {"message": "Okres zaktualizowany", "okres_id": okres.id}


@router.delete("/invoices-detailed/rozliczenie-okresy/{okres_id}")
def delete_rozliczenie_okres(okres_id: int, db: Session = Depends(get_db)):
    """Usuwa rozliczenie okresu."""
    okres = db.query(ElectricityInvoiceRozliczenieOkres).filter(ElectricityInvoiceRozliczenieOkres.id == okres_id).first()
    if not okres:
        raise HTTPException(status_code=404, detail="Okres nie znaleziony")
    db.delete(okres)
    db.commit()
    return {"message": "Okres usunięty", "okres_id": okres_id}

