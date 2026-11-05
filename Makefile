VENV ?= .venv
# The project virtualenv is used when it exists: Homebrew/Debian Python forbid
# system-wide `pip install` (PEP 668). Override with `make ... PY=python3`.
PY ?= $(if $(wildcard $(VENV)/bin/python),$(VENV)/bin/python,python3)
UV := $(shell command -v uv 2>/dev/null)
RUN = PYTHONPATH=src $(PY) -m armstat_trade

.PHONY: help install all catalog fetch-files fetch-db tnved build docs notebook lab release-pack release download download-raw download-parquet test lint clean

help:
	@echo "make install      create $(VENV) and install the package with dev + notebook extras (editable)"
	@echo "make all          full pipeline: catalog, files, web database, TN VED, build, docs"
	@echo "make catalog      crawl the site pages in en/hy/ru -> data/catalog"
	@echo "make fetch-files  download xlsx/7z files -> data/raw/files"
	@echo "make fetch-db     download the web database (Excel exports) -> data/raw/db"
	@echo "make tnved        extract Russian chapter/section names from the TN VED 2017 document"
	@echo "make build        (re)build data/armstat_trade.duckdb"
	@echo "make docs         regenerate docs/data_dictionary.md and docs/*/inventory.md"
	@echo "make notebook     execute docs/examples.ipynb against the database and save outputs"
	@echo "make lab          open docs/examples.ipynb in Jupyter Lab (interactive)"
	@echo "make download     get the latest data snapshot (database) from GitHub releases"
	@echo "make download-raw get the raw data of the latest snapshot (then: make build)"
	@echo "make download-parquet  get every table as Parquet -> data/parquet"
	@echo "make release-pack pack the snapshot into data/release/<tag> (no upload)"
	@echo "make release      pack and publish the snapshot as a GitHub release (needs gh, clean pushed HEAD)"
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
	$(PY) scripts/run_notebook.py docs/examples.ipynb

# interactive: opens the browser on the notebook; settings in scripts/jupyter_lab_config.py; stop with Ctrl+C
lab:
	$(VENV)/bin/jupyter trust docs/examples.ipynb
	$(VENV)/bin/jupyter lab --config scripts/jupyter_lab_config.py docs/examples.ipynb

# data snapshots in GitHub releases (src/armstat_trade/release.py); TAG=data-YYYY-MM-DD to pick one
TAG ?= latest

download:
	$(RUN) download --tag $(TAG) --part db

download-raw:
	$(RUN) download --tag $(TAG) --part raw

download-parquet:
	$(RUN) download --tag $(TAG) --part parquet

release-pack:
	$(RUN) release --pack-only

release:
	$(RUN) release

test:
	PYTHONPATH=src $(PY) -m pytest -q

lint:
	ruff check src tests scripts

clean:
	rm -f data/armstat_trade.duckdb data/*.building.duckdb
