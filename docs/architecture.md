# Architecture

## Data Flow

```
customers_raw.csv
       │
       ▼
   Ingestion  (src/ingestion.py)
       │  loads CSV as raw strings, verifies schema
       ▼
   Profiling  (src/profiling.py)
       │  completeness, types, formats, uniqueness, invalid values
       ├──────────────► reports/data_quality_report.txt
       ▼
  PII Detection  (src/pii_detection.py)
       │  classification + regex email/phone detection
       ├──────────────► reports/pii_detection_report.txt
       ▼
   Validation  (src/validation.py)          [pre-cleaning]
       │  every field rule, per-row pass/fail with reasons
       ├──────────────► reports/validation_results.txt
       ▼
    Cleaning  (src/cleaning.py)
       │  repair what's safely repairable; quarantine the rest
       ├──────────────► reports/cleaning_log.txt
       ├──────────────► outputs/customers_quarantined.csv
       ▼
 Re-validation  (src/validation.py)          [post-cleaning]
       │  confirms the cleaned set actually passes every rule
       ├──────────────► reports/validation_results.txt (appended)
       ▼
   Clean Data
       │
       ├──────────────► outputs/customers_cleaned.csv
       ▼
     Masking  (src/masking.py)
       │  deterministic, one-way masking of direct identifiers
       ├──────────────► outputs/customers_masked.csv
       ├──────────────► reports/masked_sample.txt
       ▼
 Execution Summary  (src/pipeline.py + src/reporting.py)
       │  per-stage timings, row-count reconciliation, file list
       └──────────────► reports/pipeline_execution_report.txt
```

## Module Responsibilities

| Module | Responsibility | Depends on |
|---|---|---|
| `config.py` | Paths and tunable constants, env-var overridable. | — |
| `generate_dataset.py` | Builds the synthetic dataset with a documented error inventory. | `config` |
| `ingestion.py` | Loads and schema-checks the raw CSV. | `config` |
| `profiling.py` | Part 1 data-quality analysis. | `config` |
| `pii_detection.py` | Part 2 PII classification + regex detection. | — (exposes `EMAIL_PATTERN`/`PHONE_PATTERN` reused by validation/cleaning) |
| `validation.py` | Part 3 per-row rule validation. | `config`, `pii_detection` (regex patterns) |
| `cleaning.py` | Part 4 normalization + quarantine. | `config`, `validation`, `pii_detection` |
| `masking.py` | Part 5 masking functions. | — |
| `reporting.py` | Renders every `.txt` report from real computed results. | `cleaning`, `masking`, `validation` (types only) |
| `pipeline.py` | Part 6 orchestration: logging, timing, error handling, wiring every stage together. | all of the above |

This is intentionally a **linear pipeline**, not a DAG framework (no
Airflow/Prefect/Dagster) — the assignment's scope is a single dataset run
end-to-end, not a scheduled multi-dependency workflow. `pipeline.py` is
the composition root; every other module is a plain function/dataclass
library with no side effects beyond what it's explicitly asked to write,
which is what makes each module independently unit-testable (see
`tests/`).

## Validation Boundaries

Validation runs **twice**: once on the raw data (to measure how bad the
input is) and once on the cleaned data (to prove cleaning actually
worked, rather than just claiming it did). `validate_dataframe()` is the
single source of truth for "is this row valid" in both cases — cleaning
doesn't duplicate the rules, it calls the same validator after
normalizing and quarantines whatever still fails.

## Error-Handling Strategy

Each pipeline stage in `pipeline.py` is wrapped in a `try/except` that
catches only the exception types that stage can realistically raise
(`IngestionError` for loading, `ValueError`/`KeyError` for the
DataFrame-processing stages, `OSError` for file writes) and re-raises as
`PipelineError` with a specific message. There is no bare `except:`
anywhere in the codebase — see the security/quality scan noted in
`DELIVERY_NOTES.md`.

## Logging Strategy

Structured logging goes to both stdout and `logs/pipeline.log`. Every log
line is a count, a file path, a row number, or a stage name — never a
raw PII value (see `pii_detection.py` / `reporting.py` module docstrings
for the specific restriction). Per-stage wall-clock timing
(`_stage_timer` in `pipeline.py`) is logged and included in
`pipeline_execution_report.txt`, which is the lightweight, pipeline-scale
equivalent of a code profiler for a batch job of this size (see the
`pipeline.py` module docstring for why a full profiler like `cProfile`
wasn't used).

## Output Strategy

Three CSVs come out of the pipeline, each with a distinct audience:

| File | Audience | Contains PII? |
|---|---|---|
| `outputs/customers_cleaned.csv` | Internal analytics needing full fidelity | Yes |
| `outputs/customers_masked.csv` | Broader analytical access | Reduced (see masking rules) |
| `outputs/customers_quarantined.csv` | Data-quality review / audit | Yes (same access tier as cleaned) |

Reports (`reports/*.txt`) are safe for the widest audience: they contain
only counts, classifications, and (because this dataset is synthetic)
customer IDs as row identifiers — never full records.
