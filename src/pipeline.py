"""
Part 6 — End-to-end pipeline orchestration.

Flow: Load -> Profile -> Detect PII -> Validate -> Clean -> Re-validate ->
Mask -> Save outputs -> Generate reports.

Run with:
    python -m src.pipeline

Performance note: this project does not use a code profiler (cProfile /
line_profiler); it's a straightforward batch job over a few hundred rows,
where per-line CPU profiling wouldn't add much. What it does track,
because it's useful in a real batch pipeline, is wall-clock duration per
stage (`_stage_timer` below), logged and included in
`pipeline_execution_report.txt` so a slow stage is visible without
needing to reach for an external profiler.
"""

from __future__ import annotations

import logging
import sys
import time
from contextlib import contextmanager
from datetime import datetime

from src import config, reporting
from src.cleaning import clean_dataframe
from src.ingestion import IngestionError, load_customers
from src.pii_detection import detect_pii
from src.masking import mask_dataframe
from src.profiling import profile_dataset
from src.validation import validate_dataframe

logger = logging.getLogger("pipeline")


def _configure_logging() -> None:
    config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(config.PIPELINE_LOG_FILE, mode="a", encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


class PipelineError(Exception):
    """Raised when the pipeline cannot complete and should stop with a clear message."""


@contextmanager
def _stage_timer(stage_name: str, timings: dict):
    """Time a pipeline stage with a monotonic clock and record it in `timings`."""
    start = time.perf_counter()
    try:
        yield
    finally:
        timings[stage_name] = round(time.perf_counter() - start, 4)


def run_pipeline() -> dict:
    """
    Execute the full pipeline. Returns the execution summary dict that also
    backs `pipeline_execution_report.txt`.

    Never uses a bare `except:` -- failures are caught at the specific step
    that can fail, logged with a useful message, and re-raised as
    PipelineError so the caller/CLI can report a clean failure status
    instead of a raw traceback.
    """
    _configure_logging()
    warnings: list[str] = []
    errors: list[str] = []
    generated_files: list[str] = []
    stage_timings: dict[str, float] = {}
    status = "SUCCESS"
    pipeline_start = time.perf_counter()

    logger.info("Pipeline started")
    logger.info("Input file: %s", config.RAW_DATA_FILE)

    try:
        with _stage_timer("ingestion", stage_timings):
            df = load_customers(config.RAW_DATA_FILE)
    except IngestionError as exc:
        logger.error("Ingestion failed: %s", exc)
        raise PipelineError(f"Ingestion failed: {exc}") from exc

    input_row_count = len(df)
    logger.info("Row count: %d", input_row_count)

    # --- Profiling ---
    try:
        with _stage_timer("profiling", stage_timings):
            profile = profile_dataset(df)
    except (ValueError, KeyError) as exc:
        logger.error("Profiling failed: %s", exc)
        raise PipelineError(f"Profiling failed: {exc}") from exc
    reporting.render_data_quality_report(profile, config.DATA_QUALITY_REPORT)
    generated_files.append(str(config.DATA_QUALITY_REPORT))
    logger.info("Data quality report written")

    # --- PII detection ---
    try:
        with _stage_timer("pii_detection", stage_timings):
            pii = detect_pii(df)
    except (ValueError, KeyError) as exc:
        logger.error("PII detection failed: %s", exc)
        raise PipelineError(f"PII detection failed: {exc}") from exc
    reporting.render_pii_detection_report(pii, config.PII_DETECTION_REPORT)
    generated_files.append(str(config.PII_DETECTION_REPORT))
    logger.info(
        "PII detection summary: %d/%d records contain PII",
        pii["records_with_any_pii"],
        pii["total_records"],
    )

    # --- Pre-cleaning validation ---
    try:
        with _stage_timer("pre_cleaning_validation", stage_timings):
            pre_validation = validate_dataframe(df)
    except (ValueError, KeyError) as exc:
        logger.error("Validation failed: %s", exc)
        raise PipelineError(f"Validation failed: {exc}") from exc
    reporting.render_validation_report(pre_validation, config.VALIDATION_RESULTS_REPORT, "PRE-CLEANING")
    generated_files.append(str(config.VALIDATION_RESULTS_REPORT))
    logger.info(
        "Pre-cleaning validation: %d passed, %d failed",
        pre_validation.passed_rows,
        pre_validation.failed_rows,
    )

    # --- Cleaning ---
    try:
        with _stage_timer("cleaning", stage_timings):
            cleaned_df, quarantined_df, cleaning_log = clean_dataframe(df)
    except (ValueError, KeyError) as exc:
        logger.error("Cleaning failed: %s", exc)
        raise PipelineError(f"Cleaning failed: {exc}") from exc
    reporting.render_cleaning_log(cleaning_log, config.CLEANING_LOG_REPORT)
    generated_files.append(str(config.CLEANING_LOG_REPORT))
    logger.info(
        "Cleaning: %d input -> %d cleaned, %d removed",
        cleaning_log.input_records,
        cleaning_log.cleaned_records,
        cleaning_log.removed_records,
    )
    if cleaning_log.input_records != cleaning_log.cleaned_records + cleaning_log.removed_records:
        warnings.append("Cleaning record-count reconciliation mismatch -- see cleaning_log.txt")

    # --- Post-cleaning validation ---
    try:
        with _stage_timer("post_cleaning_validation", stage_timings):
            post_validation = validate_dataframe(cleaned_df)
    except (ValueError, KeyError) as exc:
        logger.error("Post-cleaning validation failed: %s", exc)
        raise PipelineError(f"Post-cleaning validation failed: {exc}") from exc
    reporting.append_post_cleaning_validation(config.VALIDATION_RESULTS_REPORT, post_validation)
    logger.info(
        "Post-cleaning validation: %d passed, %d failed",
        post_validation.passed_rows,
        post_validation.failed_rows,
    )
    if post_validation.failed_rows > 0:
        warnings.append(
            f"{post_validation.failed_rows} cleaned records still fail validation; see validation_results.txt"
        )

    # --- Save cleaned + quarantined datasets ---
    try:
        config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        cleaned_df.to_csv(config.CLEANED_DATA_FILE, index=False)
        quarantined_df.to_csv(config.QUARANTINED_DATA_FILE, index=False)
    except OSError as exc:
        logger.error("Failed to write cleaned/quarantined dataset: %s", exc)
        raise PipelineError(f"Failed to write cleaned/quarantined dataset: {exc}") from exc
    generated_files.append(str(config.CLEANED_DATA_FILE))
    generated_files.append(str(config.QUARANTINED_DATA_FILE))
    logger.info("Cleaned dataset written: %d records", len(cleaned_df))
    logger.info("Quarantined dataset written: %d records", len(quarantined_df))

    # --- Masking ---
    try:
        with _stage_timer("masking", stage_timings):
            masked_df = mask_dataframe(cleaned_df)
            masked_df.to_csv(config.MASKED_DATA_FILE, index=False)
    except OSError as exc:
        logger.error("Failed to write masked dataset: %s", exc)
        raise PipelineError(f"Failed to write masked dataset: {exc}") from exc
    generated_files.append(str(config.MASKED_DATA_FILE))
    reporting.render_masked_sample(cleaned_df, config.MASKED_SAMPLE_REPORT)
    generated_files.append(str(config.MASKED_SAMPLE_REPORT))
    logger.info("Masked dataset written: %d records", len(masked_df))

    total_duration = round(time.perf_counter() - pipeline_start, 4)

    summary = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "input_file": str(config.RAW_DATA_FILE),
        "input_row_count": input_row_count,
        "pre_validation_passed": pre_validation.passed_rows,
        "pre_validation_failed": pre_validation.failed_rows,
        "cleaned_record_count": cleaning_log.cleaned_records,
        "rejected_record_count": cleaning_log.removed_records,
        "post_validation_passed": post_validation.passed_rows,
        "post_validation_failed": post_validation.failed_rows,
        "records_with_any_pii": pii["records_with_any_pii"],
        "masked_record_count": len(masked_df),
        "generated_files": generated_files,
        "warnings": warnings,
        "errors": errors,
        "status": status,
        "stage_timings_seconds": stage_timings,
        "total_duration_seconds": total_duration,
    }

    reporting.render_pipeline_execution_report(summary, config.PIPELINE_EXECUTION_REPORT)
    generated_files.append(str(config.PIPELINE_EXECUTION_REPORT))
    logger.info("Pipeline completed with status %s in %.4fs", status, total_duration)
    return summary


if __name__ == "__main__":
    try:
        result = run_pipeline()
        print(f"Pipeline finished: {result['status']} in {result['total_duration_seconds']}s")
        sys.exit(0)
    except PipelineError as exc:
        logging.getLogger("pipeline").error("Pipeline aborted: %s", exc)
        print(f"Pipeline FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
