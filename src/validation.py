"""
Part 3 — Data Validator.

Approach chosen: custom validation functions over Pandera/Pydantic/Great
Expectations. Rationale (see README "Data Quality" section for the full
write-up): the dataset is a single flat table with ~10 columns and rules
that mix cross-field logic (age derived from date_of_birth, uniqueness of
customer_id) with row-level checks. Pandera/Great Expectations add a
schema-object dependency for validation that custom functions express
just as clearly in this project's size, and custom functions make it easy
to attach a specific, human-readable failure reason per rule, which is
what `validation_results.txt` needs. Pydantic was considered but its
model-per-row style is a slightly awkward fit for whole-column checks
like uniqueness.

Each `validate_<field>` function takes an already-parsed pandas Series
(or the full DataFrame for cross-column checks) and returns a boolean
Series of "is valid" plus a list of failure reasons per invalid row.
`validate_dataframe` runs every rule and returns a structured result.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd

from src.config import (
    ADDRESS_MAX_LENGTH,
    ADDRESS_MIN_LENGTH,
    ALLOWED_ACCOUNT_STATUSES,
    INCOME_MAX,
    INCOME_MIN,
    MAX_PLAUSIBLE_AGE,
    NAME_MAX_LENGTH,
    NAME_MIN_LENGTH,
)
from src.pii_detection import EMAIL_PATTERN, PHONE_PATTERN

NAME_ALPHA_RE_SOURCE = r"^[A-Za-z\-' ]+$"
import re

NAME_ALPHA_RE = re.compile(NAME_ALPHA_RE_SOURCE)

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


@dataclass
class RowFailure:
    customer_id: str
    field: str
    rule: str


@dataclass
class ValidationResult:
    total_rows: int
    passed_rows: int
    failed_rows: int
    failures: list = field(default_factory=list)          # list[RowFailure]
    failures_by_column: dict = field(default_factory=dict)
    failures_by_rule: dict = field(default_factory=dict)
    row_is_valid: pd.Series = None                          # boolean Series aligned to df.index


def _record_failure(result: ValidationResult, customer_id: str, column: str, rule: str) -> None:
    result.failures.append(RowFailure(customer_id=customer_id, field=column, rule=rule))
    result.failures_by_column[column] = result.failures_by_column.get(column, 0) + 1
    result.failures_by_rule[rule] = result.failures_by_rule.get(rule, 0) + 1


def validate_dataframe(df: pd.DataFrame) -> ValidationResult:
    """
    Validate every row of `df` against every field rule.

    A row is considered "passed" only if it satisfies every rule for every
    column. Failures are recorded per (row, column, rule) so the report can
    show failure counts broken down both by column and by rule, as required.
    """
    total = len(df)
    row_valid = pd.Series([True] * total, index=df.index)
    result = ValidationResult(total_rows=total, passed_rows=0, failed_rows=0)

    seen_ids: dict[str, int] = {}
    id_counts = df["customer_id"].value_counts()

    today = datetime.today().date()

    for idx, row in df.iterrows():
        cid_raw = row["customer_id"].strip()
        row_ok = True

        # customer_id: integer, positive, not null, unique
        if not cid_raw:
            _record_failure(result, "N/A", "customer_id", "not_null")
            row_ok = False
        else:
            try:
                cid_int = int(cid_raw)
                if cid_int <= 0:
                    _record_failure(result, cid_raw, "customer_id", "positive")
                    row_ok = False
            except ValueError:
                _record_failure(result, cid_raw, "customer_id", "integer_type")
                row_ok = False
            if id_counts.get(cid_raw, 0) > 1:
                _record_failure(result, cid_raw, "customer_id", "unique")
                row_ok = False

        cid_for_report = cid_raw if cid_raw else "N/A"

        # first_name / last_name: non-empty, 2-50 chars, alphabetic, normalized whitespace
        for name_field in ("first_name", "last_name"):
            value = row[name_field]
            stripped = value.strip()
            if not stripped:
                _record_failure(result, cid_for_report, name_field, "non_empty")
                row_ok = False
                continue
            if not (NAME_MIN_LENGTH <= len(stripped) <= NAME_MAX_LENGTH):
                _record_failure(result, cid_for_report, name_field, "length_2_50")
                row_ok = False
            if not NAME_ALPHA_RE.match(stripped):
                _record_failure(result, cid_for_report, name_field, "alphabetic")
                row_ok = False
            if value != value.strip() or "  " in value:
                _record_failure(result, cid_for_report, name_field, "normalized_whitespace")
                row_ok = False

        # email: valid format
        email = row["email"].strip()
        if not email:
            _record_failure(result, cid_for_report, "email", "non_empty")
            row_ok = False
        elif not EMAIL_PATTERN.match(email):
            _record_failure(result, cid_for_report, "email", "valid_format")
            row_ok = False

        # phone: recognizable format (normalizable to XXX-XXX-XXXX)
        phone = row["phone"].strip()
        if not phone:
            _record_failure(result, cid_for_report, "phone", "non_empty")
            row_ok = False
        elif not PHONE_PATTERN.match(phone):
            _record_failure(result, cid_for_report, "phone", "valid_format")
            row_ok = False

        # date_of_birth: valid date, not future, age <= MAX_PLAUSIBLE_AGE
        dob_raw = row["date_of_birth"].strip()
        if not dob_raw:
            _record_failure(result, cid_for_report, "date_of_birth", "non_empty")
            row_ok = False
        else:
            dob = _try_parse_date(dob_raw)
            if dob is None:
                _record_failure(result, cid_for_report, "date_of_birth", "valid_date")
                row_ok = False
            elif dob > today:
                _record_failure(result, cid_for_report, "date_of_birth", "not_future")
                row_ok = False
            else:
                age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
                if age > MAX_PLAUSIBLE_AGE:
                    _record_failure(result, cid_for_report, "date_of_birth", "age_le_150")
                    row_ok = False

        # address: non-empty, 10-200 chars
        address = row["address"].strip()
        if not address:
            _record_failure(result, cid_for_report, "address", "non_empty")
            row_ok = False
        elif not (ADDRESS_MIN_LENGTH <= len(address) <= ADDRESS_MAX_LENGTH):
            _record_failure(result, cid_for_report, "address", "length_10_200")
            row_ok = False

        # income: numeric, non-negative, <= 10,000,000
        income_raw = row["income"].strip()
        if not income_raw:
            _record_failure(result, cid_for_report, "income", "non_empty")
            row_ok = False
        else:
            try:
                income_val = float(income_raw)
                if income_val < INCOME_MIN:
                    _record_failure(result, cid_for_report, "income", "non_negative")
                    row_ok = False
                if income_val > INCOME_MAX:
                    _record_failure(result, cid_for_report, "income", "le_10_000_000")
                    row_ok = False
            except ValueError:
                _record_failure(result, cid_for_report, "income", "numeric")
                row_ok = False

        # account_status: allowed values (case/whitespace normalized before check)
        status_raw = row["account_status"]
        status_norm = status_raw.strip().lower()
        if not status_norm:
            _record_failure(result, cid_for_report, "account_status", "non_empty")
            row_ok = False
        elif status_norm not in ALLOWED_ACCOUNT_STATUSES:
            _record_failure(result, cid_for_report, "account_status", "allowed_value")
            row_ok = False

        # created_date: valid date
        created_raw = row["created_date"].strip()
        if not created_raw:
            _record_failure(result, cid_for_report, "created_date", "non_empty")
            row_ok = False
        elif _try_parse_date(created_raw) is None:
            _record_failure(result, cid_for_report, "created_date", "valid_date")
            row_ok = False

        row_valid.at[idx] = row_ok

    result.row_is_valid = row_valid
    result.passed_rows = int(row_valid.sum())
    result.failed_rows = total - result.passed_rows
    return result
