"""
Part 2 — PII Detection.

Classifies each column into a PII category and provides regex-based
detection for email and phone fields. Produces counts/percentages used to
populate `pii_detection_report.txt`. Nothing here prints raw PII; callers
must only ever pass counts and metadata into reports/logs.
"""

from __future__ import annotations

import re

import pandas as pd

# Field -> PII category. Categories follow the assignment's three-way split.
DIRECT_IDENTIFIERS = {"first_name", "last_name", "email", "phone", "address"}
SENSITIVE_PERSONAL_INFO = {"date_of_birth", "income"}
QUASI_IDENTIFIERS = {"customer_id", "created_date"}

RISK_NOTES = {
    "first_name": "Direct identifier; combined with last_name, uniquely identifies a person.",
    "last_name": "Direct identifier; combined with first_name, uniquely identifies a person.",
    "email": "Direct identifier and a common cross-service correlation key.",
    "phone": "Direct identifier; can be used for account takeover or unsolicited contact.",
    "address": "Direct identifier; reveals physical location, a high-sensitivity attribute.",
    "date_of_birth": "Sensitive; combined with other quasi-identifiers, supports re-identification and is used in identity verification/fraud.",
    "income": "Sensitive financial attribute; disclosure risk is reputational/financial rather than identifying on its own.",
    "customer_id": "Quasi-identifier/internal key; not sensitive alone, but links all other fields for a person.",
    "created_date": "Low-sensitivity metadata; mainly useful for correlation/analytics, not identification.",
}

# Deliberately permissive but structured: local-part@domain.tld
EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")

# Accepts the formats intentionally seeded into the synthetic dataset:
# XXX-XXX-XXXX, (XXX) XXX-XXXX, XXX.XXX.XXXX, XXXXXXXXXX, +1-XXX-XXX-XXXX
PHONE_PATTERN = re.compile(
    r"^(\+1-)?(\(\d{3}\)\s|\d{3}[-.]?)\d{3}[-.]?\d{4}$"
)


def classify_columns() -> dict:
    """Return the static PII classification for every expected column."""
    classification = {}
    for col in DIRECT_IDENTIFIERS:
        classification[col] = "direct_identifier"
    for col in SENSITIVE_PERSONAL_INFO:
        classification[col] = "sensitive_personal_information"
    for col in QUASI_IDENTIFIERS:
        classification[col] = "quasi_identifier_metadata"
    return classification


def is_valid_email(value: str) -> bool:
    return bool(EMAIL_PATTERN.match(value.strip())) if value.strip() else False


def is_recognizable_phone(value: str) -> bool:
    return bool(PHONE_PATTERN.match(value.strip())) if value.strip() else False


def detect_pii(df: pd.DataFrame) -> dict:
    """
    Compute PII detection counts/percentages.

    Returns a dict with:
      - classification: column -> category
      - field_counts: column -> {present_count, present_percentage}
      - records_with_any_pii: count of rows with at least one non-empty
        direct/sensitive identifier
      - email_valid_count / email_invalid_count (regex-detected)
      - phone_recognizable_count / phone_unrecognizable_count (regex-detected)
    """
    total = len(df)
    classification = classify_columns()
    pii_columns = sorted(DIRECT_IDENTIFIERS | SENSITIVE_PERSONAL_INFO)

    field_counts = {}
    for col in pii_columns:
        present = int((df[col].astype(str).str.strip() != "").sum())
        pct = round((present / total) * 100, 2) if total else 0.0
        field_counts[col] = {"present_count": present, "present_percentage": pct}

    any_pii_mask = pd.Series([False] * total, index=df.index)
    for col in pii_columns:
        any_pii_mask = any_pii_mask | (df[col].astype(str).str.strip() != "")
    records_with_any_pii = int(any_pii_mask.sum())

    email_valid = int(df["email"].apply(is_valid_email).sum())
    email_present = int((df["email"].str.strip() != "").sum())
    email_invalid = email_present - email_valid

    phone_recognizable = int(df["phone"].apply(is_recognizable_phone).sum())
    phone_present = int((df["phone"].str.strip() != "").sum())
    phone_unrecognizable = phone_present - phone_recognizable

    return {
        "classification": classification,
        "risk_notes": RISK_NOTES,
        "field_counts": field_counts,
        "total_records": total,
        "records_with_any_pii": records_with_any_pii,
        "records_with_any_pii_percentage": round((records_with_any_pii / total) * 100, 2) if total else 0.0,
        "email_valid_count": email_valid,
        "email_invalid_count": email_invalid,
        "phone_recognizable_count": phone_recognizable,
        "phone_unrecognizable_count": phone_unrecognizable,
    }
