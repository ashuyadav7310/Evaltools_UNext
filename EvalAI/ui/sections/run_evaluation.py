#ui/sections/run_evaluation.py
import streamlit as st
from ui.services.job_manager import start_job
'''
Guards for input readiness
Prevents duplicate runs
Calls start_job(job_id)
'''

def run_evaluation_section():
    st.header("2. Run Evaluation")

    if not st.session_state.inputs_ready:
        st.info("Upload inputs first")
        return

    if st.session_state.evaluation_running:
        st.warning("Evaluation in progress")
        return

    if st.button("Run Evaluation"):
        st.session_state.evaluation_running = True
        start_job(st.session_state.job_id)
