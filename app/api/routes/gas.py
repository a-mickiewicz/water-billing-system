"""
API endpoints for gas billing.
All endpoints have prefix /api/gas/
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Body
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from typing import List, Optional, Dict, Any
from pathlib import Path
from datetime import datetime

from app.core.database import get_db
from app.models.gas import GasInvoice, GasBill
from app.models.water import Local
from app.services.gas.manager import GasBillingManager
from app.services.gas.bill_generator import generate_all_bills_for_period

router = APIRouter(prefix="/api/gas", tags=["gas"])

# Manager instance
gas_manager = GasBillingManager()


# ========== GAS INVOICE ENDPOINTS ==========

@router.get("/invoices/", response_model=List[dict])
def get_gas_invoices(db: Session = Depends(get_db)):
    """Gets list of all gas invoices."""
    invoices = db.query(GasInvoice).order_by(desc(GasInvoice.data)).all()
    return [{
        "id": i.id,
        "data": i.data,
        "invoice_number": i.invoice_number,
        "period_start": i.period_start.isoformat() if i.period_start else None,
        "period_stop": i.period_stop.isoformat() if i.period_stop else None,
        "total_gross_sum": i.total_gross_sum
    } for i in invoices]


@router.post("/invoices/")
def create_gas_invoice(
    invoice_data: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db)
):
    """
    Adds gas invoice manually to database.
    Accepts JSON body with invoice data.
    If only gross values are provided, automatically calculates net values and VAT (assuming 23% VAT).
    """
    # Extract data from dict
    data = invoice_data.get('data')
    period_start = invoice_data.get('period_start')
    period_stop = invoice_data.get('period_stop')
    previous_reading = invoice_data.get('previous_reading')
    current_reading = invoice_data.get('current_reading')
    invoice_number = invoice_data.get('invoice_number')
    total_gross_sum = invoice_data.get('total_gross_sum')
    vat_rate = invoice_data.get('vat_rate', 0.23)
    
    # Gross values (from form)
    fuel_value_gross = invoice_data.get('fuel_value_gross', 0.0)
    subscription_value_gross = invoice_data.get('subscription_value_gross', 0.0)
    distribution_fixed_value_gross = invoice_data.get('distribution_fixed_value_gross', 0.0)
    distribution_variable_value_gross = invoice_data.get('distribution_variable_value_gross', 0.0)
    
    # Validate required fields
    if not all([data, period_start, period_stop, previous_reading is not None, current_reading is not None, 
                invoice_number, total_gross_sum is not None]):
        raise HTTPException(status_code=400, detail="Missing required fields")
    
    try:
        period_start_date = datetime.strptime(period_start, "%Y-%m-%d").date()
        period_stop_date = datetime.strptime(period_stop, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        try:
            # Try HTML form format (YYYY-MM-DD)
            if isinstance(period_start, str) and len(period_start) == 10:
                period_start_date = datetime.strptime(period_start, "%Y-%m-%d").date()
                period_stop_date = datetime.strptime(period_stop, "%Y-%m-%d").date()
            else:
                raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        except:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    # Calculate net values and VAT from gross values (if not provided)
    def calculate_net_from_gross(gross_value, vat):
        """Calculates net value from gross and VAT."""
        if gross_value == 0:
            return 0.0, 0.0
        net_value = round(gross_value / (1 + vat), 2)
        vat_amount = round(gross_value - net_value, 2)
        return net_value, vat_amount
    
    # Calculate missing values for fuel
    fuel_value_net = invoice_data.get('fuel_value_net')
    fuel_vat_amount = invoice_data.get('fuel_vat_amount')
    if fuel_value_net is None or fuel_vat_amount is None:
        fuel_value_net, fuel_vat_amount = calculate_net_from_gross(fuel_value_gross, vat_rate)
    
    # Calculate missing values for subscription
    subscription_value_net = invoice_data.get('subscription_value_net')
    subscription_vat_amount = invoice_data.get('subscription_vat_amount')
    if subscription_value_net is None or subscription_vat_amount is None:
        subscription_value_net, subscription_vat_amount = calculate_net_from_gross(subscription_value_gross, vat_rate)
    
    # Calculate missing values for fixed distribution
    distribution_fixed_price_net = invoice_data.get('distribution_fixed_price_net', 0.0)
    distribution_fixed_vat_amount = invoice_data.get('distribution_fixed_vat_amount')
    if distribution_fixed_vat_amount is None:
        _, distribution_fixed_vat_amount = calculate_net_from_gross(distribution_fixed_value_gross, vat_rate)
    
    # Calculate missing values for variable distribution
    distribution_variable_price_net = invoice_data.get('distribution_variable_price_net', 0.0)
    distribution_variable_vat_amount = invoice_data.get('distribution_variable_vat_amount')
    if distribution_variable_vat_amount is None:
        _, distribution_variable_vat_amount = calculate_net_from_gross(distribution_variable_value_gross, vat_rate)
    
    # Get or set default values for remaining fields
    fuel_usage_m3 = invoice_data.get('fuel_usage_m3')
    if fuel_usage_m3 is None:
        fuel_usage_m3 = round(float(current_reading) - float(previous_reading), 2)
    
    fuel_price_net = invoice_data.get('fuel_price_net', 0.0)
    if fuel_price_net == 0 and fuel_usage_m3 > 0:
        fuel_price_net = round(fuel_value_net / fuel_usage_m3, 2)
    
    subscription_quantity = invoice_data.get('subscription_quantity')
    if subscription_quantity is None:
        # Default 2 months for bi-monthly invoice
        subscription_quantity = 2
    subscription_quantity = int(subscription_quantity)
    
    subscription_price_net = invoice_data.get('subscription_price_net', 0.0)
    if subscription_price_net == 0 and subscription_quantity > 0:
        subscription_price_net = round(subscription_value_net / subscription_quantity, 2)
    elif subscription_price_net == 0:
        subscription_price_net = 0.0
    
    distribution_fixed_quantity = invoice_data.get('distribution_fixed_quantity')
    if distribution_fixed_quantity is None:
        # Default 2 months for bi-monthly invoice
        distribution_fixed_quantity = 2
    distribution_fixed_quantity = int(distribution_fixed_quantity)
    
    if distribution_fixed_price_net == 0 and distribution_fixed_quantity > 0:
        # Calculate net price from gross value
        distribution_fixed_net_value, _ = calculate_net_from_gross(distribution_fixed_value_gross, vat_rate)
        distribution_fixed_price_net = round(distribution_fixed_net_value / distribution_fixed_quantity, 2) if distribution_fixed_quantity > 0 else 0.0
    
    distribution_variable_quantity = invoice_data.get('distribution_variable_quantity')
    if distribution_variable_quantity is None:
        # Default 2 months for bi-monthly invoice
        distribution_variable_quantity = 2
    distribution_variable_quantity = int(distribution_variable_quantity)
    
    if distribution_variable_price_net == 0 and distribution_variable_quantity > 0:
        # Calculate net price from gross value
        distribution_variable_net_value, _ = calculate_net_from_gross(distribution_variable_value_gross, vat_rate)
        distribution_variable_price_net = round(distribution_variable_net_value / distribution_variable_quantity, 2) if distribution_variable_quantity > 0 else 0.0
    
    balance_before_settlement = invoice_data.get('balance_before_settlement')
    
    new_invoice = GasInvoice(
        data=data,
        period_start=period_start_date,
        period_stop=period_stop_date,
        previous_reading=round(float(previous_reading), 2),
        current_reading=round(float(current_reading), 2),
        fuel_usage_m3=round(float(fuel_usage_m3), 2),
        fuel_price_net=round(float(fuel_price_net), 2),
        fuel_value_net=round(float(fuel_value_net), 2),
        fuel_vat_amount=round(float(fuel_vat_amount), 2),
        fuel_value_gross=round(float(fuel_value_gross), 2),
        subscription_quantity=subscription_quantity,
        subscription_price_net=round(float(subscription_price_net), 2),
        subscription_value_net=round(float(subscription_value_net), 2),
        subscription_vat_amount=round(float(subscription_vat_amount), 2),
        subscription_value_gross=round(float(subscription_value_gross), 2),
        distribution_fixed_quantity=distribution_fixed_quantity,
        distribution_fixed_price_net=round(float(distribution_fixed_price_net), 2),
        distribution_fixed_vat_amount=round(float(distribution_fixed_vat_amount), 2),
        distribution_fixed_value_gross=round(float(distribution_fixed_value_gross), 2),
        distribution_variable_quantity=distribution_variable_quantity,
        distribution_variable_price_net=round(float(distribution_variable_price_net), 2),
        distribution_variable_vat_amount=round(float(distribution_variable_vat_amount), 2),
        distribution_variable_value_gross=round(float(distribution_variable_value_gross), 2),
        vat_rate=round(float(vat_rate), 2),
        invoice_number=invoice_number,
        total_gross_sum=round(float(total_gross_sum), 2),
        balance_before_settlement=round(float(balance_before_settlement), 2) if balance_before_settlement else None
    )
    
    db.add(new_invoice)
    db.commit()
    db.refresh(new_invoice)
    
    return {
        "message": "Gas invoice added",
        "id": new_invoice.id,
        "invoice_number": new_invoice.invoice_number,
        "data": new_invoice.data
    }


@router.post("/invoices/parse")
async def parse_gas_invoice(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Parses invoice PDF and returns data for verification.
    Does NOT save to database!
    """
    from app.services.gas.invoice_reader import load_invoice_from_pdf
    
    # Save file temporarily
    upload_folder = Path("invoices_raw/gas")
    upload_folder.mkdir(parents=True, exist_ok=True)
    
    file_path = upload_folder / file.filename
    
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    # Parse invoice
    invoice_data = load_invoice_from_pdf(db, str(file_path))
    
    if not invoice_data:
        raise HTTPException(status_code=400, detail="Failed to parse invoice. Check file format.")
    
    # Convert dates to strings for JSON (dashboard expects YYYY-MM-DD format)
    if 'period_start' in invoice_data and invoice_data['period_start']:
        if isinstance(invoice_data['period_start'], datetime):
            invoice_data['period_start'] = invoice_data['period_start'].strftime('%Y-%m-%d')
        elif hasattr(invoice_data['period_start'], 'isoformat'):
            invoice_data['period_start'] = invoice_data['period_start'].isoformat()
    
    if 'period_stop' in invoice_data and invoice_data['period_stop']:
        if isinstance(invoice_data['period_stop'], datetime):
            invoice_data['period_stop'] = invoice_data['period_stop'].strftime('%Y-%m-%d')
        elif hasattr(invoice_data['period_stop'], 'isoformat'):
            invoice_data['period_stop'] = invoice_data['period_stop'].isoformat()
    
    if 'payment_due_date' in invoice_data and invoice_data['payment_due_date']:
        if isinstance(invoice_data['payment_due_date'], datetime):
            invoice_data['payment_due_date'] = invoice_data['payment_due_date'].strftime('%Y-%m-%d')
        elif hasattr(invoice_data['payment_due_date'], 'isoformat'):
            invoice_data['payment_due_date'] = invoice_data['payment_due_date'].isoformat()
    
    # Return parsed data (without message and file_path - dashboard expects data directly)
    return invoice_data


