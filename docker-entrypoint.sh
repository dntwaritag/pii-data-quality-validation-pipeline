#!/usr/bin/env sh
# Container entrypoint: ensure a raw dataset exists, then run the pipeline.
set -e

if [ ! -f "data/customers_raw.csv" ]; then
    echo "No data/customers_raw.csv found -- generating the synthetic dataset."
    python -m src.generate_dataset
fi

exec python -m src.pipeline
