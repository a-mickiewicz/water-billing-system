"""
Water meter management and billing module.
Calculates water consumption, measurement differences, and generates costs.
"""

from typing import Dict, Optional, Tuple
from datetime import datetime
from calendar import monthrange
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.models.water import Reading, Invoice, Bill, Local


def calculate_local_usage(
    current_reading: Reading,
    previous_reading: Optional[Reading],
    local_name: str
) -> float:
    """
    Calculates consumption for a specific unit as the difference between current and previous readings.
    Handles main meter replacement - when new reading < previous, treats new reading as consumption.
    
    Args:
        current_reading: Current meter reading
        previous_reading: Previous meter reading (None if this is the first reading)
        local_name: Unit name ('gora', 'gabinet', 'dol')
    
    Returns:
        Consumption in m³ for the given unit (difference between readings or direct value on meter replacement)
    """
    if previous_reading is None:
        # First reading: cannot calculate consumption without previous reading
        # Return 0.0 - consumption will be calculated from next period
        return 0.0
    
    # Check if main meter was replaced (new reading < previous reading)
    meter_main_replaced = current_reading.water_meter_main < previous_reading.water_meter_main
    
    if meter_main_replaced:
        print(f"  [INFO] Main meter replacement detected:")
        print(f"    Previous state: {previous_reading.water_meter_main} m³")
        print(f"    New state: {current_reading.water_meter_main} m³")
        print(f"    Using new state as consumption for the period")
    
    # Calculate difference for gora (physical meter)
    usage_gora = current_reading.water_meter_5 - previous_reading.water_meter_5
    # Calculate difference for gabinet (water_meter_5a - physical meter)
    usage_gabinet = current_reading.water_meter_5a - previous_reading.water_meter_5a
    
    if local_name == 'gora':
        return float(usage_gora)
    elif local_name == 'gabinet':
        return float(usage_gabinet)
    elif local_name == 'dol':
        if meter_main_replaced:
            # When main meter is replaced, don't calculate usage_dol here
            # It will be calculated in generate_bills_for_period after calculating usage_gora and usage_gabinet
            # Return 0 as placeholder - actual value will be calculated later
            return 0.0
        else:
            # Normal calculation - difference between readings
            usage_main = current_reading.water_meter_main - previous_reading.water_meter_main
            # dol (5b) = main difference - (gora difference + gabinet difference)
            return usage_main - (usage_gora + usage_gabinet)
    else:
        raise ValueError(f"Unknown unit: {local_name}")


def check_measurement_difference(
    main_reading: float,
    meter_5_reading: int,
    meter_5a_reading: int
) -> Tuple[bool, float]:
    """
    Checks the difference between sum of submeters (gora + gabinet) and main meter.
    Dol (5b) is calculated as: main - gora - gabinet
    
    Args:
        main_reading: Main meter reading
        meter_5_reading: water_meter_5 reading (gora)
        meter_5a_reading: water_meter_5a reading (gabinet)
    
    Returns:
        Tuple: (has_difference, difference_value)
    """
    sum_submeters = meter_5_reading + meter_5a_reading
    difference = main_reading - sum_submeters
    
    # Allow small tolerance (0.01 m³)
    has_difference = abs(difference) > 0.01
    
    return has_difference, difference


def calculate_bill_costs(
    usage_m3: float,
    water_cost_m3: float,
    sewage_cost_m3: float,
    water_subscr_cost: float,
    sewage_subscr_cost: float,
    nr_of_subscription: int
) -> Tuple[float, float, float, float, float]:
    """
    Calculates costs for a single bill.
    
    Args:
        usage_m3: Unit consumption in m³
        water_cost_m3: Water cost per m³
        sewage_cost_m3: Sewage cost per m³
        water_subscr_cost: Total water subscription cost (sum of all positions: quantity × price for each position)
        sewage_subscr_cost: Total sewage subscription cost (sum of all positions: quantity × price for each position)
        nr_of_subscription: Number of subscriptions (for information only, not used in calculation)
    
    Returns:
        Tuple: (cost_water, cost_sewage, cost_usage_total, subscription_share, net_sum)
    """
    # Consumption costs
    cost_water = usage_m3 * water_cost_m3
    cost_sewage = usage_m3 * sewage_cost_m3
    cost_usage_total = cost_water + cost_sewage
    
    # Subscription - divided among 3 units
    # IMPORTANT: water_subscr_cost and sewage_subscr_cost are already TOTAL sums from all positions
    # (each position: quantity × price, then all positions are summed)
    # We do NOT multiply by nr_of_subscription - it's already the total sum!
    # Just divide by 3 to get share per unit
    subscription_water_share = water_subscr_cost / 3
    subscription_sewage_share = sewage_subscr_cost / 3
    subscription_total = subscription_water_share + subscription_sewage_share
    
    # Net sum (without VAT)
    net_sum = cost_usage_total + subscription_total
    
    return cost_water, cost_sewage, cost_usage_total, subscription_total, net_sum


