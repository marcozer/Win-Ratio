.PHONY: help public-data public-results test docs clean

PY ?= python3

help:
	@echo "Targets:"
	@echo "  make public-data    Generate the public study dataset"
	@echo "  make public-results Run the public study analysis"
	@echo "  make test           Run pytest"
	@echo "  make docs           Build the MkDocs site"
	@echo "  make clean          Remove caches and generated public outputs"

public-data:
	$(PY) -m studies.distal_pancreatectomy.export_public_data

public-results: public-data
	$(PY) -m studies.distal_pancreatectomy.run_public_analysis

test:
	pytest

docs:
	mkdocs build --strict

clean:
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +
	find . -name '*.pyc' -delete
	rm -rf .pytest_cache site
	rm -f results/public/*.csv results/public/*.json results/public/*.png
