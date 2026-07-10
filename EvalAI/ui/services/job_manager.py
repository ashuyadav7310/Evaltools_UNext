#ui/services/job_manager.py
import subprocess
import sys
import os

def start_job(job_id: str):

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))

    subprocess.Popen(
        [sys.executable, "-m", "src.main_for_job", job_id],
        cwd=project_root
    )
