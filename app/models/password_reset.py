"""
Model do przechowywania kodów resetujących hasło.
"""

from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from datetime import datetime, timedelta
from app.core.database import Base
import secrets


class PasswordResetCode(Base):
    """Model kodu resetującego hasło."""
    __tablename__ = "password_reset_codes"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    code = Column(String(10), nullable=False, unique=True)  # 6-cyfrowy kod
    email = Column(String(255), nullable=False)  # Email do którego wysłano kod
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)  # Kod ważny przez 15 minut
    used = Column(String(10), default='false', nullable=False)  # 'true' lub 'false' jako string
    
    @staticmethod
    def generate_code() -> str:
        """Generuje 6-cyfrowy kod resetujący."""
        return ''.join([str(secrets.randbelow(10)) for _ in range(6)])
    
    def is_valid(self) -> bool:
        """Sprawdza czy kod jest ważny (nie użyty i nie wygasł)."""
        if self.used == 'true':
            return False
        if datetime.utcnow() > self.expires_at:
            return False
        return True
    
    def mark_as_used(self):
        """Oznacza kod jako użyty."""
        self.used = 'true'

