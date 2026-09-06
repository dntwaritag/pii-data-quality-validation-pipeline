from tests.fixtures import make_df, make_row

from src.masking import mask_address, mask_dataframe, mask_dob, mask_email, mask_name, mask_phone


def test_mask_name():
    assert mask_name("John") == "J***"
    assert mask_name("") == ""


def test_mask_email_preserves_domain():
    assert mask_email("john.doe@gmail.com") == "j***@gmail.com"
    assert "john.doe" not in mask_email("john.doe@gmail.com")


def test_mask_phone_only_shows_last_four():
    masked = mask_phone("555-123-4567")
    assert masked == "***-***-4567"
    assert "555" not in masked
    assert "123" not in masked


def test_mask_address_always_placeholder():
    assert mask_address("123 Main Street, Springfield, IL 62701") == "[MASKED ADDRESS]"


def test_mask_dob_hides_month_and_day():
    masked = mask_dob("1985-03-15")
    assert masked == "1985-**-**"
    assert "03" not in masked
    assert "15" not in masked


def test_mask_dataframe_does_not_leak_original_values():
    df = make_df([make_row(customer_id="1")])
    masked = mask_dataframe(df)
    row = masked.iloc[0]
    assert row["first_name"] == "J***"
    assert row["email"] != df.iloc[0]["email"]
    assert "jane.doe" not in row["email"]
    assert row["address"] == "[MASKED ADDRESS]"
