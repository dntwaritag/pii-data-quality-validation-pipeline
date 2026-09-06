from pathlib import Path

import pandas as pd
import pytest

from src.config import EXPECTED_COLUMNS
from src.ingestion import IngestionError, load_customers


def _write_csv(tmp_path: Path, columns: list[str], rows: list[dict]) -> Path:
    path = tmp_path / "customers_raw.csv"
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)
    return path


def test_load_valid_file(tmp_path):
    row = {col: "x" for col in EXPECTED_COLUMNS}
    path = _write_csv(tmp_path, EXPECTED_COLUMNS, [row])
    df = load_customers(path)
    assert len(df) == 1
    assert list(df.columns) == EXPECTED_COLUMNS


def test_missing_file_raises_ingestion_error(tmp_path):
    missing_path = tmp_path / "does_not_exist.csv"
    with pytest.raises(IngestionError):
        load_customers(missing_path)


def test_missing_required_column_raises_ingestion_error(tmp_path):
    columns = [c for c in EXPECTED_COLUMNS if c != "email"]
    row = {col: "x" for col in columns}
    path = _write_csv(tmp_path, columns, [row])
    with pytest.raises(IngestionError):
        load_customers(path)


def test_extra_columns_are_dropped(tmp_path):
    columns = EXPECTED_COLUMNS + ["debug_notes"]
    row = {col: "x" for col in columns}
    path = _write_csv(tmp_path, columns, [row])
    df = load_customers(path)
    assert "debug_notes" not in df.columns
