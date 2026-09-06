"""
Synthetic dataset generator.

Per the instructor's 4 September clarification, no external
`customers_raw.csv` is provided. This module generates a synthetic
customer dataset with a controlled, documented mixture of valid records
and intentional data-quality errors, so the rest of the pipeline has a
realistic (but entirely fictitious) dataset to profile, validate, clean,
and mask.

No real person's information is used anywhere in this file. All names,
emails, phone numbers, and addresses are synthetic and drawn from
generic word lists / example.com-style domains.

Running this module writes `data/customers_raw.csv` and prints a summary
of how many records were seeded with each error category so the numbers
in Part 1 (profiling) and the dataset design plan can be cross-checked
against actual output.
"""

from __future__ import annotations

import csv
import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from src.config import DATASET_RANDOM_SEED, DATASET_RECORD_COUNT, EXPECTED_COLUMNS, RAW_DATA_FILE

FIRST_NAMES = [
    "James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael", "Linda",
    "William", "Elizabeth", "David", "Barbara", "Richard", "Susan", "Joseph", "Jessica",
    "Thomas", "Sarah", "Charles", "Karen", "Daniel", "Nancy", "Matthew", "Lisa",
    "Anthony", "Betty", "Mark", "Margaret", "Paul", "Sandra", "Steven", "Ashley",
    "Andrew", "Kimberly", "Kenneth", "Emily", "Joshua", "Donna", "Kevin", "Michelle",
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
    "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson",
    "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson",
]

STREET_NAMES = [
    "Maple Street", "Oak Avenue", "Cedar Lane", "Pine Road", "Elm Street",
    "Birch Court", "Willow Way", "Sunset Boulevard", "River Drive", "Highland Avenue",
]

CITIES_STATES = [
    ("Springfield", "IL", "62701"), ("Riverside", "CA", "92501"), ("Fairview", "TX", "75001"),
    ("Georgetown", "OH", "45121"), ("Clinton", "NY", "13323"), ("Franklin", "TN", "37064"),
    ("Greenville", "SC", "29601"), ("Madison", "WI", "53703"), ("Salem", "OR", "97301"),
    ("Arlington", "VA", "22201"),
]

EMAIL_DOMAINS = ["example.com", "example.org", "example.net", "mail.example.com"]

VALID_STATUSES = ["active", "inactive", "suspended"]


@dataclass
class ErrorInventory:
    """Tracks how many records were seeded with each error category."""

    counts: dict = field(default_factory=dict)

    def bump(self, category: str, amount: int = 1) -> None:
        self.counts[category] = self.counts.get(category, 0) + amount

    def as_sorted_items(self):
        return sorted(self.counts.items(), key=lambda kv: kv[0])


def _make_valid_record(customer_id: int, rng: random.Random) -> dict:
    first = rng.choice(FIRST_NAMES)
    last = rng.choice(LAST_NAMES)
    domain = rng.choice(EMAIL_DOMAINS)
    email = f"{first.lower()}.{last.lower()}{customer_id}@{domain}"
    area = rng.randint(200, 989)
    exch = rng.randint(200, 989)
    line = rng.randint(1000, 9999)
    phone = f"{area}-{exch}-{line}"
    dob_year = rng.randint(1945, 2004)
    dob = date(dob_year, rng.randint(1, 12), rng.randint(1, 28))
    street_num = rng.randint(100, 9999)
    street = rng.choice(STREET_NAMES)
    city, state, zip_code = rng.choice(CITIES_STATES)
    address = f"{street_num} {street}, {city}, {state} {zip_code}"
    income = round(rng.uniform(28_000, 240_000), 2)
    status = rng.choice(VALID_STATUSES)
    created_year = rng.randint(2015, 2026)
    created = date(created_year, rng.randint(1, 12), rng.randint(1, 28))

    return {
        "customer_id": customer_id,
        "first_name": first,
        "last_name": last,
        "email": email,
        "phone": phone,
        "date_of_birth": dob.isoformat(),
        "address": address,
        "income": income,
        "account_status": status,
        "created_date": created.isoformat(),
    }


