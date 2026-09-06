from tests.fixtures import make_df, make_row

from src.validation import validate_dataframe


def test_all_valid_rows_pass():
    df = make_df([make_row(customer_id="1"), make_row(customer_id="2")])
    result = validate_dataframe(df)
    assert result.passed_rows == 2
    assert result.failed_rows == 0


def test_duplicate_customer_id_fails():
    df = make_df([make_row(customer_id="1"), make_row(customer_id="1")])
    result = validate_dataframe(df)
    assert result.failed_rows == 2
    assert result.failures_by_rule.get("unique") == 2


def test_negative_income_fails():
    df = make_df([make_row(customer_id="1", income="-500")])
    result = validate_dataframe(df)
    assert result.failed_rows == 1
    assert result.failures_by_column.get("income") == 1


def test_excessive_income_fails():
    df = make_df([make_row(customer_id="1", income="10000001")])
    result = validate_dataframe(df)
    assert result.failed_rows == 1
    assert "le_10_000_000" in result.failures_by_rule


def test_invalid_email_fails():
    df = make_df([make_row(customer_id="1", email="not-an-email")])
    result = validate_dataframe(df)
    assert result.failed_rows == 1
    assert result.failures_by_column.get("email") == 1


def test_invalid_phone_fails():
    df = make_df([make_row(customer_id="1", phone="12345")])
    result = validate_dataframe(df)
    assert result.failed_rows == 1
    assert result.failures_by_column.get("phone") == 1


def test_invalid_date_fails():
    df = make_df([make_row(customer_id="1", date_of_birth="not-a-date")])
    result = validate_dataframe(df)
    assert result.failed_rows == 1
    assert "valid_date" in result.failures_by_rule


def test_invalid_account_status_fails():
    df = make_df([make_row(customer_id="1", account_status="pending")])
    result = validate_dataframe(df)
    assert result.failed_rows == 1
    assert result.failures_by_column.get("account_status") == 1


def test_invalid_name_fails():
    df = make_df([make_row(customer_id="1", first_name="J0hn123")])
    result = validate_dataframe(df)
    assert result.failed_rows == 1
    assert result.failures_by_column.get("first_name") == 1


def test_invalid_address_fails():
    df = make_df([make_row(customer_id="1", address="1 A St")])
    result = validate_dataframe(df)
    assert result.failed_rows == 1
    assert result.failures_by_column.get("address") == 1


def test_invalid_customer_id_fails():
    df = make_df([make_row(customer_id="not-a-number")])
    result = validate_dataframe(df)
    assert result.failed_rows == 1
    assert result.failures_by_column.get("customer_id") == 1
