"""
Moduł integracji z Google Sheets.
Pozwala na import danych z arkuszy Google Sheets bezpośrednio do bazy danych.
"""

import os
import gspread
from google.oauth2.service_account import Credentials
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.models.water import Reading, Local, Invoice


class GoogleSheetsIntegration:
    """Klasa do obsługi połączenia z Google Sheets."""
    
    def __init__(self, credentials_path: str, spreadsheet_id: str):
        """
        Inicjalizuje połączenie z Google Sheets.
        
        Args:
            credentials_path: Ścieżka do pliku JSON z poświadczeniami Google Service Account
            spreadsheet_id: ID arkusza Google Sheets (można znaleźć w URL arkusza)
        """
        # Normalizuj ścieżkę (konwertuj względną ścieżkę na bezwzględną)
        if not os.path.isabs(credentials_path):
            # Jeśli ścieżka jest względna, połącz z katalogiem roboczym
            credentials_path = os.path.join(os.getcwd(), credentials_path)
        
        # Normalizuj ścieżkę dla Windows/Linux
        credentials_path = os.path.normpath(credentials_path)
        
        # Sprawdź czy plik istnieje
        if not os.path.exists(credentials_path):
            raise FileNotFoundError(
                f"Plik credentials nie został znaleziony: {credentials_path}\n"
                f"Upewnij się, że plik istnieje i ścieżka jest prawidłowa.\n"
                f"Obecny katalog roboczy: {os.getcwd()}"
            )
        
        self.credentials_path = credentials_path
        self.spreadsheet_id = spreadsheet_id
        self.client = None
        self.spreadsheet = None
        
    def connect(self):
        """Nawiazyuje połączenie z Google Sheets."""
        try:
            scope = [
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/drive"
            ]
            
            creds = Credentials.from_service_account_file(
                self.credentials_path,
                scopes=scope
            )
            
            self.client = gspread.authorize(creds)
            self.spreadsheet = self.client.open_by_key(self.spreadsheet_id)
            print(f"[OK] Połączono z arkuszem: {self.spreadsheet.title}")
        except FileNotFoundError:
            raise FileNotFoundError(
                f"Nie można znaleźć pliku credentials: {self.credentials_path}\n"
                f"Sprawdź czy ścieżka jest prawidłowa."
            )
        except PermissionError as e:
            # Odczytaj email konta serwisowego z pliku credentials
            try:
                import json
                with open(self.credentials_path, 'r', encoding='utf-8') as f:
                    creds_data = json.load(f)
                    service_account_email = creds_data.get('client_email', 'nieznany')
            except:
                service_account_email = 'nieznany'
            
            raise PermissionError(
                f"❌ BRAK DOSTĘPU DO ARKUSZA GOOGLE SHEETS\n\n"
                f"Konto serwisowe nie ma uprawnień do arkusza.\n\n"
                f"🔧 ROZWIĄZANIE:\n"
                f"1. Otwórz arkusz Google Sheets\n"
                f"2. Kliknij przycisk 'Udostępnij' (Share)\n"
                f"3. Dodaj ten email jako 'Edytor' (Editor):\n"
                f"   {service_account_email}\n"
                f"4. Kliknij 'Wyślij'\n\n"
                f"Spreadsheet ID: {self.spreadsheet_id}\n"
                f"Szczegóły błędu: {str(e)}"
            )
        except Exception as e:
            raise Exception(
                f"Błąd podczas łączenia z Google Sheets: {str(e)}\n"
                f"Sprawdź czy:\n"
                f"1. Plik credentials jest poprawny\n"
                f"2. Spreadsheet ID jest prawidłowy\n"
                f"3. Konto serwisowe ma dostęp do arkusza"
            )
    
    def get_worksheet(self, sheet_name: str):
        """Pobiera konkretny arkusz po nazwie."""
        if not self.spreadsheet:
            self.connect()
        
        try:
            return self.spreadsheet.worksheet(sheet_name)
        except gspread.exceptions.WorksheetNotFound:
            print(f"[BŁĄD] Arkusz '{sheet_name}' nie został znaleziony")
            return None
    
    def get_readings_data(self, sheet_name: str = "Odczyty") -> List[Dict]:
        """
        Pobiera dane odczytów liczników z Google Sheets.
        
        Oczekiwany format arkusza:
        | data      | water_meter_main | water_meter_5 | water_meter_5b |
        | 2025-02   | 150.5            | 45            | 38             |
        
        Args:
            sheet_name: Nazwa arkusza z odczytami
            
        Returns:
            Lista słowników z danymi odczytów
        """
        worksheet = self.get_worksheet(sheet_name)
        if not worksheet:
            return []
        
        # Pobierz wszystkie dane - użyj expected_headers aby obsłużyć zduplikowane nagłówki
        expected_headers = ['data', 'water_meter_main', 'water_meter_5', 'water_meter_5b']
        try:
            data = worksheet.get_all_records(expected_headers=expected_headers)
        except Exception as e:
            # Jeśli expected_headers nie działa, spróbuj bez niego
            print(f"[WARNING] Problem z nagłówkami, próbuję alternatywną metodę: {e}")
            try:
                data = worksheet.get_all_records()
            except Exception as e2:
                print(f"[BŁĄD] Nie można wczytać danych z arkusza: {e2}")
                print(f"[INFO] Sprawdź czy arkusz '{sheet_name}' ma poprawne nagłówki: {expected_headers}")
                return []
        
        readings = []
        for row in data:
            try:
                reading = {
                    'data': str(row.get('data', '')).strip(),
                    'water_meter_main': float(row.get('water_meter_main', 0)),
                    'water_meter_5': int(row.get('water_meter_5', 0)),
                    'water_meter_5b': int(row.get('water_meter_5b', 0))
                }
                readings.append(reading)
            except (ValueError, TypeError) as e:
                print(f"[BŁĄD] Błędny wiersz: {row}. Błąd: {e}")
        
        print(f"[OK] Wczytano {len(readings)} odczytów z Google Sheets")
        return readings
    
    def get_locals_data(self, sheet_name: str = "Lokale") -> List[Dict]:
        """
        Pobiera dane lokali z Google Sheets.
        
        Oczekiwany format arkusza:
        | water_meter_name | tenant         | local   |
        | water_meter_5    | Jan Kowalski   | gora    |
        
        Args:
            sheet_name: Nazwa arkusza z lokalami
            
        Returns:
            Lista słowników z danymi lokali
        """
        worksheet = self.get_worksheet(sheet_name)
        if not worksheet:
            return []
        
        data = worksheet.get_all_records()
        
        locals = []
        for row in data:
            try:
                local = {
                    'water_meter_name': str(row.get('water_meter_name', '')).strip(),
                    'tenant': str(row.get('tenant', '')).strip(),
                    'local': str(row.get('local', '')).strip()
                }
                locals.append(local)
            except (ValueError, TypeError) as e:
                print(f"[BŁĄD] Błędny wiersz: {row}. Błąd: {e}")
        
        print(f"[OK] Wczytano {len(locals)} lokali z Google Sheets")
        return locals
    
    def get_invoices_data(self, sheet_name: str = "Faktury") -> List[Dict]:
        """
        Pobiera dane faktur z Google Sheets.
        
        Oczekiwany format arkusza:
        | data   | usage | water_cost_m3 | sewage_cost_m3 | ... |
        
        Args:
            sheet_name: Nazwa arkusza z fakturami
            
        Returns:
            Lista słowników z danymi faktur
        """
        worksheet = self.get_worksheet(sheet_name)
        if not worksheet:
            return []
        
        data = worksheet.get_all_records()
        
        invoices = []
        for row in data:
            try:
                invoice = {
                    'data': str(row.get('data', '')).strip(),
                    'usage': float(row.get('usage', 0)),
                    'water_cost_m3': float(row.get('water_cost_m3', 0)),
                    'sewage_cost_m3': float(row.get('sewage_cost_m3', 0)),
                    'nr_of_subscription': int(row.get('nr_of_subscription', 0)),
                    'water_subscr_cost': float(row.get('water_subscr_cost', 0)),
                    'sewage_subscr_cost': float(row.get('sewage_subscr_cost', 0)),
                    'vat': float(row.get('vat', 0)),
                    'period_start': str(row.get('period_start', '')).strip(),
                    'period_stop': str(row.get('period_stop', '')).strip(),
                    'invoice_number': str(row.get('invoice_number', '')).strip(),
                    'gross_sum': float(row.get('gross_sum', 0))
                }
                invoices.append(invoice)
            except (ValueError, TypeError) as e:
                print(f"[BŁĄD] Błędny wiersz: {row}. Błąd: {e}")
        
        print(f"[OK] Wczytano {len(invoices)} faktur z Google Sheets")
        return invoices


