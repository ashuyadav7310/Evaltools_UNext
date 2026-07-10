# ui/services/rubric_excel_parser.py
import pandas as pd

REQUIRED_COLUMNS = {
    "Rubric ID",
    "Rubric Name",
    "Description",
    "Weight",
    "Type",
    "Requires Keypoints",
}

def excel_to_rubric_json(df: pd.DataFrame) -> dict:
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Missing rubric columns: {missing}")

    rubrics = []

    for _, row in df.iterrows():
        rubrics.append({
            "id": str(row["Rubric ID"]).strip(),
            "name": str(row["Rubric Name"]).strip(),
            "description": str(row["Description"]).strip(),
            "weight": int(row["Weight"]),
            "type": str(row["Type"]).strip().lower(),
            "requires_keypoints": bool(row["Requires Keypoints"]),
        })

    return {"rubrics": rubrics}
