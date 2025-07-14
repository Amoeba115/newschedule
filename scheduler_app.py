# File: scheduler_app.py (Corrected NameError)
import streamlit as st
import pandas as pd
from datetime import datetime
from io import StringIO
import yaml
import os

# Import the scheduling function AND the WORK_POSITIONS constant
from scheduler_logic import create_rule_based_schedule, parse_time_input, WORK_POSITIONS

# --- Helper Functions ---
def parse_summary_file(file_content):
    """Parses a text file to extract employee data."""
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
    """Converts the list of employee data back into a downloadable string."""
    summary_string = ""
    for i, emp_data in enumerate(employee_data_list):
        summary_string += f"--- Employee {i+1} ---\n"
        summary_string += f"Name: {emp_data.get('Name', '')}\n"
        summary_string += f"Shift Start: {emp_data.get('Shift Start', '')}\n"
        summary_string += f"Shift End: {emp_data.get('Shift End', '')}\n"
        summary_string += f"Break: {emp_data.get('Break', '')}\n"
        has_tofftl = emp_data.get('Has ToffTL', 'No').lower() == 'yes'
        summary_string += f"Has ToffTL: {'Yes' if has_tofftl else 'No'}\n"
        if has_tofftl:
            summary_string += f"ToffTL Start: {emp_data.get('ToffTL Start', '')}\n"
        summary_string += "\n"
    return summary_string.strip()

# --- Page Configuration and Styling ---
st.set_page_config(page_title="Employee Scheduler", layout="wide")
st.markdown("""
<style>
    div.stButton > button {
        background-color: #4CAF50; color: white; font-size: 16px; font-weight: bold;
        border-radius: 8px; border: 2px solid #4CAF50; width: 100%;
    }
    div.stButton > button:hover { background-color: #45a049; border-color: #45a049; }
    div.stDownloadButton > button { background-color: #008CBA; border-color: #008CBA; }
    div.stDownloadButton > button:hover { background-color: #007B9E; border-color: #007B9E; }
</style>
""", unsafe_allow_html=True)

# --- Initialize Session State ---
if 'employee_data' not in st.session_state:
    st.session_state.employee_data = []
if 'overrides' not in st.session_state:
    if os.path.exists("overrides.yaml"):
        with open("overrides.yaml", 'r') as f:
            st.session_state.overrides = yaml.safe_load(f) or []
    else:
        st.session_state.overrides = []

# --- Page Title ---
st.markdown('<h1 style="color: #4CAF50;">Rule-Based Employee Scheduler</h1>', unsafe_allow_html=True)

# --- Sidebar ---
st.sidebar.markdown('<h1 style="color: #4CAF50; font-size: 24px;">Configuration</h1>', unsafe_allow_html=True)

# File Uploader
st.sidebar.markdown('<h3>Import Data</h3>', unsafe_allow_html=True)
uploaded_file = st.sidebar.file_uploader("Upload an employee data file", type=["txt"])
if uploaded_file is not None:
    file_content = uploaded_file.getvalue().decode("utf-8")
    st.session_state.employee_data = parse_summary_file(file_content)
    uploaded_file = None
    st.success("Data loaded successfully!")

# Store Hours
st.sidebar.markdown('<h3>Store Hours</h3>', unsafe_allow_html=True)
store_open_time_str = st.sidebar.text_input("Store Open Time", "7:30 AM")
store_close_time_str = st.sidebar.text_input("Store Close Time", "10:00 PM")

