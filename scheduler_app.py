# File: scheduler_app.py (Final Version with Session-Based Rules)
import streamlit as st
import pandas as pd
from datetime import datetime
from io import StringIO
import yaml
import os

from scheduler_logic import create_rule_based_schedule, parse_time_input, WORK_POSITIONS

# --- Helper Functions ---
def parse_summary_file(file_content):
    employees, current_employee = [], {}
    for line in file_content.splitlines():
        line = line.strip()
        if not line: continue
        if line.startswith("--- Employee"):
            if current_employee: employees.append(current_employee)
            current_employee = {}
        elif ":" in line:
            key, value = line.split(":", 1)
            current_employee[key.strip()] = value.strip()
    if current_employee: employees.append(current_employee)
    return employees

def format_employee_data_for_download(employee_data_list):
    summary_string = ""
    for i, emp_data in enumerate(employee_data_list):
        summary_string += f"--- Employee {i+1} ---\n"
        summary_string += f"Name: {emp_data.get('Name', '')}\n"
        summary_string += f"Shift Start: {emp_data.get('Shift Start', '')}\n"
        summary_string += f"Shift End: {emp_data.get('Shift End', '')}\n"
        summary_string += f"Break: {emp_data.get('Break', '')}\n"
        has_training = emp_data.get('Training off the Line or Frosting?', 'No').lower() == 'yes'
        summary_string += f"Training off the Line or Frosting?: {'Yes' if has_training else 'No'}\n"
        if has_training:
            summary_string += f"Training Start: {emp_data.get('Training Start', '')}\n"
            summary_string += f"Training End: {emp_data.get('Training End', '')}\n"
        summary_string += "\n"
    return summary_string.strip()

def load_default_rules():
    """Loads rules from the YAML file to initialize the session state."""
    try:
        with open("rules.yaml", 'r') as f:
            return f.read()
    except FileNotFoundError:
        return "# rules.yaml not found."

# --- Page Configuration & State Initialization ---
st.set_page_config(page_title="Employee Scheduler", layout="wide")
if 'employee_data' not in st.session_state:
    st.session_state.employee_data = []
if 'overrides' not in st.session_state:
    if os.path.exists("overrides.yaml"):
        with open("overrides.yaml", 'r') as f:
            st.session_state.overrides = yaml.safe_load(f) or []
    else:
        st.session_state.overrides = []
# NEW: Initialize rules in session state
if 'rules_text' not in st.session_state:
    st.session_state.rules_text = load_default_rules()

# --- UI Rendering ---
st.markdown('<h1 style="color: #4CAF50;">Rule-Based Employee Scheduler</h1>', unsafe_allow_html=True)
st.sidebar.markdown('<h1 style="color: #4CAF50; font-size: 24px;">Configuration</h1>', unsafe_allow_html=True)
# ... (Instructions and other sidebar elements are unchanged)

# Main Content Area
main_col1, main_col2 = st.columns(2)
with main_col1:
    st.subheader("Schedule Overrides")
    # ... (Override management UI is unchanged)

with main_col2:
    st.subheader("Active Scheduling Rules")
    st.write("Changes made here apply only to your current session.")
    # The text area now reads from and writes to the session state
    edited_rules = st.text_area(
        "Edit Rules for this session",
        value=st.session_state.rules_text,
        height=300
    )
    st.session_state.rules_text = edited_rules # Update state as user types

st.markdown("---")
if st.button("Generate Schedule", use_container_width=True):
    # (Override saving logic is unchanged)
    with open("overrides.yaml", 'w') as f:
        yaml.dump(st.session_state.overrides, f, default_flow_style=False)
        
    # NEW: The app now parses the rules from the session state text box
    # and passes them to the scheduling function. It no longer saves to file.
    try:
        session_rules = yaml.safe_load(st.session_state.rules_text)
    except yaml.YAMLError as e:
        st.error(f"Cannot generate schedule due to a syntax error in your rules: {e}")
        st.stop()

    if not st.session_state.employee_data: st.error("Please add at least one employee.")
    else:
        ref_date = datetime(1970,1,1).date()
        store_open_dt, store_close_dt = parse_time_input(store_open_time_str, ref_date), parse_time_input(store_close_time_str, ref_date)
        if pd.isna(store_open_dt) or pd.isna(store_close_dt): st.error("Invalid store open/close time.")
        else:
            with st.spinner("Generating schedule..."):
                # Pass the session-specific rules to the function
                schedule_output = create_rule_based_schedule(
                    store_open_dt.time(), store_close_dt.time(),
                    st.session_state.employee_data, session_rules
                )
                st.subheader("Generated Schedule")
                if "ERROR:" in schedule_output: st.error(schedule_output)
                else:
                    st.success("Schedule Generated!")
                    csv_data = schedule_output
                    st.dataframe(pd.read_csv(StringIO(csv_data)))
                    st.download_button("Download Schedule CSV", csv_data, "schedule.csv", "text/csv", use_container_width=True)
