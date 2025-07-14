# File: scheduler_logic.py (Corrected Override Logic)
import pandas as pd
import yaml
from io import StringIO
from datetime import datetime, time
from itertools import permutations

# --- Configuration & Helper Functions ---
# (These helpers remain the same as before)
FINAL_SCHEDULE_ROW_ORDER = [
    "Handout", "Line Buster 1", "Conductor", "Line Buster 2", "Expo",
    "Drink Maker 1", "Drink Maker 2", "Line Buster 3", "Break", "ToffTL"
]
WORK_POSITIONS = [p for p in FINAL_SCHEDULE_ROW_ORDER if p not in ["Break", "ToffTL"]]

def parse_time_input(time_val, ref_date):
    if pd.isna(time_val) or str(time_val).strip().upper() in ['N/A', '']: return pd.NaT
    try: return pd.to_datetime(f"{ref_date.strftime('%Y-%m-%d')} {str(time_val).strip()}")
    except ValueError: return pd.NaT

def load_config(filepath, default_value={}):
    try:
        with open(filepath, 'r') as file:
            config = yaml.safe_load(file)
            return config if config else default_value
    except FileNotFoundError:
        return default_value

def preprocess_employee_data(employee_data_list):
    # (This function is unchanged)
    all_slots = []
    ref_date = datetime(1970, 1, 1).date()
    for emp_data in employee_data_list:
        name_parts = emp_data.get('Name', '').split(' ', 1)
        name = f"{name_parts[0]} {name_parts[1][0] if len(name_parts) > 1 and name_parts[1] else ''}.".strip()
        s_start, s_end = parse_time_input(emp_data.get('Shift Start'), ref_date), parse_time_input(emp_data.get('Shift End'), ref_date)
        b_start, t_start = parse_time_input(emp_data.get('Break'), ref_date), parse_time_input(emp_data.get('ToffTL Start'), ref_date)
        b_end = b_start + pd.Timedelta(minutes=30) if pd.notna(b_start) else pd.NaT
        t_end = t_start + pd.Timedelta(minutes=60) if pd.notna(t_start) else pd.NaT
        if pd.notna(s_start) and pd.notna(s_end):
            curr = s_start
            while curr < s_end:
                on_break = pd.notna(b_start) and b_start <= curr < b_end
                on_tofftl = pd.notna(t_start) and t_start <= curr < t_end
                is_working = not (on_break or on_tofftl)
                all_slots.append({
                    'Time': curr, 'EmployeeName': name, 'IsWorking': is_working,
                    'IsOnBreak': on_break, 'IsOnToffTL': on_tofftl
                })
                curr += pd.Timedelta(minutes=30)
    return pd.DataFrame(all_slots) if all_slots else pd.DataFrame()

# --- Core Rule-Checking and Scheduling Logic ---

def is_assignment_valid(employee, position, employee_states, rules):
    # (Simplified this function slightly as time-based rules are now handled elsewhere)
    state = employee_states.get(employee, {})
    last_pos = state.get('last_pos')
    time_in_pos = state.get('time_in_pos', 0)
    for rule in rules.get('position_rules', []):
        rule_positions = rule['position'] if isinstance(rule['position'], list) else [rule['position']]
        if position in rule_positions:
            if position == last_pos and time_in_pos >= rule.get('max_consecutive_slots', 99):
                return False
    return True

