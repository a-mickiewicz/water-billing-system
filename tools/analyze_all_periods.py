import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import SessionLocal
from app.models.electricity import ElectricityReading
from app.services.electricity.calculator import calculate_all_usage
from datetime import date

db = SessionLocal()

print("="*80)
print("ANALIZA WSZYSTKICH OKRESÓW ROZLICZENIOWYCH")
print("="*80)

# Pobieramy wszystkie odczyty
readings = db.query(ElectricityReading).order_by(ElectricityReading.data).all()

# Filtrujemy odczyty z okresu faktury (2023-10 do 2024-10)
relevant_readings = [r for r in readings if r.data >= '2023-10' and r.data <= '2024-10']

print(f"\nZnaleziono {len(relevant_readings)} odczytów w okresie faktury\n")

issues = []
warnings = []

for i in range(1, len(relevant_readings)):
    prev_reading = relevant_readings[i-1]
    current_reading = relevant_readings[i]
    
    # Obliczamy zużycie
    usage_data = calculate_all_usage(current_reading, prev_reading)
    
    # Daty okresu
    period_start = prev_reading.data_odczytu_licznika
    period_end = current_reading.data_odczytu_licznika
    
    if not period_start or not period_end:
        issues.append(f"Brak dat odczytu dla okresu {prev_reading.data} - {current_reading.data}")
        continue
    
    period_start_str = period_start.strftime('%d.%m.%Y')
    period_end_str = period_end.strftime('%d.%m.%Y')
    
    # Pobieramy wartości zużycia
    dom_usage = usage_data.get('dom', {})
    gora_usage = usage_data.get('gora', {})
    dol_usage = usage_data.get('dol', {})
    gabinet_usage = usage_data.get('gabinet', {})
    
    dom_dzienna = dom_usage.get('zuzycie_dom_I', 0) or 0
    dom_nocna = dom_usage.get('zuzycie_dom_II', 0) or 0
    dom_lacznie = dom_usage.get('zuzycie_dom_lacznie', 0) or 0
    
    gora_dzienna = gora_usage.get('zuzycie_gora_I', 0) or 0
    gora_nocna = gora_usage.get('zuzycie_gora_II', 0) or 0
    gora_lacznie = gora_usage.get('zuzycie_gora_lacznie', 0) or 0
    
    dol_dzienna = dol_usage.get('zuzycie_dol_I', 0) or 0
    dol_nocna = dol_usage.get('zuzycie_dol_II', 0) or 0
    dol_lacznie = dol_usage.get('zuzycie_dol_lacznie', 0) or 0
    
    gabinet_dzienna = gabinet_usage.get('zuzycie_gabinet_dzienna', 0) or 0
    gabinet_nocna = gabinet_usage.get('zuzycie_gabinet_nocna', 0) or 0
    gabinet_lacznie = gabinet_usage.get('zuzycie_gabinet', 0) or 0
    
    # Weryfikacja: DOM = GÓRA + DÓŁ + GABINET
    suma_lokali_dzienna = gora_dzienna + dol_dzienna + gabinet_dzienna
    suma_lokali_nocna = gora_nocna + dol_nocna + gabinet_nocna
    suma_lokali_lacznie = gora_lacznie + dol_lacznie + gabinet_lacznie
    
    print(f"\n{'='*80}")
    print(f"Okres: {prev_reading.data} - {current_reading.data}")
    print(f"Dat: {period_start_str} - {period_end_str}")
    print(f"{'='*80}")
    
    print(f"\nDOM:")
    print(f"  Dzienna: {dom_dzienna:.2f} kWh")
    print(f"  Nocna: {dom_nocna:.2f} kWh")
    print(f"  Łącznie: {dom_lacznie:.2f} kWh")
    
    print(f"\nGÓRA:")
    print(f"  Dzienna: {gora_dzienna:.2f} kWh")
    print(f"  Nocna: {gora_nocna:.2f} kWh")
    print(f"  Łącznie: {gora_lacznie:.2f} kWh")
    
    print(f"\nDÓŁ (Mikołaj):")
    print(f"  Dzienna: {dol_dzienna:.2f} kWh")
    print(f"  Nocna: {dol_nocna:.2f} kWh")
    print(f"  Łącznie: {dol_lacznie:.2f} kWh")
    
    print(f"\nGABINET:")
    print(f"  Dzienna: {gabinet_dzienna:.2f} kWh")
    print(f"  Nocna: {gabinet_nocna:.2f} kWh")
    print(f"  Łącznie: {gabinet_lacznie:.2f} kWh")
    
    print(f"\nWERYFIKACJA:")
    print(f"  Suma lokali (dzienna): {suma_lokali_dzienna:.2f} kWh")
    print(f"  DOM (dzienna): {dom_dzienna:.2f} kWh")
    diff_dzienna = abs(dom_dzienna - suma_lokali_dzienna)
    if diff_dzienna > 0.01:
        issues.append(f"Okres {prev_reading.data} - {current_reading.data}: Roznica w zuzyciu dziennym DOM vs suma lokali: {diff_dzienna:.2f} kWh")
        print(f"  [BLAD] ROZNICA: {diff_dzienna:.2f} kWh")
    else:
        print(f"  [OK] Zgadza sie")
    
    print(f"  Suma lokali (nocna): {suma_lokali_nocna:.2f} kWh")
    print(f"  DOM (nocna): {dom_nocna:.2f} kWh")
    diff_nocna = abs(dom_nocna - suma_lokali_nocna)
    if diff_nocna > 0.01:
        issues.append(f"Okres {prev_reading.data} - {current_reading.data}: Roznica w zuzyciu nocnym DOM vs suma lokali: {diff_nocna:.2f} kWh")
        print(f"  [BLAD] ROZNICA: {diff_nocna:.2f} kWh")
    else:
        print(f"  [OK] Zgadza sie")
    
    print(f"  Suma lokali (lacznie): {suma_lokali_lacznie:.2f} kWh")
    print(f"  DOM (lacznie): {dom_lacznie:.2f} kWh")
    diff_lacznie = abs(dom_lacznie - suma_lokali_lacznie)
    if diff_lacznie > 0.01:
        issues.append(f"Okres {prev_reading.data} - {current_reading.data}: Roznica w zuzyciu lacznym DOM vs suma lokali: {diff_lacznie:.2f} kWh")
        print(f"  [BLAD] ROZNICA: {diff_lacznie:.2f} kWh")
    else:
        print(f"  [OK] Zgadza sie")
    
    # Sprawdzamy ujemne wartości
    if gora_nocna < 0:
        warnings.append(f"Okres {prev_reading.data} - {current_reading.data}: GÓRA ma ujemne zużycie nocne: {gora_nocna:.2f} kWh")
    if dol_dzienna < 0 or dol_nocna < 0:
        warnings.append(f"Okres {prev_reading.data} - {current_reading.data}: DÓŁ ma ujemne zużycie")
    if gabinet_dzienna < 0 or gabinet_nocna < 0:
        warnings.append(f"Okres {prev_reading.data} - {current_reading.data}: GABINET ma ujemne zużycie")

print(f"\n\n{'='*80}")
print("PODSUMOWANIE ANALIZY")
print(f"{'='*80}")

if issues:
    print(f"\n[BLAD] ZNALEZIONO {len(issues)} PROBLEMOW:")
    for issue in issues:
        print(f"  - {issue}")
else:
    print("\n[OK] Nie znaleziono problemow z sumowaniem!")

if warnings:
    print(f"\n[OSTRZEZENIE] ZNALEZIONO {len(warnings)} OSTRZEZEN:")
    for warning in warnings:
        print(f"  - {warning}")

db.close()

