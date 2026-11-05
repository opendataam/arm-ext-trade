PY ?= python3
RUN = PYTHONPATH=src $(PY) -m armstat_trade

.PHONY: help install all catalog fetch-files fetch-db tnved build docs test lint clean

help:
	@echo "make install      install the package and dev dependencies (editable)"
	@echo "make all          full pipeline: catalog, files, web database, TN VED, build, docs"
	@echo "make catalog      crawl the site pages in en/hy/ru -> data/catalog"
	@echo "make fetch-files  download xlsx/7z files -> data/raw/files"
	@echo "make fetch-db     download the web database (Excel exports) -> data/raw/db"
	@echo "make tnved        extract Russian chapter/section names from the TN VED 2017 document"
	@echo "make build        (re)build data/armstat_trade.duckdb"
	@echo "make docs         regenerate docs/data_dictionary.md from the database"
	@echo "make test         run tests"

install:
	$(PY) -m pip install -e '.[dev]'

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

test:
	PYTHONPATH=src $(PY) -m pytest -q

lint:
	ruff check src tests

clean:
	rm -f data/armstat_trade.duckdb data/*.building.duckdb
