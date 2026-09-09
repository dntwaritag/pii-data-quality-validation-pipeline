# Architecture

## Overview

This is a linear, single-run batch pipeline: one CSV goes in, and a set of
cleaned/masked/quarantined datasets and audit reports come out. There is
no scheduler, queue, or DAG framework involved — `src/pipeline.py` is the
composition root that calls every stage, in order, once per run.

## Data Flow

```mermaid
flowchart TD
    A[("customers_raw.csv")] --> B["Ingestion<br/><small>ingestion.py</small>"]
    B --> C["Profiling<br/><small>profiling.py</small>"]
    C --> C1[["data_quality_report.txt"]]
    C --> D["PII Detection<br/><small>pii_detection.py</small>"]
    D --> D1[["pii_detection_report.txt"]]
    D --> E["Validation<br/><small>validation.py</small><br/>(pre-cleaning)"]
    E --> E1[["validation_results.txt"]]
    E --> F["Cleaning<br/><small>cleaning.py</small>"]
    F --> F1[["cleaning_log.txt"]]
    F --> F2[("customers_quarantined.csv")]
    F --> G["Re-validation<br/><small>validation.py</small><br/>(post-cleaning)"]
    G --> E1
    G --> H[("customers_cleaned.csv")]
    H --> I["Masking<br/><small>masking.py</small>"]
    I --> I1[("customers_masked.csv")]
    I --> I2[["masked_sample.txt"]]
    I --> J["Execution Summary<br/><small>reporting.py</small>"]
    J --> J1[["pipeline_execution_report.txt"]]

    classDef stage fill:#1f2937,stroke:#60a5fa,stroke-width:1px,color:#f9fafb;
    classDef artifact fill:#0f172a,stroke:#34d399,stroke-width:1px,color:#f9fafb;
    classDef data fill:#0f172a,stroke:#fbbf24,stroke-width:1px,color:#f9fafb;
    class B,C,D,E,F,G,I,J stage;
    class C1,D1,E1,F1,I2,J1 artifact;
    class A,F2,H,I1 data;
```

**Legend:** blue = processing stage, yellow = CSV dataset, green = text
report.

## Execution Sequence

```mermaid
sequenceDiagram
    participant CLI as python -m src.pipeline
    participant P as pipeline.run_pipeline()
    participant Ing as ingestion
    participant Prof as profiling
    participant PII as pii_detection
    participant Val as validation
    participant Clean as cleaning
    participant Mask as masking
    participant Rep as reporting

    CLI->>P: run_pipeline()
    P->>Ing: load_customers(RAW_DATA_FILE)
    Ing-->>P: DataFrame (raises IngestionError on failure)
    P->>Prof: profile_dataset(df)
    Prof-->>Rep: render_data_quality_report()
    P->>PII: detect_pii(df)
    PII-->>Rep: render_pii_detection_report()
    P->>Val: validate_dataframe(df)  [pre-cleaning]
    Val-->>Rep: render_validation_report()
    P->>Clean: clean_dataframe(df)
    Clean-->>Rep: render_cleaning_log()
    Clean-->>P: cleaned_df, quarantined_df, log
    P->>Val: validate_dataframe(cleaned_df)  [post-cleaning]
    Val-->>Rep: append_post_cleaning_validation()
    P->>P: write cleaned + quarantined CSVs
    P->>Mask: mask_dataframe(cleaned_df)
    Mask-->>P: masked_df
    P->>P: write masked CSV
    Mask-->>Rep: render_masked_sample()
    P->>Rep: render_pipeline_execution_report(summary)
    P-->>CLI: summary dict (status, counts, stage timings)
```

Every stage is wrapped in a narrow `try/except` (`IngestionError`,
`ValueError`/`KeyError`, or `OSError` depending on what that stage can
actually raise) and re-raised as `PipelineError` with a specific message
— there is no bare `except:` anywhere in the codebase.

## Module Responsibilities

