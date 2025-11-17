"""
Endpointy API dla rachunków łączonych (wszystkie media).
"""

from typing import List, Optional
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.models.combined import CombinedBill
from app.services.combined.manager import CombinedBillingManager
from app.services.combined.bill_generator import generate_combined_bill_pdf
from app.services.combined.email_sender import send_combined_bill_email
from datetime import date

router = APIRouter(prefix="/api/combined", tags=["combined"])


@router.get("/available-periods")
def get_available_periods(db: Session = Depends(get_db)):
    """
    Zwraca listę dostępnych okresów dwumiesięcznych dla rachunków łączonych.
    Okresy muszą mieć rachunki dla wszystkich trzech mediów (woda, gaz, prąd).
    """
    from app.models.water import Bill
    from app.models.gas import GasBill
    from app.models.electricity import ElectricityBill
    
    # Pobierz wszystkie okresy dla diagnostyki
    water_periods = {b.data for b in db.query(Bill.data).distinct().all()}
    gas_periods = {b.data for b in db.query(GasBill.data).distinct().all()}
    electricity_periods = {b.data for b in db.query(ElectricityBill.data).distinct().all()}
    
    manager = CombinedBillingManager()
    periods = manager.get_two_month_periods(db)
    
    # Pobierz okresy, które już mają wygenerowane rachunki łączone
    existing_periods = db.query(CombinedBill.period_start, CombinedBill.period_end).distinct().all()
    existing_set = {(p[0], p[1]) for p in existing_periods}
    
    # Podziel na te z rachunkami i bez
    periods_with_bills = [p for p in periods if p in existing_set]
    periods_without_bills = [p for p in periods if p not in existing_set]
    
    # Sprawdź wszystkie możliwe pary kolejnych miesięcy dla diagnostyki
    all_periods_sorted = sorted(water_periods | gas_periods | electricity_periods)
    possible_pairs = []
    for i in range(len(all_periods_sorted) - 1):
        period_start = all_periods_sorted[i]
        period_end = all_periods_sorted[i + 1]
        from datetime import datetime
        current = datetime.strptime(period_start, '%Y-%m')
        next_period = datetime.strptime(period_end, '%Y-%m')
        months_diff = (next_period.year - current.year) * 12 + (next_period.month - current.month)
        if months_diff == 1:
            possible_pairs.append((period_start, period_end))
    
    return {
        "available_periods": periods,
        "available_periods_without_bills": sorted(periods_without_bills, reverse=True),
        "available_periods_with_bills": sorted(periods_with_bills, reverse=True),
        "diagnostics": {
            "water_periods": sorted(water_periods),
            "gas_periods": sorted(gas_periods),
            "electricity_periods": sorted(electricity_periods),
            "water_count": len(water_periods),
            "gas_count": len(gas_periods),
            "electricity_count": len(electricity_periods),
            "common_periods": sorted(water_periods & gas_periods & electricity_periods),
            "common_count": len(water_periods & gas_periods & electricity_periods),
            "all_periods": sorted(all_periods_sorted),
            "possible_consecutive_pairs": possible_pairs,
            "possible_pairs_count": len(possible_pairs),
        }
    }


