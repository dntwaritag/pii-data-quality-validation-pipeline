.PHONY: help install generate run test clean docker-build docker-run docker-test all

.DEFAULT_GOAL := help

## help: Show this list of available targets.
help:
	@echo "Available targets:"
	@grep -E '^## ' Makefile | sed -E 's/^## /  /'

## install: Create a venv and install dependencies.
install:
	python3 -m venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -r requirements.txt

## generate: Regenerate the synthetic raw dataset (seeded, reproducible).
generate:
	python3 -m src.generate_dataset

## run: Run the full profiling -> PII detection -> validation -> cleaning -> masking -> reporting pipeline.
run:
	python3 -m src.pipeline

## test: Run the automated test suite.
test:
	python3 -m pytest -q

## all: Generate the dataset, run the pipeline, then run the tests.
all: generate run test

## clean: Remove generated artifacts and caches (keeps source and .git untouched).
clean:
	rm -rf outputs/* reports/* logs/*.log
	find . -type d -name "__pycache__" -exec rm -rf {} +
	rm -rf .pytest_cache

## docker-build: Build the Docker image.
docker-build:
	docker build -t pii-data-quality-pipeline .

## docker-run: Run the pipeline in a container; outputs/reports/logs are bind-mounted to the host.
docker-run:
	docker run --rm \
		-v "$(PWD)/outputs:/app/outputs" \
		-v "$(PWD)/reports:/app/reports" \
		-v "$(PWD)/logs:/app/logs" \
		pii-data-quality-pipeline

## docker-test: Run the test suite inside a container.
docker-test:
	docker run --rm --entrypoint pytest pii-data-quality-pipeline -q

## compose-run: Run the pipeline via docker compose (equivalent to docker-run, declarative volumes).
compose-run:
	docker compose run --rm pipeline

## compose-test: Run the test suite via docker compose.
compose-test:
	docker compose run --rm test
