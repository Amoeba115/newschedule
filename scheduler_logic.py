# File: scheduler_logic.py (Rule-Based Engine)
import pandas as pd
import yaml
from io import StringIO
from datetime import datetime
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

def load_rules(filepath="rules.yaml"):
    """Loads scheduling rules from a YAML file."""
    try:
        with open(filepath, 'r') as file:
            return yaml.safe_load(file)
    except FileNotFoundError:
        # Provide default rules if the file doesn't exist
        return {
            'position_rules': [
                {'position': 'Conductor', 'max_consecutive_slots': 2, 'must_start_on_the_hour': True},
                {'position': ['Line Buster 1', 'Line Buster 2', 'Line Buster 3'], 'max_consecutive_slots': 1},
                {'position': ['Handout', 'Expo', 'Drink Maker 1', 'Drink Maker 2'], 'max_consecutive_slots': 2}
            ],
            'preferences': {'prioritize_rested_employees': True, 'prefer_variety': True}
        }

def preprocess_employee_data(employee_data_list):
    """Prepares raw employee input into a structured DataFrame for scheduling."""
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
    """Checks if assigning an employee to a position at a specific time is valid based on the rules."""
    state = employee_states.get(employee, {})
    last_pos = state.get('last_pos')
    time_in_pos = state.get('time_in_pos', 0)

    for rule in rules['position_rules']:
        rule_positions = rule['position'] if isinstance(rule['position'], list) else [rule['position']]
        if position in rule_positions:
            # Check max consecutive slots
            if position == last_pos and time_in_pos >= rule['max_consecutive_slots']:
                return False
            # Check Conductor start time rule
            if position == 'Conductor' and rule.get('must_start_on_the_hour', False):
                if last_pos != 'Conductor' and time_slot_obj.minute != 0:
                    return False
    return True

def solve_schedule_recursive(time_idx, time_slots, availability, schedule, employee_states, rules):
    """The new backtracking solver that strictly follows the loaded rules."""
    if time_idx >= len(time_slots):
        return True, schedule # Successfully filled the entire schedule

    current_time_slot_str = time_slots[time_idx]
    current_time_slot_obj = parse_time_input(current_time_slot_str, datetime(1970,1,1).date())
    available_employees = sorted(list(availability.get(current_time_slot_str, [])))
    
    # Determine the positions that need to be filled
    positions_to_fill = WORK_POSITIONS[:len(available_employees)]

    # Iterate through all permutations of available employees for the positions
    for p in permutations(available_employees):
        assignments = {pos: emp for pos, emp in zip(positions_to_fill, p)}
        
        # Check if this entire set of assignments is valid before proceeding
        is_permutation_valid = all(
            is_assignment_valid(emp, pos, current_time_slot_obj, schedule, employee_states, rules)
            for pos, emp in assignments.items()
        )

        if is_permutation_valid:
            # If valid, update the states for the next recursive call
            new_states = employee_states.copy()
            for pos, emp in assignments.items():
                last_pos = employee_states.get(emp, {}).get('last_pos')
                time_in_pos = employee_states.get(emp, {}).get('time_in_pos', 0)
                new_states[emp] = {
                    'last_pos': pos,
                    'time_in_pos': time_in_pos + 1 if pos == last_pos else 1
                }
            
            # Add the valid assignments to the schedule
            schedule[current_time_slot_str] = assignments
            
            # Recurse to the next time slot
            is_solved, final_schedule = solve_schedule_recursive(
                time_idx + 1, time_slots, availability, schedule, new_states, rules
            )
            if is_solved:
                return True, final_schedule

    # If no valid permutation was found, backtrack
    schedule[current_time_slot_str] = {} # Clear assignments for this slot
    return False, None


def create_rule_based_schedule(store_open_time_obj, store_close_time_obj, employee_data_list):
    """Main function to generate the schedule using the rule-based engine."""
    rules = load_rules()
    df_long = preprocess_employee_data(employee_data_list)
    if df_long.empty: return "No employee data to process."

    time_slots_dt = sorted(df_long['Time'].unique())
    time_slots_str = [t.strftime('%I:%M %p').lstrip('0') for t in time_slots_dt]

    # Create a lookup for who is working, on break, or on ToffTL
    availability = {}
    breaks = {}
    tofftl = {}
    for time_dt, time_str in zip(time_slots_dt, time_slots_str):
        slot_data = df_long[df_long['Time'] == time_dt]
        availability[time_str] = set(slot_data[slot_data['IsWorking']]['EmployeeName'])
        breaks[time_str] = set(slot_data[slot_data['IsOnBreak']]['EmployeeName'])
        tofftl[time_str] = set(slot_data[slot_data['IsOnToffTL']]['EmployeeName'])

    # The schedule dictionary will hold the final state for each position
    schedule_assignments = {t: {} for t in time_slots_str}
    
    # Solve the schedule
    is_solved, final_work_assignments = solve_schedule_recursive(
        0, time_slots_str, availability, schedule_assignments, {}, rules
    )

    if not is_solved:
        return "ERROR: Could not find a valid schedule that satisfies all the rules in rules.yaml. Please check for rule conflicts or insufficient employee coverage."

    # Assemble the final DataFrame for display
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
