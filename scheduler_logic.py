# File: scheduler_logic.py (Now with Override Support)
import pandas as pd
import yaml
from io import StringIO
from datetime import datetime, time
from itertools import permutations

# --- Configuration & Helper Functions ---
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
    """Loads a YAML configuration file."""
    try:
        with open(filepath, 'r') as file:
            config = yaml.safe_load(file)
            return config if config else default_value
    except FileNotFoundError:
        return default_value

def preprocess_employee_data(employee_data_list):
    # This function remains the same as before
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
                    'Time': curr,
                    'EmployeeName': name,
                    'IsWorking': is_working,
                    'IsOnBreak': on_break,
                    'IsOnToffTL': on_tofftl
                })
                curr += pd.Timedelta(minutes=30)
    return pd.DataFrame(all_slots) if all_slots else pd.DataFrame()

# --- Core Rule-Checking and Scheduling Logic ---

def is_assignment_valid(employee, position, time_slot_obj, schedule, employee_states, rules):
    # This function remains the same as before
    state = employee_states.get(employee, {})
    last_pos = state.get('last_pos')
    time_in_pos = state.get('time_in_pos', 0)

    for rule in rules.get('position_rules', []):
        rule_positions = rule['position'] if isinstance(rule['position'], list) else [rule['position']]
        if position in rule_positions:
            if position == last_pos and time_in_pos >= rule.get('max_consecutive_slots', 99):
                return False
            if position == 'Conductor' and rule.get('must_start_on_the_hour', False):
                if last_pos != 'Conductor' and time_slot_obj.minute != 0:
                    return False
    return True

def solve_schedule_recursive(time_idx, time_slots, availability, schedule, employee_states, rules):
    if time_idx >= len(time_slots):
        return True, schedule

    current_time_slot_str = time_slots[time_idx]
    
    # --- NEW: Check if this time slot is already filled by an override ---
    if schedule.get(current_time_slot_str):
        # This slot is pre-filled, so we just move to the next one
        return solve_schedule_recursive(time_idx + 1, time_slots, availability, schedule, employee_states, rules)

    current_time_slot_obj = parse_time_input(current_time_slot_str, datetime(1970,1,1).date())
    available_employees = sorted(list(availability.get(current_time_slot_str, [])))
    positions_to_fill = WORK_POSITIONS[:len(available_employees)]

    for p in permutations(available_employees):
        assignments = {pos: emp for pos, emp in zip(positions_to_fill, p)}
        
        is_permutation_valid = all(
            is_assignment_valid(emp, pos, current_time_slot_obj, schedule, employee_states, rules)
            for pos, emp in assignments.items()
        )

        if is_permutation_valid:
            new_states = employee_states.copy()
            for pos, emp in assignments.items():
                last_pos = employee_states.get(emp, {}).get('last_pos')
                time_in_pos = employee_states.get(emp, {}).get('time_in_pos', 0)
                new_states[emp] = {
                    'last_pos': pos,
                    'time_in_pos': time_in_pos + 1 if pos == last_pos else 1
                }
            
            schedule[current_time_slot_str] = assignments
            
            is_solved, final_schedule = solve_schedule_recursive(
                time_idx + 1, time_slots, availability, schedule, new_states, rules
            )
            if is_solved:
                return True, final_schedule

    schedule[current_time_slot_str] = {}
    return False, None


def create_rule_based_schedule(store_open_time_obj, store_close_time_obj, employee_data_list):
    rules = load_config("rules.yaml")
    overrides = load_config("overrides.yaml", default_value=[]) # NEW: Load overrides
    df_long = preprocess_employee_data(employee_data_list)
    if df_long.empty: return "No employee data to process."

    time_slots_dt = sorted(df_long['Time'].unique())
    time_slots_str = [t.strftime('%I:%M %p').lstrip('0') for t in time_slots_dt]

    availability = {}
    breaks = {}
    tofftl = {}
    for time_dt, time_str in zip(time_slots_dt, time_slots_str):
        slot_data = df_long[df_long['Time'] == time_dt]
        availability[time_str] = set(slot_data[slot_data['IsWorking']]['EmployeeName'])
        breaks[time_str] = set(slot_data[slot_data['IsOnBreak']]['EmployeeName'])
        tofftl[time_str] = set(slot_data[slot_data['IsOnToffTL']]['EmployeeName'])

    schedule_assignments = {t: {} for t in time_slots_str}
    employee_states = {}

    # --- NEW: Apply overrides BEFORE solving the rest of the schedule ---
    ref_date = datetime(1970, 1, 1).date()
    for override in overrides:
        emp = override.get('employee')
        pos = override.get('position')
        start_dt = parse_time_input(override.get('start_time'), ref_date)
        end_dt = parse_time_input(override.get('end_time'), ref_date)

        if not all([emp, pos, pd.notna(start_dt), pd.notna(end_dt)]): continue
        
        curr = start_dt
        while curr < end_dt:
            time_str = curr.strftime('%I:%M %p').lstrip('0')
            if time_str in schedule_assignments:
                # Pin the assignment
                schedule_assignments[time_str][pos] = emp
                # Remove employee from general availability for this slot
                if emp in availability.get(time_str, set()):
                    availability[time_str].remove(emp)
                # Update state for rule-checking continuity
                last_pos = employee_states.get(emp, {}).get('last_pos')
                time_in_pos = employee_states.get(emp, {}).get('time_in_pos', 0)
                employee_states[emp] = {
                    'last_pos': pos,
                    'time_in_pos': time_in_pos + 1 if pos == last_pos else 1
                }
            curr += pd.Timedelta(minutes=30)
    
    is_solved, final_work_assignments = solve_schedule_recursive(
        0, time_slots_str, availability, schedule_assignments, employee_states, rules
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
