.PHONY: install generate run test clean docker-build docker-run docker-test

# Create a venv and install dependencies.
install:
	python3 -m venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -r requirements.txt

# Regenerate the synthetic raw dataset (seeded, reproducible).
generate:
	python3 -m src.generate_dataset

# Run the full profiling -> PII detection -> validation -> cleaning ->
# masking -> reporting pipeline.
run:
	python3 -m src.pipeline

# Run the automated test suite.
test:
	python3 -m pytest -q

# Remove generated artifacts and caches (keeps source and .git untouched).
clean:
	rm -rf outputs/* reports/* logs/*.log
	find . -type d -name "__pycache__" -exec rm -rf {} +
	rm -rf .pytest_cache

# Build the Docker image.
docker-build:
	docker build -t pii-data-quality-pipeline .

# Run the pipeline inside a container; writes outputs/reports to the
# host via a bind mount so results are visible outside the container.
docker-run:
	docker run --rm \
		-v "$(PWD)/outputs:/app/outputs" \
		-v "$(PWD)/reports:/app/reports" \
		-v "$(PWD)/logs:/app/logs" \
		pii-data-quality-pipeline

# Run the test suite inside a container.
docker-test:
	docker run --rm --entrypoint pytest pii-data-quality-pipeline -q
