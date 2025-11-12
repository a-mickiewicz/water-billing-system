"""Sprawdza jakie indeksy i constrainty są w tabeli electricity_invoice_odczyty."""

import sqlite3
from pathlib import Path

db_path = Path("water_billing.db")

if not db_path.exists():
    print(f"[ERROR] Baza danych {db_path} nie istnieje!")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("=== INDEKSY W TABELI electricity_invoice_odczyty ===\n")

# Sprawdź wszystkie indeksy
cursor.execute("""
    SELECT name, sql FROM sqlite_master 
    WHERE type='index' AND tbl_name='electricity_invoice_odczyty'
""")

indeksy = cursor.fetchall()
if indeksy:
    for name, sql in indeksy:
        print(f"Indeks: {name}")
        if sql:
            print(f"  SQL: {sql}")
        print()
else:
    print("Brak indeksów\n")

# Sprawdź strukturę tabeli
print("=== STRUKTURA TABELI ===\n")
cursor.execute("PRAGMA table_info(electricity_invoice_odczyty)")
kolumny = cursor.fetchall()
for kolumna in kolumny:
    print(f"{kolumna[1]} ({kolumna[2]})")

# Sprawdź wszystkie constrainty
print("\n=== CONSTRAINTY ===\n")
cursor.execute("PRAGMA index_list(electricity_invoice_odczyty)")
index_list = cursor.fetchall()
for idx in index_list:
    print(f"Index: {idx[1]}, Unique: {idx[2]}")
    # Sprawdź kolumny w indeksie
    cursor.execute(f"PRAGMA index_info({idx[1]})")
    columns = cursor.fetchall()
    if columns:
        col_names = [col[2] for col in columns]
        print(f"  Kolumny: {', '.join(col_names)}")
    print()

conn.close()

