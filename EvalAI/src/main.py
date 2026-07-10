# src/main.py
import os

from src.pipeline import EvaluationPipeline
from src.output_generator import build_master_report
from src.logging_config import get_logger, setup_logging

ASSIGNMENT_DIR = "./input_data/Assignments"
STUDENTS_DIR = "./input_data/students"
RUBRICS_DIR = "./config/rubrics"

log = get_logger("main")


# Detect assignment file
def get_assignment_file():
    files = [f for f in os.listdir(ASSIGNMENT_DIR)
             if f.lower().endswith((".docx", ".pdf"))]

    if not files:
        raise FileNotFoundError("No assignment found in /Assignments")

    return f"{ASSIGNMENT_DIR}/{files[0]}"


# Detect rubric JSON
def get_rubric_file():
    files = [f for f in os.listdir(RUBRICS_DIR)
             if f.lower().endswith(".json")]

    if not files:
        raise FileNotFoundError("No rubric JSON found in /config/rubrics")

    return f"{RUBRICS_DIR}/{files[0]}"


# Detect student folders & files
def get_student_submissions_folder():
    """
    Returns: assignment_id, full_path_to_that_student_folder
    E.g., ("ASSIGNMENT_01", "./input_data/students/ASSIGNMENT_01")
    """

    found = [
        f for f in os.listdir(STUDENTS_DIR)
        if os.path.isdir(f"{STUDENTS_DIR}/{f}")
    ]

    if not found:
        raise FileNotFoundError("No assignment folder found under /students")

    assignment_id = found[0]  # choose first
    return assignment_id, f"{STUDENTS_DIR}/{assignment_id}"


# MAIN RUN
def run():
    setup_logging()
    log.info("Starting complete evaluation process")

    # Detect assignment + rubric
    assignment_file = get_assignment_file()
    rubric_file = get_rubric_file()
    assignment_id, _ = get_student_submissions_folder()


    print("\n===== AUTO CASE STUDY EVALUATION SYSTEM =====")
    print(f"Assignment      : {assignment_file}")
    print(f"Rubrics         : {rubric_file}")
    print(f"Students Folder : {assignment_id}")
    print("=============================================\n")

    # Initialise pipeline (INDEPENDENT FROM STUDENT LOOP)
    pipeline = EvaluationPipeline(
        assignment_file=assignment_file,
        rubric_file=rubric_file,
        assignment_id=assignment_id,
    )

    # Run complete evaluation (students, scoring, plagiarism)
    try:
        results_per_student, plagiarism_report = pipeline.run()

    except Exception as e:
        log.error("Fatal error in pipeline.run(): %s", e)
        print("\n PROCESS FAILED →", e)
        return

    # Build final Excel report
    if not results_per_student:
        print("\n No results generated. Process failed.")
        return

    report_path = build_master_report(results_per_student, plagiarism_report)
    print(f"\nMaster Excel report generated → {report_path}")
    log.info("Master report generated → %s", report_path)


    # Summary
    student_names = [r["student_name"] for r in results_per_student]

    print("\n============== SUMMARY ==============")
    print(f"Total Students : {len(student_names)}")
    print(f"Students       : {student_names if student_names else 'None'}")
    print("======================================\n")

    print("===== PROCESS COMPLETE =====\n")


if __name__ == "__main__":
    run()