@router.post("/invoices/verify")
def verify_and_save_gas_invoice(
    invoice_data: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db)
):
    """
    Saves gas invoice after user verification.
    Called from dashboard after confirmation.
    """
    from app.services.gas.invoice_reader import save_invoice_after_verification
    
    try:
        # Save invoice
        invoice = save_invoice_after_verification(db, invoice_data)
        
        if not invoice:
            raise HTTPException(status_code=400, detail="Error saving invoice")
        
        return {
            "message": "Gas invoice saved",
            "id": invoice.id,
            "invoice_number": invoice.invoice_number,
            "data": invoice.data
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"[ERROR] Błąd zapisu faktury gazu: {error_details}")
        raise HTTPException(status_code=500, detail=f"Error saving invoice: {str(e)}")


# ========== GAS BILL ENDPOINTS ==========

@router.get("/bills/", response_model=List[dict])
def get_gas_bills(db: Session = Depends(get_db)):
    """Gets list of all gas bills."""
    bills = db.query(GasBill).order_by(desc(GasBill.data)).all()
    return [{
        "id": b.id,
        "data": b.data,
        "local": b.local,
        "cost_share": b.cost_share,
        # Use values from database (updated by PDF generator)
        "fuel_cost_gross": b.fuel_cost_gross,
        "subscription_cost_gross": b.subscription_cost_gross,
        "distribution_fixed_cost_gross": b.distribution_fixed_cost_gross,
        "distribution_variable_cost_gross": b.distribution_variable_cost_gross,
        "total_net_sum": b.total_net_sum,
        "total_gross_sum": b.total_gross_sum,  # Final gross amount to pay (including interest for gora)
        "pdf_path": b.pdf_path
    } for b in bills]


