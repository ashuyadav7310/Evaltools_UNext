# ui/sections/progress_view.py
'''
Checks if evaluation running/done
Polls for DONE file
Auto-refresh every 5 seconds
'''

import streamlit as st
import os
from streamlit_autorefresh import st_autorefresh

def progress_view_section():
    if not st.session_state.get("evaluation_running") and not st.session_state.get("evaluation_done"):
        return

    st.header("3. Evaluation Progress")

    job_id = st.session_state.get("job_id")
    if not job_id:
        return

    done_file = os.path.join("jobs", job_id, "outputs", "DONE")

    if st.session_state.evaluation_done:
        st.success("Evaluation completed successfully.")
        return

    if st.session_state.evaluation_running:

        if os.path.exists(done_file):
            st.session_state.evaluation_running = False
            st.session_state.evaluation_done = True
            st.rerun()
        else:
            st.info("Evaluation is running... Please wait.")

            # Auto refresh every 5 seconds
            st_autorefresh(interval=5000, key="progress_refresh")