| Module | Responsibility | Depends on |
|---|---|---|
| `config.py` | Paths and tunable constants, env-var overridable. | — |
| `generate_dataset.py` | Builds the synthetic dataset with a documented, seeded error inventory. | `config` |
| `ingestion.py` | Loads and schema-checks the raw CSV. | `config` |
| `profiling.py` | Part 1 data-quality analysis. | `config` |
| `pii_detection.py` | Part 2 PII classification + regex detection (`EMAIL_PATTERN`/`PHONE_PATTERN`, reused by validation/cleaning). | — |
| `validation.py` | Part 3 per-row rule validation; single source of truth for "is this row valid," called both pre- and post-cleaning. | `config`, `pii_detection` |
| `cleaning.py` | Part 4 normalization + quarantine. | `config`, `validation`, `pii_detection` |
| `masking.py` | Part 5 masking functions. | — |
| `reporting.py` | Renders every `.txt` report from real computed results — no hand-written numbers. | `cleaning`, `masking`, `validation` (types only) |
| `pipeline.py` | Part 6 orchestration: logging, per-stage timing, error handling, wiring every stage together. | all of the above |

```mermaid
flowchart LR
    config --> ingestion
    config --> profiling
    config --> validation
    config --> cleaning
    pii_detection --> validation
    pii_detection --> cleaning
    validation --> cleaning
    ingestion --> pipeline
    profiling --> pipeline
    pii_detection --> pipeline
    validation --> pipeline
    cleaning --> pipeline
    masking --> pipeline
    reporting --> pipeline
    cleaning --> reporting
    masking --> reporting
```

`pipeline.py` is the only module that imports everything; every other
module is a plain function/dataclass library with no side effects beyond
what it's explicitly asked to write, which is what makes each one
independently unit-testable (see `tests/`).

## Repository Layout

```
pii-data-quality-validation-pipeline/
├── src/                  # pipeline source (see table above)
├── tests/                # pytest suite, one file per module + integration
├── data/                 # customers_raw.csv (generated, seeded)
├── outputs/              # cleaned / masked / quarantined CSVs
├── reports/              # all six required .txt reports
├── docs/                 # architecture.md (this file), data_governance.md
├── logs/                 # pipeline.log (git-ignored; .gitkeep tracked)
├── reflection.md
├── README.md
├── Makefile              # make help for the full target list
├── Dockerfile / docker-entrypoint.sh / .dockerignore
├── requirements.txt
└── .gitignore / .env.example
```

## Validation Boundaries

Validation runs **twice** against the exact same rule set
(`validate_dataframe()`): once on the raw data (to measure how bad the
input is) and once on the cleaned data (to prove cleaning actually
worked, rather than just claiming it did). Cleaning does not duplicate
the rules — it normalizes, then calls the same validator and quarantines
whatever still fails.

## Output Strategy

Three CSVs come out of the pipeline, each with a distinct audience:

| File | Audience | Contains PII? |
|---|---|---|
| `outputs/customers_cleaned.csv` | Internal analytics needing full fidelity | Yes |
| `outputs/customers_masked.csv` | Broader analytical access | Reduced (see masking rules) |
| `outputs/customers_quarantined.csv` | Data-quality review / audit | Yes — same access tier as cleaned |

Reports (`reports/*.txt`) are safe for the widest audience: counts,
classifications, and (because this dataset is synthetic) customer IDs as
row identifiers — never full records.

## Performance & Observability

No code profiler (`cProfile`, `line_profiler`) is used — this is a
sub-second batch job over a few hundred rows, where per-line CPU
profiling wouldn't add much. What *is* tracked is wall-clock duration per
stage (`_stage_timer` in `pipeline.py`), logged and included in
`pipeline_execution_report.txt` — the practically useful equivalent of a
profiler at this scale, and enough to spot a stage that starts taking
disproportionately long as the dataset grows.

Structured logs go to both stdout and `logs/pipeline.log`. Every log line
is a count, a file path, a row number, or a stage name — never a raw PII
value.