@router.get("/bills/period/{period}", response_model=List[dict])
def get_gas_bills_for_period(period: str, db: Session = Depends(get_db)):
    """Gets gas bills for given period."""
    bills = db.query(GasBill).filter(GasBill.data == period).all()
    return [{
        "id": b.id,
        "data": b.data,
        "local": b.local,
        "total_gross_sum": b.total_gross_sum
    } for b in bills]


@router.post("/bills/generate/{period}")
def generate_gas_bills(period: str, db: Session = Depends(get_db)):
    """
    Generates gas bills for given period.
    Requires invoice for this period.
    """
    try:
        # Check if bills already exist
        existing = db.query(GasBill).filter(GasBill.data == period).first()
        if existing:
            return {"message": f"Bills for period {period} already exist. Use /api/gas/bills/regenerate/{period}"}
        
        # Generate bills
        bills = gas_manager.generate_bills_for_period(db, period)
        
        # Refresh session to have current objects from database
        db.flush()
        
        # Generate PDF files
        try:
            pdf_files = generate_all_bills_for_period(db, period)
        except Exception as pdf_error:
            # Log error but don't interrupt - bills are already generated
            import traceback
            error_details = traceback.format_exc()
            print(f"[ERROR] Error generating PDF for period {period}: {pdf_error}")
            print(error_details)
            pdf_files = []
        
        return {
            "message": "Gas bills generated",
            "period": period,
            "bills_count": len(bills),
            "pdfs_generated": len(pdf_files),
            "warning": f"Wygenerowano {len(bills)} rachunków, ale {len(pdf_files)} plików PDF" if len(pdf_files) != len(bills) else None
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/bills/generate-pdf/{period}")
def generate_gas_bills_pdf(period: str, db: Session = Depends(get_db)):
    """
    Generates PDF files for existing gas bills of given period.
    Useful when bills already exist but don't have generated PDFs.
    """
    try:
        pdf_files = generate_all_bills_for_period(db, period)
        return {
            "message": "PDF files generated",
            "period": period,
            "pdfs_generated": len(pdf_files)
        }
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"[ERROR] Błąd podczas generowania PDF dla okresu {period}: {e}")
        print(error_details)
        raise HTTPException(status_code=500, detail=f"Error generating PDF: {str(e)}")


