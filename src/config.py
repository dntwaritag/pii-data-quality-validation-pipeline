"""
Central configuration for the PII Detection & Data Quality Validation Pipeline.

All file paths and tunable constants live here so the rest of the codebase
never hardcodes locations. Paths can be overridden with environment
variables (see .env.example) for running the pipeline against different
data or output locations without touching source code.
"""

from __future__ import annotations

import os
from pathlib import Path

# Project root is the parent of this file's parent (src/ -> repo root).
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Directories (overridable via environment variables).
DATA_DIR = Path(os.environ.get("PIPELINE_DATA_DIR", PROJECT_ROOT / "data"))
OUTPUT_DIR = Path(os.environ.get("PIPELINE_OUTPUT_DIR", PROJECT_ROOT / "outputs"))
REPORTS_DIR = Path(os.environ.get("PIPELINE_REPORTS_DIR", PROJECT_ROOT / "reports"))
LOGS_DIR = Path(os.environ.get("PIPELINE_LOGS_DIR", PROJECT_ROOT / "logs"))

# Input / output files.
RAW_DATA_FILE = DATA_DIR / "customers_raw.csv"
CLEANED_DATA_FILE = OUTPUT_DIR / "customers_cleaned.csv"
MASKED_DATA_FILE = OUTPUT_DIR / "customers_masked.csv"

# Report files.
DATA_QUALITY_REPORT = REPORTS_DIR / "data_quality_report.txt"
PII_DETECTION_REPORT = REPORTS_DIR / "pii_detection_report.txt"
VALIDATION_RESULTS_REPORT = REPORTS_DIR / "validation_results.txt"
CLEANING_LOG_REPORT = REPORTS_DIR / "cleaning_log.txt"
MASKED_SAMPLE_REPORT = REPORTS_DIR / "masked_sample.txt"
PIPELINE_EXECUTION_REPORT = REPORTS_DIR / "pipeline_execution_report.txt"

# Log file.
PIPELINE_LOG_FILE = LOGS_DIR / "pipeline.log"

# Expected raw schema, in order.
EXPECTED_COLUMNS = [
    "customer_id",
    "first_name",
    "last_name",
    "email",
    "phone",
    "date_of_birth",
    "address",
    "income",
    "account_status",
    "created_date",
]

# Validation constants.
NAME_MIN_LENGTH = 2
NAME_MAX_LENGTH = 50
ADDRESS_MIN_LENGTH = 10
ADDRESS_MAX_LENGTH = 200
INCOME_MIN = 0
INCOME_MAX = 10_000_000
MAX_PLAUSIBLE_AGE = 150
ALLOWED_ACCOUNT_STATUSES = {"active", "inactive", "suspended"}

# Normalized output formats.
PHONE_OUTPUT_FORMAT = "XXX-XXX-XXXX"
DATE_OUTPUT_FORMAT = "%Y-%m-%d"

# Random seed for reproducible synthetic dataset generation.
DATASET_RANDOM_SEED = 42
DATASET_RECORD_COUNT = 220
