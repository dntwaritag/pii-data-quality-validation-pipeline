import pandas as pd
import pytest

from src import config
from src.pipeline import PipelineError, run_pipeline
from tests.fixtures import make_row


@pytest.fixture
def isolated_pipeline_dirs(tmp_path, monkeypatch):
    """Point every pipeline path at a scratch directory so tests never touch real project files."""
    data_dir = tmp_path / "data"
    output_dir = tmp_path / "outputs"
    reports_dir = tmp_path / "reports"
    logs_dir = tmp_path / "logs"
    for d in (data_dir, output_dir, reports_dir, logs_dir):
        d.mkdir()

    monkeypatch.setattr(config, "DATA_DIR", data_dir)
    monkeypatch.setattr(config, "OUTPUT_DIR", output_dir)
    monkeypatch.setattr(config, "REPORTS_DIR", reports_dir)
    monkeypatch.setattr(config, "LOGS_DIR", logs_dir)
    monkeypatch.setattr(config, "RAW_DATA_FILE", data_dir / "customers_raw.csv")
    monkeypatch.setattr(config, "CLEANED_DATA_FILE", output_dir / "customers_cleaned.csv")
    monkeypatch.setattr(config, "MASKED_DATA_FILE", output_dir / "customers_masked.csv")
    monkeypatch.setattr(config, "DATA_QUALITY_REPORT", reports_dir / "data_quality_report.txt")
    monkeypatch.setattr(config, "PII_DETECTION_REPORT", reports_dir / "pii_detection_report.txt")
    monkeypatch.setattr(config, "VALIDATION_RESULTS_REPORT", reports_dir / "validation_results.txt")
    monkeypatch.setattr(config, "CLEANING_LOG_REPORT", reports_dir / "cleaning_log.txt")
    monkeypatch.setattr(config, "MASKED_SAMPLE_REPORT", reports_dir / "masked_sample.txt")
    monkeypatch.setattr(config, "PIPELINE_EXECUTION_REPORT", reports_dir / "pipeline_execution_report.txt")
    monkeypatch.setattr(config, "PIPELINE_LOG_FILE", logs_dir / "pipeline.log")
    return {"data_dir": data_dir, "output_dir": output_dir, "reports_dir": reports_dir}


def test_pipeline_success_end_to_end(isolated_pipeline_dirs):
    rows = [make_row(customer_id=str(i)) for i in range(1, 6)]
    rows.append(make_row(customer_id="6", income="-999"))  # one unrepairable row
    pd.DataFrame(rows).to_csv(config.RAW_DATA_FILE, index=False)

    summary = run_pipeline()

    assert summary["status"] == "SUCCESS"
    assert summary["input_row_count"] == 6
    assert summary["cleaned_record_count"] == 5
    assert summary["rejected_record_count"] == 1
    assert config.CLEANED_DATA_FILE.exists()
    assert config.MASKED_DATA_FILE.exists()
    assert config.DATA_QUALITY_REPORT.exists()
    assert config.PII_DETECTION_REPORT.exists()
    assert config.VALIDATION_RESULTS_REPORT.exists()
    assert config.CLEANING_LOG_REPORT.exists()
    assert config.MASKED_SAMPLE_REPORT.exists()
    assert config.PIPELINE_EXECUTION_REPORT.exists()


def test_pipeline_missing_input_file_raises(isolated_pipeline_dirs):
    # No CSV written to config.RAW_DATA_FILE.
    with pytest.raises(PipelineError):
        run_pipeline()
