# Data Governance

This project processes a synthetic customer dataset. This document
describes the governance controls that would matter even though the data
itself is fictitious, because the same pipeline logic would apply to real
customer data.

## Data Classification

| Category | Fields | Notes |
|---|---|---|
| Direct identifiers | first_name, last_name, email, phone, address | Directly identify or contact a person. |
| Sensitive personal information | date_of_birth, income | Not identifying alone, but sensitive and used in identity verification / financial profiling. |
| Quasi-identifier metadata | customer_id, created_date | Low sensitivity alone, but customer_id links every other field for a person. |

## PII Identification

`src/pii_detection.py` implements the classification above and regex-based
detection for email and phone so the pipeline can quantify how much of the
dataset is PII-bearing before any cleaning or masking happens
(`reports/pii_detection_report.txt`).

## Least-Privilege Access

In a real deployment:
- Raw data (`data/customers_raw.csv`) would be restricted to the roles that
  need pre-cleaning access (data engineering), not general analytics users.
- The masked dataset (`outputs/customers_masked.csv`) is the appropriate
  artifact for broader analytical access.
- Reports (`reports/*.txt`) intentionally contain counts and metadata only,
  never raw PII values, so they can be shared more widely without
  re-exposing the data they describe.

## Data Minimization

The masking functions in `src/masking.py` reduce names, emails, phone
numbers, and addresses to the minimum detail needed for a human to
recognize a masked record belongs to *a* customer, without exposing which
one. Income is retained unmasked as a deliberate, documented trade-off
(see `reflection.md`) because it is not independently identifying and has
high analytical value.

## Validation

`src/validation.py` enforces explicit, documented rules per field
(type, format, range, allowed values). Validation runs both before and
after cleaning so the pipeline can show, with real numbers, how many
issues were resolved and whether any remain.

## Auditability

Every pipeline run produces:
- `pipeline_execution_report.txt` — a timestamped summary of what ran and
  what it produced.
- `cleaning_log.txt` — every normalization and every row removal, with the
  specific reason and (for this synthetic dataset) the affected
  customer_id.
- `logs/pipeline.log` — a structured, append-only log of each pipeline
  stage.

## Retention

This project does not implement automated retention policies, since it
runs as a single batch job rather than a persistent data store. In a
production deployment, raw data with direct identifiers would need an
explicit retention window and a scheduled deletion job; the cleaned/masked
outputs, being lower-risk, could be retained longer for analytics.

## Secure Handling / Logging Restrictions

`src/pipeline.py` logs only counts, file paths, and row numbers — never
full emails, phone numbers, addresses, or names (see the module docstrings
in `pii_detection.py` and `reporting.py`). Reports likewise show counts,
classifications, and (only because this dataset is synthetic) customer IDs
as safe row identifiers, never full records.
