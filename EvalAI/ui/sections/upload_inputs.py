# ui/sections/upload_inputs.py
import streamlit as st
import os
from pathlib import Path
from uuid import uuid4
import zipfile
import pandas as pd
import json
from ui.services.rubric_excel_parser import excel_to_rubric_json


def _extract_zip_safely(archive: zipfile.ZipFile, destination: str) -> None:
    destination_path = Path(destination).resolve()
    for member in archive.infolist():
        member_path = (destination_path / member.filename).resolve()
        try:
            member_path.relative_to(destination_path)
        except ValueError as exc:
            raise ValueError(f"Unsafe path in submissions ZIP: {member.filename}") from exc
    archive.extractall(destination_path)

'''
Handles all file uploads:
- Case study (PDF/DOCX)
- Rubric Excel (XLSX)
- Student submissions (ZIP)
Also handles optional keypoint uploads for rubrics that require them.
On "Confirm Uploads":
- Validates inputs
- Saves files to structured directories
- Updates session state to indicate readiness for evaluation
  '''

def upload_inputs_section():
    st.header("1. Upload Inputs")

    if st.session_state.inputs_ready:
        st.success("Inputs uploaded successfully")
        return

    case_study = st.file_uploader(
        "Case Study (PDF / DOCX)",
        type=["pdf", "docx"]
    )

    rubric_excel = st.file_uploader(
        "Rubric Excel",
        type=["xlsx"]
    )

    submissions_zip = st.file_uploader(
        "Student Submissions (ZIP)",
        type=["zip"]
    )

    if not (case_study and rubric_excel and submissions_zip):
        return

    # ---- Parse rubric Excel early (needed for UI) ----
    df = pd.read_excel(rubric_excel)
    rubric_json = excel_to_rubric_json(df)
    rubrics = rubric_json["rubrics"]

    # ---- Keypoint configuration UI ----
    st.subheader("Keypoint Configuration")

    keypoint_uploads = {}

    for r in rubrics:
        if not r.get("requires_keypoints"):
            continue

        rid = r["id"]
        rname = r["name"]

        mode = st.radio(
            f"Keypoints for {rname} ({rid})",
            options=["Auto-generate", "Upload manually"],
            key=f"kp_mode_{rid}",
            horizontal=True
        )

        if mode == "Upload manually":
            kp_file = st.file_uploader(
                f"Upload keypoints DOCX for {rname}",
                type=["docx"],
                key=f"kp_file_{rid}"
            )
            if kp_file:
                keypoint_uploads[rid] = kp_file

    # ---- Confirm uploads ----
    if st.button("Confirm Uploads"):
        job_id = f"job_{uuid4().hex[:8]}"
        base_dir = os.path.join("jobs", job_id)
        input_dir = os.path.join(base_dir, "inputs")

        os.makedirs(input_dir, exist_ok=True)

        # ---- Save case study ----
        case_ext = os.path.splitext(case_study.name)[1]
        case_path = os.path.join(input_dir, f"case_study{case_ext}")
        with open(case_path, "wb") as f:
            f.write(case_study.read())

        # ---- Save rubric Excel ----
        rubric_excel_path = os.path.join(input_dir, "rubric.xlsx")
        with open(rubric_excel_path, "wb") as f:
            f.write(rubric_excel.read())

        # ---- Save keypoints (if any) ----
        kp_dir = os.path.join(
            "input_data",
            "Assignments",
            job_id,
            "keypoints"
        )
        os.makedirs(kp_dir, exist_ok=True)

        for r in rubrics:
            rid = r["id"]
            if rid in keypoint_uploads:
                kp_filename = f"{rid}.docx"
                kp_path = os.path.join(kp_dir, kp_filename)

                with open(kp_path, "wb") as f:
                    f.write(keypoint_uploads[rid].read())

                r["keypoints_file"] = kp_filename
            else:
                r.pop("keypoints_file", None)

        # ---- Write final rubrics.json ----
        rubric_json_path = os.path.join(input_dir, "rubrics.json")
        with open(rubric_json_path, "w", encoding="utf-8") as f:
            json.dump({"rubrics": rubrics}, f, indent=2)

        # ---- Save & extract submissions ----
        zip_path = os.path.join(input_dir, "submissions.zip")
        with open(zip_path, "wb") as f:
            f.write(submissions_zip.read())

        students_dir = os.path.join("input_data", "students", job_id)
        os.makedirs(students_dir, exist_ok=True)

        with zipfile.ZipFile(zip_path, "r") as z:
            _extract_zip_safely(z, students_dir)

        # ---- Update state ----
        st.session_state.job_id = job_id
        st.session_state.inputs_ready = True

        st.success("All inputs uploaded and processed successfully")
