#ui/state.py
import streamlit as st

def init_state():
    defaults = {
        "job_id": None,
        "inputs_ready": False,
        "evaluation_running": False,
        "evaluation_done": False,
    }

    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