@router.post("/bills/regenerate/{period}")
def regenerate_gas_bills(period: str, db: Session = Depends(get_db)):
    """Regenerates gas bills for given period."""
    # Delete old bills
    bills = db.query(GasBill).filter(GasBill.data == period).all()
    for bill in bills:
        # Delete PDF file if exists
        if bill.pdf_path and Path(bill.pdf_path).exists():
            Path(bill.pdf_path).unlink()
        db.delete(bill)
    db.commit()
    
    try:
        # Generate new bills
        bills = gas_manager.generate_bills_for_period(db, period)
        
        # Refresh session to have current objects from database
        db.flush()
        
        # Generate PDF files
        try:
            pdf_files = generate_all_bills_for_period(db, period)
        except Exception as pdf_error:
            # Log error but don't interrupt - bills are already generated
            import traceback
            error_details = traceback.format_exc()
            print(f"[ERROR] Error generating PDF for period {period}: {pdf_error}")
            print(error_details)
            pdf_files = []
        
        return {
            "message": "Gas bills regenerated",
            "period": period,
            "bills_count": len(bills),
            "pdfs_generated": len(pdf_files),
            "warning": f"Wygenerowano {len(bills)} rachunków, ale {len(pdf_files)} plików PDF" if len(pdf_files) != len(bills) else None
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/bills/download/{bill_id}")
def download_gas_bill(bill_id: int, db: Session = Depends(get_db)):
    """Downloads gas bill PDF file."""
    from app.services.gas.bill_generator import generate_bill_pdf
    
    bill = db.query(GasBill).filter(GasBill.id == bill_id).first()
    
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    
    if not bill.pdf_path or not Path(bill.pdf_path).exists():
        # Generate file if it doesn't exist
        try:
            bill.pdf_path = generate_bill_pdf(db, bill)
            db.commit()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Cannot generate PDF file: {str(e)}")
    
    return FileResponse(bill.pdf_path, media_type="application/pdf")


@router.get("/bills/{bill_id}")
def get_gas_bill(bill_id: int, db: Session = Depends(get_db)):
    """Gets single gas bill by ID."""
    bill = db.query(GasBill).filter(GasBill.id == bill_id).first()
    
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    
    return {
        "id": bill.id,
        "data": bill.data,
        "local": bill.local,
        "cost_share": bill.cost_share,
        "fuel_cost_gross": bill.fuel_cost_gross,
        "subscription_cost_gross": bill.subscription_cost_gross,
        "distribution_fixed_cost_gross": bill.distribution_fixed_cost_gross,
        "distribution_variable_cost_gross": bill.distribution_variable_cost_gross,
        "total_net_sum": bill.total_net_sum,
        "total_gross_sum": bill.total_gross_sum,
        "pdf_path": bill.pdf_path
    }


@router.put("/bills/{bill_id}")
def update_gas_bill(
    bill_id: int,
    bill_data: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db)
):
    """Updates gas bill by ID."""
    bill = db.query(GasBill).filter(GasBill.id == bill_id).first()
    
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
        "message": "Gas bill updated",
        "id": bill.id,
        "data": bill.data,
        "local": bill.local
    }


