# Reflection

## 1. Top 5 Data Quality Issues

**Missing required fields (email, phone, income, address, first_name).**
Detection: `completeness()` in `src/profiling.py` computes a missing
count/percentage per column directly from the raw CSV. Remediation: none
of these are safely repairable without inventing data, so rows with a
missing mandatory field are quarantined during cleaning rather than
filled with a placeholder. Impact: this was the single largest driver of
row removal (20 of the 72 removed rows failed a `non_empty` rule).

**Invalid or impossible dates (bad date_of_birth/created_date, future
DOB, age > 150).** Detection: `validate_dataframe()` attempts to parse
each date against four known formats; anything unparseable, in the
future, or implying an age over 150 fails. Remediation: dates in a
recognized non-ISO format (e.g. `MM/DD/YYYY`) are reformatted to
`YYYY-MM-DD` automatically; genuinely invalid or implausible dates cause
quarantine. Impact: 12 of 220 raw rows failed a date_of_birth rule, plus
4 more on created_date.

**Out-of-range or negative income.** Detection: `invalid_values()` casts
the income column to float and checks it against `[0, 10,000,000]`.
Remediation: values outside this range are not corrected (there is no
safe way to guess a "real" income), so those rows are quarantined.
Impact: 12 rows failed an income rule (negative, above threshold, or
missing).

**Inconsistent phone/name/status formatting.** Detection:
`format_issues()` in profiling buckets phone numbers by shape and flags
whitespace/capitalization inconsistencies in names and account_status.
Remediation: this is the one category that is fully auto-repairable —
`cleaning.py` normalizes any recognized phone shape to `XXX-XXX-XXXX`,
collapses whitespace, and normalizes name/status casing. Impact: 39
individual field values were reformatted (12 first names, 10 last names,
9 statuses, 4 dates, 4 phones) without removing a single row for this
reason alone.

**Duplicate customer_id values.** Detection: `uniqueness()` flags every
row sharing a customer_id with another row. Remediation: the first
occurrence is kept and treated as authoritative; later duplicates are
removed, since there is no reliable way to tell which duplicate is
"correct." Impact: 4 rows removed.

## 2. Risk Assessment

- **Names**: direct identifiers, but low risk in isolation (many people
  share a name); risk rises sharply once paired with email/phone/address.
- **Emails**: direct identifiers and a common cross-service correlation
  key — an exposed email can be used to link this dataset to other
  breaches or services.
- **Phones**: direct identifiers with a higher misuse potential (spam,
  account-recovery attacks, SIM-swap-style social engineering).
- **Addresses**: direct identifiers revealing physical location; the
  highest-sensitivity direct identifier here because it enables real-world
  contact/harm, not just digital correlation.
- **Date of birth**: not identifying alone, but a classic quasi-identifier
  used in identity verification and fraud; combined with ZIP/name it can
  narrow down a specific person.
- **Income**: sensitive but not identifying by itself; the risk is
  reputational/financial (e.g. targeted scams) rather than
  re-identification.
- **Customer IDs**: not sensitive alone, but they are the join key that
  links every other field back to one person — protecting the mapping
  from customer_id to the direct identifiers is as important as
  protecting the identifiers themselves.

## 3. Masking Trade-offs

- **Privacy protection**: masking removes exact values for names, emails,
  phones, addresses, and the month/day of birth, which is enough to
  prevent casual re-identification from the masked file alone.
- **Analytical utility**: first-initial and email-domain are preserved,
  which supports some aggregate analysis (e.g. domain distribution)
  without exposing the underlying identity. Income was left unmasked
  entirely to preserve its full analytical value (see next section).
- **Traceability**: masking here is one-directional by design — there is
  no stored mapping back to the original value in the masked file. If an
  analyst needs to trace a masked record back to a real customer, they
  must go through the cleaned (unmasked) dataset under stricter access
  controls, not the masked one.
