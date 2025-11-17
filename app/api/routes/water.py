"""
API endpoints for water billing.
All endpoints have prefix /api/water/
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Body
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from sqlalchemy.exc import IntegrityError
from typing import List, Optional, Dict, Any
from pathlib import Path
from datetime import datetime
import os

from app.core.database import get_db
from app.models.water import Local, Reading, Invoice, Bill
from app.models.gas import GasBill
from app.services.water.invoice_reader import (
    extract_text_from_pdf,
    parse_invoice_data,
    parse_period_from_filename,
    load_invoice_from_pdf
)
from app.services.water.meter_manager import generate_bills_for_period
from app.services.water import bill_generator
from app.integrations.google_sheets import (
    import_readings_from_sheets,
    import_locals_from_sheets,
    import_invoices_from_sheets
)
from app.core.water_credentials import (
    save_credentials,
    get_credentials,
    credentials_exist,
    delete_credentials
)

router = APIRouter(prefix="/api/water", tags=["water"])


# ========== UNIT ENDPOINTS ==========

@router.get("/locals/", response_model=List[dict])
def get_locals(db: Session = Depends(get_db)):
    """Gets list of all units."""
    locals_list = db.query(Local).all()
    return [{
        "id": l.id,
        "water_meter_name": l.water_meter_name,
        "gas_meter_name": l.gas_meter_name,
        "tenant": l.tenant,
        "local": l.local,
        "email": l.email
    } for l in locals_list]


@router.post("/locals/")
def create_local(water_meter_name: str, tenant: str, local: str, gas_meter_name: Optional[str] = None, email: Optional[str] = None, db: Session = Depends(get_db)):
    """Creates a new unit."""
    # Check if unit with the same water_meter_name already exists
    if water_meter_name:
        existing = db.query(Local).filter(Local.water_meter_name == water_meter_name).first()
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Unit with water meter '{water_meter_name}' already exists (ID: {existing.id}, unit: {existing.local}, tenant: {existing.tenant}). Use PUT /api/water/locals/{existing.id} to update."
            )
    
    # Check if unit with the same gas_meter_name already exists
    if gas_meter_name:
        existing_gas = db.query(Local).filter(Local.gas_meter_name == gas_meter_name).first()
        if existing_gas:
            raise HTTPException(
                status_code=400,
                detail=f"Unit with gas meter '{gas_meter_name}' already exists (ID: {existing_gas.id}, unit: {existing_gas.local}, tenant: {existing_gas.tenant}). Use PUT /api/water/locals/{existing_gas.id} to update."
            )
    
    try:
        new_local = Local(
            water_meter_name=water_meter_name,
            gas_meter_name=gas_meter_name,
            tenant=tenant,
            local=local,
            email=email
        )
        db.add(new_local)
        db.commit()
        db.refresh(new_local)
        return {"id": new_local.id, "message": "Unit created"}
    except IntegrityError as e:
        db.rollback()
        # Check if error relates to water_meter_name
        if "water_meter_name" in str(e.orig):
            existing = db.query(Local).filter(Local.water_meter_name == water_meter_name).first()
            if existing:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unit with water meter '{water_meter_name}' already exists (ID: {existing.id}, unit: {existing.local}, tenant: {existing.tenant}). Use PUT /api/water/locals/{existing.id} to update."
                )
        # Check if error relates to gas_meter_name
        elif gas_meter_name and "gas_meter_name" in str(e.orig):
            existing = db.query(Local).filter(Local.gas_meter_name == gas_meter_name).first()
            if existing:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unit with gas meter '{gas_meter_name}' already exists (ID: {existing.id}, unit: {existing.local}, tenant: {existing.tenant}). Use PUT /api/water/locals/{existing.id} to update."
                )
        # Other uniqueness error
        raise HTTPException(
            status_code=400,
            detail=f"Uniqueness error: {str(e.orig)}. Unit with this data already exists in database."
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating unit: {str(e)}")


@router.put("/locals/{local_id}")
def update_local(
    local_id: int,
    water_meter_name: Optional[str] = None,
    gas_meter_name: Optional[str] = None,
    tenant: Optional[str] = None,
    local: Optional[str] = None,
    email: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Updates an existing unit."""
    existing_local = db.query(Local).filter(Local.id == local_id).first()
    
    if not existing_local:
        raise HTTPException(status_code=404, detail="Unit not found")
    
    # Check if new water_meter_name is not already used by another unit
    if water_meter_name and water_meter_name != existing_local.water_meter_name:
        duplicate = db.query(Local).filter(
            Local.water_meter_name == water_meter_name,
            Local.id != local_id
        ).first()
        if duplicate:
            raise HTTPException(
                status_code=400,
                detail=f"Water meter '{water_meter_name}' is already used by another unit (ID: {duplicate.id})"
            )
        existing_local.water_meter_name = water_meter_name
    
    # Check if new gas_meter_name is not already used by another unit
    if gas_meter_name is not None and gas_meter_name != existing_local.gas_meter_name:
        duplicate_gas = db.query(Local).filter(
            Local.gas_meter_name == gas_meter_name,
            Local.id != local_id
        ).first()
        if duplicate_gas:
            raise HTTPException(
                status_code=400,
                detail=f"Gas meter '{gas_meter_name}' is already used by another unit (ID: {duplicate_gas.id})"
            )
        existing_local.gas_meter_name = gas_meter_name
    
    # Update remaining fields if provided
    if tenant is not None:
        existing_local.tenant = tenant
    if local is not None:
        existing_local.local = local
    if email is not None:
        existing_local.email = email
    
    try:
        db.commit()
        db.refresh(existing_local)
        return {
            "id": existing_local.id,
            "message": "Lokal zaktualizowany",
            "water_meter_name": existing_local.water_meter_name,
            "gas_meter_name": existing_local.gas_meter_name,
            "tenant": existing_local.tenant,
            "local": existing_local.local,
            "email": existing_local.email
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error updating unit: {str(e)}")


@router.delete("/locals/{local_id}")
def delete_local(local_id: int, db: Session = Depends(get_db)):
    """Deletes unit by ID. Also deletes all related bills."""
    local = db.query(Local).filter(Local.id == local_id).first()
    
    if not local:
        raise HTTPException(status_code=404, detail="Unit not found")
    
    # Delete all bills related to this unit
    bills = db.query(Bill).filter(Bill.local_id == local_id).all()
    for bill in bills:
        # Delete PDF file if exists
        if bill.pdf_path and Path(bill.pdf_path).exists():
            Path(bill.pdf_path).unlink()
        db.delete(bill)
    
    # Also delete gas bills
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


# ========== READING ENDPOINTS ==========

@router.get("/readings/", response_model=List[dict])
def get_readings(db: Session = Depends(get_db)):
    """Gets list of all readings."""
    readings = db.query(Reading).order_by(desc(Reading.data)).all()
    return [{
        "data": r.data,
        "water_meter_main": r.water_meter_main,
        "water_meter_5": r.water_meter_5,
        "water_meter_5a": r.water_meter_5a,
        "water_meter_5b": r.water_meter_5b  # Stored in database
    } for r in readings]


@router.get("/readings/{period}")
def get_reading(period: str, db: Session = Depends(get_db)):
    """Gets single reading by period."""
    reading = db.query(Reading).filter(Reading.data == period).first()
    
    if not reading:
        raise HTTPException(status_code=404, detail="Reading not found")
    
    return {
        "data": reading.data,
        "water_meter_main": reading.water_meter_main,
        "water_meter_5": reading.water_meter_5,
        "water_meter_5a": reading.water_meter_5a,
        "water_meter_5b": reading.water_meter_5b  # Stored in database
    }


@router.put("/readings/{period}")
def update_reading(
    period: str,
    water_meter_main: float,
    water_meter_5: int,
    water_meter_5a: int,
    db: Session = Depends(get_db)
):
    """Updates reading by period.
    Note: water_meter_5b (dol) is calculated as main - 5 - 5a.
    """
    reading = db.query(Reading).filter(Reading.data == period).first()
    
    if not reading:
        raise HTTPException(status_code=404, detail="Reading not found")
    
    # Calculate water_meter_5b (dol) as: main - 5 - 5a
    water_meter_5b = int(round(float(water_meter_main), 2) - water_meter_5 - water_meter_5a)
    
    reading.water_meter_main = round(float(water_meter_main), 2)
    reading.water_meter_5 = int(water_meter_5)
    reading.water_meter_5a = int(water_meter_5a)
    reading.water_meter_5b = water_meter_5b
    
    db.commit()
    db.refresh(reading)
    
    return {
        "message": "Reading updated",
        "data": reading.data
    }


@router.post("/readings/")
def create_reading(
    data: str,
    water_meter_main: float,
    water_meter_5: int,
    water_meter_5a: int,
    db: Session = Depends(get_db)
):
    """Creates a new meter reading.
    Note: water_meter_5b (dol) is calculated as main - 5 - 5a.
    """
    existing = db.query(Reading).filter(Reading.data == data).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Reading for period {data} already exists")
    
    # Calculate water_meter_5b (dol) as: main - 5 - 5a
    water_meter_5b = int(round(float(water_meter_main), 2) - water_meter_5 - water_meter_5a)
    
    # Round water_meter_main to 2 decimal places
    new_reading = Reading(
        data=data,
        water_meter_main=round(float(water_meter_main), 2),
        water_meter_5=water_meter_5,
        water_meter_5a=water_meter_5a,
        water_meter_5b=water_meter_5b
    )
    db.add(new_reading)
    db.commit()
    db.refresh(new_reading)
    return {"message": "Reading created", "data": data}


@router.delete("/readings/{period}")
def delete_reading(period: str, db: Session = Depends(get_db)):
    """Deletes reading for given period. Also deletes all bills for this period."""
    reading = db.query(Reading).filter(Reading.data == period).first()
    
    if not reading:
        raise HTTPException(status_code=404, detail=f"Reading for period {period} not found")
    
    # Delete all bills for this period
    bills = db.query(Bill).filter(Bill.reading_id == period).all()
    deleted_bills_count = 0
    for bill in bills:
        # Delete PDF file if exists
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


# ========== INVOICE ENDPOINTS ==========

@router.get("/invoices/", response_model=List[dict])
def get_invoices(db: Session = Depends(get_db)):
    """Gets list of all invoices."""
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


@router.post("/invoices/parse")
async def parse_invoice(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Parses invoice PDF and returns data for verification.
    Does NOT save to database!
    """
    # Save file temporarily
    upload_folder = Path("invoices_raw")
    upload_folder.mkdir(exist_ok=True)
    
    file_path = upload_folder / file.filename
    
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    # Extract text from PDF
    text = extract_text_from_pdf(str(file_path))
    if not text:
        raise HTTPException(status_code=400, detail="Failed to extract text from PDF file")
    
    # Parse invoice data
    invoice_data = parse_invoice_data(text)
    
    if not invoice_data:
        raise HTTPException(status_code=400, detail="Failed to parse invoice data")
    
    # Determine billing period
    period = None
    if '_extracted_period' in invoice_data:
        period = invoice_data['_extracted_period']
    else:
        # Try to extract from filename
        period = parse_period_from_filename(os.path.basename(file_path))
        if not period and 'period_start' in invoice_data:
            period_start = invoice_data['period_start']
            if isinstance(period_start, datetime):
                period = f"{period_start.year}-{period_start.month:02d}"
    
    # Add period to data
    if period:
        invoice_data['data'] = period
    
    # Convert dates to strings (for JSON)
    if 'period_start' in invoice_data and isinstance(invoice_data['period_start'], datetime):
        invoice_data['period_start'] = invoice_data['period_start'].strftime('%Y-%m-%d')
    if 'period_stop' in invoice_data and isinstance(invoice_data['period_stop'], datetime):
        invoice_data['period_stop'] = invoice_data['period_stop'].strftime('%Y-%m-%d')
    
    # Remove helper fields that are not needed in the form
    invoice_data.pop('_extracted_period', None)
    invoice_data.pop('meter_readings', None)
    
    return invoice_data


@router.post("/invoices/upload")
async def upload_invoice(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Loads invoice PDF from file (DEPRECATED - use /invoices/parse + /invoices/verify)."""
    # Save file temporarily
    upload_folder = Path("invoices_raw")
    upload_folder.mkdir(exist_ok=True)
    
    file_path = upload_folder / file.filename
    
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    # Load invoice
    invoice = load_invoice_from_pdf(db, str(file_path))
    
    if not invoice:
        raise HTTPException(status_code=400, detail="Failed to load invoice")
    
    return {"message": "Invoice loaded", "invoice_number": invoice.invoice_number}


@router.post("/invoices/verify")
def verify_and_save_invoice(
    invoice_data: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db)
):
    """
    Saves invoice after user verification.
    Called from dashboard after confirmation.
    """
    # Validate required fields
    required_fields = ['data', 'usage', 'water_cost_m3', 'sewage_cost_m3', 
                      'nr_of_subscription', 'water_subscr_cost', 'sewage_subscr_cost',
                      'vat', 'period_start', 'period_stop', 'invoice_number', 'gross_sum']
    
    missing_fields = [field for field in required_fields if field not in invoice_data]
    if missing_fields:
        raise HTTPException(status_code=400, detail=f"Missing required fields: {', '.join(missing_fields)}")
    
    # Convert dates
    try:
        period_start_date = datetime.strptime(invoice_data['period_start'], "%Y-%m-%d").date()
        period_stop_date = datetime.strptime(invoice_data['period_stop'], "%Y-%m-%d").date()
    except (ValueError, TypeError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {e}")
    
    # Round all Float values to 2 decimal places
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


@router.post("/invoices/")
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
    """Adds invoice manually to database.
    Multiple invoices for the same period (data) are possible in case of cost increases."""
    
    # Convert dates
    try:
        period_start_date = datetime.strptime(period_start, "%Y-%m-%d").date()
        period_stop_date = datetime.strptime(period_stop, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    # Round all Float values to 2 decimal places
    # Create new invoice
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


@router.get("/invoices/{invoice_id}")
def get_invoice(invoice_id: int, db: Session = Depends(get_db)):
    """Gets single invoice by ID."""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
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


@router.put("/invoices/{invoice_id}")
def update_invoice(
    invoice_id: int,
    invoice_data: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db)
):
    """Updates invoice by ID."""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    # Convert dates if provided
    if 'period_start' in invoice_data:
        try:
            invoice_data['period_start'] = datetime.strptime(invoice_data['period_start'], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Invalid date format for period_start")
    
    if 'period_stop' in invoice_data:
        try:
            invoice_data['period_stop'] = datetime.strptime(invoice_data['period_stop'], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Invalid date format for period_stop")
    
    # Update fields
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


@router.delete("/invoices/{invoice_id}")
def delete_invoice(invoice_id: int, db: Session = Depends(get_db)):
    """Deletes invoice by ID. Also deletes all bills for this invoice's period."""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    period = invoice.data
    
    # Delete all bills for this period (may be multiple invoices for the same period)
    # Check if there are other invoices for this period
    other_invoices = db.query(Invoice).filter(
        Invoice.data == period,
        Invoice.id != invoice_id
    ).count()
    
    deleted_bills_count = 0
    if other_invoices == 0:
        # If this is the last invoice for this period, delete all bills
        bills = db.query(Bill).filter(Bill.data == period).all()
        for bill in bills:
            # Delete PDF file if exists
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


# ========== BILL ENDPOINTS ==========

@router.get("/bills/", response_model=List[dict])
def get_bills(db: Session = Depends(get_db)):
    """Gets list of all bills."""
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


@router.get("/bills/period/{period}", response_model=List[dict])
def get_bills_for_period(period: str, db: Session = Depends(get_db)):
    """Gets bills for given period."""
    bills = db.query(Bill).filter(Bill.data == period).all()
    return [{
        "id": b.id,
        "data": b.data,
        "local": b.local,
        "usage_m3": b.usage_m3,
        "gross_sum": b.gross_sum
    } for b in bills]


@router.post("/bills/generate/{period}")
def generate_bills(period: str, db: Session = Depends(get_db)):
    """
    Generates bills for given period.
    Requires invoice and readings for this period.
    """
    try:
        # Check if bills already exist
        existing = db.query(Bill).filter(Bill.data == period).first()
        if existing:
            return {"message": f"Bills for period {period} already exist. Use /bills/regenerate/{period}"}
        
        # Generate bills
        bills = generate_bills_for_period(db, period)
        
        # Generate PDF files
        pdf_files = bill_generator.generate_all_bills_for_period(db, period)
        
        # Sprawdź czy okres jest w pełni rozliczony i wykonaj backup jeśli tak
        from app.core.billing_period import handle_period_settlement
        settlement_result = handle_period_settlement(db, period)
        
        response = {
            "message": "Bills generated",
            "period": period,
            "bills_count": len(bills),
            "pdf_files": pdf_files
        }
        
        if settlement_result.get("is_fully_settled"):
            response["settlement"] = settlement_result
        
        return response
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/bills/regenerate/{period}")
def regenerate_bills(period: str, db: Session = Depends(get_db)):
    """Regenerates bills and PDF files for given period."""
    # Delete old bills
    bills = db.query(Bill).filter(Bill.data == period).all()
    for bill in bills:
        # Delete PDF file if exists
        if bill.pdf_path and Path(bill.pdf_path).exists():
            Path(bill.pdf_path).unlink()
        db.delete(bill)
    db.commit()
    
    try:
        # Generate new bills
        bills = generate_bills_for_period(db, period)
        
        # Generate PDF files
        pdf_files = bill_generator.generate_all_bills_for_period(db, period)
        
        return {
            "message": "Bills regenerated",
            "period": period,
            "bills_count": len(bills),
            "pdf_files": pdf_files
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/bills/generate-all")
def generate_all_bills(db: Session = Depends(get_db)):
    """
    Generates all possible bills for all periods
    that have invoices and readings.
    Generates ONLY missing bills (does not delete existing ones).
    """
    try:
        result = bill_generator.generate_all_possible_bills(db)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating bills: {str(e)}")


@router.post("/bills/regenerate-all")
def regenerate_all_bills(db: Session = Depends(get_db)):
    """
    Regenerates ALL bills - deletes existing and generates anew.
    Use this endpoint after changes in calculation logic (e.g., bug fixes).
    
    Performs:
    1. Deletes all existing bills from database
    2. Deletes all bill PDF files
    3. Generates all possible bills for periods with invoices and readings
    4. Generates PDF files for all generated bills
    """
    try:
        # 1. Delete all existing bills
        all_bills = db.query(Bill).all()
        deleted_count = 0
        
        for bill in all_bills:
            # Delete PDF file if exists
            if bill.pdf_path and Path(bill.pdf_path).exists():
                try:
                    Path(bill.pdf_path).unlink()
                except Exception as e:
                    print(f"[WARNING] Failed to delete file {bill.pdf_path}: {e}")
            db.delete(bill)
            deleted_count += 1
        
        db.commit()
        
        if deleted_count > 0:
            print(f"[INFO] Deleted {deleted_count} existing bills")
        
        # 2. Generate all bills anew
        result = bill_generator.generate_all_possible_bills(db)
        
        return {
            "message": "All bills regenerated",
            "deleted_bills": deleted_count,
            "regenerated_periods": result.get("periods_processed", 0),
            "bills_generated": result.get("bills_generated", 0),
            "pdfs_generated": result.get("pdfs_generated", 0),
            "errors": result.get("errors", []),
            "processed_periods": result.get("processed_periods", [])
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error regenerating bills: {str(e)}")


@router.get("/bills/{bill_id}")
def get_bill(bill_id: int, db: Session = Depends(get_db)):
    """Gets single bill by ID."""
    bill = db.query(Bill).filter(Bill.id == bill_id).first()
    
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    
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


@router.put("/bills/{bill_id}")
def update_bill(
    bill_id: int,
    bill_data: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db)
):
    """Updates bill by ID."""
    bill = db.query(Bill).filter(Bill.id == bill_id).first()
    
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    
    # Update fields
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


@router.get("/bills/download/{bill_id}")
def download_bill(bill_id: int, db: Session = Depends(get_db)):
    """Downloads bill PDF file."""
    bill = db.query(Bill).filter(Bill.id == bill_id).first()
    
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    
    if not bill.pdf_path or not Path(bill.pdf_path).exists():
        # Generate file if it doesn't exist
        bill.pdf_path = bill_generator.generate_bill_pdf(db, bill)
        db.commit()
    
    return FileResponse(bill.pdf_path, media_type="application/pdf")


@router.delete("/bills/{bill_id}")
def delete_bill(bill_id: int, db: Session = Depends(get_db)):
    """Deletes single bill by ID."""
    bill = db.query(Bill).filter(Bill.id == bill_id).first()
    
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    
    # Delete PDF file if exists
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


@router.delete("/bills/period/{period}")
def delete_bills_for_period(period: str, db: Session = Depends(get_db)):
    """Deletes all bills for given period."""
    bills = db.query(Bill).filter(Bill.data == period).all()
    
    if not bills:
        return {"message": f"No bills for period {period}", "deleted_count": 0}
    
    deleted_ids = []
    for bill in bills:
        # Delete PDF file if exists
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


@router.delete("/bills/")
def delete_all_bills(db: Session = Depends(get_db)):
    """Deletes all bills from database."""
    bills = db.query(Bill).all()
    
    if not bills:
        return {"message": "No bills in database", "deleted_count": 0}
    
    deleted_count = 0
    for bill in bills:
        # Delete PDF file if exists
        if bill.pdf_path and Path(bill.pdf_path).exists():
            Path(bill.pdf_path).unlink()
        
        db.delete(bill)
        deleted_count += 1
    
    db.commit()
    
    return {
        "message": f"All bills deleted ({deleted_count})",
        "deleted_count": deleted_count
    }


# ========== GOOGLE SHEETS ENDPOINTS ==========

@router.post("/import/readings")
def import_readings(
    credentials_path: str,
    spreadsheet_id: str,
    sheet_name: str = "Odczyty",
    db: Session = Depends(get_db)
):
    """
    Imports meter readings from Google Sheets.
    
    Requires:
    - credentials_path: Path to JSON file with Google Service Account credentials
    - spreadsheet_id: Spreadsheet ID (from URL: https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit)
    - sheet_name: Sheet name (default: "Odczyty")
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
        raise HTTPException(status_code=500, detail=f"Import error: {str(e)}")


@router.post("/import/locals")
def import_locals(
    credentials_path: str,
    spreadsheet_id: str,
    sheet_name: str = "Lokale",
    db: Session = Depends(get_db)
):
    """
    Imports units from Google Sheets.
    
    Requires:
    - credentials_path: Path to JSON file with Google Service Account credentials
    - spreadsheet_id: Spreadsheet ID
    - sheet_name: Sheet name (default: "Lokale")
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
        raise HTTPException(status_code=500, detail=f"Import error: {str(e)}")


@router.post("/import/invoices")
def import_invoices(
    credentials_path: str,
    spreadsheet_id: str,
    sheet_name: str = "Faktury",
    db: Session = Depends(get_db)
):
    """
    Imports invoices from Google Sheets.
    
    Requires:
    - credentials_path: Path to JSON file with Google Service Account credentials
    - spreadsheet_id: Spreadsheet ID
    - sheet_name: Sheet name (default: "Faktury")
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
        raise HTTPException(status_code=500, detail=f"Import error: {str(e)}")


# ========== STATISTICS ENDPOINTS ==========

@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    """Returns statistics for dashboard."""
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
    
    # Latest period
    latest_reading = db.query(Reading).order_by(desc(Reading.data)).first()
    if latest_reading:
        stats["latest_period"] = latest_reading.data
    
    # Total gross sum of all bills
    total_sum = db.query(func.sum(Bill.gross_sum)).scalar()
    if total_sum:
        stats["total_gross_sum"] = float(total_sum)
    
    # Periods with bills
    periods = db.query(Bill.data).distinct().order_by(desc(Bill.data)).all()
    stats["periods_with_bills"] = [p[0] for p in periods[:10]]  # Last 10
    
    # Available periods (having both invoices and readings)
    reading_periods = set(r.data for r in db.query(Reading.data).distinct().all())
    invoice_periods = set(i.data for i in db.query(Invoice.data).distinct().all())
    stats["available_periods"] = sorted(reading_periods & invoice_periods, reverse=True)
    
    return stats


# ========== AQUANET CREDENTIALS ENDPOINTS ==========

@router.post("/credentials/")
def save_aquanet_credentials(
    username: str = Body(...),
    password: str = Body(...),
    db: Session = Depends(get_db)
):
    """Zapisuje dane logowania do AQUANET w zaszyfrowanym pliku."""
    success = save_credentials(username, password)
    if not success:
        raise HTTPException(status_code=500, detail="Błąd zapisywania danych logowania")
    return {"message": "Dane logowania zapisane pomyślnie"}


@router.get("/credentials/")
def get_aquanet_credentials(db: Session = Depends(get_db)):
    """Pobiera dane logowania do AQUANET (tylko do użycia w automatycznym logowaniu)."""
    credentials = get_credentials()
    if not credentials:
        raise HTTPException(status_code=404, detail="Brak zapisanych danych logowania")
    return credentials


@router.get("/credentials/exists/")
def check_credentials_exist(db: Session = Depends(get_db)):
    """Sprawdza czy dane logowania są zapisane."""
    return {"exists": credentials_exist()}


@router.delete("/credentials/")
def delete_aquanet_credentials(db: Session = Depends(get_db)):
    """Usuwa zapisane dane logowania do AQUANET."""
    success = delete_credentials()
    if not success:
        raise HTTPException(status_code=500, detail="Błąd usuwania danych logowania")
    return {"message": "Dane logowania usunięte pomyślnie"}

