"""
Skrypt migracyjny - aktualizuje nazewnictwo lokali w bazie danych.
Zmienia:
- water_meter_5b: Anna Nowak, gabinet → Mikołaj, dol
- water_meter_5a: Piotr Wiśniewski, dol → Bartek, gabinet
"""

import sqlite3
import os

# Ścieżka do bazy danych
DATABASE_PATH = os.path.join(os.path.dirname(__file__), "water_billing.db")

def migrate():
    """Aktualizuje nazewnictwo lokali w tabeli locals."""
    if not os.path.exists(DATABASE_PATH):
        print(f"[BŁĄD] Baza danych nie istnieje: {DATABASE_PATH}")
        return False
    
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    try:
        print("[INFO] Sprawdzanie istniejących rekordów w tabeli locals...")
        
        # Sprawdź czy tabela istnieje
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='locals'")
        if not cursor.fetchone():
            print("[INFO] Tabela locals nie istnieje - migracja nie jest potrzebna.")
            return True
        
        # Sprawdź obecne dane
        cursor.execute("SELECT id, water_meter_name, tenant, local FROM locals")
        existing = cursor.fetchall()
        
        if not existing:
            print("[INFO] Brak rekordów w tabeli locals - migracja nie jest potrzebna.")
            return True
        
        print(f"[INFO] Znaleziono {len(existing)} rekordów w tabeli locals.")
        
        updated_count = 0
        
        for record_id, meter_name, tenant, local in existing:
            if meter_name == "water_meter_5b":
                # Sprawdź czy trzeba zaktualizować
                if tenant == "Mikołaj" and local == "dol":
                    print(f"[INFO] water_meter_5b (ID: {record_id}) już ma poprawne dane (Mikołaj, dol)")
                elif tenant == "Anna Nowak" and local == "gabinet":
                    print(f"[INFO] Aktualizuję water_meter_5b (ID: {record_id}):")
                    print(f"  Stare: tenant='Anna Nowak', local='gabinet'")
                    print(f"  Nowe: tenant='Mikołaj', local='dol'")
                    cursor.execute(
                        "UPDATE locals SET tenant = ?, local = ? WHERE id = ?",
                        ("Mikołaj", "dol", record_id)
                    )
                    updated_count += 1
                else:
                    # Może być zamienione - popraw
                    print(f"[INFO] Aktualizuję water_meter_5b (ID: {record_id}):")
                    print(f"  Stare: tenant='{tenant}', local='{local}'")
                    print(f"  Nowe: tenant='Mikołaj', local='dol'")
                    cursor.execute(
                        "UPDATE locals SET tenant = ?, local = ? WHERE id = ?",
                        ("Mikołaj", "dol", record_id)
                    )
                    updated_count += 1
            
            elif meter_name == "water_meter_5a":
                # Sprawdź czy trzeba zaktualizować
                if tenant == "Bartek" and local == "gabinet":
                    print(f"[INFO] water_meter_5a (ID: {record_id}) już ma poprawne dane (Bartek, gabinet)")
                elif tenant == "Piotr Wiśniewski" and local == "dol":
                    print(f"[INFO] Aktualizuję water_meter_5a (ID: {record_id}):")
                    print(f"  Stare: tenant='Piotr Wiśniewski', local='dol'")
                    print(f"  Nowe: tenant='Bartek', local='gabinet'")
                    cursor.execute(
                        "UPDATE locals SET tenant = ?, local = ? WHERE id = ?",
                        ("Bartek", "gabinet", record_id)
                    )
                    updated_count += 1
                else:
                    # Może być zamienione - popraw
                    print(f"[INFO] Aktualizuję water_meter_5a (ID: {record_id}):")
                    print(f"  Stare: tenant='{tenant}', local='{local}'")
                    print(f"  Nowe: tenant='Bartek', local='gabinet'")
                    cursor.execute(
                        "UPDATE locals SET tenant = ?, local = ? WHERE id = ?",
                        ("Bartek", "gabinet", record_id)
                    )
                    updated_count += 1
        
        conn.commit()
        
        if updated_count > 0:
            print(f"\n[OK] Zaktualizowano {updated_count} rekordów w tabeli locals!")
        else:
            print("\n[INFO] Wszystkie rekordy już mają poprawne dane - migracja nie była potrzebna.")
        
        return True
        
    except sqlite3.Error as e:
        print(f"[BŁĄD] Wystąpił błąd podczas migracji: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    print("=" * 60)
    print("MIGRACJA: Aktualizacja nazewnictwa lokali w bazie danych")
    print("=" * 60)
    print("\nZmiany:")
    print("  water_meter_5b: Anna Nowak, gabinet -> Mikołaj, dol")
    print("  water_meter_5a: Piotr Wiśniewski, dol -> Bartek, gabinet")
    print()
    
    if migrate():
        print("\n[OK] Migracja zakończona pomyślnie!")
    else:
        print("\n[BŁĄD] Migracja nie powiodła się!")

