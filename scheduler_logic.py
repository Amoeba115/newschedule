# File: scheduler_logic.py (Final Version with Training End Time)
import pandas as pd
import yaml
from io import StringIO
from datetime import datetime
from itertools import permutations

# --- Configuration & Helper Functions ---
FINAL_SCHEDULE_ROW_ORDER = [
    "Handout", "Line Buster 1", "Conductor", "Line Buster 2", "Expo",
    "Drink Maker 1", "Drink Maker 2", "Line Buster 3", "Break", "Training off the Line or Frosting?"
]
WORK_POSITIONS = [p for p in FINAL_SCHEDULE_ROW_ORDER if p not in ["Break", "Training off the Line or Frosting?"]]

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
    all_slots = []
    ref_date = datetime(1970, 1, 1).date()
    for emp_data in employee_data_list:
        name_parts = emp_data.get('Name', '').split(' ', 1)
        name = f"{name_parts[0]} {name_parts[1][0] if len(name_parts) > 1 and name_parts[1] else ''}.".strip()
        s_start, s_end = parse_time_input(emp_data.get('Shift Start'), ref_date), parse_time_input(emp_data.get('Shift End'), ref_date)
        b_start = parse_time_input(emp_data.get('Break'), ref_date)
        
        # UPDATED: Now uses both start and end times for training
        training_start = parse_time_input(emp_data.get('Training Start'), ref_date)
        training_end = parse_time_input(emp_data.get('Training End'), ref_date)

        b_end = b_start + pd.Timedelta(minutes=30) if pd.notna(b_start) else pd.NaT
        t_end = training_end if pd.notna(training_end) else (training_start + pd.Timedelta(minutes=60) if pd.notna(training_start) else pd.NaT)
        
        if pd.notna(s_start) and pd.notna(s_end):
            curr = s_start
            while curr < s_end:
                on_break = pd.notna(b_start) and b_start <= curr < b_end
                on_training = pd.notna(training_start) and training_start <= curr < t_end
                is_working = not (on_break or on_training)
                all_slots.append({
                    'Time': curr, 'EmployeeName': name, 'IsWorking': is_working,
                    'IsOnBreak': on_break, 'IsOnTraining': on_training
                })
                curr += pd.Timedelta(minutes=30)
    return pd.DataFrame(all_slots) if all_slots else pd.DataFrame()

# --- Core Logic (Unchanged) ---
def is_assignment_valid(employee, position, employee_states, rules):
    # ... (no changes in this function)
    state = employee_states.get(employee, {})
    last_pos = state.get('last_pos')
    time_in_pos = state.get('time_in_pos', 0)
    for rule in rules.get('position_rules', []):
        rule_positions = rule.get('position', [])
        rule_positions = rule_positions if isinstance(rule_positions, list) else [rule_positions]
        if position in rule_positions:
            if position == last_pos and time_in_pos >= rule.get('max_consecutive_slots', 99):
                return False
    return True

def calculate_assignment_score(assignments, employee_states, rules):
    # ... (no changes in this function)
    score = 0
    strategy = rules.get('prioritization_strategy', {})
    consistency_roles = strategy.get('focus_on_consistency_for', [])
    for pos, emp in assignments.items():
        state = employee_states.get(emp, {})
        if pos in consistency_roles:
            if state.get('last_pos') == pos: score += 10
        else:
            history = state.get('history', [])
            if pos not in history: score += 1
            else:
                if len(history) > 0 and history[-1] == pos: score -= 10
                elif len(history) > 1 and history[-2] == pos: score -= 5
    return score

def solve_schedule_recursive(time_idx, time_slots, availability, schedule, employee_states, rules):
    # ... (no changes in this function)
    if time_idx >= len(time_slots): return True, schedule
    current_time_slot_str = time_slots[time_idx]
    pre_assigned_positions = set(schedule[current_time_slot_str].keys())
    positions_to_fill = [p for p in WORK_POSITIONS if p not in pre_assigned_positions]
    available_employees = sorted(list(availability.get(current_time_slot_str, [])))
    positions_to_fill = positions_to_fill[:len(available_employees)]
    best_permutation, best_score = None, -float('inf')
    for p in permutations(available_employees):
        current_assignments = {pos: emp for pos, emp in zip(positions_to_fill, p)}
        if all(is_assignment_valid(emp, pos, employee_states, rules) for pos, emp in current_assignments.items()):
            score = calculate_assignment_score(current_assignments, employee_states, rules)
            if score > best_score:
                best_score, best_permutation = score, current_assignments
    if best_permutation is not None:
        new_states = employee_states.copy()
        full_slot_assignments = {**schedule[current_time_slot_str], **best_permutation}
        for pos, emp in full_slot_assignments.items():
            state = employee_states.get(emp, {})
            history = (state.get('history', []) + [pos])[-3:]
            new_states[emp] = {
                'last_pos': pos,
                'time_in_pos': state.get('time_in_pos', 0) + 1 if pos == state.get('last_pos') else 1,
                'history': history
            }
        schedule[current_time_slot_str].update(best_permutation)
        is_solved, final_schedule = solve_schedule_recursive(time_idx + 1, time_slots, availability, schedule, new_states, rules)
        if is_solved: return True, final_schedule
    return False, None

def create_rule_based_schedule(store_open_time_obj, store_close_time_obj, employee_data_list):
    rules = load_config("rules.yaml")
    overrides = load_config("overrides.yaml", default_value=[])
    df_long = preprocess_employee_data(employee_data_list)
    if df_long.empty: return "No employee data to process."
    time_slots_dt = sorted(df_long['Time'].unique())
    time_slots_str = [t.strftime('%I:%M %p').lstrip('0') for t in time_slots_dt]
    availability, breaks, training = {}, {}, {}
    for time_dt, time_str in zip(time_slots_dt, time_slots_str):
        slot_data = df_long[df_long['Time'] == time_dt]
        availability[time_str] = set(slot_data[slot_data['IsWorking']]['EmployeeName'])
        breaks[time_str] = set(slot_data[slot_data['IsOnBreak']]['EmployeeName'])
        training[time_str] = set(slot_data[slot_data['IsOnTraining']]['EmployeeName']) # Changed from ToffTL
    schedule_assignments = {t: {} for t in time_slots_str}
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
        return "ERROR: Could not find a valid schedule."
    rows = []
    for time_str in time_slots_str:
        row = {"Time": time_str}
        row.update(final_work_assignments.get(time_str, {}))
        row["Break"] = ", ".join(sorted(list(breaks.get(time_str, []))))
        row["Training off the Line or Frosting?"] = ", ".join(sorted(list(training.get(time_str, []))))
        rows.append(row)
    out_df = pd.DataFrame(rows, columns=["Time"] + FINAL_SCHEDULE_ROW_ORDER)
    final_df = out_df.set_index("Time").transpose().reset_index().rename(columns={'index':'Position'})
    return final_df.to_csv(index=False)
