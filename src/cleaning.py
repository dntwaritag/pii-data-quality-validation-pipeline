"""
Part 4 — Clean the Data (and the missing-value strategy from the
assignment's "Missing Values" section).

Cleaning strategy, decided up front (see docs/data_governance.md and
README "Data Quality" section for the full write-up):

Automatically repairable (never invents information, only reformats what
is already present and unambiguous):
  - phone numbers in any of the recognized formats -> normalized to
    XXX-XXX-XXXX
  - dates in any of the recognized formats -> normalized to YYYY-MM-DD
  - first/last name / account_status whitespace and capitalization

Not safely repairable -> the row is quarantined (removed from the cleaned
output) and the reason is logged. This applies to: duplicate customer_id
(keep first occurrence, drop the rest), missing/invalid customer_id,
empty or invalid-character names, names exceeding the length limit,
invalid email format, unparseable phone numbers, invalid/impossible or
future dates of birth, ages beyond the plausible limit, invalid
created_date, out-of-range or missing income, too-short/empty addresses,
and account statuses outside the allowed set. None of these can be
repaired without inventing data, which the assignment explicitly
disallows.

`clean_dataframe` returns the cleaned DataFrame plus a structured log of
every decision made, so `cleaning_log.txt` reports real, traceable
numbers rather than a summary written by hand.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd

from src.config import ALLOWED_ACCOUNT_STATUSES
from src.validation import _try_parse_date, validate_dataframe
from src.pii_detection import PHONE_PATTERN


@dataclass
class CleaningLog:
    input_records: int = 0
    cleaned_records: int = 0
    removed_records: int = 0
    changes_by_column: dict = field(default_factory=dict)
    removal_reasons: dict = field(default_factory=dict)     # reason -> count
    removed_customer_ids: dict = field(default_factory=dict)  # reason -> [customer_ids]
    corrected_problems: dict = field(default_factory=dict)   # description -> count
    uncorrectable_problems: dict = field(default_factory=dict)  # description -> count

    def bump_change(self, column: str) -> None:
        self.changes_by_column[column] = self.changes_by_column.get(column, 0) + 1

    def record_removal(self, reason: str, customer_id: str) -> None:
        self.removal_reasons[reason] = self.removal_reasons.get(reason, 0) + 1
        self.removed_customer_ids.setdefault(reason, []).append(customer_id)


def _normalize_phone(value: str) -> str | None:
    """Return XXX-XXX-XXXX if the value matches a recognized phone shape, else None."""
    stripped = value.strip()
    if not PHONE_PATTERN.match(stripped):
        return None
    digits = "".join(ch for ch in stripped if ch.isdigit())
    if digits.startswith("1") and len(digits) == 11:
        digits = digits[1:]
    if len(digits) != 10:
        return None
    return f"{digits[0:3]}-{digits[3:6]}-{digits[6:10]}"


def _normalize_date(value: str) -> str | None:
    parsed = _try_parse_date(value)
    if parsed is None:
        return None
    return parsed.strftime("%Y-%m-%d")


def _normalize_name(value: str) -> str:
    return " ".join(value.strip().split()).title()


def _normalize_status(value: str) -> str:
    return value.strip().lower()


def clean_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, CleaningLog]:
    log = CleaningLog(input_records=len(df))
    working = df.copy()

    # --- Step 1: drop duplicate customer_id, keeping the first occurrence ---
    id_series = working["customer_id"].str.strip()
    is_dup = id_series.duplicated(keep="first") & (id_series != "")
    for idx in working.index[is_dup]:
        log.record_removal("duplicate_customer_id", working.at[idx, "customer_id"].strip())
    working = working[~is_dup].copy()

    # --- Step 2: deterministic, non-inventive normalization ---
    for idx, row in working.iterrows():
        # Phone
        original_phone = row["phone"]
        normalized_phone = _normalize_phone(original_phone) if original_phone.strip() else None
        if normalized_phone and normalized_phone != original_phone.strip():
            working.at[idx, "phone"] = normalized_phone
            log.bump_change("phone")

        # Dates
        for date_col in ("date_of_birth", "created_date"):
            original_date = row[date_col]
            if original_date.strip():
                normalized_date = _normalize_date(original_date)
                if normalized_date and normalized_date != original_date.strip():
                    working.at[idx, date_col] = normalized_date
                    log.bump_change(date_col)

        # Names
        for name_col in ("first_name", "last_name"):
            original_name = row[name_col]
            if original_name.strip():
                normalized_name = _normalize_name(original_name)
                if normalized_name != original_name:
                    working.at[idx, name_col] = normalized_name
                    log.bump_change(name_col)

        # Account status
        original_status = row["account_status"]
        if original_status.strip():
            normalized_status = _normalize_status(original_status)
            if normalized_status != original_status:
                working.at[idx, "account_status"] = normalized_status
                log.bump_change("account_status")

    # --- Step 3: re-validate after normalization; quarantine anything still invalid ---
    post_normalization_validation = validate_dataframe(working)
    keep_mask = post_normalization_validation.row_is_valid

    # Attribute each remaining failure to a specific reason for the log.
    failure_reasons_by_row: dict = {}
    for failure in post_normalization_validation.failures:
        failure_reasons_by_row.setdefault(failure.customer_id, []).append(f"{failure.field}:{failure.rule}")

    for idx in working.index[~keep_mask]:
        cid = working.at[idx, "customer_id"].strip() or "N/A"
        reasons = failure_reasons_by_row.get(cid, ["unknown"])
        primary_reason = reasons[0]
        log.record_removal(primary_reason, cid)
        for r in reasons:
            log.uncorrectable_problems[r] = log.uncorrectable_problems.get(r, 0) + 1

    for column, count in log.changes_by_column.items():
        log.corrected_problems[f"{column}_normalized"] = count

    cleaned = working[keep_mask].copy()
    log.cleaned_records = len(cleaned)
    log.removed_records = log.input_records - log.cleaned_records

    return cleaned.reset_index(drop=True), log
