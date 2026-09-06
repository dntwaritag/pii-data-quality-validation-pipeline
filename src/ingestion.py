"""
Ingestion: load the raw customer CSV into a DataFrame and verify it has the
expected shape before anything downstream touches it.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from src.config import EXPECTED_COLUMNS

logger = logging.getLogger(__name__)


class IngestionError(Exception):
    """Raised when the input file cannot be loaded or does not match the expected schema."""


def load_customers(path: Path) -> pd.DataFrame:
    """
    Load the raw customer CSV.

    Raises IngestionError (not a bare exception) for:
      - a missing input file
      - a file that pandas cannot parse as CSV
      - a file missing one or more expected columns
    """
    if not path.exists():
        raise IngestionError(f"Input file not found: {path}")

    try:
        # dtype=str keeps every field as raw text so validation/cleaning
        # decide how to interpret values, rather than pandas silently
        # coercing types (e.g. turning "" into NaN of a numeric dtype).
        df = pd.read_csv(path, dtype=str, keep_default_na=False)
    except pd.errors.ParserError as exc:
        raise IngestionError(f"Could not parse '{path}' as CSV: {exc}") from exc
    except UnicodeDecodeError as exc:
        raise IngestionError(f"Could not decode '{path}': {exc}") from exc

    missing_columns = [c for c in EXPECTED_COLUMNS if c not in df.columns]
    if missing_columns:
        raise IngestionError(
            f"Input file '{path}' is missing required columns: {missing_columns}"
        )

    # Keep only the expected columns, in the expected order, so any extra
    # accidental columns never leak into downstream processing.
    df = df[EXPECTED_COLUMNS].copy()

    logger.info("Loaded %d rows and %d columns from %s", len(df), len(df.columns), path.name)
    return df
