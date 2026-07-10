# src/main_for_job.py

import sys
import os
from src.pipeline import EvaluationPipeline
from src.output_generator import build_master_report

def main():
    if len(sys.argv) < 2:
        raise RuntimeError("Job ID required")

    job_id = sys.argv[1]
    job_dir = os.path.join("jobs", job_id)
    inputs_dir = os.path.join(job_dir, "inputs")
    outputs_dir = os.path.join(job_dir, "outputs")

    os.makedirs(outputs_dir, exist_ok=True)

    # resolve assignment
    assignment_file = next(
        os.path.join(inputs_dir, f)
        for f in os.listdir(inputs_dir)
        if f.startswith("case_study")
    )

    rubric_file = os.path.join(inputs_dir, "rubrics.json")

    pipeline = EvaluationPipeline(
        assignment_file=assignment_file,
        rubric_file=rubric_file,
        assignment_id=job_id
    )

    results, plagiarism = pipeline.run()

    report_path = build_master_report(
        all_students_data=results,
        plagiarism_data=plagiarism
    )

    final_report = os.path.join(outputs_dir, os.path.basename(report_path))
    os.replace(report_path, final_report)

    with open(os.path.join(outputs_dir, "DONE"), "w") as f:
        f.write("completed")

if __name__ == "__main__":
    main()
