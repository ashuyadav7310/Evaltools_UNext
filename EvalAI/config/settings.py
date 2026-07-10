#config/settings.py
import os

# ================================
# PATHS / PROJECT ROOT
# ================================
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

INPUT_DIR = os.path.join(PROJECT_ROOT, "input_data")
ASSIGNMENTS_DIR = os.path.join(INPUT_DIR, "Assignments")
STUDENTS_DIR = os.path.join(INPUT_DIR, "students")

OUTPUT_ROOT = os.path.join(PROJECT_ROOT, "output")
REPORTS_DIR = os.path.join(OUTPUT_ROOT, "reports")
LOGS_DIR = os.path.join(OUTPUT_ROOT, "logs")

RUBRICS_DIR = os.path.join(PROJECT_ROOT, "config", "rubrics")

os.makedirs(REPORTS_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(RUBRICS_DIR, exist_ok=True)


# ================================
# NLP / EMBEDDING MODELS
# ================================
# Embedding model → used for cosine similarity
EMBED_MODEL = "BAAI/bge-large-en-v1.5"

# Reranker model → MUST be present (no fallback)
RERANKER_MODEL = "BAAI/bge-reranker-large"

# DEVICE = "cpu" / "cuda"
DEVICE = "cpu"   # set to "cuda" if you have GPU

# ================================
# RUBRIC SYSTEM
# ================================
SUPPORTED_RUBRIC_TYPES = ["content", "style", "format"]
DEFAULT_RUBRIC_MAX = 1.0
FALLBACK_ZERO_IF_PARSE_FAIL = True

# ================================
# LOGGING
# ================================
LOG_LEVEL = "INFO"
LOG_FILE = os.path.join(LOGS_DIR, "evaluator.log")

# ================================
# MISC
# ================================
ENCODING = "utf-8"