- **Loss of information**: masking DOB down to birth year discards the
  exact date needed for age-in-days calculations; if a future use case
  needs exact age, a separate `age_at_masking` field would need to be
  computed before masking rather than after.
- **Reversibility**: the masking functions in `src/masking.py` are lossy
  (e.g. `mask_name` keeps only the first character) and not designed to be
  reversible. This is intentional: reversible masking (like simple
  substitution or encryption with a stored key) would need its own key
  management story, which this project's scope does not require.

## 4. Validation Strategy

- **Rule-based validation strengths**: rules are explicit, deterministic,
  and fast to run against every row; failure reasons are specific enough
  to drive automatic remediation decisions (see `cleaning.py`).
- **Limitations**: the rules encode assumptions about what "valid" looks
  like (e.g. only 5 recognized phone shapes, only 4 recognized date
  formats) that may not generalize to every real-world input format.
- **False positives**: a genuinely valid but unusual phone or date format
  not on the recognized list would be flagged invalid even though it is
  real data — this is a deliberate conservative choice (better to
  quarantine and review than silently mis-normalize).
- **False negatives**: the email regex accepts syntactically valid but
  non-existent addresses (e.g. `nobody@example.com` where the mailbox
  does not exist); format validity is not the same as deliverability, and
  this pipeline does not attempt to verify deliverability.

## 5. Production Operations

- **Scheduling**: run as a batch job (e.g. daily via cron/Airflow) rather
  than continuously, since the dataset is not a live stream.
- **Monitoring**: track the pass rate over time (from
  `pipeline_execution_report.txt`); a sudden change signals either an
  upstream source problem or a code regression.
- **Logging**: `src/pipeline.py` writes structured, count-only logs to
  `logs/pipeline.log` — no raw PII, per the assignment's logging
  restriction.
- **Failure handling & retries**: each pipeline stage raises a specific
  `PipelineError` with a clear message rather than crashing with a raw
  traceback; a scheduler could retry ingestion (e.g. transient file-system
  issues) but should not blindly retry a validation/cleaning failure,
  since that usually indicates a real data problem, not a transient one.
- **Alerting**: alert when `status != SUCCESS`, when the rejected-record
  count exceeds a threshold, or when any report's numbers fail the
  internal consistency check (input = cleaned + removed).
- **Data retention**: raw data with direct identifiers should have a
  short, explicit retention window; masked outputs, being lower risk,
  can be retained longer for analytics.
- **Access control**: raw/cleaned data restricted to roles that need
  pre-masking access; masked data available more broadly; reports
  (counts only) available to a wider audience still.
- **Auditability**: every run's `cleaning_log.txt` and
  `pipeline_execution_report.txt` provide a record of exactly what was
  changed and why, tied to (synthetic) customer IDs.

## 6. Lessons Learned

Building this pipeline reinforced that most "cleaning" decisions are
really policy decisions in disguise: whether to repair, quarantine, or
retain-as-null is not a technical question so much as a judgment about
how much invented data a downstream consumer can tolerate. Making that
policy explicit per field (in `cleaning.py`'s module docstring and in
`cleaning_log.txt`'s output) made the rest of the implementation
mechanical. On privacy, classifying fields into direct/sensitive/
quasi-identifier categories up front made the masking design fall out
naturally — each category had an obvious, defensible treatment. On
automation and reproducibility, seeding the synthetic dataset generator
(`DATASET_RANDOM_SEED` in `src/config.py`) and re-running the pipeline
from scratch during development caught several bugs early (e.g. an
initial version of the phone regex accepted 11-digit numbers with no
country code check) that would have been much harder to catch against a
one-off hand-written dataset. On governance, writing
`docs/data_governance.md` alongside the code — rather than after — made
it obvious where the logging code needed to be more careful (an early
draft of `pipeline.py` logged full row counts per email domain, which was
harmless here but would not generalize safely to a smaller real dataset
where domain counts could re-identify someone).