def generate_dataset(
    record_count: int = DATASET_RECORD_COUNT,
    seed: int = DATASET_RANDOM_SEED,
) -> tuple[list[dict], ErrorInventory]:
    """
    Build the synthetic dataset in memory.

    Returns the list of row dicts (in CSV column order via EXPECTED_COLUMNS)
    plus an ErrorInventory documenting how many rows were seeded with each
    intentional error category. Roughly 60% of rows are left fully valid;
    the remainder each receive exactly one seeded error category so the
    dataset stays easy to reason about (per the assignment's instruction
    not to introduce random, uninterpretable corruption).
    """
    rng = random.Random(seed)
    inventory = ErrorInventory()
    rows = [_make_valid_record(cid, rng) for cid in range(1, record_count + 1)]

    valid_fraction = 0.6
    n_valid = int(record_count * valid_fraction)
    error_pool = list(range(n_valid, record_count))
    rng.shuffle(error_pool)

    error_categories = [
        "duplicate_customer_id",
        "missing_email",
        "missing_phone",
        "missing_income",
        "missing_address",
        "negative_income",
        "income_above_10m",
        "invalid_email_format",
        "malformed_phone",
        "inconsistent_phone_formatting",
        "invalid_date_of_birth",
        "non_standard_date_format",
        "future_date_of_birth",
        "age_above_150",
        "invalid_account_status",
        "empty_first_name",
        "name_with_invalid_characters",
        "name_too_long",
        "address_too_short",
        "inconsistent_capitalization",
        "inconsistent_whitespace",
        "invalid_created_date",
    ]

    # Distribute the remaining rows round-robin across error categories so
    # every category gets at least a couple of examples (dataset size
    # permitting) without hand-tuning exact counts.
    idx = 0
    for pos in error_pool:
        category = error_categories[idx % len(error_categories)]
        idx += 1
        row = rows[pos]

        if category == "duplicate_customer_id":
            # Reuse an earlier valid customer_id to create a genuine duplicate.
            dup_source = rng.randint(1, n_valid)
            row["customer_id"] = rows[dup_source - 1]["customer_id"]
        elif category == "missing_email":
            row["email"] = ""
        elif category == "missing_phone":
            row["phone"] = ""
        elif category == "missing_income":
            row["income"] = ""
        elif category == "missing_address":
            row["address"] = ""
        elif category == "negative_income":
            row["income"] = -round(rng.uniform(1_000, 50_000), 2)
        elif category == "income_above_10m":
            row["income"] = round(rng.uniform(10_000_001, 50_000_000), 2)
        elif category == "invalid_email_format":
            row["email"] = rng.choice([
                "not-an-email", "missing.domain@", "@nodomain.com", "spaced name@example.com",
            ])
        elif category == "malformed_phone":
            row["phone"] = rng.choice(["12345", "abcdefghij", "555-CALL-NOW", "000-000-0000000"])
        elif category == "inconsistent_phone_formatting":
            # Still a valid number, but in an alternate accepted format.
            area = rng.randint(200, 989)
            exch = rng.randint(200, 989)
            line = rng.randint(1000, 9999)
            row["phone"] = rng.choice([
                f"({area}) {exch}-{line}",
                f"{area}.{exch}.{line}",
                f"{area}{exch}{line}",
                f"+1-{area}-{exch}-{line}",
            ])
        elif category == "invalid_date_of_birth":
            row["date_of_birth"] = rng.choice(["2024-02-30", "1990-13-05", "not-a-date"])
        elif category == "non_standard_date_format":
            d = date(rng.randint(1960, 2000), rng.randint(1, 12), rng.randint(1, 28))
            row["date_of_birth"] = rng.choice([
                d.strftime("%m/%d/%Y"), d.strftime("%d-%m-%Y"), d.strftime("%B %d, %Y"),
            ])
        elif category == "future_date_of_birth":
            future = date.today() + timedelta(days=rng.randint(30, 3650))
            row["date_of_birth"] = future.isoformat()
        elif category == "age_above_150":
            row["date_of_birth"] = date(rng.randint(1830, 1870), rng.randint(1, 12), rng.randint(1, 28)).isoformat()
        elif category == "invalid_account_status":
            row["account_status"] = rng.choice(["pending", "closed", "unknown", "ACTIVE-ish"])
        elif category == "empty_first_name":
            row["first_name"] = ""
        elif category == "name_with_invalid_characters":
            row["last_name"] = rng.choice(["O'Br13n", "Smith$", "Doe#1", "123456"])
        elif category == "name_too_long":
            row["first_name"] = "Maximilianus" * 5  # far beyond 50 chars
        elif category == "address_too_short":
            row["address"] = rng.choice(["1 A St", "N/A", "??"])
        elif category == "inconsistent_capitalization":
            row["first_name"] = row["first_name"].upper()
            row["last_name"] = row["last_name"].lower()
            row["account_status"] = row["account_status"].upper()
        elif category == "inconsistent_whitespace":
            row["first_name"] = f"  {row['first_name']}  "
            row["last_name"] = f" {row['last_name']}"
            row["account_status"] = f" {row['account_status']} "
        elif category == "invalid_created_date":
            row["created_date"] = rng.choice(["2026-02-30", "13/40/2026", "not-a-date"])

        inventory.bump(category)

    return rows, inventory


def write_dataset(path: Path = RAW_DATA_FILE) -> ErrorInventory:
    """Generate the dataset and write it to `path` as CSV. Returns the ErrorInventory."""
    rows, inventory = generate_dataset()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=EXPECTED_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return inventory


if __name__ == "__main__":
    inv = write_dataset()
    print(f"Wrote {DATASET_RECORD_COUNT} records to {RAW_DATA_FILE}")
    print("Seeded error categories:")
    for category, count in inv.as_sorted_items():
        print(f"  {category}: {count}")
