"""
API endpoints dla gazu.
Wszystkie endpointy mają prefix /api/gas/
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

# Instancja managera
gas_manager = GasBillingManager()


# ========== ENDPOINTY FAKTUR GAZU ==========

@router.get("/invoices/", response_model=List[dict])
def get_gas_invoices(db: Session = Depends(get_db)):
    """Pobiera listę wszystkich faktur gazu."""
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
    Dodaje fakturę gazu ręcznie do bazy danych.
    Akceptuje JSON body z danymi faktury.
    Jeśli podane są tylko wartości brutto, automatycznie oblicza wartości netto i VAT (zakładając VAT 23%).
    """
    # Wyciągnij dane z dict
    data = invoice_data.get('data')
    period_start = invoice_data.get('period_start')
    period_stop = invoice_data.get('period_stop')
    previous_reading = invoice_data.get('previous_reading')
    current_reading = invoice_data.get('current_reading')
    invoice_number = invoice_data.get('invoice_number')
    total_gross_sum = invoice_data.get('total_gross_sum')
    vat_rate = invoice_data.get('vat_rate', 0.23)
    
    # Wartości brutto (z formularza)
    fuel_value_gross = invoice_data.get('fuel_value_gross', 0.0)
    subscription_value_gross = invoice_data.get('subscription_value_gross', 0.0)
    distribution_fixed_value_gross = invoice_data.get('distribution_fixed_value_gross', 0.0)
    distribution_variable_value_gross = invoice_data.get('distribution_variable_value_gross', 0.0)
    
    # Walidacja wymaganych pól
    if not all([data, period_start, period_stop, previous_reading is not None, current_reading is not None, 
                invoice_number, total_gross_sum is not None]):
        raise HTTPException(status_code=400, detail="Brakuje wymaganych pól")
    
    try:
        period_start_date = datetime.strptime(period_start, "%Y-%m-%d").date()
        period_stop_date = datetime.strptime(period_stop, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        try:
            # Spróbuj też format z formularza HTML (YYYY-MM-DD)
            if isinstance(period_start, str) and len(period_start) == 10:
                period_start_date = datetime.strptime(period_start, "%Y-%m-%d").date()
                period_stop_date = datetime.strptime(period_stop, "%Y-%m-%d").date()
            else:
                raise HTTPException(status_code=400, detail="Nieprawidłowy format daty. Użyj YYYY-MM-DD")
        except:
            raise HTTPException(status_code=400, detail="Nieprawidłowy format daty. Użyj YYYY-MM-DD")
    
    # Oblicz wartości netto i VAT z wartości brutto (jeśli nie podane)
    def calculate_net_from_gross(gross_value, vat):
        """Oblicza wartość netto z brutto i VAT."""
        if gross_value == 0:
            return 0.0, 0.0
        net_value = round(gross_value / (1 + vat), 2)
        vat_amount = round(gross_value - net_value, 2)
        return net_value, vat_amount
    
    # Oblicz brakujące wartości dla paliwa
    fuel_value_net = invoice_data.get('fuel_value_net')
    fuel_vat_amount = invoice_data.get('fuel_vat_amount')
    if fuel_value_net is None or fuel_vat_amount is None:
        fuel_value_net, fuel_vat_amount = calculate_net_from_gross(fuel_value_gross, vat_rate)
    
    # Oblicz brakujące wartości dla abonamentu
    subscription_value_net = invoice_data.get('subscription_value_net')
    subscription_vat_amount = invoice_data.get('subscription_vat_amount')
    if subscription_value_net is None or subscription_vat_amount is None:
        subscription_value_net, subscription_vat_amount = calculate_net_from_gross(subscription_value_gross, vat_rate)
    
    # Oblicz brakujące wartości dla dystrybucji stałej
    distribution_fixed_price_net = invoice_data.get('distribution_fixed_price_net', 0.0)
    distribution_fixed_vat_amount = invoice_data.get('distribution_fixed_vat_amount')
    if distribution_fixed_vat_amount is None:
        _, distribution_fixed_vat_amount = calculate_net_from_gross(distribution_fixed_value_gross, vat_rate)
    
    # Oblicz brakujące wartości dla dystrybucji zmiennej
    distribution_variable_price_net = invoice_data.get('distribution_variable_price_net', 0.0)
    distribution_variable_vat_amount = invoice_data.get('distribution_variable_vat_amount')
    if distribution_variable_vat_amount is None:
        _, distribution_variable_vat_amount = calculate_net_from_gross(distribution_variable_value_gross, vat_rate)
    
    # Pobierz lub ustaw domyślne wartości dla pozostałych pól
    fuel_usage_m3 = invoice_data.get('fuel_usage_m3')
    if fuel_usage_m3 is None:
        fuel_usage_m3 = round(float(current_reading) - float(previous_reading), 2)
    
    fuel_price_net = invoice_data.get('fuel_price_net', 0.0)
    if fuel_price_net == 0 and fuel_usage_m3 > 0:
        fuel_price_net = round(fuel_value_net / fuel_usage_m3, 2)
    
    subscription_quantity = invoice_data.get('subscription_quantity')
    if subscription_quantity is None:
        # Domyślnie 2 miesiące dla faktury dwumiesięcznej
        subscription_quantity = 2
    subscription_quantity = int(subscription_quantity)
    
    subscription_price_net = invoice_data.get('subscription_price_net', 0.0)
    if subscription_price_net == 0 and subscription_quantity > 0:
        subscription_price_net = round(subscription_value_net / subscription_quantity, 2)
    elif subscription_price_net == 0:
        subscription_price_net = 0.0
    
    distribution_fixed_quantity = invoice_data.get('distribution_fixed_quantity')
    if distribution_fixed_quantity is None:
        # Domyślnie 2 miesiące dla faktury dwumiesięcznej
        distribution_fixed_quantity = 2
    distribution_fixed_quantity = int(distribution_fixed_quantity)
    
    if distribution_fixed_price_net == 0 and distribution_fixed_quantity > 0:
        # Oblicz cenę netto z wartości brutto
        distribution_fixed_net_value, _ = calculate_net_from_gross(distribution_fixed_value_gross, vat_rate)
        distribution_fixed_price_net = round(distribution_fixed_net_value / distribution_fixed_quantity, 2) if distribution_fixed_quantity > 0 else 0.0
    
    distribution_variable_quantity = invoice_data.get('distribution_variable_quantity')
    if distribution_variable_quantity is None:
        # Domyślnie 2 miesiące dla faktury dwumiesięcznej
        distribution_variable_quantity = 2
    distribution_variable_quantity = int(distribution_variable_quantity)
    
    if distribution_variable_price_net == 0 and distribution_variable_quantity > 0:
        # Oblicz cenę netto z wartości brutto
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
        "message": "Faktura gazu dodana",
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
    Parsuje fakturę PDF i zwraca dane do weryfikacji.
    NIE zapisuje do bazy danych!
    """
    from app.services.gas.invoice_reader import load_invoice_from_pdf
    
    # Zapisuj plik tymczasowo
    upload_folder = Path("invoices_raw/gas")
    upload_folder.mkdir(parents=True, exist_ok=True)
    
    file_path = upload_folder / file.filename
    
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    # Parsuj fakturę
    invoice_data = load_invoice_from_pdf(db, str(file_path))
    
    if not invoice_data:
        raise HTTPException(status_code=400, detail="Nie udało się sparsować faktury. Sprawdź format pliku.")
    
    # Konwertuj daty na stringi dla JSON (dashboard oczekuje formatu YYYY-MM-DD)
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
    
    # Zwróć sparsowane dane (bez message i file_path - dashboard oczekuje bezpośrednio danych)
    return invoice_data


@router.post("/invoices/verify")
def verify_and_save_gas_invoice(
    invoice_data: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db)
):
    """
    Zapisuje fakturę gazu po weryfikacji przez użytkownika.
    Wywoływane z dashboardu po zatwierdzeniu.
    """
    from app.services.gas.invoice_reader import save_invoice_after_verification
    
    try:
        # Zapisz fakturę
        invoice = save_invoice_after_verification(db, invoice_data)
        
        if not invoice:
            raise HTTPException(status_code=400, detail="Błąd zapisu faktury")
        
        return {
            "message": "Faktura gazu zapisana",
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
        raise HTTPException(status_code=500, detail=f"Błąd zapisu faktury: {str(e)}")


# ========== ENDPOINTY RACHUNKÓW GAZU ==========

@router.get("/bills/", response_model=List[dict])
def get_gas_bills(db: Session = Depends(get_db)):
    """Pobiera listę wszystkich rachunków gazu."""
    bills = db.query(GasBill).order_by(desc(GasBill.data)).all()
    return [{
        "id": b.id,
        "data": b.data,
        "local": b.local,
        "cost_share": b.cost_share,
        # Użyj wartości z bazy danych (zaktualizowane przez generator PDF)
        "fuel_cost_gross": b.fuel_cost_gross,
        "subscription_cost_gross": b.subscription_cost_gross,
        "distribution_fixed_cost_gross": b.distribution_fixed_cost_gross,
        "distribution_variable_cost_gross": b.distribution_variable_cost_gross,
        "total_net_sum": b.total_net_sum,
        "total_gross_sum": b.total_gross_sum,  # Ostateczna kwota brutto do zapłaty (z uwzględnieniem odsetek dla gora)
        "pdf_path": b.pdf_path
    } for b in bills]


@router.get("/bills/period/{period}", response_model=List[dict])
def get_gas_bills_for_period(period: str, db: Session = Depends(get_db)):
    """Pobiera rachunki gazu dla danego okresu."""
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
    Generuje rachunki gazu dla danego okresu.
    Wymaga obecności faktury dla tego okresu.
    """
    try:
        # Sprawdź czy rachunki już istnieją
        existing = db.query(GasBill).filter(GasBill.data == period).first()
        if existing:
            return {"message": f"Rachunki dla okresu {period} już istnieją. Użyj /api/gas/bills/regenerate/{period}"}
        
        # Wygeneruj rachunki
        bills = gas_manager.generate_bills_for_period(db, period)
        
        # Odśwież sesję, aby mieć aktualne obiekty z bazy danych
        db.flush()
        
        # Wygeneruj pliki PDF
        try:
            pdf_files = generate_all_bills_for_period(db, period)
        except Exception as pdf_error:
            # Loguj błąd, ale nie przerywaj - rachunki są już wygenerowane
            import traceback
            error_details = traceback.format_exc()
            print(f"[ERROR] Błąd podczas generowania PDF dla okresu {period}: {pdf_error}")
            print(error_details)
            pdf_files = []
        
        return {
            "message": "Rachunki gazu wygenerowane",
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
    Generuje pliki PDF dla istniejących rachunków gazu danego okresu.
    Przydatne gdy rachunki już istnieją, ale nie mają wygenerowanych PDF.
    """
    try:
        pdf_files = generate_all_bills_for_period(db, period)
        return {
            "message": "Pliki PDF wygenerowane",
            "period": period,
            "pdfs_generated": len(pdf_files)
        }
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"[ERROR] Błąd podczas generowania PDF dla okresu {period}: {e}")
        print(error_details)
        raise HTTPException(status_code=500, detail=f"Błąd generowania PDF: {str(e)}")


@router.post("/bills/regenerate/{period}")
def regenerate_gas_bills(period: str, db: Session = Depends(get_db)):
    """Ponownie generuje rachunki gazu dla danego okresu."""
    # Usuń stare rachunki
    bills = db.query(GasBill).filter(GasBill.data == period).all()
    for bill in bills:
        # Usuń plik PDF jeśli istnieje
        if bill.pdf_path and Path(bill.pdf_path).exists():
            Path(bill.pdf_path).unlink()
        db.delete(bill)
    db.commit()
    
    try:
        # Wygeneruj nowe rachunki
        bills = gas_manager.generate_bills_for_period(db, period)
        
        # Odśwież sesję, aby mieć aktualne obiekty z bazy danych
        db.flush()
        
        # Wygeneruj pliki PDF
        try:
            pdf_files = generate_all_bills_for_period(db, period)
        except Exception as pdf_error:
            # Loguj błąd, ale nie przerywaj - rachunki są już wygenerowane
            import traceback
            error_details = traceback.format_exc()
            print(f"[ERROR] Błąd podczas generowania PDF dla okresu {period}: {pdf_error}")
            print(error_details)
            pdf_files = []
        
        return {
            "message": "Rachunki gazu ponownie wygenerowane",
            "period": period,
            "bills_count": len(bills),
            "pdfs_generated": len(pdf_files),
            "warning": f"Wygenerowano {len(bills)} rachunków, ale {len(pdf_files)} plików PDF" if len(pdf_files) != len(bills) else None
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/bills/download/{bill_id}")
def download_gas_bill(bill_id: int, db: Session = Depends(get_db)):
    """Pobiera plik PDF rachunku gazu."""
    from app.services.gas.bill_generator import generate_bill_pdf
    
    bill = db.query(GasBill).filter(GasBill.id == bill_id).first()
    
    if not bill:
        raise HTTPException(status_code=404, detail="Rachunek nie znaleziony")
    
    if not bill.pdf_path or not Path(bill.pdf_path).exists():
        # Wygeneruj plik jeśli nie istnieje
        try:
            bill.pdf_path = generate_bill_pdf(db, bill)
            db.commit()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Nie można wygenerować pliku PDF: {str(e)}")
    
    return FileResponse(bill.pdf_path, media_type="application/pdf")


@router.get("/bills/{bill_id}")
def get_gas_bill(bill_id: int, db: Session = Depends(get_db)):
    """Pobiera pojedynczy rachunek gazu po ID."""
    bill = db.query(GasBill).filter(GasBill.id == bill_id).first()
    
    if not bill:
        raise HTTPException(status_code=404, detail="Rachunek nie znaleziony")
    
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
    """Aktualizuje rachunek gazu po ID."""
    bill = db.query(GasBill).filter(GasBill.id == bill_id).first()
    
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
        "message": "Rachunek gazu zaktualizowany",
        "id": bill.id,
        "data": bill.data,
        "local": bill.local
    }


@router.delete("/bills/{bill_id}")
def delete_gas_bill(bill_id: int, db: Session = Depends(get_db)):
    """Usuwa rachunek gazu po ID."""
    bill = db.query(GasBill).filter(GasBill.id == bill_id).first()
    
    if not bill:
        raise HTTPException(status_code=404, detail="Rachunek nie znaleziony")
    
    # Usuń plik PDF jeśli istnieje
    if bill.pdf_path and Path(bill.pdf_path).exists():
        Path(bill.pdf_path).unlink()
    
    db.delete(bill)
    db.commit()
    
    return {
        "message": "Rachunek gazu usunięty",
        "id": bill_id,
        "period": bill.data,
        "local": bill.local
    }


# ========== ENDPOINTY STATYSTYK ==========

@router.get("/invoices/{invoice_id}")
def get_gas_invoice(invoice_id: int, db: Session = Depends(get_db)):
    """Pobiera pojedynczą fakturę gazu po ID."""
    invoice = db.query(GasInvoice).filter(GasInvoice.id == invoice_id).first()
    
    if not invoice:
        raise HTTPException(status_code=404, detail="Faktura nie znaleziona")
    
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
    """Aktualizuje fakturę gazu po ID."""
    from datetime import datetime
    
    invoice = db.query(GasInvoice).filter(GasInvoice.id == invoice_id).first()
    
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
    
    if 'payment_due_date' in invoice_data:
        try:
            invoice_data['payment_due_date'] = datetime.strptime(invoice_data['payment_due_date'], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Nieprawidłowy format daty payment_due_date")
    
    # Aktualizuj pola
    for key, value in invoice_data.items():
        if hasattr(invoice, key):
            if isinstance(value, float):
                value = round(value, 2)
            setattr(invoice, key, value)
    
    db.commit()
    db.refresh(invoice)
    
    return {
        "message": "Faktura gazu zaktualizowana",
        "id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "data": invoice.data
    }


@router.delete("/invoices/{invoice_id}")
def delete_gas_invoice(invoice_id: int, db: Session = Depends(get_db)):
    """Usuwa fakturę gazu po ID. Usuwa również wszystkie rachunki dla okresu tej faktury."""
    invoice = db.query(GasInvoice).filter(GasInvoice.id == invoice_id).first()
    
    if not invoice:
        raise HTTPException(status_code=404, detail="Faktura nie znaleziona")
    
    period = invoice.data
    
    # Sprawdź czy są jeszcze inne faktury dla tego okresu
    other_invoices = db.query(GasInvoice).filter(
        GasInvoice.data == period,
        GasInvoice.id != invoice_id
    ).count()
    
    deleted_bills_count = 0
    if other_invoices == 0:
        # Jeśli to ostatnia faktura dla tego okresu, usuń wszystkie rachunki
        bills = db.query(GasBill).filter(GasBill.data == period).all()
        for bill in bills:
            # Usuń plik PDF jeśli istnieje
            if bill.pdf_path and Path(bill.pdf_path).exists():
                Path(bill.pdf_path).unlink()
            db.delete(bill)
            deleted_bills_count += 1
    
    db.delete(invoice)
    db.commit()
    
    return {
        "message": "Faktura gazu usunięta",
        "id": invoice_id,
        "invoice_number": invoice.invoice_number,
        "period": period,
        "deleted_bills_count": deleted_bills_count
    }


@router.get("/stats")
def get_gas_stats(db: Session = Depends(get_db)):
    """Zwraca statystyki dla dashboardu gazu."""
    stats = {
        "invoices_count": db.query(GasInvoice).count(),
        "bills_count": db.query(GasBill).count(),
        "latest_period": None,
        "total_gross_sum": 0,
        "available_periods": []
    }
    
    # Najnowszy okres z faktur
    latest_invoice = db.query(GasInvoice).order_by(desc(GasInvoice.data)).first()
    if latest_invoice:
        stats["latest_period"] = latest_invoice.data
    
    # Suma brutto wszystkich rachunków
    total_sum = db.query(func.sum(GasBill.total_gross_sum)).scalar()
    if total_sum:
        stats["total_gross_sum"] = float(total_sum)
    
    # Okresy z rachunkami
    periods = db.query(GasBill.data).distinct().order_by(desc(GasBill.data)).all()
    stats["available_periods"] = [p[0] for p in periods[:10]]  # Ostatnie 10
    
    return stats

