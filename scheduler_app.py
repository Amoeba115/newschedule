# File: scheduler_app.py (Rule-Based Version)
import streamlit as st
import pandas as pd
from datetime import datetime
from io import StringIO
import yaml

# Import the new rule-based scheduling function
from scheduler_logic import create_rule_based_schedule, parse_time_input, load_rules

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
st.markdown("""
<style>
    div.stButton > button {
        background-color: #4CAF50; color: white; font-size: 16px; font-weight: bold;
        border-radius: 8px; border: 2px solid #4CAF50; width: 100%;
    }
    div.stButton > button:hover {
        background-color: #45a049; border-color: #45a049; color: white;
    }
</style>
""", unsafe_allow_html=True)

# --- Initialize Session State ---
if 'employee_data' not in st.session_state:
    st.session_state.employee_data = []

# --- Page Title ---
st.markdown('<h1 style="color: #4CAF50;">Rule-Based Employee Scheduler</h1>', unsafe_allow_html=True)
st.write("This tool generates a schedule based on a set of defined rules. Fill in employee details manually, or import data from a file using the sidebar.")

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

# --- Display Scheduling Rules ---
st.sidebar.markdown('<h3>Active Scheduling Rules</h3>', unsafe_allow_html=True)
try:
    with open("rules.yaml", 'r') as f:
        rules_content = f.read()
    st.sidebar.code(rules_content, language="yaml")
except FileNotFoundError:
    st.sidebar.error("rules.yaml not found! Using default rules.")

# Store Hours & Employee Inputs
st.sidebar.markdown('<h3>Store Hours</h3>', unsafe_allow_html=True)
store_open_time_str = st.sidebar.text_input("Store Open Time", "7:30 AM")
store_close_time_str = st.sidebar.text_input("Store Close Time", "10:00 PM")

st.sidebar.markdown('<h3>Employees</h3>', unsafe_allow_html=True)
num_employees = st.sidebar.number_input(
    "Number of Employees", min_value=1, 
    value=len(st.session_state.employee_data) if st.session_state.employee_data else 2, step=1
)

employee_data_list = []
for i in range(num_employees):
    defaults = st.session_state.employee_data[i] if i < len(st.session_state.employee_data) else {}
    st.sidebar.markdown(f"--- **Employee {i+1}** ---")
    emp_name = st.sidebar.text_input(f"Name (Employee {i+1})", value=defaults.get("Name", ""), key=f"name_{i}")
    shift_start_str = st.sidebar.text_input(f"Shift Start", value=defaults.get("Shift Start", "9:00 AM"), key=f"s_start_{i}")
    shift_end_str = st.sidebar.text_input(f"Shift End", value=defaults.get("Shift End", "5:00 PM"), key=f"s_end_{i}")
    break_start_str = st.sidebar.text_input(f"Break", value=defaults.get("Break", "1:00 PM"), key=f"break_{i}")
    has_tofftl = st.sidebar.checkbox(f"Training Off The Line?", value=(defaults.get("Has ToffTL", "No") == "Yes"), key=f"has_tofftl_{i}")
    tofftl_start_str, tofftl_end_str = None, None
    if has_tofftl:
        tofftl_start_str = st.sidebar.text_input(f"ToffTL Start", value=defaults.get("ToffTL Start", "11:00 AM"), key=f"tofftl_s_{i}")
        tofftl_end_str = st.sidebar.text_input(f"ToffTL End", value=defaults.get("ToffTL End", "12:00 PM"), key=f"tofftl_e_{i}")
    if emp_name:
        employee_data_list.append({"Name": emp_name, "Shift Start": shift_start_str, "Shift End": shift_end_str, "Break": break_start_str, "ToffTL Start": tofftl_start_str, "ToffTL End": tofftl_end_str})

st.sidebar.markdown("---")
# Action Buttons
if st.sidebar.button("Generate Schedule"):
    if not employee_data_list: st.error("Please add at least one employee.")
    else:
        ref_date = datetime(1970,1,1).date()
        store_open_dt = parse_time_input(store_open_time_str, ref_date)
        store_close_dt = parse_time_input(store_close_time_str, ref_date)
        if pd.isna(store_open_dt) or pd.isna(store_close_dt): st.error("Invalid store open/close time.")
        else:
            with st.spinner("Generating schedule based on the defined rules..."):
                schedule_output = create_rule_based_schedule(store_open_dt.time(), store_close_dt.time(), employee_data_list)
                
                if "ERROR:" in schedule_output:
                    st.error(schedule_output)
                else:
                    st.success("Schedule Generated!")
                    st.subheader("Generated Schedule")
                    
                    csv_data = schedule_output
                    st.dataframe(pd.read_csv(StringIO(csv_data)))
                    st.download_button("Download Schedule", csv_data, "schedule.csv", "text/csv")