#========================================================================================#
#====== THIS IS THE CORRECTED RECURSIVE SOLVER ==========================================#
#========================================================================================#
def solve_schedule_recursive(time_idx, time_slots, availability, schedule, employee_states, rules):
    if time_idx >= len(time_slots):
        return True, schedule

    current_time_slot_str = time_slots[time_idx]
    
    # Identify positions and employees already fixed by overrides for this slot
    pre_assigned_positions = set(schedule[current_time_slot_str].keys())
    
    # Determine the positions that still need to be filled
    positions_to_fill = [p for p in WORK_POSITIONS if p not in pre_assigned_positions]
    
    # Determine which employees are available (not on break, not overridden)
    available_employees = sorted(list(availability.get(current_time_slot_str, [])))
    
    # Ensure we only try to fill as many positions as we have available staff
    positions_to_fill = positions_to_fill[:len(available_employees)]

    for p in permutations(available_employees):
        current_assignments = {pos: emp for pos, emp in zip(positions_to_fill, p)}
        
        # Check if the proposed new assignments are valid
        is_permutation_valid = all(
            is_assignment_valid(emp, pos, employee_states, rules)
            for pos, emp in current_assignments.items()
        )

        if is_permutation_valid:
            # Create a combined state for the next step
            # Start with the original state
            new_states = employee_states.copy()
            # Combine pre-assigned and newly assigned for the full picture
            full_slot_assignments = {**schedule[current_time_slot_str], **current_assignments}

            for pos, emp in full_slot_assignments.items():
                last_pos = employee_states.get(emp, {}).get('last_pos')
                time_in_pos = employee_states.get(emp, {}).get('time_in_pos', 0)
                new_states[emp] = {
                    'last_pos': pos,
                    'time_in_pos': time_in_pos + 1 if pos == last_pos else 1
                }
            
            # Update the schedule with the newly solved assignments
            schedule[current_time_slot_str].update(current_assignments)
            
            # Recurse
            is_solved, final_schedule = solve_schedule_recursive(
                time_idx + 1, time_slots, availability, schedule, new_states, rules
            )
            if is_solved:
                return True, final_schedule

    # If no solution found, backtrack by removing only the assignments added in this step
    for pos in positions_to_fill:
        if pos in schedule[current_time_slot_str]:
            del schedule[current_time_slot_str][pos]
            
    return False, None


def create_rule_based_schedule(store_open_time_obj, store_close_time_obj, employee_data_list):
    rules = load_config("rules.yaml")
    overrides = load_config("overrides.yaml", default_value=[])
    df_long = preprocess_employee_data(employee_data_list)
    if df_long.empty: return "No employee data to process."

    time_slots_dt = sorted(df_long['Time'].unique())
    time_slots_str = [t.strftime('%I:%M %p').lstrip('0') for t in time_slots_dt]

    availability, breaks, tofftl = {}, {}, {}
    for time_dt, time_str in zip(time_slots_dt, time_slots_str):
        slot_data = df_long[df_long['Time'] == time_dt]
        availability[time_str] = set(slot_data[slot_data['IsWorking']]['EmployeeName'])
        breaks[time_str] = set(slot_data[slot_data['IsOnBreak']]['EmployeeName'])
        tofftl[time_str] = set(slot_data[slot_data['IsOnToffTL']]['EmployeeName'])

    schedule_assignments = {t: {} for t in time_slots_str}
    
    # Apply overrides BEFORE solving
    ref_date = datetime(1970, 1, 1).date()
    for override in overrides:
        emp, pos = override.get('employee'), override.get('position')
        start_dt, end_dt = parse_time_input(override.get('start_time'), ref_date), parse_time_input(override.get('end_time'), ref_date)

        if not all([emp, pos, pd.notna(start_dt), pd.notna(end_dt)]): continue
        
        curr = start_dt
        while curr < end_dt:
            time_str = curr.strftime('%I:%M %p').lstrip('0')
            if time_str in schedule_assignments:
                schedule_assignments[time_str][pos] = emp
                if emp in availability.get(time_str, set()):
                    availability[time_str].remove(emp)
            curr += pd.Timedelta(minutes=30)
    
    is_solved, final_work_assignments = solve_schedule_recursive(
        0, time_slots_str, availability, schedule_assignments, {}, rules
    )

    if not is_solved:
        return "ERROR: Could not find a valid schedule. There may be a conflict between your overrides and employee availability, or there is not enough staff to fill the remaining slots."

    rows = []
    for time_str in time_slots_str:
        row = {"Time": time_str}
        row.update(final_work_assignments.get(time_str, {}))
        row["Break"] = ", ".join(sorted(list(breaks.get(time_str, []))))
        row["ToffTL"] = ", ".join(sorted(list(tofftl.get(time_str, []))))
        rows.append(row)
        
    out_df = pd.DataFrame(rows, columns=["Time"] + FINAL_SCHEDULE_ROW_ORDER)
    final_df = out_df.set_index("Time").transpose().reset_index().rename(columns={'index':'Position'})
    return final_df.to_csv(index=False)