def import_readings_from_sheets(
    db: Session,
    credentials_path: str,
    spreadsheet_id: str,
    sheet_name: str = "Odczyty"
) -> Dict:
    """
    Importuje odczyty liczników z Google Sheets do bazy danych.
    
    Args:
        db: Sesja bazy danych
        credentials_path: Ścieżka do pliku JSON z poświadczeniami
        spreadsheet_id: ID arkusza Google Sheets
        sheet_name: Nazwa arkusza z odczytami
        
    Returns:
        Słownik z informacjami o importowanych danych
    """
    integration = GoogleSheetsIntegration(credentials_path, spreadsheet_id)
    readings_data = integration.get_readings_data(sheet_name)
    
    imported = 0
    skipped = 0
    errors = []
    
    # Usuń duplikaty z danych (po kluczu 'data')
    seen_dates = set()
    unique_readings = []
    for reading_data in readings_data:
        data_key = reading_data.get('data')
        if data_key and data_key not in seen_dates:
            seen_dates.add(data_key)
            unique_readings.append(reading_data)
        elif data_key in seen_dates:
            errors.append(f"Duplikat okresu w Google Sheets: {data_key}")
    
    # Importuj tylko unikalne rekordy
    for reading_data in unique_readings:
        try:
            # Sprawdź czy odczyt już istnieje w bazie
            existing = db.query(Reading).filter(
                Reading.data == reading_data['data']
            ).first()
            
            if existing:
                skipped += 1
                continue
            
            # Zaokrąglij water_meter_main do 2 miejsc po przecinku
            if 'water_meter_main' in reading_data and reading_data['water_meter_main'] is not None:
                reading_data['water_meter_main'] = round(float(reading_data['water_meter_main']), 2)
            
            # Utwórz nowy odczyt
            new_reading = Reading(**reading_data)
            db.add(new_reading)
            db.commit()  # Commit każdy rekord osobno
            imported += 1
            
        except Exception as e:
            db.rollback()  # Cofnij zmiany w przypadku błędu
            error_msg = f"Błąd dla okresu {reading_data.get('data')}: {str(e)}"
            errors.append(error_msg)
            print(f"[BŁĄD] {error_msg}")
    
    return {
        "imported": imported,
        "skipped": skipped,
        "errors": errors,
        "total": len(readings_data),
        "unique_records": len(unique_readings)
    }


