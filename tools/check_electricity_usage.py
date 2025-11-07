"""
Skrypt do sprawdzania zużycia prądu dla danego zakresu okresów.
"""

import sys
from pathlib import Path

# Dodaj główny katalog projektu do ścieżki
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import SessionLocal
from app.models.electricity import ElectricityReading
from app.services.electricity.calculator import calculate_all_usage, get_previous_reading

def check_usage_period(start_period: str, end_period: str):
    """Sprawdza zużycie prądu dla zakresu okresów."""
    db = SessionLocal()
    
    # Pobierz wszystkie odczyty w zakresie
    readings = db.query(ElectricityReading).filter(
        ElectricityReading.data >= start_period,
        ElectricityReading.data <= end_period
    ).order_by(ElectricityReading.data).all()
    
    print(f"\n=== ZUŻYCIE PRĄDU DLA OKRESU {start_period} - {end_period} ===\n")
    
    total_dom = 0
    total_dol = 0
    total_gabinet = 0
    total_gora = 0
    
    for reading in readings:
        prev = get_previous_reading(db, reading.data)
        
        if prev:
            usage = calculate_all_usage(reading, prev)
            
            # Pobierz szczegółowe wartości
            dom_usage = usage.get("dom", {})
            dol_usage = usage.get("dol", {})
            gabinet_usage = usage.get("gabinet", {})
            gora_usage = usage.get("gora", {})
            
            dom_I = dom_usage.get("zuzycie_dom_I")
            dom_II = dom_usage.get("zuzycie_dom_II")
            dom_lacznie = dom_usage.get("zuzycie_dom_lacznie", 0)
            
            dol_I = dol_usage.get("zuzycie_dol_I")
            dol_II = dol_usage.get("zuzycie_dol_II")
            dol_lacznie = dol_usage.get("zuzycie_dol_lacznie", 0)
            
            gabinet = gabinet_usage.get("zuzycie_gabinet", 0)
            
            gora_I = gora_usage.get("zuzycie_gora_I")
            gora_II = gora_usage.get("zuzycie_gora_II")
            gora_lacznie = gora_usage.get("zuzycie_gora_lacznie", 0)
            
            print(f"Okres: {reading.data}")
            print(f"  DOM:")
            if dom_I is not None and dom_II is not None:
                print(f"    Taryfa I: {dom_I:.2f} kWh")
                print(f"    Taryfa II: {dom_II:.2f} kWh")
                print(f"    Lacznie: {dom_lacznie:.2f} kWh")
            else:
                if dom_lacznie < 0:
                    print(f"    [!] Lacznie: {dom_lacznie:.2f} kWh (UJEMNE - mozliwa wymiana licznika!)")
                else:
                    print(f"    Lacznie: {dom_lacznie:.2f} kWh (jednotaryfowy)")
            
            print(f"  DOL:")
            if dol_I is not None and dol_II is not None:
                print(f"    Taryfa I: {dol_I:.2f} kWh")
                print(f"    Taryfa II: {dol_II:.2f} kWh")
                print(f"    Lacznie: {dol_lacznie:.2f} kWh")
            else:
                if dol_lacznie < 0:
                    print(f"    [!] Lacznie: {dol_lacznie:.2f} kWh (UJEMNE - mozliwa wymiana licznika!)")
                else:
                    print(f"    Lacznie: {dol_lacznie:.2f} kWh (jednotaryfowy)")
            
            print(f"  GABINET: {gabinet:.2f} kWh (zawsze jednotaryfowy)")
            
            print(f"  GORA:")
            if gora_I is not None and gora_II is not None:
                print(f"    Taryfa I: {gora_I:.2f} kWh")
                print(f"    Taryfa II: {gora_II:.2f} kWh")
                print(f"    Lacznie: {gora_lacznie:.2f} kWh")
            else:
                if gora_lacznie < 0:
                    print(f"    [!] Lacznie: {gora_lacznie:.2f} kWh (UJEMNE - mozliwa wymiana licznika!)")
                else:
                    print(f"    Lacznie: {gora_lacznie:.2f} kWh")
            
            print()
            
            # Dodaj tylko dodatnie wartości do sumy
            if dom_lacznie > 0:
                total_dom += dom_lacznie
            if dol_lacznie > 0:
                total_dol += dol_lacznie
            if gabinet > 0:
                total_gabinet += gabinet
            if gora_lacznie > 0:
                total_gora += gora_lacznie
        else:
            print(f"Okres: {reading.data} - brak poprzedniego odczytu (pierwszy odczyt)\n")
    
    print("=== SUMA CAŁKOWITA ===")
    print(f"DOM: {total_dom:.2f} kWh")
    print(f"DOL: {total_dol:.2f} kWh")
    print(f"GABINET: {total_gabinet:.2f} kWh")
    print(f"GORA: {total_gora:.2f} kWh")
    print(f"\nSUMA WSZYSTKICH: {total_dom + total_dol + total_gabinet + total_gora:.2f} kWh")
    
    db.close()

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 2:
        start_period = sys.argv[1]
        end_period = sys.argv[2]
        check_usage_period(start_period, end_period)
    else:
        # Domyślnie sprawdź 2025-06 do 2025-08
        check_usage_period("2025-06", "2025-08")

