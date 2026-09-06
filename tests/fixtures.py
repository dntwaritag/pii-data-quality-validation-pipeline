"""Small, deterministic fixtures shared across test modules. No full dataset dependency."""

import pandas as pd

from src.config import EXPECTED_COLUMNS

VALID_ROW = {
    "customer_id": "1",
    "first_name": "Jane",
    "last_name": "Doe",
    "email": "jane.doe@example.com",
    "phone": "555-123-4567",
    "date_of_birth": "1990-05-15",
    "address": "123 Main Street, Springfield, IL 62701",
    "income": "75000.00",
    "account_status": "active",
    "created_date": "2020-01-01",
}


def make_row(**overrides) -> dict:
    row = dict(VALID_ROW)
    row.update(overrides)
    return row


def make_df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=EXPECTED_COLUMNS)
