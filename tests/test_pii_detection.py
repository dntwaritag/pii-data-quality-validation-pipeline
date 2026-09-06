from tests.fixtures import make_df, make_row

from src.pii_detection import classify_columns, detect_pii, is_recognizable_phone, is_valid_email


def test_email_detection():
    assert is_valid_email("jane.doe@example.com") is True
    assert is_valid_email("not-an-email") is False
    assert is_valid_email("") is False


def test_phone_detection():
    assert is_recognizable_phone("555-123-4567") is True
    assert is_recognizable_phone("(555) 123-4567") is True
    assert is_recognizable_phone("12345") is False


def test_classification_covers_all_categories():
    classification = classify_columns()
    assert classification["email"] == "direct_identifier"
    assert classification["income"] == "sensitive_personal_information"
    assert classification["customer_id"] == "quasi_identifier_metadata"


def test_detect_pii_counts():
    df = make_df([make_row(customer_id="1"), make_row(customer_id="2", email="")])
    result = detect_pii(df)
    assert result["total_records"] == 2
    assert result["field_counts"]["email"]["present_count"] == 1
    assert result["records_with_any_pii"] == 2
