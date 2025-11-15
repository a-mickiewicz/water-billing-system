"""
Model użytkownika dla systemu autentykacji.
"""

from sqlalchemy import Column, String, Boolean, Integer
from app.core.database import Base


class User(Base):
    """Model użytkownika."""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=True)  # Email użytkownika (opcjonalny dla admina)
    password_hash = Column(String(255), nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)