@router.delete("/bills/{bill_id}")
def delete_gas_bill(bill_id: int, db: Session = Depends(get_db)):
    """Deletes gas bill by ID."""
    bill = db.query(GasBill).filter(GasBill.id == bill_id).first()
    
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    
    # Delete PDF file if exists
    if bill.pdf_path and Path(bill.pdf_path).exists():
        Path(bill.pdf_path).unlink()
    
    db.delete(bill)
    db.commit()
    
    return {
        "message": "Gas bill deleted",
        "id": bill_id,
        "period": bill.data,
        "local": bill.local
    }


# ========== STATISTICS ENDPOINTS ==========

@router.get("/invoices/{invoice_id}")
def get_gas_invoice(invoice_id: int, db: Session = Depends(get_db)):
    """Gets single gas invoice by ID."""
    invoice = db.query(GasInvoice).filter(GasInvoice.id == invoice_id).first()
    
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    result = {
        "id": invoice.id,
        "data": invoice.data,
        "invoice_number": invoice.invoice_number,
        "period_start": invoice.period_start.isoformat() if invoice.period_start else None,
        "period_stop": invoice.period_stop.isoformat() if invoice.period_stop else None,
        "previous_reading": invoice.previous_reading,
        "current_reading": invoice.current_reading,
        "fuel_usage_m3": invoice.fuel_usage_m3,
        "fuel_conversion_factor": invoice.fuel_conversion_factor,
        "fuel_usage_kwh": invoice.fuel_usage_kwh,
        "fuel_price_net": invoice.fuel_price_net,
        "fuel_value_net": invoice.fuel_value_net,
        "fuel_value_gross": invoice.fuel_value_gross,
        "subscription_quantity": invoice.subscription_quantity,
        "subscription_price_net": invoice.subscription_price_net,
        "subscription_value_net": invoice.subscription_value_net,
        "subscription_value_gross": invoice.subscription_value_gross,
        "distribution_fixed_quantity": invoice.distribution_fixed_quantity,
        "distribution_fixed_price_net": invoice.distribution_fixed_price_net,
        "distribution_fixed_value_net": invoice.distribution_fixed_value_net,
        "distribution_fixed_value_gross": invoice.distribution_fixed_value_gross,
        "distribution_variable_usage_m3": invoice.distribution_variable_usage_m3,
        "distribution_variable_conversion_factor": invoice.distribution_variable_conversion_factor,
        "distribution_variable_usage_kwh": invoice.distribution_variable_usage_kwh,
        "distribution_variable_price_net": invoice.distribution_variable_price_net,
        "distribution_variable_value_net": invoice.distribution_variable_value_net,
        "distribution_variable_value_gross": invoice.distribution_variable_value_gross,
        "distribution_variable_2_usage_m3": invoice.distribution_variable_2_usage_m3,
        "distribution_variable_2_conversion_factor": invoice.distribution_variable_2_conversion_factor,
        "distribution_variable_2_usage_kwh": invoice.distribution_variable_2_usage_kwh,
        "distribution_variable_2_price_net": invoice.distribution_variable_2_price_net,
        "distribution_variable_2_value_net": invoice.distribution_variable_2_value_net,
        "total_net_sum": invoice.total_net_sum,
        "vat_rate": invoice.vat_rate,
        "vat_amount": invoice.vat_amount,
        "total_gross_sum": invoice.total_gross_sum,
        "late_payment_interest": invoice.late_payment_interest,
        "payment_due_date": invoice.payment_due_date.isoformat() if invoice.payment_due_date else None,
        "amount_to_pay": invoice.amount_to_pay
    }
    
    return result


