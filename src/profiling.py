"""
Part 1 — Exploratory Data Quality Analysis.

All functions here compute real statistics from a DataFrame; nothing is
hardcoded or invented. `profile_dataset` returns a single dict that
`reporting.py` turns into `data_quality_report.txt`.
"""

from __future__ import annotations

import re
from datetime import datetime

import pandas as pd

from src.config import ALLOWED_ACCOUNT_STATUSES, INCOME_MAX, MAX_PLAUSIBLE_AGE

PHONE_DIGITS_RE = re.compile(r"\d")
WHITESPACE_EDGE_RE = re.compile(r"^\s|\s$|\s{2,}")

# Recognized (parseable) date patterns, used only to report whether a value
# is in a "standard" ISO shape vs. some other recognizable shape.
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

KNOWN_DATE_FORMATS = ["%Y-%m-%d", "%m/%d/%Y", "%d-%m-%Y", "%B %d, %Y"]


def _try_parse_date(value: str):
    value = value.strip()
    if not value:
        return None
    for fmt in KNOWN_DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def completeness(df: pd.DataFrame) -> dict:
    """Per-column total/missing counts and missing percentage."""
    total = len(df)
    result = {}
    for col in df.columns:
        missing = int((df[col].astype(str).str.strip() == "").sum())
        pct = round((missing / total) * 100, 2) if total else 0.0
        result[col] = {"total_records": total, "missing_count": missing, "missing_percentage": pct}
    return result


def data_type_analysis(df: pd.DataFrame) -> dict:
    """Report source vs. expected type per column, and whether conversion is required."""
    expected_types = {
        "customer_id": "integer",
        "first_name": "string",
        "last_name": "string",
        "email": "string",
        "phone": "string",
        "date_of_birth": "date (YYYY-MM-DD)",
        "address": "string",
        "income": "numeric (float)",
        "account_status": "categorical string",
        "created_date": "date (YYYY-MM-DD)",
    }
    result = {}
    for col, expected in expected_types.items():
        # Every column is ingested as raw string (see ingestion.py); report
        # that honestly and flag whether the expected type requires
        # conversion out of that raw string.
        result[col] = {
            "detected_source_type": "string (raw CSV text)",
            "expected_type": expected,
            "conversion_required": expected != "string",
        }
    return result


def format_issues(df: pd.DataFrame) -> dict:
    """Inconsistent/malformed phone and date formats, capitalization, whitespace."""
    phone_formats: dict[str, int] = {}
    malformed_phone_count = 0
    for raw in df["phone"]:
        value = raw.strip()
        if not value:
            continue
        digit_count = len(PHONE_DIGITS_RE.findall(value))
        if digit_count != 10:
            malformed_phone_count += 1
            continue
        if re.fullmatch(r"\d{3}-\d{3}-\d{4}", value):
            shape = "XXX-XXX-XXXX"
        elif re.fullmatch(r"\(\d{3}\)\s\d{3}-\d{4}", value):
            shape = "(XXX) XXX-XXXX"
        elif re.fullmatch(r"\d{3}\.\d{3}\.\d{4}", value):
            shape = "XXX.XXX.XXXX"
        elif re.fullmatch(r"\d{10}", value):
            shape = "XXXXXXXXXX"
        elif re.fullmatch(r"\+1-\d{3}-\d{3}-\d{4}", value):
            shape = "+1-XXX-XXX-XXXX"
        else:
            shape = "other_recognizable"
        phone_formats[shape] = phone_formats.get(shape, 0) + 1

    date_formats: dict[str, int] = {}
    invalid_dates = 0
    for col in ("date_of_birth", "created_date"):
        for raw in df[col]:
            value = raw.strip()
            if not value:
                continue
            parsed = _try_parse_date(value)
            if parsed is None:
                invalid_dates += 1
                continue
            if ISO_DATE_RE.match(value):
                date_formats["YYYY-MM-DD"] = date_formats.get("YYYY-MM-DD", 0) + 1
            else:
                date_formats["non_standard"] = date_formats.get("non_standard", 0) + 1

    capitalization_issues = 0
    whitespace_issues = 0
    for col in ("first_name", "last_name", "account_status"):
        for raw in df[col]:
            if raw != raw.strip() or re.search(r"\s{2,}", raw):
                whitespace_issues += 1
            stripped = raw.strip()
            if stripped and col in ("first_name", "last_name") and stripped != stripped.title():
                capitalization_issues += 1
            if stripped and col == "account_status" and stripped != stripped.lower():
                capitalization_issues += 1

    return {
        "phone_format_distribution": phone_formats,
        "malformed_phone_count": malformed_phone_count,
        "date_format_distribution": date_formats,
        "invalid_date_count": invalid_dates,
        "capitalization_issue_count": capitalization_issues,
        "whitespace_issue_count": whitespace_issues,
    }


def uniqueness(df: pd.DataFrame) -> dict:
    """customer_id uniqueness, duplicate customer IDs, and full duplicate rows."""
    ids = df["customer_id"]
    duplicate_id_mask = ids.duplicated(keep=False) & (ids.str.strip() != "")
    duplicate_ids = sorted(set(ids[duplicate_id_mask]))
    full_duplicate_rows = int(df.duplicated(keep=False).sum())

    return {
        "total_records": len(df),
        "unique_customer_ids": int(ids[ids.str.strip() != ""].nunique()),
        "duplicate_customer_id_count": int(duplicate_id_mask.sum()),
        "duplicate_customer_id_values": duplicate_ids,
        "full_duplicate_row_count": full_duplicate_rows,
    }


def invalid_values(df: pd.DataFrame) -> dict:
    """Invalid dates, negative income, income above threshold, age > max, invalid statuses."""
    negative_income = 0
    excessive_income = 0
    for raw in df["income"]:
        value = raw.strip()
        if not value:
            continue
        try:
            amount = float(value)
        except ValueError:
            continue
        if amount < 0:
            negative_income += 1
        if amount > INCOME_MAX:
            excessive_income += 1

    ages_over_limit = 0
    invalid_dob = 0
    future_dob = 0
    today = datetime.today().date()
    for raw in df["date_of_birth"]:
        value = raw.strip()
        if not value:
            continue
        parsed = _try_parse_date(value)
        if parsed is None:
            invalid_dob += 1
            continue
        if parsed > today:
            future_dob += 1
            continue
        age = today.year - parsed.year - ((today.month, today.day) < (parsed.month, parsed.day))
        if age > MAX_PLAUSIBLE_AGE:
            ages_over_limit += 1

    invalid_statuses = 0
    for raw in df["account_status"]:
        value = raw.strip().lower()
        if value and value not in ALLOWED_ACCOUNT_STATUSES:
            invalid_statuses += 1

    invalid_created_date = 0
    for raw in df["created_date"]:
        value = raw.strip()
        if value and _try_parse_date(value) is None:
            invalid_created_date += 1

    return {
        "negative_income_count": negative_income,
        "income_above_threshold_count": excessive_income,
        "invalid_date_of_birth_count": invalid_dob,
        "future_date_of_birth_count": future_dob,
        "age_above_limit_count": ages_over_limit,
        "invalid_account_status_count": invalid_statuses,
        "invalid_created_date_count": invalid_created_date,
    }


def profile_dataset(df: pd.DataFrame) -> dict:
    """Run every Part 1 analysis and return a single results dict."""
    return {
        "completeness": completeness(df),
        "data_types": data_type_analysis(df),
        "format_issues": format_issues(df),
        "uniqueness": uniqueness(df),
        "invalid_values": invalid_values(df),
    }
