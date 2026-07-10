# ui/app.py
import sys
import os

# Add project root to PYTHONPATH
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import streamlit as st

from ui.state import init_state
from ui.sections.upload_inputs import upload_inputs_section
from ui.sections.run_evaluation import run_evaluation_section
from ui.sections.progress_view import progress_view_section
from ui.sections.results_view import results_view_section

# MUST be first Streamlit command
st.set_page_config(
    page_title="Case Study Evaluator Tool",
    layout="wide"
)

init_state()

st.title("EvalAI Tool")

st.markdown(
    """
    Upload Case Study Assignments, Rubrics, and Student submissions to run
    automated rubric-driven evaluation.
    """
)

upload_inputs_section()
run_evaluation_section()
progress_view_section()
results_view_section()