@router.put("/invoices/{invoice_id}")
def update_gas_invoice(
    invoice_id: int,
    invoice_data: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db)
):
    """Updates gas invoice by ID."""
    from datetime import datetime
    
    invoice = db.query(GasInvoice).filter(GasInvoice.id == invoice_id).first()
    
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
    
    if 'payment_due_date' in invoice_data:
        try:
            invoice_data['payment_due_date'] = datetime.strptime(invoice_data['payment_due_date'], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Invalid date format for payment_due_date")
    
    # Update fields
    for key, value in invoice_data.items():
        if hasattr(invoice, key):
            if isinstance(value, float):
                value = round(value, 2)
            setattr(invoice, key, value)
    
    db.commit()
    db.refresh(invoice)
    
    return {
        "message": "Gas invoice updated",
        "id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "data": invoice.data
    }


@router.delete("/invoices/{invoice_id}")
def delete_gas_invoice(invoice_id: int, db: Session = Depends(get_db)):
    """Deletes gas invoice by ID. Also deletes all bills for this invoice's period."""
    invoice = db.query(GasInvoice).filter(GasInvoice.id == invoice_id).first()
    
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    period = invoice.data
    
    # Check if there are other invoices for this period
    other_invoices = db.query(GasInvoice).filter(
        GasInvoice.data == period,
        GasInvoice.id != invoice_id
    ).count()
    
    deleted_bills_count = 0
    if other_invoices == 0:
        # If this is the last invoice for this period, delete all bills
        bills = db.query(GasBill).filter(GasBill.data == period).all()
        for bill in bills:
            # Delete PDF file if exists
            if bill.pdf_path and Path(bill.pdf_path).exists():
                Path(bill.pdf_path).unlink()
            db.delete(bill)
            deleted_bills_count += 1
    
    db.delete(invoice)
    db.commit()
    
    return {
        "message": "Gas invoice deleted",
        "id": invoice_id,
        "invoice_number": invoice.invoice_number,
        "period": period,
        "deleted_bills_count": deleted_bills_count
    }


@router.get("/stats")
def get_gas_stats(db: Session = Depends(get_db)):
    """Returns statistics for gas dashboard."""
    stats = {
        "invoices_count": db.query(GasInvoice).count(),
        "bills_count": db.query(GasBill).count(),
        "latest_period": None,
        "total_gross_sum": 0,
        "available_periods": []
    }
    
    # Latest period from invoices
    latest_invoice = db.query(GasInvoice).order_by(desc(GasInvoice.data)).first()
    if latest_invoice:
        stats["latest_period"] = latest_invoice.data
    
    # Total gross sum of all bills
    total_sum = db.query(func.sum(GasBill.total_gross_sum)).scalar()
    if total_sum:
        stats["total_gross_sum"] = float(total_sum)
    
    # Periods with bills
    periods = db.query(GasBill.data).distinct().order_by(desc(GasBill.data)).all()
    stats["available_periods"] = [p[0] for p in periods[:10]]  # Last 10
    
    return stats

