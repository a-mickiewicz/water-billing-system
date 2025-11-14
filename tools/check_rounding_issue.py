"""
Sprawdza problem z zaokrągleniem wartości dziesiętnych w obliczeniach.
Symuluje obliczenia dla faktury FRP/24/02/008566.
"""

# Dane z faktury (po poprawieniu parsera)
usage = 27.0  # 8.1 + 18.9
water_cost_m3 = 5.1829629629629625  # średnia ważona
sewage_cost_m3 = 7.971111111111111  # średnia ważona
water_subscr_cost = 12.83
sewage_subscr_cost = 26.89
vat = 0.08

# Przykładowe zużycie dla lokali (symulacja)
usage_gora = 17.0
usage_gabinet = 4.0
usage_dol = 6.0

print("=" * 80)
print("ANALIZA ZAOKRAGLEN W OBLICZENIACH")
print("=" * 80)

print(f"\n1. DANE Z FAKTURY:")
print(f"   Zuzycie: {usage} m3")
print(f"   Cena wody: {water_cost_m3:.10f} zl/m3")
print(f"   Cena sciekow: {sewage_cost_m3:.10f} zl/m3")
print(f"   Abonament wody: {water_subscr_cost} zl")
print(f"   Abonament sciekow: {sewage_subscr_cost} zl")

print(f"\n2. OBLICZENIA DLA LOKALI (BEZ ZAOKRAGLEN):")
locals_data = [
    ("gora", usage_gora),
    ("gabinet", usage_gabinet),
    ("dol", usage_dol)
]

total_gross_exact = 0.0
total_gross_rounded = 0.0

for local_name, local_usage in locals_data:
    # Koszty zużycia (bez zaokrąglenia)
    cost_water_exact = local_usage * water_cost_m3
    cost_sewage_exact = local_usage * sewage_cost_m3
    cost_usage_total_exact = cost_water_exact + cost_sewage_exact
    
    # Abonament (dzielony przez 3)
    subscription_water_share_exact = water_subscr_cost / 3
    subscription_sewage_share_exact = sewage_subscr_cost / 3
    subscription_total_exact = subscription_water_share_exact + subscription_sewage_share_exact
    
    # Suma netto
    net_sum_exact = cost_usage_total_exact + subscription_total_exact
    
    # Suma brutto
    gross_sum_exact = net_sum_exact * (1 + vat)
    
    # Zaokrąglone wartości (jak w kodzie)
    cost_water_rounded = round(cost_water_exact, 2)
    cost_sewage_rounded = round(cost_sewage_exact, 2)
    cost_usage_total_rounded = round(cost_usage_total_exact, 2)
    subscription_water_share_rounded = round(subscription_water_share_exact, 2)
    subscription_sewage_share_rounded = round(subscription_sewage_share_exact, 2)
    subscription_total_rounded = round(subscription_total_exact, 2)
    net_sum_rounded = round(net_sum_exact, 2)
    gross_sum_rounded = round(gross_sum_exact, 2)
    
    print(f"\n   {local_name.upper()} ({local_usage} m3):")
    print(f"     Koszt wody: {cost_water_exact:.10f} -> {cost_water_rounded:.2f} zl")
    print(f"     Koszt sciekow: {cost_sewage_exact:.10f} -> {cost_sewage_rounded:.2f} zl")
    print(f"     Koszt zuzycia: {cost_usage_total_exact:.10f} -> {cost_usage_total_rounded:.2f} zl")
    print(f"     Abonament: {subscription_total_exact:.10f} -> {subscription_total_rounded:.2f} zl")
    print(f"     Suma netto: {net_sum_exact:.10f} -> {net_sum_rounded:.2f} zl")
    print(f"     Suma brutto: {gross_sum_exact:.10f} -> {gross_sum_rounded:.2f} zl")
    
    total_gross_exact += gross_sum_exact
    total_gross_rounded += gross_sum_rounded

print(f"\n3. SUMA BRUTTO:")
print(f"   Dokladna (bez zaokraglen): {total_gross_exact:.10f} zl")
print(f"   Zaokraglona (suma zaokraglonych): {total_gross_rounded:.2f} zl")
print(f"   Zaokraglona (zaokraglenie sumy): {round(total_gross_exact, 2):.2f} zl")
print(f"   Roznica: {abs(total_gross_rounded - total_gross_exact):.10f} zl")

# Sprawdz czy problem jest z zaokrągleniem wartości dziesiętnych w zużyciu
print(f"\n4. TEST Z WARTOSCIAMI DZIESIETNYMI W ZUZYCIU:")
usage_gora_decimal = 17.0
usage_gabinet_decimal = 4.0
usage_dol_decimal = 6.0  # 27 - 17 - 4 = 6

# Ale jeśli faktyczne zużycie to 8.1 i 18.9, to może być problem z podziałem
print(f"   Zuzycie z faktury: {usage} m3 (8.1 + 18.9)")
print(f"   Gora: {usage_gora_decimal} m3")
print(f"   Gabinet: {usage_gabinet_decimal} m3")
print(f"   Dol: {usage_dol_decimal} m3")
print(f"   Suma: {usage_gora_decimal + usage_gabinet_decimal + usage_dol_decimal} m3")

