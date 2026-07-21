.PHONY: help public-data public-results test lint docs build check clean

PY ?= python3

help:
	@echo "Targets:"
	@echo "  make public-data    Generate the public study dataset"
	@echo "  make public-results Run the public study analysis"
	@echo "  make test           Run pytest"
	@echo "  make lint           Run Ruff"
	@echo "  make docs           Build the MkDocs site"
	@echo "  make build          Build wheel and source distribution"
	@echo "  make check          Run tests, lint, docs, and build"
	@echo "  make clean          Remove caches and generated public outputs"

public-data:
	$(PY) -m studies.distal_pancreatectomy.export_public_data

public-results: public-data
	$(PY) -m studies.distal_pancreatectomy.run_public_analysis

test:
	pytest

lint:
	ruff check src tests studies examples

docs:
	mkdocs build --strict

build:
	$(PY) -m build

check: test lint docs build

clean:
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +
	find . -name '*.pyc' -delete
	rm -rf .pytest_cache site
	rm -f results/public/*.csv results/public/*.json results/public/*.png
