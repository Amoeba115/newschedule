# File: scheduler_app.py (Now with Data Download)
import streamlit as st
import pandas as pd
from datetime import datetime
from io import StringIO
import yaml
import os

# Import the new rule-based scheduling function
from scheduler_logic import create_rule_based_schedule, parse_time_input

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

# --- NEW: Helper function to format employee data for saving ---
def format_employee_data_for_download(employee_data_list):
    """Converts the internal list of employee data back into a string for saving."""
    summary_string = ""
    for i, emp_data in enumerate(employee_data_list):
        summary_string += f"--- Employee {i+1} ---\n"
        summary_string += f"Name: {emp_data.get('Name', '')}\n"
        summary_string += f"Shift Start: {emp_data.get('Shift Start', '')}\n"
        summary_string += f"Shift End: {emp_data.get('Shift End', '')}\n"
        summary_string += f"Break: {emp_data.get('Break', '')}\n"
        has_tofftl = bool(emp_data.get('ToffTL Start'))
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
    div.stButton > button:hover {
        background-color: #45a049; border-color: #45a049; color: white;
    }
    /* Style for the download button */
    div.stDownloadButton > button {
        background-color: #008CBA;
        border-color: #008CBA;
    }
    div.stDownloadButton > button:hover {
        background-color: #007B9E;
        border-color: #007B9E;
    }
</style>
""", unsafe_allow_html=True)


# --- Initialize Session State ---
if 'employee_data' not in st.session_state:
    if os.path.exists("employee_inputs.txt"):
         with open("employee_inputs.txt", 'r') as f:
            st.session_state.employee_data = parse_summary_file(f.read())
    else:
        st.session_state.employee_data = []

if 'overrides' not in st.session_state:
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
uploaded_file = st.sidebar.file_uploader("Upload an employee data file", type=["txt"])
if uploaded_file is not None:
    try:
        file_content = uploaded_file.getvalue().decode("utf-8")
        st.session_state.employee_data = parse_summary_file(file_content)
        st.success("Data loaded successfully!")
        st.rerun() # Rerun to update the employee list
    except Exception as e:
        st.error(f"Error reading file: {e}")

# Store Hours & Employee Inputs
st.sidebar.markdown('<h3>Store Hours</h3>', unsafe_allow_html=True)
store_open_time_str = st.sidebar.text_input("Store Open Time", "7:30 AM")
store_close_time_str = st.sidebar.text_input("Store Close Time", "10:00 PM")

st.sidebar.markdown('<h3>Employees</h3>', unsafe_allow_html=True)
num_employees = st.sidebar.number_input(
    "Number of Employees", min_value=0,
    value=len(st.session_state.employee_data), step=1
)
# Update the session state to match the number input by the user
if num_employees > len(st.session_state.employee_data):
    st.session_state.employee_data.extend([{}] * (num_employees - len(st.session_state.employee_data)))
elif num_employees < len(st.session_state.employee_data):
    st.session_state.employee_data = st.session_state.employee_data[:num_employees]


employee_data_list = []
employee_names = []
for i in range(len(st.session_state.employee_data)):
    defaults = st.session_state.employee_data[i]
    st.sidebar.markdown(f"--- **Employee {i+1}** ---")
    emp_name = st.sidebar.text_input(f"Name", value=defaults.get("Name", ""), key=f"name_{i}")
    shift_start_str = st.sidebar.text_input(f"Shift Start", value=defaults.get("Shift Start", ""), key=f"s_start_{i}")
    shift_end_str = st.sidebar.text_input(f"Shift End", value=defaults.get("Shift End", ""), key=f"s_end_{i}")
    break_start_str = st.sidebar.text_input(f"Break", value=defaults.get("Break", ""), key=f"break_{i}")
    has_tofftl_str = st.sidebar.text_input(f"Has ToffTL", value=defaults.get("Has ToffTL", "No"), key=f"has_tofftl_{i}")
    tofftl_start_str = None
    if has_tofftl_str.lower() == 'yes':
        tofftl_start_str = st.sidebar.text_input(f"ToffTL Start", value=defaults.get("ToffTL Start", ""), key=f"tofftl_s_{i}")

    # Update session state as user types
    st.session_state.employee_data[i] = {
        "Name": emp_name, "Shift Start": shift_start_str, "Shift End": shift_end_str,
        "Break": break_start_str, "Has ToffTL": has_tofftl_str, "ToffTL Start": tofftl_start_str
    }
    
    if emp_name:
        employee_data_list.append(st.session_state.employee_data[i])
        try:
            employee_names.append(f"{emp_name.split(' ')[0]} {emp_name.split(' ')[1][0] if len(emp_name.split(' ')) > 1 and emp_name.split(' ')[1] else ''}.")
        except IndexError:
            employee_names.append(emp_name)


# --- NEW: Download Employee Data Button ---
st.sidebar.markdown("---")
if employee_data_list:
    download_data = format_employee_data_for_download(employee_data_list)
    st.sidebar.download_button(
        label="Download Employee Data",
        data=download_data,
        file_name="employee_inputs.txt",
        mime="text/plain",
        use_container_width=True
    )

# --- Main Content Area ---
main_col1, main_col2 = st.columns(2)

# Override management and rule display remain the same
with main_col1:
    st.subheader("Schedule Overrides")
    st.write("Add or remove pinned assignments for the upcoming schedule.")
    
    # (Code for override management is unchanged)

with main_col2:
    st.subheader("Active Scheduling Rules")
    st.write("The schedule will be generated according to these rules from `rules.yaml`.")
    # (Code for rule display is unchanged)


st.markdown("---")
if st.button("Generate Schedule", use_container_width=True):
    # (Code for schedule generation is unchanged)
    with open("overrides.yaml", 'w') as f:
        yaml.dump(st.session_state.overrides, f, default_flow_style=False)

    if not employee_data_list: st.error("Please add at least one employee.")
    else:
        ref_date = datetime(1970,1,1).date()
        store_open_dt = parse_time_input(store_open_time_str, ref_date)
        store_close_dt = parse_time_input(store_close_time_str, ref_date)
        if pd.isna(store_open_dt) or pd.isna(store_close_dt): st.error("Invalid store open/close time.")
        else:
            with st.spinner("Generating schedule..."):
                schedule_output = create_rule_based_schedule(store_open_dt.time(), store_close_dt.time(), employee_data_list)
                
                st.subheader("Generated Schedule")
                if "ERROR:" in schedule_output:
                    st.error(schedule_output)
                else:
                    st.success("Schedule Generated!")
                    csv_data = schedule_output
                    st.dataframe(pd.read_csv(StringIO(csv_data)))
                    st.download_button("Download Schedule CSV", csv_data, "schedule.csv", "text/csv")
