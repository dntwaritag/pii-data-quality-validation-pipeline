from tests.fixtures import make_df, make_row

from src.profiling import completeness, invalid_values, profile_dataset, uniqueness


def test_completeness_counts_missing_values():
    df = make_df([make_row(customer_id="1", email="")])
    stats = completeness(df)
    assert stats["email"]["missing_count"] == 1
    assert stats["email"]["missing_percentage"] == 100.0


def test_uniqueness_detects_duplicate_ids():
    df = make_df([make_row(customer_id="1"), make_row(customer_id="1")])
    stats = uniqueness(df)
    assert stats["duplicate_customer_id_count"] == 2
    assert stats["duplicate_customer_id_values"] == ["1"]


def test_invalid_values_detects_negative_income():
    df = make_df([make_row(customer_id="1", income="-500")])
    stats = invalid_values(df)
    assert stats["negative_income_count"] == 1


def test_profile_dataset_returns_all_sections():
    df = make_df([make_row(customer_id="1")])
    profile = profile_dataset(df)
    assert set(profile.keys()) == {
        "completeness", "data_types", "format_issues", "uniqueness", "invalid_values",
    }
