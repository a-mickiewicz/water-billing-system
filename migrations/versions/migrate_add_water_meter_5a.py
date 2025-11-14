"""
Skrypt migracyjny - dodaje kolumnę water_meter_5a do tabeli readings.
Kolumna water_meter_5a reprezentuje fizyczny licznik dla lokalu "gabinet".
Kolumna water_meter_5b była wcześniej fizyczna, ale teraz jest obliczana jako: main - 5 - 5a

Uruchom ten skrypt raz, aby zaktualizować istniejącą bazę danych.
"""

import sqlite3
from pathlib import Path

db_path = Path("water_billing.db")

if not db_path.exists():
    print(f"[INFO] Baza danych {db_path} nie istnieje - zostanie utworzona automatycznie przy następnym uruchomieniu aplikacji.")
    exit(0)

print(f"[INFO] Łączenie z bazą danych: {db_path}")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Sprawdź czy kolumna już istnieje
cursor.execute("PRAGMA table_info(readings)")
columns = [col[1] for col in cursor.fetchall()]

if 'water_meter_5a' in columns:
    print("[INFO] Kolumna water_meter_5a już istnieje - migracja nie jest potrzebna.")
    conn.close()
    exit(0)

# Sprawdź czy istnieje kolumna water_meter_5b (stara struktura)
has_5b = 'water_meter_5b' in columns

print("[INFO] Dodawanie kolumny water_meter_5a do tabeli readings...")
try:
    # Dodaj kolumnę water_meter_5a
    cursor.execute("ALTER TABLE readings ADD COLUMN water_meter_5a INTEGER")
    
    # Jeśli istnieją dane w water_meter_5b, musimy je zmigrować
    # W starej strukturze: water_meter_5b był dla "dol", a gabinet był obliczany
    # W nowej strukturze: water_meter_5a jest dla "gabinet" (fizyczny), a dol jest obliczany
    # Więc musimy obliczyć water_meter_5a z istniejących danych
    if has_5b:
        print("[INFO] Migrowanie danych z water_meter_5b do water_meter_5a...")
        print("[INFO] UWAGA: W starej strukturze water_meter_5b był dla 'dol', a gabinet był obliczany.")
        print("[INFO] W nowej strukturze water_meter_5a jest dla 'gabinet' (fizyczny), a dol jest obliczany.")
        print("[INFO] Obliczanie water_meter_5a jako: main - 5 - 5b (gabinet w starej strukturze)")
        
        # Pobierz wszystkie odczyty
        cursor.execute("SELECT data, water_meter_main, water_meter_5, water_meter_5b FROM readings")
        readings = cursor.fetchall()
        
        updated_count = 0
        for data, main, meter_5, meter_5b in readings:
            if main is not None and meter_5 is not None and meter_5b is not None:
                # W starej strukturze: gabinet = main - 5 - 5b
                # Więc water_meter_5a (nowy gabinet) = main - 5 - 5b (stary dol)
                water_meter_5a = int(main - meter_5 - meter_5b)
                cursor.execute(
                    "UPDATE readings SET water_meter_5a = ? WHERE data = ?",
                    (water_meter_5a, data)
                )
                updated_count += 1
        
        print(f"[INFO] Zaktualizowano {updated_count} odczytów.")
    else:
        # Jeśli nie ma water_meter_5b, ustaw domyślną wartość 0
        print("[INFO] Brak kolumny water_meter_5b - ustawianie domyślnej wartości 0 dla water_meter_5a...")
        cursor.execute("UPDATE readings SET water_meter_5a = 0 WHERE water_meter_5a IS NULL")
    
    conn.commit()
    print("[OK] Kolumna water_meter_5a została dodana pomyślnie!")
    
except sqlite3.OperationalError as e:
    print(f"[ERROR] Błąd podczas dodawania kolumny: {e}")
    conn.rollback()
    conn.close()
    exit(1)

conn.close()
print("[OK] Migracja zakończona pomyślnie!")

