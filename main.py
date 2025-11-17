"""
Główny moduł aplikacji FastAPI dla systemu rozliczania rachunków za wodę.
Zawiera endpointy do zarządzania danymi i generowania rachunków.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from sqlalchemy.orm import Session

from app.core.database import init_db, get_db
from app.models.water import Local
from app.config import settings
from app.api.routes.gas import router as gas_router
from app.api.routes.electricity import router as electricity_router
from app.api.routes.water import router as water_router
from app.api.routes.auth import router as auth_router
from app.api.routes.backup import router as backup_router
from app.api.routes.combined import router as combined_router


def init_admin_user(db: Session):
    """Inicjalizuje konto administratora jeśli nie istnieje."""
    import os
    from app.models.user import User
    from app.core.auth import get_password_hash
    
    # W produkcji użyj zmiennych środowiskowych ADMIN_USERNAME i ADMIN_PASSWORD
    admin_username = os.getenv("ADMIN_USERNAME", "admin")
    admin_password = os.getenv("ADMIN_PASSWORD", "admin")
    
    admin = db.query(User).filter(User.username == admin_username).first()
    if not admin:
        admin = User(
            username=admin_username,
            password_hash=get_password_hash(admin_password),
            is_admin=True
        )
        db.add(admin)
        db.commit()
        print(f"[OK] Konto administratora utworzone (login: {admin_username}, hasło: {admin_password})")
        print("[WARN] W produkcji ustaw zmienne środowiskowe ADMIN_USERNAME i ADMIN_PASSWORD!")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Zarządzanie cyklem życia aplikacji - inicjalizacja i zamknięcie."""
    # Startup - inicjalizacja bazy danych
    init_db()
    
    # Utwórz konto admina
    from app.core.database import SessionLocal
    db = SessionLocal()
    try:
        init_admin_user(db)
    finally:
        db.close()
    
    yield
    # Shutdown - tutaj można dodać czyszczenie zasobów jeśli potrzeba


app = FastAPI(
    title=settings.api_title,
    description=settings.api_description,
    version=settings.api_version,
    lifespan=lifespan
)

# CORS dla frontendu
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
)

# Serwowanie plików statycznych
static_dir = Path(settings.static_dir)
static_dir.mkdir(exist_ok=True, parents=True)
app.mount("/static", StaticFiles(directory=settings.static_dir), name="static")

# Rejestracja routerów dla mediów
app.include_router(water_router)  # /api/water/*
app.include_router(gas_router)  # /api/gas/*
app.include_router(electricity_router)  # /api/electricity/*
app.include_router(auth_router)  # /api/auth/*
app.include_router(backup_router)  # /api/backup/*
app.include_router(combined_router)  # /api/combined/*


# ========== ENDPOINTY POMOCNICZE ==========

@app.get("/favicon.ico")
def favicon():
    """Endpoint dla favicon.ico - zwraca 204 No Content, aby uniknąć błędów 404."""
    return Response(status_code=204)


@app.get("/", response_class=HTMLResponse)
def root():
    """Strona główna - przekierowanie do logowania."""
    login_path = static_dir / "login.html"
    if login_path.exists():
        return login_path.read_text(encoding="utf-8")
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


@app.get("/login", response_class=HTMLResponse)
def login_page():
    """Strona logowania."""
    login_path = static_dir / "login.html"
    if login_path.exists():
        return login_path.read_text(encoding="utf-8")
    return "<h1>Strona logowania nie znaleziona</h1>"


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    """Dashboard aplikacji."""
    dashboard_path = static_dir / "dashboard.html"
    if dashboard_path.exists():
        return dashboard_path.read_text(encoding="utf-8")
    return "<h1>Dashboard nie znaleziony. Sprawdź folder static/</h1>"


@app.get("/dashboard-alt", response_class=HTMLResponse)
def dashboard_alt():
    """Alternatywny dashboard aplikacji."""
    dashboard_path = static_dir / "dashboard_alt.html"
    if dashboard_path.exists():
        return dashboard_path.read_text(encoding="utf-8")
    return "<h1>Alternatywny dashboard nie znaleziony. Sprawdź folder static/</h1>"


@app.post("/load_sample_data")
def load_sample_data(db: Session = Depends(get_db)):
    """Ładuje przykładowe dane do bazy."""
    # Dodaj lokale
    # UWAGA: Przykładowe dane - nie są to rzeczywiste osoby
    locals_data = [
        {"water_meter_name": "water_meter_5", "tenant": "Jan Kowalski", "local": "gora"},
        {"water_meter_name": "water_meter_5b", "tenant": "Mikiołaj", "local": "dol"},
        {"water_meter_name": "water_meter_5a", "tenant": "Bartosz", "local": "gabinet"},
    ]
    
    added = 0
    skipped = 0
    errors = []
    
    for local_data in locals_data:
        try:
            # Sprawdź czy lokal z tym samym water_meter_name już istnieje
            existing = db.query(Local).filter(
                Local.water_meter_name == local_data["water_meter_name"]
            ).first()
            
            if existing:
                skipped += 1
                continue
            
            # Utwórz nowy lokal
            new_local = Local(**local_data)
            db.add(new_local)
            db.commit()
            added += 1
            
        except Exception as e:
            db.rollback()
            error_msg = f"Błąd dla lokalu {local_data.get('water_meter_name')}: {str(e)}"
            errors.append(error_msg)
    
    if errors:
        return {
            "message": f"Przykładowe dane załadowane częściowo",
            "added": added,
            "skipped": skipped,
            "errors": errors
        }
    
    return {
        "message": "Przykładowe dane załadowane (tylko lokale)",
        "added": added,
        "skipped": skipped
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

