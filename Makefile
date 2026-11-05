VENV ?= .venv
# The project virtualenv is used when it exists: Homebrew/Debian Python forbid
# system-wide `pip install` (PEP 668). Override with `make ... PY=python3`.
PY ?= $(if $(wildcard $(VENV)/bin/python),$(VENV)/bin/python,python3)
UV := $(shell command -v uv 2>/dev/null)
RUN = PYTHONPATH=src $(PY) -m armstat_trade

.PHONY: help install all catalog fetch-files fetch-db tnved build docs notebook test lint clean

help:
	@echo "make install      create $(VENV) and install the package with dev + notebook extras (editable)"
	@echo "make all          full pipeline: catalog, files, web database, TN VED, build, docs"
	@echo "make catalog      crawl the site pages in en/hy/ru -> data/catalog"
	@echo "make fetch-files  download xlsx/7z files -> data/raw/files"
	@echo "make fetch-db     download the web database (Excel exports) -> data/raw/db"
	@echo "make tnved        extract Russian chapter/section names from the TN VED 2017 document"
	@echo "make build        (re)build data/armstat_trade.duckdb"
	@echo "make docs         regenerate docs/data_dictionary.md from the database"
	@echo "make notebook     execute docs/examples.ipynb against the database and save outputs"
	@echo "make test         run tests"

install:
ifdef UV
	$(UV) venv --allow-existing $(VENV)
	$(UV) pip install --python $(VENV)/bin/python -e '.[dev,notebook]'
else
	python3 -m venv $(VENV)
	$(VENV)/bin/python -m pip install -e '.[dev,notebook]'
endif

all: catalog fetch-files fetch-db tnved build docs

catalog:
	$(RUN) catalog

fetch-files:
	$(RUN) fetch-files

fetch-db:
	$(RUN) fetch-db

tnved:
	$(RUN) tnved

build:
	$(RUN) build

docs:
	$(RUN) docs

# needs the notebook extras (make install)
notebook:
	$(PY) -c "import nbformat; from nbclient import NotebookClient; \
	nb = nbformat.read('docs/examples.ipynb', as_version=4); \
	NotebookClient(nb, timeout=600, kernel_name='python3', resources={'metadata': {'path': 'docs'}}).execute(); \
	nbformat.write(nb, 'docs/examples.ipynb')"

test:
	PYTHONPATH=src $(PY) -m pytest -q

lint:
	ruff check src tests

clean:
	rm -f data/armstat_trade.duckdb data/*.building.duckdb