def import_locals_from_sheets(
    db: Session,
    credentials_path: str,
    spreadsheet_id: str,
    sheet_name: str = "Lokale"
) -> Dict:
    """
    Importuje lokale z Google Sheets do bazy danych.
    
    Args:
        db: Sesja bazy danych
        credentials_path: Ścieżka do pliku JSON z poświadczeniami
        spreadsheet_id: ID arkusza Google Sheets
        sheet_name: Nazwa arkusza z lokalami
        
    Returns:
        Słownik z informacjami o importowanych danych
    """
    integration = GoogleSheetsIntegration(credentials_path, spreadsheet_id)
    locals_data = integration.get_locals_data(sheet_name)
    
    imported = 0
    skipped = 0
    errors = []
    
    # Usuń duplikaty z danych (po kluczu 'water_meter_name')
    seen_names = set()
    unique_locals = []
    for local_data in locals_data:
        name_key = local_data.get('water_meter_name')
        if name_key and name_key not in seen_names:
            seen_names.add(name_key)
            unique_locals.append(local_data)
        elif name_key in seen_names:
            errors.append(f"Duplikat lokalu w Google Sheets: {name_key}")
    
    for local_data in unique_locals:
        try:
            # Sprawdź czy lokal już istnieje
            existing = db.query(Local).filter(
                Local.water_meter_name == local_data['water_meter_name']
            ).first()
            
            if existing:
                skipped += 1
                continue
            
            # Utwórz nowy lokal
            new_local = Local(**local_data)
            db.add(new_local)
            db.commit()  # Commit każdy rekord osobno
            imported += 1
            
        except Exception as e:
            db.rollback()  # Cofnij zmiany w przypadku błędu
            error_msg = f"Błąd dla lokalu {local_data.get('water_meter_name')}: {str(e)}"
            errors.append(error_msg)
            print(f"[BŁĄD] {error_msg}")
    
    return {
        "imported": imported,
        "skipped": skipped,
        "errors": errors,
        "total": len(locals_data),
        "unique_records": len(unique_locals)
    }