# Employee Data Management
st.sidebar.markdown('<h3>Employees</h3>', unsafe_allow_html=True)
employee_ui_list = []
employee_names_for_override = []
for i, emp in enumerate(st.session_state.employee_data):
    st.sidebar.markdown(f"--- **Employee {i+1}** ---")
    name = st.sidebar.text_input("Name", value=emp.get("Name", ""), key=f"name_{i}")
    shift_start = st.sidebar.text_input("Shift Start", value=emp.get("Shift Start", ""), key=f"s_start_{i}")
    shift_end = st.sidebar.text_input("Shift End", value=emp.get("Shift End", ""), key=f"s_end_{i}")
    break_time = st.sidebar.text_input("Break", value=emp.get("Break", ""), key=f"break_{i}")
    has_tofftl = st.sidebar.selectbox("Has ToffTL?", ["No", "Yes"], index=0 if emp.get("Has ToffTL", "No").lower() == 'no' else 1, key=f"has_tofftl_{i}")
    tofftl_start = ""
    if has_tofftl == "Yes":
        tofftl_start = st.sidebar.text_input("ToffTL Start", value=emp.get("ToffTL Start", ""), key=f"tofftl_s_{i}")
    employee_ui_list.append({
        "Name": name, "Shift Start": shift_start, "Shift End": shift_end,
        "Break": break_time, "Has ToffTL": has_tofftl, "ToffTL Start": tofftl_start
    })
    if name:
        try:
            employee_names_for_override.append(f"{name.split(' ')[0]} {name.split(' ')[1][0] if len(name.split(' ')) > 1 and name.split(' ')[1] else ''}.")
        except IndexError:
            employee_names_for_override.append(name)
st.session_state.employee_data = employee_ui_list

col1, col2 = st.sidebar.columns(2)
if col1.button("Add Employee", use_container_width=True):
    st.session_state.employee_data.append({})
    st.rerun()
if col2.button("Remove Last", use_container_width=True):
    if st.session_state.employee_data:
        st.session_state.employee_data.pop()
        st.rerun()

st.sidebar.markdown("---")
if st.session_state.employee_data:
    download_data = format_employee_data_for_download(st.session_state.employee_data)
    if download_data:
        st.sidebar.download_button(
            label="Download Employee Data", data=download_data, file_name="employee_inputs.txt",
            mime="text/plain", use_container_width=True
        )

# --- Main Content Area ---
main_col1, main_col2 = st.columns(2)

with main_col1:
    st.subheader("Schedule Overrides")
    for i, override in enumerate(st.session_state.overrides):
        emp = override.get('employee', 'N/A')
        pos = override.get('position', 'N/A')
        st.markdown(f"`{emp}` in `{pos}` from `{override.get('start_time')}` to `{override.get('end_time')}`")
        if st.button(f"Remove##{i}", key=f"del_ovr_{i}"):
            st.session_state.overrides.pop(i)
            st.rerun()
    with st.expander("Add New Override"):
        with st.form("new_override_form"):
            new_emp = st.selectbox("Employee", options=sorted(employee_names_for_override), key="new_emp")
            new_pos = st.selectbox("Position", options=WORK_POSITIONS, key="new_pos")
            new_start = st.text_input("Start Time (e.g., 3:30 PM)", key="new_start")
            new_end = st.text_input("End Time (e.g., 5:00 PM)", key="new_end")
            if st.form_submit_button("Add Override"):
                st.session_state.overrides.append({"employee": new_emp, "position": new_pos, "start_time": new_start, "end_time": new_end})
                st.rerun()

with main_col2:
    st.subheader("Active Scheduling Rules")
    try:
        with open("rules.yaml", 'r') as f:
            st.code(f.read(), language="yaml")
    except FileNotFoundError:
        st.error("rules.yaml not found!")

st.markdown("---")
if st.button("Generate Schedule", use_container_width=True):
    with open("overrides.yaml", 'w') as f:
        yaml.dump(st.session_state.overrides, f, default_flow_style=False)
    if not st.session_state.employee_data: st.error("Please add at least one employee.")
    else:
        ref_date = datetime(1970,1,1).date()
        store_open_dt = parse_time_input(store_open_time_str, ref_date)
        store_close_dt = parse_time_input(store_close_time_str, ref_date)
        if pd.isna(store_open_dt) or pd.isna(store_close_dt): st.error("Invalid store open/close time.")
        else:
            with st.spinner("Generating schedule..."):
                schedule_output = create_rule_based_schedule(store_open_dt.time(), store_close_dt.time(), st.session_state.employee_data)
                st.subheader("Generated Schedule")
                if "ERROR:" in schedule_output:
                    st.error(schedule_output)
                else:
                    st.success("Schedule Generated!")
                    csv_data = schedule_output
                    st.dataframe(pd.read_csv(StringIO(csv_data)))
                    st.download_button("Download Schedule CSV", csv_data, "schedule.csv", "text/csv", use_container_width=True)
