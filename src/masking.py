"""
Part 5 — PII Masking.

Deterministic, one-way-in-effect masking functions applied to the cleaned
dataset. Income decision (the assignment leaves this open): income is
retained unmasked in `customers_masked.csv`. Rationale: income here is an
aggregate financial figure, not a direct identifier, and the assignment's
downstream value of the dataset is largely analytical (income
distribution, quality/validation metrics). Masking a continuous field
like income (e.g., bucketing) would reduce analytical utility while
providing little added privacy protection beyond what removing direct
identifiers already achieves, since income alone rarely re-identifies
someone. This decision is documented again in reflection.md and
docs/data_governance.md.
"""

from __future__ import annotations

import pandas as pd


def mask_name(value: str) -> str:
    """'John' -> 'J***'. Empty/whitespace-only input stays empty."""
    stripped = value.strip()
    if not stripped:
        return ""
    return f"{stripped[0]}***"


def mask_email(value: str) -> str:
    """'john.doe@gmail.com' -> 'j***@gmail.com'. Preserves the domain."""
    stripped = value.strip()
    if not stripped or "@" not in stripped:
        return "***"
    local, _, domain = stripped.partition("@")
    first_char = local[0] if local else ""
    return f"{first_char}***@{domain}"


def mask_phone(value: str) -> str:
    """'555-123-4567' -> '***-***-4567'. Expects the normalized XXX-XXX-XXXX shape."""
    stripped = value.strip()
    if not stripped:
        return ""
    digits = "".join(ch for ch in stripped if ch.isdigit())
    if len(digits) < 4:
        return "***-***-****"
    last_four = digits[-4:]
    return f"***-***-{last_four}"


def mask_address(_value: str) -> str:
    """Always replace with the fixed placeholder, per the assignment spec."""
    return "[MASKED ADDRESS]"


def mask_dob(value: str) -> str:
    """'1985-03-15' -> '1985-**-**'. Expects normalized YYYY-MM-DD input."""
    stripped = value.strip()
    if len(stripped) >= 4 and stripped[:4].isdigit():
        return f"{stripped[:4]}-**-**"
    return "****-**-**"


def mask_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Apply every masking rule to a cleaned DataFrame and return the masked copy."""
    masked = df.copy()
    masked["first_name"] = masked["first_name"].apply(mask_name)
    masked["last_name"] = masked["last_name"].apply(mask_name)
    masked["email"] = masked["email"].apply(mask_email)
    masked["phone"] = masked["phone"].apply(mask_phone)
    masked["address"] = masked["address"].apply(mask_address)
    masked["date_of_birth"] = masked["date_of_birth"].apply(mask_dob)
    # income intentionally left unmasked -- see module docstring.
    return masked
