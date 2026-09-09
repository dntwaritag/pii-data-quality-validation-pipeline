from tests.fixtures import make_df, make_row

from src.cleaning import clean_dataframe


def test_phone_normalization():
    df = make_df([make_row(customer_id="1", phone="(555) 123-4567")])
    cleaned, quarantined, log = clean_dataframe(df)
    assert cleaned.iloc[0]["phone"] == "555-123-4567"
    assert log.changes_by_column.get("phone") == 1


def test_date_normalization():
    df = make_df([make_row(customer_id="1", date_of_birth="05/15/1990")])
    cleaned, quarantined, log = clean_dataframe(df)
    assert cleaned.iloc[0]["date_of_birth"] == "1990-05-15"
    assert log.changes_by_column.get("date_of_birth") == 1


def test_name_normalization():
    df = make_df([make_row(customer_id="1", first_name="  jane  ")])
    cleaned, quarantined, log = clean_dataframe(df)
    assert cleaned.iloc[0]["first_name"] == "Jane"
    assert log.changes_by_column.get("first_name") == 1


def test_account_status_normalization():
    df = make_df([make_row(customer_id="1", account_status=" ACTIVE ")])
    cleaned, quarantined, log = clean_dataframe(df)
    assert cleaned.iloc[0]["account_status"] == "active"
    assert log.changes_by_column.get("account_status") == 1


def test_duplicate_customer_id_quarantined():
    df = make_df([make_row(customer_id="1"), make_row(customer_id="1")])
    cleaned, quarantined, log = clean_dataframe(df)
    assert len(cleaned) == 1
    assert log.removal_reasons.get("duplicate_customer_id") == 1
    assert len(quarantined) == 1
    assert quarantined.iloc[0]["quarantine_reason"] == "duplicate_customer_id"
    assert quarantined.iloc[0]["customer_id"] == "1"


def test_unrepairable_row_is_removed_and_logged():
    df = make_df([make_row(customer_id="1", income="-100")])
    cleaned, quarantined, log = clean_dataframe(df)
    assert len(cleaned) == 0
    assert log.removed_records == 1
    assert log.input_records == log.cleaned_records + log.removed_records


def test_missing_value_is_not_invented():
    df = make_df([make_row(customer_id="1", phone="")])
    cleaned, quarantined, log = clean_dataframe(df)
    # Missing phone cannot be safely repaired -> row is quarantined, not
    # filled with a fabricated value.
    assert len(cleaned) == 0
    assert log.removal_reasons.get("phone:non_empty") == 1
    assert len(quarantined) == 1
    assert "phone:non_empty" in quarantined.iloc[0]["quarantine_reason"]


def test_quarantined_dataframe_has_expected_columns():
    df = make_df([make_row(customer_id="1", income="-100")])
    _, quarantined, _ = clean_dataframe(df)
    assert "quarantine_reason" in quarantined.columns
    assert "customer_id" in quarantined.columns


def test_no_removals_yields_empty_quarantine_dataframe():
    df = make_df([make_row(customer_id="1"), make_row(customer_id="2")])
    _, quarantined, log = clean_dataframe(df)
    assert len(quarantined) == 0
    assert log.removed_records == 0
