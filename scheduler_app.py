# File: scheduler_app.py (Now with Override Management)
import streamlit as st
import pandas as pd
from datetime import datetime
from io import StringIO
import yaml
import os

# Import the new rule-based scheduling function
from scheduler_logic import create_rule_based_schedule, parse_time_input

# --- Helper Function for Importing Data ---
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

# --- Page Configuration and Styling ---
st.set_page_config(page_title="Employee Scheduler", layout="wide")
# (Styling remains the same)

# --- Initialize Session State ---
if 'employee_data' not in st.session_state:
    st.session_state.employee_data = []
if 'overrides' not in st.session_state:
    # Load overrides from file or start with an empty list
    if os.path.exists("overrides.yaml"):
        with open("overrides.yaml", 'r') as f:
            st.session_state.overrides = yaml.safe_load(f) or []
    else:
        st.session_state.overrides = []


# --- Page Title ---
st.markdown('<h1 style="color: #4CAF50;">Rule-Based Employee Scheduler</h1>', unsafe_allow_html=True)
st.write("This tool generates a schedule based on a set of defined rules. You can also add specific 'Overrides' to pin an employee to a position.")

# --- Sidebar ---
st.sidebar.markdown('<h1 style="color: #4CAF50; font-size: 24px;">Configuration</h1>', unsafe_allow_html=True)

# File Uploader
st.sidebar.markdown('<h3>Import Data</h3>', unsafe_allow_html=True)
uploaded_file = st.sidebar.file_uploader("Upload a schedule summary file", type=["txt"])
if uploaded_file is not None:
    try:
        file_content = uploaded_file.getvalue().decode("utf-8")
        st.session_state.employee_data = parse_summary_file(file_content)
        st.success("Data loaded successfully!")
    except Exception as e:
        st.error(f"Error reading file: {e}")

# Store Hours & Employee Inputs
st.sidebar.markdown('<h3>Store Hours</h3>', unsafe_allow_html=True)
store_open_time_str = st.sidebar.text_input("Store Open Time", "7:30 AM")
store_close_time_str = st.sidebar.text_input("Store Close Time", "10:00 PM")

st.sidebar.markdown('<h3>Employees</h3>', unsafe_allow_html=True)
num_employees = st.sidebar.number_input(
    "Number of Employees", min_value=1, 
    value=len(st.session_state.employee_data) if st.session_state.employee_data else 1, step=1
)

employee_data_list = []
employee_names = []
for i in range(num_employees):
    defaults = st.session_state.employee_data[i] if i < len(st.session_state.employee_data) else {}
    st.sidebar.markdown(f"--- **Employee {i+1}** ---")
    emp_name = st.sidebar.text_input(f"Name (Employee {i+1})", value=defaults.get("Name", ""), key=f"name_{i}")
    if emp_name:
        employee_names.append(f"{emp_name.split(' ')[0]} {emp_name.split(' ')[1][0] if len(emp_name.split(' ')) > 1 else ''}.")
        shift_start_str = st.sidebar.text_input(f"Shift Start", value=defaults.get("Shift Start", "9:00 AM"), key=f"s_start_{i}")
        shift_end_str = st.sidebar.text_input(f"Shift End", value=defaults.get("Shift End", "5:00 PM"), key=f"s_end_{i}")
        break_start_str = st.sidebar.text_input(f"Break", value=defaults.get("Break", "1:00 PM"), key=f"break_{i}")
        has_tofftl = st.sidebar.checkbox(f"Training Off The Line?", value=(defaults.get("Has ToffTL", "No") == "Yes"), key=f"has_tofftl_{i}")
        tofftl_start_str = None
        if has_tofftl:
            tofftl_start_str = st.sidebar.text_input(f"ToffTL Start", value=defaults.get("ToffTL Start", "11:00 AM"), key=f"tofftl_s_{i}")
        
        employee_data_list.append({"Name": emp_name, "Shift Start": shift_start_str, "Shift End": shift_end_str, "Break": break_start_str, "ToffTL Start": tofftl_start_str})

# --- Main Content Area ---
main_col1, main_col2 = st.columns(2)

# --- Schedule Override Management in Main Column ---
with main_col1:
    st.subheader("Schedule Overrides")
    st.write("Add or remove pinned assignments for the upcoming schedule.")
    
    for i, override in enumerate(st.session_state.overrides):
        emp = override.get('employee', 'N/A')
        pos = override.get('position', 'N/A')
        start = override.get('start_time', 'N/A')
        end = override.get('end_time', 'N/A')
        st.markdown(f"`{emp}` in `{pos}` from `{start}` to `{end}`")
        if st.button(f"Remove##{i}", key=f"del_{i}"):
            st.session_state.overrides.pop(i)
            st.rerun()

    with st.expander("Add New Override"):
        with st.form("new_override_form"):
            new_emp = st.selectbox("Employee", options=sorted(employee_names), key="new_emp")
            new_pos = st.selectbox("Position", options=["Conductor", "Handout", "Line Buster 1", "Expo"], key="new_pos")
            new_start = st.text_input("Start Time (e.g., 3:30 PM)", key="new_start")
            new_end = st.text_input("End Time (e.g., 5:00 PM)", key="new_end")
            submitted = st.form_submit_button("Add Override")
            if submitted:
                st.session_state.overrides.append({
                    "employee": new_emp, "position": new_pos, "start_time": new_start, "end_time": new_end
                })
                st.rerun()

# --- Active Rules Display in Main Column ---
with main_col2:
    st.subheader("Active Scheduling Rules")
    st.write("The schedule will be generated according to these rules from `rules.yaml`.")
    try:
        with open("rules.yaml", 'r') as f:
            rules_content = f.read()
        st.code(rules_content, language="yaml")
    except FileNotFoundError:
        st.error("rules.yaml not found! Using default rules.")


st.markdown("---")
if st.button("Generate Schedule", use_container_width=True):
    # First, save the current overrides to the yaml file so the logic can read it
    with open("overrides.yaml", 'w') as f:
        yaml.dump(st.session_state.overrides, f, default_flow_style=False)

    if not employee_data_list: st.error("Please add at least one employee.")
    else:
        ref_date = datetime(1970,1,1).date()
        store_open_dt = parse_time_input(store_open_time_str, ref_date)
        store_close_dt = parse_time_input(store_close_time_str, ref_date)
        if pd.isna(store_open_dt) or pd.isna(store_close_dt): st.error("Invalid store open/close time.")
        else:
            with st.spinner("Generating schedule with overrides..."):
                schedule_output = create_rule_based_schedule(store_open_dt.time(), store_close_dt.time(), employee_data_list)
                
                st.subheader("Generated Schedule")
                if "ERROR:" in schedule_output:
                    st.error(schedule_output)
                else:
                    st.success("Schedule Generated!")
                    csv_data = schedule_output
                    st.dataframe(pd.read_csv(StringIO(csv_data)))
                    st.download_button("Download Schedule", csv_data, "schedule.csv", "text/csv")
