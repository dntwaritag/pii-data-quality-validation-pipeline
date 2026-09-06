# Minimal image for running the PII Detection & Data Quality Validation
# Pipeline. Not required to use the project (plain `python -m src.pipeline`
# in a venv works too) -- provided for reproducible, isolated execution.

FROM python:3.12-slim

WORKDIR /app

# Install dependencies first so this layer is cached across code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the project.
COPY src/ src/
COPY tests/ tests/
COPY data/ data/
COPY docker-entrypoint.sh .
RUN chmod +x docker-entrypoint.sh

# Directories the pipeline writes to; mount these as volumes to see
# results on the host (see `make docker-run`).
RUN mkdir -p outputs reports logs

ENTRYPOINT ["./docker-entrypoint.sh"]
