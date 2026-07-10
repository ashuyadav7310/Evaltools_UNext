'''
import pandas as pd

def parse_scoring_excel(file) -> dict:
    config = {}

    try:
        df_format = pd.read_excel(file, sheet_name="FORMAT_RULES")
        df_style = pd.read_excel(file, sheet_name="STYLE_RULES")

        config["format_rules"] = df_format.to_dict(orient="records")
        config["style_rules"] = df_style.to_dict(orient="records")

    except Exception as e:
        raise ValueError(f"Invalid scoring config Excel: {e}")

    return config
'''