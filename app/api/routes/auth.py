"""
Endpointy autentykacji - logowanie i rejestracja.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from app.core.database import get_db
from app.core.auth import (
    verify_password,
    get_password_hash,
    create_access_token,
    get_current_user
)
from app.models.user import User
from app.models.password_reset import PasswordResetCode
from app.core.email_sender import send_password_reset_code
from datetime import datetime, timedelta
from pathlib import Path
import re

router = APIRouter(prefix="/api/auth", tags=["auth"])
security = HTTPBearer()


def is_valid_email(email: str) -> bool:
    """Sprawdza czy string jest poprawnym emailem."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


class UserRegister(BaseModel):
    """Model rejestracji użytkownika."""
    email: str  # Email jest teraz loginem
    password: str


class UserLogin(BaseModel):
    """Model logowania użytkownika."""
    username: str  # Może być email (dla zwykłych użytkowników) lub "admin" (dla admina)
    password: str


class TokenResponse(BaseModel):
    """Odpowiedź z tokenem."""
    access_token: str
    token_type: str = "bearer"
    username: str
    is_admin: bool


@router.post("/register", response_model=TokenResponse)
def register(user_data: UserRegister, db: Session = Depends(get_db)):
    """Rejestracja nowego użytkownika. Email jest loginem."""
    # Walidacja email
    if not is_valid_email(user_data.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nieprawidłowy format email"
        )
    
    # Sprawdź czy użytkownik z tym emailem już istnieje
    existing_user = db.query(User).filter(
        (User.email == user_data.email) | (User.username == user_data.email)
    ).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Użytkownik o tym emailu już istnieje"
        )
    
    # Utwórz nowego użytkownika - email jest zarówno username jak i email
    hashed_password = get_password_hash(user_data.password)
    new_user = User(
        username=user_data.email,  # Username = email
        email=user_data.email,
        password_hash=hashed_password,
        is_admin=False
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Utwórz token
    access_token = create_access_token(data={"sub": new_user.username})
    
    return TokenResponse(
        access_token=access_token,
        username=new_user.username,
        is_admin=new_user.is_admin
    )


@router.post("/login", response_model=TokenResponse)
def login(user_data: UserLogin, db: Session = Depends(get_db)):
    """Logowanie użytkownika. Dla zwykłych użytkowników login to email, dla admina to 'admin'."""
    # Dla admina - szukaj po username "admin"
    if user_data.username == "admin":
        user = db.query(User).filter(
            User.username == "admin",
            User.is_admin == True
        ).first()
    else:
        # Dla zwykłych użytkowników - szukaj po email (który jest też username)
        user = db.query(User).filter(
            (User.email == user_data.username) | (User.username == user_data.username)
        ).first()
    
    if not user or not verify_password(user_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nieprawidłowa nazwa użytkownika lub hasło"
        )
    
    # Utwórz token
    access_token = create_access_token(data={"sub": user.username})
    
    return TokenResponse(
        access_token=access_token,
        username=user.username,
        is_admin=user.is_admin
    )


@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    """Pobiera informacje o zalogowanym użytkowniku."""
    return {
        "username": current_user.username,
        "email": current_user.email,
        "is_admin": current_user.is_admin
    }


class UpdateEmailRequest(BaseModel):
    """Model aktualizacji email."""
    email: str


@router.put("/me/email")
def update_email(
    email_data: UpdateEmailRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Aktualizuje email użytkownika."""
    # Walidacja email
    if not is_valid_email(email_data.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nieprawidłowy format email"
        )
    
    # Sprawdź czy email nie jest już używany przez innego użytkownika
    existing_user = db.query(User).filter(
        User.email == email_data.email,
        User.id != current_user.id
    ).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email jest już używany przez innego użytkownika"
        )
    
    # Zaktualizuj email
    current_user.email = email_data.email
    # Jeśli użytkownik nie jest adminem, zaktualizuj też username
    if not current_user.is_admin:
        current_user.username = email_data.email
    
    db.commit()
    db.refresh(current_user)
    
    return {
        "message": "Email zaktualizowany",
        "email": current_user.email,
        "username": current_user.username
    }


class ChangePasswordRequest(BaseModel):
    """Model zmiany hasła."""
    old_password: str
    new_password: str


@router.put("/me/password")
def change_password(
    password_data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Zmienia hasło użytkownika. Wymaga podania starego hasła."""
    # Sprawdź stare hasło
    if not verify_password(password_data.old_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nieprawidłowe stare hasło"
        )
    
    # Walidacja nowego hasła
    if len(password_data.new_password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nowe hasło musi mieć co najmniej 6 znaków"
        )
    
    # Zaktualizuj hasło
    current_user.password_hash = get_password_hash(password_data.new_password)
    db.commit()
    db.refresh(current_user)
    
    return {
        "message": "Hasło zostało zmienione"
    }


class RequestPasswordResetRequest(BaseModel):
    """Model żądania resetu hasła."""
    email: str


@router.post("/password-reset/request")
def request_password_reset(
    reset_request: RequestPasswordResetRequest,
    db: Session = Depends(get_db)
):
    """Generuje kod resetujący hasło i wysyła go na email."""
    # Walidacja email
    if not is_valid_email(reset_request.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nieprawidłowy format email"
        )
    
    # Znajdź użytkownika po email
    user = db.query(User).filter(User.email == reset_request.email).first()
    if not user:
        # Dla bezpieczeństwa nie ujawniamy czy użytkownik istnieje
        return {
            "message": "Jeśli użytkownik z tym emailem istnieje, kod resetujący został wysłany na email"
        }
    
    # Generuj kod resetujący
    code = PasswordResetCode.generate_code()
    expires_at = datetime.utcnow() + timedelta(minutes=15)
    
    # Zapisz kod w bazie danych
    reset_code = PasswordResetCode(
        user_id=user.id,
        code=code,
        email=user.email,
        expires_at=expires_at,
        used='false'
    )
    db.add(reset_code)
    db.commit()
    
    # Wyślij kod na email
    email_sent = send_password_reset_code(
        recipient_email=user.email,
        reset_code=code
    )
    
    if not email_sent:
        # Sprawdź czy to problem z konfiguracją SMTP
        import os
        smtp_user = os.getenv("SMTP_USER")
        smtp_password = os.getenv("SMTP_PASSWORD")
        
        if not smtp_user or not smtp_password:
            # Dla lokalnego środowiska - zapisz kod w pliku i wyświetl w konsoli
            reset_code_file = Path("password_reset_code.txt")
            reset_code_file.write_text(
                f"Kod resetujący hasło dla {user.email}:\n"
                f"Kod: {code}\n"
                f"Ważny do: {expires_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"Email: {user.email}\n"
            )
            print(f"\n{'='*60}")
            print(f"[INFO] KOD RESETUJĄCY HASŁO (SMTP nie skonfigurowany):")
            print(f"Email: {user.email}")
            print(f"Kod: {code}")
            print(f"Ważny do: {expires_at.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"Kod został również zapisany w pliku: {reset_code_file}")
            print(f"{'='*60}\n")
            
            # Nie usuwaj kodu z bazy - użytkownik może go użyć
            return {
                "message": f"Kod resetujący został wygenerowany. Sprawdź plik password_reset_code.txt lub konsolę serwera. (SMTP nie jest skonfigurowany)",
                "code": code,  # Tylko dla lokalnego środowiska
                "expires_at": expires_at.isoformat()
            }
        else:
            # Jeśli SMTP jest skonfigurowany ale nie udało się wysłać - usuń kod
            db.delete(reset_code)
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Nie udało się wysłać kodu resetującego. Sprawdź konfigurację SMTP i logi serwera."
            )
    
    return {
        "message": "Kod resetujący hasło został wysłany na email"
    }


class ResetPasswordRequest(BaseModel):
    """Model resetowania hasła z kodem."""
    email: str
    code: str
    new_password: str


@router.post("/password-reset/reset")
def reset_password(
    reset_data: ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    """Resetuje hasło używając kodu resetującego."""
    # Walidacja email
    if not is_valid_email(reset_data.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nieprawidłowy format email"
        )
    
    # Walidacja nowego hasła
    if len(reset_data.new_password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nowe hasło musi mieć co najmniej 6 znaków"
        )
    
    # Znajdź użytkownika
    user = db.query(User).filter(User.email == reset_data.email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Użytkownik nie znaleziony"
        )
    
    # Znajdź kod resetujący
    reset_code = db.query(PasswordResetCode).filter(
        PasswordResetCode.user_id == user.id,
        PasswordResetCode.code == reset_data.code,
        PasswordResetCode.email == reset_data.email
    ).order_by(PasswordResetCode.created_at.desc()).first()
    
    if not reset_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nieprawidłowy kod resetujący"
        )
    
    # Sprawdź czy kod jest ważny
    if not reset_code.is_valid():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Kod resetujący wygasł lub został już użyty"
        )
    
    # Zaktualizuj hasło
    user.password_hash = get_password_hash(reset_data.new_password)
    
    # Oznacz kod jako użyty
    reset_code.mark_as_used()
    
    db.commit()
    
    return {
        "message": "Hasło zostało zresetowane pomyślnie"
    }

