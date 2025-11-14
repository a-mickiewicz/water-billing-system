"""
Skrypt migracyjny - naprawia dane w kolumnie water_meter_5a.
Problem: W poprzedniej migracji obliczyłem water_meter_5a jako main - 5 - 5b,
ale w rzeczywistości water_meter_5b zawierał dane dla gabinet (fizyczny licznik).

Poprawka: Skopiuj dane z water_meter_5b do water_meter_5a (gabinet ma swój fizyczny licznik).
"""

import sqlite3
from pathlib import Path

db_path = Path("water_billing.db")

if not db_path.exists():
    print(f"[INFO] Baza danych {db_path} nie istnieje - migracja nie jest potrzebna.")
    exit(0)

print(f"[INFO] Łączenie z bazą danych: {db_path}")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Sprawdź czy kolumna water_meter_5a istnieje
cursor.execute("PRAGMA table_info(readings)")
columns = [col[1] for col in cursor.fetchall()]

if 'water_meter_5a' not in columns:
    print("[INFO] Kolumna water_meter_5a nie istnieje - uruchom najpierw migrate_add_water_meter_5a.py")
    conn.close()
    exit(1)

# Sprawdź czy istnieje kolumna water_meter_5b
if 'water_meter_5b' not in columns:
    print("[INFO] Kolumna water_meter_5b nie istnieje - nie można naprawić danych")
    conn.close()
    exit(1)

print("[INFO] Naprawianie danych w kolumnie water_meter_5a...")
print("[INFO] Kopiowanie danych z water_meter_5b do water_meter_5a (gabinet ma swój fizyczny licznik)")

try:
    # Pobierz wszystkie odczyty
    cursor.execute("SELECT data, water_meter_5b FROM readings WHERE water_meter_5b IS NOT NULL")
    readings = cursor.fetchall()
    
    updated_count = 0
    for data, meter_5b in readings:
        if meter_5b is not None:
            # Skopiuj wartość z water_meter_5b do water_meter_5a
            # water_meter_5b zawierał dane dla gabinet (fizyczny licznik)
            cursor.execute(
                "UPDATE readings SET water_meter_5a = ? WHERE data = ?",
                (int(meter_5b), data)
            )
            updated_count += 1
    
    conn.commit()
    print(f"[OK] Zaktualizowano {updated_count} odczytów - dane z water_meter_5b skopiowane do water_meter_5a")
    
except sqlite3.OperationalError as e:
    print(f"[ERROR] Błąd podczas naprawiania danych: {e}")
    conn.rollback()
    conn.close()
    exit(1)

conn.close()
print("[OK] Migracja zakończona pomyślnie!")

