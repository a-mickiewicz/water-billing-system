"""
Moduł szyfrowania i deszyfrowania plików.
Używa Fernet (symmetric encryption) z biblioteki cryptography.
"""

import os
from pathlib import Path
from typing import Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
import base64


def get_encryption_key() -> bytes:
    """
    Pobiera klucz szyfrowania z zmiennej środowiskowej lub generuje nowy.
    
    Jeśli zmienna środowiskowa ENCRYPTION_KEY nie istnieje, generuje nowy klucz
    i zapisuje go w pliku .encryption_key (który powinien być w .gitignore).
    
    Returns:
        Klucz szyfrowania jako bytes
    """
    # Najpierw sprawdź zmienną środowiskową
    env_key = os.getenv("ENCRYPTION_KEY")
    if env_key:
        try:
            # Sprawdź czy to już zakodowany klucz Fernet
            if len(env_key) == 44 and env_key.endswith('='):
                return env_key.encode()
            # Jeśli nie, spróbuj użyć jako hasło do generowania klucza
            return _derive_key_from_password(env_key.encode())
        except Exception:
            # Jeśli nie działa, użyj jako hasło
            return _derive_key_from_password(env_key.encode())
    
    # Jeśli nie ma zmiennej środowiskowej, sprawdź plik
    key_file = Path(".encryption_key")
    if key_file.exists():
        try:
            key = key_file.read_text().strip()
            if len(key) == 44 and key.endswith('='):
                return key.encode()
            return _derive_key_from_password(key.encode())
        except Exception:
            pass
    
    # Jeśli nie ma klucza, wygeneruj nowy
    key = Fernet.generate_key()
    
    # Zapisz do pliku (użytkownik powinien dodać .encryption_key do .gitignore)
    try:
        key_file.write_text(key.decode())
        print(f"[INFO] Wygenerowano nowy klucz szyfrowania i zapisano w {key_file}")
        print(f"[WARNING] Dodaj .encryption_key do .gitignore aby chronić klucz!")
    except Exception as e:
        print(f"[WARNING] Nie udało się zapisać klucza do pliku: {e}")
        print(f"[INFO] Klucz szyfrowania (dodaj do zmiennej środowiskowej ENCRYPTION_KEY):")
        print(key.decode())
    
    return key


def _derive_key_from_password(password: bytes) -> bytes:
    """
    Pochodzi klucz Fernet z hasła używając PBKDF2.
    
    Args:
        password: Hasło jako bytes
    
    Returns:
        Klucz Fernet jako bytes
    """
    # Użyj stałej soli (w produkcji można użyć zmiennej środowiskowej)
    salt = os.getenv("ENCRYPTION_SALT", "water_billing_salt_2025").encode()
    
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
        backend=default_backend()
    )
    key = base64.urlsafe_b64encode(kdf.derive(password))
    return key


def encrypt_file(input_file_path: str, output_file_path: Optional[str] = None) -> str:
    """
    Szyfruje plik używając Fernet.
    
    Args:
        input_file_path: Ścieżka do pliku do zaszyfrowania
        output_file_path: Ścieżka do zaszyfrowanego pliku (opcjonalnie, domyślnie dodaje .encrypted)
    
    Returns:
        Ścieżka do zaszyfrowanego pliku
    """
    if not os.path.exists(input_file_path):
        raise FileNotFoundError(f"Plik nie istnieje: {input_file_path}")
    
    if output_file_path is None:
        output_file_path = str(Path(input_file_path).with_suffix('.encrypted'))
    
    # Pobierz klucz
    key = get_encryption_key()
    fernet = Fernet(key)
    
    # Przeczytaj plik
    with open(input_file_path, 'rb') as file:
        file_data = file.read()
    
    # Zaszyfruj
    encrypted_data = fernet.encrypt(file_data)
    
    # Zapisz zaszyfrowany plik
    with open(output_file_path, 'wb') as file:
        file.write(encrypted_data)
    
    print(f"[OK] Zaszyfrowano plik: {input_file_path} -> {output_file_path}")
    return output_file_path


def decrypt_file(input_file_path: str, output_file_path: Optional[str] = None) -> str:
    """
    Deszyfruje plik używając Fernet.
    
    Args:
        input_file_path: Ścieżka do zaszyfrowanego pliku
        output_file_path: Ścieżka do odszyfrowanego pliku (opcjonalnie, usuwa .encrypted)
    
    Returns:
        Ścieżka do odszyfrowanego pliku
    """
    if not os.path.exists(input_file_path):
        raise FileNotFoundError(f"Plik nie istnieje: {input_file_path}")
    
    if output_file_path is None:
        # Usuń rozszerzenie .encrypted jeśli istnieje
        path = Path(input_file_path)
        if path.suffix == '.encrypted':
            output_file_path = str(path.with_suffix(''))
        else:
            output_file_path = str(path.with_suffix('.decrypted'))
    
    # Pobierz klucz
    key = get_encryption_key()
    fernet = Fernet(key)
    
    # Przeczytaj zaszyfrowany plik
    with open(input_file_path, 'rb') as file:
        encrypted_data = file.read()
    
    # Odszyfruj
    try:
        decrypted_data = fernet.decrypt(encrypted_data)
    except Exception as e:
        raise ValueError(f"Nie udało się odszyfrować pliku. Sprawdź czy używasz właściwego klucza: {e}")
    
    # Zapisz odszyfrowany plik
    with open(output_file_path, 'wb') as file:
        file.write(decrypted_data)
    
    print(f"[OK] Odszyfrowano plik: {input_file_path} -> {output_file_path}")
    return output_file_path


def encrypt_file_in_memory(file_path: str) -> bytes:
    """
    Szyfruje plik w pamięci i zwraca zaszyfrowane dane jako bytes.
    Przydatne do wysyłania przez email bez zapisywania na dysku.
    
    Args:
        file_path: Ścieżka do pliku do zaszyfrowania
    
    Returns:
        Zaszyfrowane dane jako bytes
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Plik nie istnieje: {file_path}")
    
    # Pobierz klucz
    key = get_encryption_key()
    fernet = Fernet(key)
    
    # Przeczytaj i zaszyfruj
    with open(file_path, 'rb') as file:
        file_data = file.read()
    
    encrypted_data = fernet.encrypt(file_data)
    return encrypted_data


def decrypt_file_in_memory(encrypted_data: bytes) -> bytes:
    """
    Deszyfruje dane w pamięci i zwraca odszyfrowane dane jako bytes.
    
    Args:
        encrypted_data: Zaszyfrowane dane jako bytes
    
    Returns:
        Odszyfrowane dane jako bytes
    """
    # Pobierz klucz
    key = get_encryption_key()
    fernet = Fernet(key)
    
    try:
        decrypted_data = fernet.decrypt(encrypted_data)
        return decrypted_data
    except Exception as e:
        raise ValueError(f"Nie udało się odszyfrować danych. Sprawdź czy używasz właściwego klucza: {e}")