def generate_bills_for_period(db: Session, period: str) -> list[Bill]:
    """
    Generates bills for all units for a given period.
    Handles multiple invoices for one period (e.g., cost increase mid-period).
    
    Args:
        db: Database session
        period: Billing period in 'YYYY-MM' format
    
    Returns:
        List of generated bills
    """
    # Get current reading for the period
    current_reading = db.query(Reading).filter(Reading.data == period).first()
    if not current_reading:
        raise ValueError(f"No reading for period {period}")
    
    # Get previous reading (latest before current period)
    previous_reading = db.query(Reading).filter(Reading.data < period).order_by(desc(Reading.data)).first()
    
    # Get ALL invoices for the period (may be multiple with cost increases)
    invoices = db.query(Invoice).filter(Invoice.data == period).order_by(Invoice.period_start).all()
    if not invoices:
        raise ValueError(f"No invoices for period {period}")
    
    # Check if invoices have the same number as invoices in the next period
    # (situation when one invoice is split across two billing periods)
    # IMPORTANT: Only add invoices from next period if they actually cover the current period
    # (i.e., invoice period_start overlaps with current billing period)
    if invoices:
        invoice_numbers = set(inv.invoice_number for inv in invoices)
        # Get next period (YYYY-MM -> YYYY-MM+1)
        try:
            year, month = map(int, period.split('-'))
            if month == 12:
                next_period = f"{year + 1}-01"
            else:
                next_period = f"{year}-{month + 1:02d}"
            
            # Check invoices from next period with the same number
            next_invoices = db.query(Invoice).filter(
                Invoice.data == next_period,
                Invoice.invoice_number.in_(invoice_numbers)
            ).all()
            
            if next_invoices:
                # Only add invoices from next period if their period_start is before or during current period
                # This prevents adding invoices that belong to a different billing period
                current_period_start = f"{period}-01"
                added_invoices = []
                for next_inv in next_invoices:
                    # Check if invoice period overlaps with current billing period
                    # If invoice period_start is in current period or earlier, it belongs to current period
                    if next_inv.period_start:
                        # Parse current period start date
                        try:
                            period_start_date = datetime.strptime(current_period_start, "%Y-%m-%d").date()
                            # If invoice period_start is before or equal to end of current period, include it
                            # Current period ends at last day of month
                            last_day = monthrange(year, month)[1]
                            period_end_date = datetime(year, month, last_day).date()
                            
                            if next_inv.period_start <= period_end_date:
                                added_invoices.append(next_inv)
                                print(f"[INFO] Found invoice {next_inv.invoice_number} from period {next_period}"
                                      f" with period_start {next_inv.period_start} that overlaps with {period},"
                                      f" added to billing for {period}")
                            else:
                                print(f"[INFO] Invoice {next_inv.invoice_number} from period {next_period}"
                                      f" has period_start {next_inv.period_start} which is after {period},"
                                      f" NOT adding to billing for {period}")
                        except (ValueError, AttributeError):
                            # If we can't parse dates, don't add the invoice (safer)
                            print(f"[WARNING] Cannot parse dates for invoice {next_inv.invoice_number},"
                                  f" skipping addition to period {period}")
                
                if added_invoices:
                    invoices.extend(added_invoices)
                    invoices.sort(key=lambda inv: inv.period_start)
        except (ValueError, IndexError):
            pass  # If period cannot be parsed, continue without checking next period
    
    # Check if there was compensation to transfer from previous period
    # WYŁĄCZONE: Kompensacja z poprzednich okresów nie jest już obliczana
    compensation_from_previous = 0.0
    # if previous_reading:
    #     try:
    #         # Get previous period
    #         prev_period = previous_reading.data
    #         # Check if there was a bill for "dol" in previous period with negative consumption
    #         prev_bills = db.query(Bill).filter(
    #             Bill.data == prev_period,
    #             Bill.local == 'dol'
    #         ).all()
    #         
    #         for prev_bill in prev_bills:
    #             if prev_bill.usage_m3 < 0:
    #                 # Transfer compensation to current period on "gora"
    #                 compensation_from_previous = abs(prev_bill.usage_m3)
    #                 print(f"[INFO] Transferring compensation from previous period {prev_period}:")
    #                 print(f"  Negative dol consumption: {prev_bill.usage_m3:.2f} m3")
    #                 print(f"  Adding {compensation_from_previous:.2f} m3 to 'gora' unit in period {period}")
    #                 break
    #     except Exception as e:
    #         print(f"[WARNING] Cannot check compensation from previous period: {e}")
    
    # Check if main meter was replaced
    meter_main_replaced = False
    if previous_reading:
        meter_main_replaced = current_reading.water_meter_main < previous_reading.water_meter_main
    
    # Calculate consumption for each unit as difference between readings
    # Gora and gabinet have physical meters, dol is calculated
    usage_gora = calculate_local_usage(current_reading, previous_reading, 'gora')
    usage_gabinet = calculate_local_usage(current_reading, previous_reading, 'gabinet')
    
    # If main meter was replaced, calculate usage_dol specially
    if meter_main_replaced:
        # When main meter is replaced:
        # water_meter_main is total consumption for the period (e.g., 33 m³)
        # usage_dol = total consumption - (gora consumption + gabinet consumption)
        print(f"[INFO] Using water_meter_main directly as total consumption due to meter replacement")
        calculated_total_usage = current_reading.water_meter_main
        usage_dol = calculated_total_usage - (usage_gora + usage_gabinet)
        print(f"  Total consumption for period: {calculated_total_usage:.2f} m3")
        print(f"  Distribution:")
        print(f"    Gora: {usage_gora:.2f} m3")
        print(f"    Gabinet: {usage_gabinet:.2f} m3")
        print(f"    Dol: {usage_dol:.2f} m3 (calculated as {calculated_total_usage:.2f} - ({usage_gora:.2f} + {usage_gabinet:.2f}))")
    else:
        # Normal calculation - dol as main - gora - gabinet
        usage_dol = calculate_local_usage(current_reading, previous_reading, 'dol')
        # Calculate total consumption from differences between readings
        calculated_total_usage = usage_gora + usage_gabinet + usage_dol
    
    # If usage_dol is negative, keep it negative (will be saved in bill)
    # WYŁĄCZONE: Kompensacja nie jest już dodawana do 'gora' w następnym okresie
    if usage_dol < 0 and not meter_main_replaced:
        print(f"[INFO] Unit 'dol' has negative consumption ({usage_dol:.2f} m3) for period {period}")
        print(f"  This is normal when sum of submeters (gora + gabinet) is greater than main meter")
        print(f"  Keeping negative consumption (compensation disabled)")
    
    # WYŁĄCZONE: Dodawanie kompensacji z poprzedniego okresu do "gora"
    # if compensation_from_previous > 0:
    #     usage_gora += compensation_from_previous
    #     # Update total consumption if meter was not replaced
    #     if not meter_main_replaced:
    #         calculated_total_usage = usage_gora + usage_gabinet + usage_dol
    
    # Calculate total consumption from all invoices
    total_invoice_usage = sum(inv.usage for inv in invoices)
    
    # Calculate difference between invoice and sum of readings
    usage_adjustment = total_invoice_usage - calculated_total_usage
    
    # Warning if difference is very large (may indicate data error)
    if abs(usage_adjustment) > 5.0:
        print(f"[WARNING] Large difference between readings and invoice for {period}:")
        print(f"  Sum of reading differences: {calculated_total_usage:.2f} m3")
        print(f"  Consumption from invoice: {total_invoice_usage:.2f} m3")
        print(f"  Difference: {usage_adjustment:.2f} m3")
        print(f"  Possible causes: incorrect readings, incorrect invoice, or non-overlapping billing periods")
    
    # If there are differences between invoice and calculations, add correction only to "gora" unit
    # (compensation for difference in next period will be on "gora")
    if abs(usage_adjustment) > 0.01:
        print(f"[INFO] Difference between invoice and calculations: {usage_adjustment:.2f} m3")
        print(f"  Adding correction only to 'gora' unit")
        usage_gora += usage_adjustment
    
    # Calculate average costs from all invoices (weighted by consumption)
    total_usage = sum(inv.usage for inv in invoices)
    weighted_water_cost = sum(inv.water_cost_m3 * inv.usage for inv in invoices) / total_usage if total_usage > 0 else 0
    weighted_sewage_cost = sum(inv.sewage_cost_m3 * inv.usage for inv in invoices) / total_usage if total_usage > 0 else 0
    
    # Sum subscriptions from all invoices
    # IMPORTANT: water_subscr_cost and sewage_subscr_cost are already TOTAL sums from all positions
    # (each position: quantity × price, then all positions are summed)
    # Example: Position 1: 1×15=15, Position 2: 1×15=15 → water_subscr_cost = 30
    # Example: Position 1: 1×12=12, Position 2: 1×14=14 → water_subscr_cost = 26
    # We do NOT multiply by nr_of_subscription here - it's already the total sum!
    total_water_subscr = sum(inv.water_subscr_cost for inv in invoices)
    total_sewage_subscr = sum(inv.sewage_subscr_cost for inv in invoices)
    
    # Use average VAT from invoices
    avg_vat = sum(inv.vat for inv in invoices) / len(invoices)
    
    # Generate bills for all units
    locals_list = ['gora', 'gabinet', 'dol']
    bills = []
    
    for local_name in locals_list:
        # Assign appropriate consumption
        if local_name == 'gora':
            usage_m3 = usage_gora
        elif local_name == 'gabinet':
            usage_m3 = usage_gabinet
        else:  # dol
            usage_m3 = usage_dol
        
        # Calculate costs using weighted average costs from all invoices
        cost_water = usage_m3 * weighted_water_cost
        cost_sewage = usage_m3 * weighted_sewage_cost
        cost_usage_total = cost_water + cost_sewage
        
        # Subscription divided among 3 units
        subscription_water_share = total_water_subscr / 3
        subscription_sewage_share = total_sewage_subscr / 3
        subscription_total = subscription_water_share + subscription_sewage_share
        
        # Net sum
        net_sum = cost_usage_total + subscription_total
        
        # VAT
        gross_sum = net_sum * (1 + avg_vat)
        
        # Find unit in database
        local_obj = db.query(Local).filter(Local.local == local_name).first()
        
        if not local_obj:
            raise ValueError(f"Unit '{local_name}' not found in database")
        
        # Get current meter reading value
        if local_name == 'gora':
            current_reading_value = current_reading.water_meter_5
            previous_reading_value = previous_reading.water_meter_5 if previous_reading else 0
        elif local_name == 'gabinet':
            current_reading_value = current_reading.water_meter_5a
            previous_reading_value = previous_reading.water_meter_5a if previous_reading else 0
        else:  # dol (5b)
            # For dol, reading value is calculated as: main - gora - gabinet
            current_reading_value = current_reading.water_meter_main - (current_reading.water_meter_5 + current_reading.water_meter_5a)
            if previous_reading:
                previous_main = previous_reading.water_meter_main - (previous_reading.water_meter_5 + previous_reading.water_meter_5a)
                previous_reading_value = previous_main
            else:
                previous_reading_value = 0
        
        # Get reading value for display (current state)
        reading_value = current_reading_value
        
        # Round all Float values to 2 decimal places before saving to database
        def round_to_2(value):
            """Rounds value to 2 decimal places."""
            return round(float(value), 2) if value is not None else None
        
        # Create bill (using ID of first invoice)
        bill = Bill(
            data=period,
            local=local_name,
            reading_id=period,
            invoice_id=invoices[0].id,  # First invoice from the period
            local_id=local_obj.id,
            reading_value=round_to_2(reading_value),
            usage_m3=round_to_2(usage_m3),
            cost_water=round_to_2(cost_water),
            cost_sewage=round_to_2(cost_sewage),
            cost_usage_total=round_to_2(cost_usage_total),
            abonament_water_share=round_to_2(subscription_water_share),
            abonament_sewage_share=round_to_2(subscription_sewage_share),
            abonament_total=round_to_2(subscription_total),
            net_sum=round_to_2(net_sum),
            gross_sum=round_to_2(gross_sum)
        )
        
        db.add(bill)
        bills.append(bill)
    
    db.commit()
    
    return bills