def import_invoices_from_sheets(
    db: Session,
    credentials_path: str,
    spreadsheet_id: str,
    sheet_name: str = "Faktury"
) -> Dict:
    """
    Importuje faktury z Google Sheets do bazy danych.
    
    Args:
        db: Sesja bazy danych
        credentials_path: Ścieżka do pliku JSON z poświadczeniami
        spreadsheet_id: ID arkusza Google Sheets
        sheet_name: Nazwa arkusza z fakturami
        
    Returns:
        Słownik z informacjami o importowanych danych
    """
    integration = GoogleSheetsIntegration(credentials_path, spreadsheet_id)
    invoices_data = integration.get_invoices_data(sheet_name)
    
    imported = 0
    skipped = 0
    errors = []
    
    for invoice_data in invoices_data:
        try:
            from datetime import datetime
            
            # Konwertuj daty
            period_start = datetime.strptime(
                invoice_data['period_start'], 
                "%Y-%m-%d"
            ).date()
            period_stop = datetime.strptime(
                invoice_data['period_stop'], 
                "%Y-%m-%d"
            ).date()
            
            # Dodaj przekonwertowane daty
            invoice_data['period_start'] = period_start
            invoice_data['period_stop'] = period_stop
            
            # Sprawdź czy faktura już istnieje - porównaj wszystkie kluczowe pola
            # (nie tylko invoice_number, bo może być wiele faktur o tym samym numerze)
            existing = db.query(Invoice).filter(
                Invoice.invoice_number == invoice_data['invoice_number'],
                Invoice.data == invoice_data['data'],
                Invoice.period_start == period_start,
                Invoice.period_stop == period_stop,
                Invoice.usage == invoice_data['usage'],
                Invoice.gross_sum == invoice_data['gross_sum']
            ).first()
            
            if existing:
                skipped += 1
                continue
            
            # Zaokrąglij wszystkie wartości Float do 2 miejsc po przecinku
            float_fields = ['usage', 'water_cost_m3', 'sewage_cost_m3', 'water_subscr_cost', 
                            'sewage_subscr_cost', 'vat', 'gross_sum']
            for field in float_fields:
                if field in invoice_data and invoice_data[field] is not None:
                    invoice_data[field] = round(float(invoice_data[field]), 2)
            
            # Utwórz nową fakturę
            new_invoice = Invoice(**invoice_data)
            db.add(new_invoice)
            db.commit()  # Commit każdy rekord osobno
            imported += 1
            
        except IntegrityError as e:
            # Jeśli baza ma UNIQUE constraint na invoice_number, pomiń fakturę
            db.rollback()
            skipped += 1
            print(f"[POMINIĘTO] Faktura {invoice_data.get('invoice_number')} już istnieje w bazie (UNIQUE constraint)")
        except ValueError as e:
            db.rollback()  # Cofnij zmiany w przypadku błędu
            error_msg = f"Błąd parsowania daty dla faktury {invoice_data.get('invoice_number')}: {str(e)}"
            errors.append(error_msg)
            print(f"[BŁĄD] {error_msg}")
        except Exception as e:
            db.rollback()  # Cofnij zmiany w przypadku błędu
            error_msg = f"Błąd dla faktury {invoice_data.get('invoice_number')}: {str(e)}"
            errors.append(error_msg)
            print(f"[BŁĄD] {error_msg}")
    
    return {
        "imported": imported,
        "skipped": skipped,
        "errors": errors,
        "total": len(invoices_data)
    }

