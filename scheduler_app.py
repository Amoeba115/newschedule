# File: scheduler_app.py (Final Version with All Text Changes)
import streamlit as st
import pandas as pd
from datetime import datetime
from io import StringIO
import yaml
import os

from scheduler_logic import create_rule_based_schedule, parse_time_input, UI_WORK_POSITIONS

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
if 'rules_text' not in st.session_state:
    try:
        with open("rules.yaml", 'r') as f:
            st.session_state.rules_text = f.read()
    except FileNotFoundError:
        st.session_state.rules_text = "# rules.yaml not found."

# --- UI Rendering ---
st.markdown('<h1 style="color: #4CAF50;">Rule-Based Employee Scheduler</h1>', unsafe_allow_html=True)
st.sidebar.markdown('<h1 style="color: #4CAF50; font-size: 24px;">Configuration</h1>', unsafe_allow_html=True)

st.sidebar.info("""
Welcome to the scheduler tool! Enter your employees' work times below.

To ensure you never have to enter it by hand more than once, there's a button at the bottom that lets you download the info you've entered in a file that the site knows how to read.

Also, there's a bug I haven't figured out how to fix yet, so if you upload an employee data file, it might look like the site is bugging out and the data isn't loading in. Just click the little x that appears next to the file name and it'll stop the bugging and load the data. Ik it's weird, I haven't figured it out yet lol.

If anything doesn't make sense or the site doesn't appear to be working correctly, please text me at 385-212-1506.
""")
st.sidebar.markdown("---")

# File Uploader
st.sidebar.markdown('<h3>Import Data</h3>', unsafe_allow_html=True)
uploaded_file = st.sidebar.file_uploader("Upload an employee data file", type=["txt"])
if uploaded_file is not None:
    file_content = uploaded_file.getvalue().decode("utf-8")
    st.session_state.employee_data = parse_summary_file(file_content)
    st.rerun()

# Store Hours & Settings
st.sidebar.markdown('<h3>Store Settings</h3>', unsafe_allow_html=True)
store_open_time_str = st.sidebar.text_input("Store Open Time", "7:30 AM")
store_close_time_str = st.sidebar.text_input("Store Close Time", "10:00 PM")
has_lobby = st.sidebar.checkbox("Check this box if your store has a lobby (toggles the Greeter position)", value=True)

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
    has_training = st.sidebar.selectbox("Training off the Line or Frosting?", ["No", "Yes"],
                                        index=1 if emp.get("Training off the Line or Frosting?", "No").lower() == 'yes' else 0,
                                        key=f"has_training_{i}")
    training_start, training_end = "", ""
    if has_training == "Yes":
        training_start = st.sidebar.text_input("Training Start", value=emp.get("Training Start", ""), key=f"training_s_{i}")
        training_end = st.sidebar.text_input("Training End", value=emp.get("Training End", ""), key=f"training_e_{i}")
    current_employee_data = {
        "Name": name, "Shift Start": shift_start, "Shift End": shift_end,
        "Break": break_time, "Training off the Line or Frosting?": has_training,
        "Training Start": training_start, "Training End": training_end
    }
    employee_ui_list.append(current_employee_data)
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
    if download_data.strip():
        st.sidebar.download_button(
            label="Download Employee Data", data=download_data, file_name="employee_inputs.txt",
            mime="text/plain", use_container_width=True
        )

# Main Content Area
main_col1, main_col2 = st.columns(2)
with main_col1:
    st.subheader("Schedule Overrides")
    st.write("This is for if you need a certain employee on a specific position for a given period of time. For example, if someone has Shift Lead Sidekick so you need them on Conductor from 3:30 pm to 5:00 pm")
    for i, override in enumerate(st.session_state.overrides):
        emp, pos = override.get('employee', 'N/A'), override.get('position', 'N/A')
        st.markdown(f"`{emp}` in `{pos}` from `{override.get('start_time')}` to `{override.get('end_time')}`")
        if st.button(f"Remove##{i}", key=f"del_ovr_{i}"):
            st.session_state.overrides.pop(i)
            st.rerun()
    with st.expander("Add New Override"):
        with st.form("new_override_form"):
            new_emp = st.selectbox("Employee", options=sorted(employee_names_for_override), key="new_emp")
            new_pos = st.selectbox("Position", options=UI_WORK_POSITIONS, key="new_pos")
            new_start = st.text_input("Start Time", key="new_start")
            new_end = st.text_input("End Time", key="new_end")
            if st.form_submit_button("Add Override"):
                st.session_state.overrides.append({"employee": new_emp, "position": new_pos, "start_time": new_start, "end_time": new_end})
                st.rerun()
with main_col2:
    st.subheader("Active Scheduling Rules")
    st.markdown("""
    Edit the rules for this session here. I promise it's not as complex as it might look at first lol.

    I've input presets, which you'll see. Currently, it allows for two consecutive Line Buster slots before 12:30 PM or after 7:30 PM when it's presumably cooler. You can edit that however you want. I'll probably change the presets in the winter to not have people outside too much in the colder mornings and evenings.
    
    You get the point, I'll stop rambling lol.
    """)
    edited_rules = st.text_area(
        label="Edit Rules for this session:",
        value=st.session_state.rules_text,
        height=300
    )
    st.session_state.rules_text = edited_rules

st.markdown("---")
if st.button("Generate Schedule", use_container_width=True):
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
                schedule_output = create_rule_based_schedule(
                    store_open_dt.time(), store_close_dt.time(),
                    st.session_state.employee_data, session_rules,
                    has_lobby=has_lobby,
                    overrides=st.session_state.overrides
                )
                st.subheader("Generated Schedule")
                if "ERROR:" in schedule_output: st.error(schedule_output)
                else:
                    st.success("Schedule Generated!")
                    csv_data = schedule_output
                    st.dataframe(pd.read_csv(StringIO(csv_data)))
                    st.download_button("Download Schedule CSV", csv_data, "schedule.csv", "text/csv", use_container_width=True)
