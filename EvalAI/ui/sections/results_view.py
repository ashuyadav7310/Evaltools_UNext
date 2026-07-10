#ui/sections/results_view.py
import streamlit as st
import os

'''
Looks inside outputs folder
Finds first .xlsx
Displays download button
'''

def results_view_section():
    if not st.session_state.evaluation_done:
        return

    st.header("4. Results")

    job_id = st.session_state.job_id
    output_dir = f"jobs/{job_id}/outputs"

    report_file = next(
        (f for f in os.listdir(output_dir) if f.endswith(".xlsx")),
        None
    )

    if report_file:
        with open(os.path.join(output_dir, report_file), "rb") as f:
            st.download_button(
                "Download Final Report",
                f,
                file_name=report_file
            )
    else:
        st.warning("No report file found.")
