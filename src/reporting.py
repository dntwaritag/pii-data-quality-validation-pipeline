"""
Renders every required report file from the actual data structures produced
by profiling/pii_detection/validation/cleaning/masking. No numbers in this
module are invented; every value is read out of the structures passed in.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from src.cleaning import CleaningLog
from src.masking import mask_dob, mask_email, mask_name, mask_phone
from src.validation import ValidationResult


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def render_data_quality_report(profile: dict, path: Path) -> None:
    lines = ["DATA QUALITY REPORT", "=" * 60, ""]

    lines.append("1. COMPLETENESS")
    lines.append("-" * 60)
    for col, stats in profile["completeness"].items():
        lines.append(
            f"{col}: total={stats['total_records']}, missing={stats['missing_count']} "
            f"({stats['missing_percentage']}%)"
        )
    lines.append("")

    lines.append("2. DATA TYPES")
    lines.append("-" * 60)
    for col, stats in profile["data_types"].items():
        lines.append(
            f"{col}: source={stats['detected_source_type']}, expected={stats['expected_type']}, "
            f"conversion_required={stats['conversion_required']}"
        )
    lines.append("")

    lines.append("3. FORMAT ISSUES")
    lines.append("-" * 60)
    fmt = profile["format_issues"]
    lines.append(f"Phone format distribution: {fmt['phone_format_distribution']}")
    lines.append(f"Malformed phone count: {fmt['malformed_phone_count']}")
    lines.append(f"Date format distribution (date_of_birth + created_date): {fmt['date_format_distribution']}")
    lines.append(f"Invalid/unparseable date count: {fmt['invalid_date_count']}")
    lines.append(f"Capitalization issue count (names/status): {fmt['capitalization_issue_count']}")
    lines.append(f"Whitespace issue count (names/status): {fmt['whitespace_issue_count']}")
    lines.append("")

    lines.append("4. UNIQUENESS")
    lines.append("-" * 60)
    uniq = profile["uniqueness"]
    lines.append(f"Total records: {uniq['total_records']}")
    lines.append(f"Unique customer_id values: {uniq['unique_customer_ids']}")
    lines.append(f"Records involved in duplicate customer_id: {uniq['duplicate_customer_id_count']}")
    lines.append(f"Duplicate customer_id values: {uniq['duplicate_customer_id_values']}")
    lines.append(f"Fully duplicate rows: {uniq['full_duplicate_row_count']}")
    lines.append("")

    lines.append("5. INVALID VALUES")
    lines.append("-" * 60)
    inv = profile["invalid_values"]
    lines.append(f"Negative income: {inv['negative_income_count']}")
    lines.append(f"Income above $10,000,000: {inv['income_above_threshold_count']}")
    lines.append(f"Invalid/unparseable date_of_birth: {inv['invalid_date_of_birth_count']}")
    lines.append(f"Future date_of_birth: {inv['future_date_of_birth_count']}")
    lines.append(f"Age above 150: {inv['age_above_limit_count']}")
    lines.append(f"Invalid account_status: {inv['invalid_account_status_count']}")
    lines.append(f"Invalid/unparseable created_date: {inv['invalid_created_date_count']}")
    lines.append("")

    _write(path, "\n".join(lines))


def render_pii_detection_report(pii: dict, path: Path) -> None:
    lines = ["PII DETECTION REPORT", "=" * 60, ""]

    lines.append("1. CLASSIFICATION")
    lines.append("-" * 60)
    for col, category in sorted(pii["classification"].items()):
        lines.append(f"{col}: {category}")
    lines.append("")

    lines.append("2. FIELD PRESENCE COUNTS")
    lines.append("-" * 60)
    for col, stats in sorted(pii["field_counts"].items()):
        lines.append(f"{col}: present={stats['present_count']} ({stats['present_percentage']}%)")
    lines.append("")

    lines.append("3. RECORD-LEVEL SUMMARY")
    lines.append("-" * 60)
    lines.append(f"Total records: {pii['total_records']}")
    lines.append(
        f"Records containing at least one PII field: {pii['records_with_any_pii']} "
        f"({pii['records_with_any_pii_percentage']}%)"
    )
    lines.append("")

    lines.append("4. EMAIL / PHONE PATTERN DETECTION")
    lines.append("-" * 60)
    lines.append(f"Emails matching valid pattern: {pii['email_valid_count']}")
    lines.append(f"Emails present but not matching valid pattern: {pii['email_invalid_count']}")
    lines.append(f"Phones matching a recognized pattern: {pii['phone_recognizable_count']}")
    lines.append(f"Phones present but not matching a recognized pattern: {pii['phone_unrecognizable_count']}")
    lines.append("")

    lines.append("5. RISK IMPLICATIONS")
    lines.append("-" * 60)
    for col, note in sorted(pii["risk_notes"].items()):
        lines.append(f"{col}: {note}")
    lines.append("")

    lines.append("Note: this report intentionally contains only counts and")
    lines.append("classifications -- no raw PII values are printed here.")

    _write(path, "\n".join(lines))


def render_validation_report(result: ValidationResult, path: Path, stage_label: str) -> None:
    lines = [f"VALIDATION RESULTS -- {stage_label}", "=" * 60, ""]
    lines.append(f"Total rows: {result.total_rows}")
    lines.append(f"Passed rows: {result.passed_rows}")
    lines.append(f"Failed rows: {result.failed_rows}")
    pass_rate = round((result.passed_rows / result.total_rows) * 100, 2) if result.total_rows else 0.0
    lines.append(f"Pass rate: {pass_rate}%")
    lines.append("")

    lines.append("FAILURE COUNTS BY COLUMN")
    lines.append("-" * 60)
    for col, count in sorted(result.failures_by_column.items(), key=lambda kv: -kv[1]):
        lines.append(f"{col}: {count}")
    if not result.failures_by_column:
        lines.append("(none)")
    lines.append("")

    lines.append("FAILURE COUNTS BY RULE")
    lines.append("-" * 60)
    for rule, count in sorted(result.failures_by_rule.items(), key=lambda kv: -kv[1]):
        lines.append(f"{rule}: {count}")
    if not result.failures_by_rule:
        lines.append("(none)")
    lines.append("")

    lines.append("REPRESENTATIVE FAILING CUSTOMER IDS (first 20, safe to show for synthetic data)")
    lines.append("-" * 60)
    shown_ids = []
    for failure in result.failures:
        if failure.customer_id not in shown_ids:
            shown_ids.append(failure.customer_id)
        if len(shown_ids) >= 20:
            break
    lines.append(", ".join(shown_ids) if shown_ids else "(none)")
    lines.append("")

    if result.failed_rows == 0:
        lines.append("SUMMARY: All rows passed validation at this stage.")
    else:
        lines.append(
            f"SUMMARY: {result.failed_rows} of {result.total_rows} rows failed one or more rules "
            f"at this stage. See cleaning_log.txt for how repairable issues were fixed and "
            f"unrepairable rows were quarantined."
        )

    _write(path, "\n".join(lines))


def append_post_cleaning_validation(pre_path: Path, post_result: ValidationResult) -> None:
    """Append post-cleaning validation results onto the same validation_results.txt file."""
    existing = pre_path.read_text(encoding="utf-8") if pre_path.exists() else ""
    lines = ["", "", "=" * 60, "POST-CLEANING VALIDATION", "=" * 60, ""]
    lines.append(f"Total rows: {post_result.total_rows}")
    lines.append(f"Passed rows: {post_result.passed_rows}")
    lines.append(f"Failed rows: {post_result.failed_rows}")
    if post_result.failed_rows == 0:
        lines.append("All records in the cleaned dataset pass every validation rule.")
    else:
        lines.append(
            f"{post_result.failed_rows} records in the cleaned dataset still fail validation; "
            f"these represent issues discovered after cleaning and are documented, not hidden."
        )
        for col, count in sorted(post_result.failures_by_column.items(), key=lambda kv: -kv[1]):
            lines.append(f"  {col}: {count}")
    _write(pre_path, existing + "\n".join(lines))


def render_cleaning_log(log: CleaningLog, path: Path) -> None:
    lines = ["CLEANING LOG", "=" * 60, ""]
    lines.append(f"Input records: {log.input_records}")
    lines.append(f"Cleaned (retained) records: {log.cleaned_records}")
    lines.append(f"Removed records: {log.removed_records}")
    lines.append("")
    lines.append(
        "Every removed row (with the value it had at the moment of removal) is "
        "written to outputs/customers_quarantined.csv with a quarantine_reason "
        "column -- removed records are an inspectable dataset, not just a count."
    )
    lines.append("")

    lines.append("CHANGES BY COLUMN (values reformatted, not removed)")
    lines.append("-" * 60)
    for col, count in sorted(log.changes_by_column.items(), key=lambda kv: -kv[1]):
        lines.append(f"{col}: {count} values normalized")
    if not log.changes_by_column:
        lines.append("(none)")
    lines.append("")

    lines.append("REMOVAL REASONS (rows quarantined, with counts)")
    lines.append("-" * 60)
    for reason, count in sorted(log.removal_reasons.items(), key=lambda kv: -kv[1]):
        ids = log.removed_customer_ids.get(reason, [])
        sample = ", ".join(ids[:5])
        more = f" (+{len(ids) - 5} more)" if len(ids) > 5 else ""
        lines.append(f"{reason}: {count} row(s) -- customer_id(s): {sample}{more}")
    if not log.removal_reasons:
        lines.append("(none)")
    lines.append("")

    lines.append("MISSING-VALUE / REMEDIATION STRATEGY")
    lines.append("-" * 60)
    lines.append("Automatically repaired (reformatted only, no data invented):")
    lines.append("  phone -> normalized to XXX-XXX-XXXX where a recognized shape existed")
    lines.append("  date_of_birth / created_date -> normalized to YYYY-MM-DD where a recognized shape existed")
    lines.append("  first_name / last_name -> whitespace collapsed, title-cased")
    lines.append("  account_status -> whitespace stripped, lower-cased")
    lines.append("Quarantined (row removed, reason logged, nothing invented):")
    lines.append("  duplicate customer_id (kept first occurrence)")
    lines.append("  missing/invalid customer_id, empty/invalid-character/too-long names")
    lines.append("  invalid email format, unparseable phone numbers")
    lines.append("  invalid/impossible/future date_of_birth, age above 150")
    lines.append("  invalid created_date, out-of-range or missing income")
    lines.append("  too-short/empty address, account_status outside the allowed set")
    lines.append("")

    lines.append(
        "CONSISTENCY CHECK: input_records ({}) == cleaned_records ({}) + removed_records ({}): {}".format(
            log.input_records,
            log.cleaned_records,
            log.removed_records,
            log.input_records == log.cleaned_records + log.removed_records,
        )
    )

    _write(path, "\n".join(lines))


def render_masked_sample(cleaned_df: pd.DataFrame, path: Path, n: int = 3) -> None:
    lines = ["PII MASKING SAMPLE", "=" * 60, ""]
    lines.append(
        "Because the source data is entirely synthetic, this file shows a small "
        "before/after comparison for a few sample fields. No real customer data "
        "is displayed anywhere in this project."
    )
    lines.append("")

    sample = cleaned_df.head(n)
    for _, row in sample.iterrows():
        lines.append(f"Record customer_id={row['customer_id']}")
        lines.append(f"  FIELD: First name  | Before: {row['first_name']:<20} | After: {mask_name(row['first_name'])}")
        lines.append(f"  FIELD: Last name   | Before: {row['last_name']:<20} | After: {mask_name(row['last_name'])}")
        lines.append(f"  FIELD: Email       | Before: {row['email']:<30} | After: {mask_email(row['email'])}")
        lines.append(f"  FIELD: Phone       | Before: {row['phone']:<15} | After: {mask_phone(row['phone'])}")
        lines.append("  FIELD: Address     | Before: [synthetic address]     | After: [MASKED ADDRESS]")
        lines.append(f"  FIELD: DOB         | Before: {row['date_of_birth']:<12} | After: {mask_dob(row['date_of_birth'])}")
        lines.append("")

    lines.append(
        "Income is intentionally NOT masked in this dataset (see masking.py "
        "module docstring and reflection.md for the reasoning)."
    )

    _write(path, "\n".join(lines))


def render_pipeline_execution_report(summary: dict, path: Path) -> None:
    lines = ["PIPELINE EXECUTION REPORT", "=" * 60, ""]
    lines.append(f"Execution timestamp: {summary['timestamp']}")
    lines.append(f"Input file: {summary['input_file']}")
    lines.append(f"Input row count: {summary['input_row_count']}")
    lines.append("")

    lines.append("VALIDATION (pre-cleaning)")
    lines.append("-" * 60)
    lines.append(f"Passed: {summary['pre_validation_passed']}")
    lines.append(f"Failed: {summary['pre_validation_failed']}")
    lines.append("")

    lines.append("CLEANING")
    lines.append("-" * 60)
    lines.append(f"Cleaned records: {summary['cleaned_record_count']}")
    lines.append(f"Rejected/quarantined records: {summary['rejected_record_count']}")
    lines.append("")

    lines.append("VALIDATION (post-cleaning)")
    lines.append("-" * 60)
    lines.append(f"Passed: {summary['post_validation_passed']}")
    lines.append(f"Failed: {summary['post_validation_failed']}")
    lines.append("")

    lines.append("PII DETECTION")
    lines.append("-" * 60)
    lines.append(f"Records with any PII: {summary['records_with_any_pii']}")
    lines.append("")

    lines.append("MASKING")
    lines.append("-" * 60)
    lines.append(f"Masked records written: {summary['masked_record_count']}")
    lines.append("")

    lines.append("STAGE TIMINGS (wall-clock seconds)")
    lines.append("-" * 60)
    for stage, seconds in summary["stage_timings_seconds"].items():
        lines.append(f"{stage}: {seconds}s")
    lines.append(f"TOTAL: {summary['total_duration_seconds']}s")
    lines.append("")

    lines.append("GENERATED FILES")
    lines.append("-" * 60)
    for f in summary["generated_files"]:
        lines.append(f"  {f}")
    lines.append("")

    lines.append("WARNINGS")
    lines.append("-" * 60)
    for w in summary["warnings"]:
        lines.append(f"  {w}")
    if not summary["warnings"]:
        lines.append("  (none)")
    lines.append("")

    lines.append("ERRORS")
    lines.append("-" * 60)
    for e in summary["errors"]:
        lines.append(f"  {e}")
    if not summary["errors"]:
        lines.append("  (none)")
    lines.append("")

    lines.append(f"Pipeline Status: {summary['status']}")
    lines.append(f"Input Records: {summary['input_row_count']}")
    lines.append(f"Cleaned Records: {summary['cleaned_record_count']}")
    lines.append(f"Rejected Records: {summary['rejected_record_count']}")
    lines.append(f"Masked Records: {summary['masked_record_count']}")

    _write(path, "\n".join(lines))