@router.post("/generate-bills")
def generate_combined_bills(
    period_start: str,
    period_end: str,
    db: Session = Depends(get_db)
):
    """
    Generuje rachunki łączone dla wszystkich lokali na dany okres dwumiesięczny.
    
    Args:
        period_start: Pierwszy miesiąc okresu (YYYY-MM)
        period_end: Drugi miesiąc okresu (YYYY-MM)
    """
    manager = CombinedBillingManager()
    
    try:
        bills = manager.generate_bills_for_period(db, period_start, period_end)
        
        if not bills:
            raise HTTPException(
                status_code=400,
                detail=f"Nie można wygenerować rachunków dla okresu {period_start} - {period_end}. Sprawdź czy istnieją rachunki dla wszystkich mediów."
            )
        
        return {
            "message": f"Wygenerowano {len(bills)} rachunków łączonych dla okresu {period_start} - {period_end}",
            "bills_count": len(bills),
            "period_start": period_start,
            "period_end": period_end
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Błąd generowania rachunków: {str(e)}")


@router.get("/bills")
def get_combined_bills(
    period_start: Optional[str] = None,
    period_end: Optional[str] = None,
    local: Optional[str] = None,
    id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    Pobiera listę rachunków łączonych.
    
    Args:
        period_start: Filtr - pierwszy miesiąc okresu (YYYY-MM)
        period_end: Filtr - drugi miesiąc okresu (YYYY-MM)
        local: Filtr - nazwa lokalu
        id: Filtr - ID rachunku
    """
    query = db.query(CombinedBill).options(joinedload(CombinedBill.local_obj))
    
    if id:
        query = query.filter(CombinedBill.id == id)
    if period_start:
        query = query.filter(CombinedBill.period_start == period_start)
    if period_end:
        query = query.filter(CombinedBill.period_end == period_end)
    if local:
        query = query.filter(CombinedBill.local == local)
    
    bills = query.all()
    
    result = []
    for bill in bills:
        result.append({
            "id": bill.id,
            "period_start": bill.period_start,
            "period_end": bill.period_end,
            "local": bill.local,
            "water_bill_id": bill.water_bill_id,
            "gas_bill_id": bill.gas_bill_id,
            "electricity_bill_id": bill.electricity_bill_id,
            "total_net_sum": bill.total_net_sum,
            "total_gross_sum": bill.total_gross_sum,
            "generated_date": bill.generated_date.isoformat() if bill.generated_date else None,
            "pdf_path": bill.pdf_path,
            "email_sent_date": bill.email_sent_date.isoformat() if bill.email_sent_date else None,
            "local_email": bill.local_obj.email if bill.local_obj else None,
            "local_id": bill.local_id,
        })
    
    return result


@router.post("/generate-pdf")
def generate_combined_bills_pdf(
    period_start: str,
    period_end: str,
    db: Session = Depends(get_db)
):
    """
    Generuje pliki PDF dla wszystkich rachunków łączonych w danym okresie.
    
    Args:
        period_start: Pierwszy miesiąc okresu (YYYY-MM)
        period_end: Drugi miesiąc okresu (YYYY-MM)
    """
    bills = db.query(CombinedBill).options(joinedload(CombinedBill.local_obj)).filter(
        CombinedBill.period_start == period_start,
        CombinedBill.period_end == period_end
    ).all()
    
    if not bills:
        raise HTTPException(
            status_code=404,
            detail=f"Brak rachunków łączonych dla okresu {period_start} - {period_end}"
        )
    
    pdf_files = []
    
    for bill in bills:
        try:
            # Sprawdź czy plik już istnieje
            if bill.pdf_path:
                from pathlib import Path
                if Path(bill.pdf_path).exists():
                    pdf_files.append(bill.pdf_path)
                    continue
            
            # Wygeneruj plik PDF
            pdf_path = generate_combined_bill_pdf(db, bill)
            
            # Zaktualizuj ścieżkę w bazie
            bill.pdf_path = pdf_path
            db.commit()
            
            pdf_files.append(pdf_path)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Błąd generowania PDF dla rachunku {bill.id}: {str(e)}"
            )
    
    return {
        "message": f"Wygenerowano {len(pdf_files)} plików PDF",
        "pdf_files": pdf_files,
        "period_start": period_start,
        "period_end": period_end
    }


@router.get("/bills/download/{bill_id}")
def download_combined_bill(bill_id: int, db: Session = Depends(get_db)):
    """Pobiera plik PDF rachunku łączonego."""
    bill = db.query(CombinedBill).options(joinedload(CombinedBill.local_obj)).filter(CombinedBill.id == bill_id).first()
    
    if not bill:
        raise HTTPException(status_code=404, detail="Rachunek nie znaleziony")
    
    if not bill.pdf_path or not Path(bill.pdf_path).exists():
        # Wygeneruj plik jeśli nie istnieje
        try:
            bill.pdf_path = generate_combined_bill_pdf(db, bill)
            db.commit()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Nie można wygenerować pliku PDF: {str(e)}")
    
    return FileResponse(bill.pdf_path, media_type="application/pdf")


@router.post("/bills/{bill_id}/send-email")
def send_combined_bill_email_endpoint(bill_id: int, db: Session = Depends(get_db)):
    """
    Wysyła pojedynczy rachunek łączony na email.
    
    Args:
        bill_id: ID rachunku łączonego
    """
    bill = db.query(CombinedBill).options(joinedload(CombinedBill.local_obj)).filter(CombinedBill.id == bill_id).first()
    
    if not bill:
        raise HTTPException(status_code=404, detail="Rachunek nie znaleziony")
    
    # Sprawdź czy lokal ma email
    if not bill.local_obj or not bill.local_obj.email:
        raise HTTPException(
            status_code=400,
            detail=f"Lokal {bill.local} nie ma przypisanego adresu email"
        )
    
    # Sprawdź czy PDF istnieje
    if not bill.pdf_path or not Path(bill.pdf_path).exists():
        # Wygeneruj PDF jeśli nie istnieje
        try:
            bill.pdf_path = generate_combined_bill_pdf(db, bill)
            db.commit()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Nie można wygenerować pliku PDF: {str(e)}")
    
    # Wyślij email
    try:
        success = send_combined_bill_email(
            recipient_email=bill.local_obj.email,
            bill=bill,
            pdf_path=bill.pdf_path
        )
        
        if success:
            # Zaktualizuj datę wysłania
            bill.email_sent_date = date.today()
            db.commit()
            
            return {
                "message": f"Rachunek wysłany na email: {bill.local_obj.email}",
                "bill_id": bill_id,
                "email": bill.local_obj.email,
                "email_sent_date": bill.email_sent_date.isoformat()
            }
        else:
            raise HTTPException(status_code=500, detail="Nie udało się wysłać emaila")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Błąd wysyłania emaila: {str(e)}")


@router.post("/send-emails")
def send_combined_bills_emails(
    period_start: str,
    period_end: str,
    db: Session = Depends(get_db)
):
    """
    Wysyła wszystkie rachunki łączone z danego okresu na emaile.
    
    Args:
        period_start: Pierwszy miesiąc okresu (YYYY-MM)
        period_end: Drugi miesiąc okresu (YYYY-MM)
    """
    bills = db.query(CombinedBill).options(joinedload(CombinedBill.local_obj)).filter(
        CombinedBill.period_start == period_start,
        CombinedBill.period_end == period_end
    ).all()
    
    if not bills:
        raise HTTPException(
            status_code=404,
            detail=f"Brak rachunków łączonych dla okresu {period_start} - {period_end}"
        )
    
    results = []
    errors = []
    
    for bill in bills:
        # Sprawdź czy lokal ma email
        if not bill.local_obj or not bill.local_obj.email:
            errors.append({
                "bill_id": bill.id,
                "local": bill.local,
                "error": "Brak adresu email"
            })
            continue
        
        # Sprawdź czy PDF istnieje
        if not bill.pdf_path or not Path(bill.pdf_path).exists():
            try:
                bill.pdf_path = generate_combined_bill_pdf(db, bill)
                db.commit()
            except Exception as e:
                errors.append({
                    "bill_id": bill.id,
                    "local": bill.local,
                    "error": f"Nie można wygenerować PDF: {str(e)}"
                })
                continue
        
        # Wyślij email
        try:
            success = send_combined_bill_email(
                recipient_email=bill.local_obj.email,
                bill=bill,
                pdf_path=bill.pdf_path
            )
            
            if success:
                # Zaktualizuj datę wysłania
                bill.email_sent_date = date.today()
                db.commit()
                
                results.append({
                    "bill_id": bill.id,
                    "local": bill.local,
                    "email": bill.local_obj.email,
                    "status": "sent"
                })
            else:
                errors.append({
                    "bill_id": bill.id,
                    "local": bill.local,
                    "error": "Nie udało się wysłać emaila"
                })
        except Exception as e:
            errors.append({
                "bill_id": bill.id,
                "local": bill.local,
                "error": str(e)
            })
    
    return {
        "message": f"Wysłano {len(results)} z {len(bills)} rachunków",
        "sent_count": len(results),
        "total_count": len(bills),
        "errors_count": len(errors),
        "results": results,
        "errors": errors
    }

