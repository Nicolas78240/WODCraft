PY ?= python3
WODC ?= wodc_merged.py
WOD ?= team_mixer.wod
CATALOG ?= box_catalog.json
TRACK ?= RX
GENDER ?= male
OUT ?= out
VENV ?= .venv
PYBIN ?= $(VENV)/bin/python
PIP ?= $(VENV)/bin/pip

.PHONY: help parse lint run export-json export-html export-ics test clean check-spec demo venv install fmt fmt-py fmt-wod

help:
	@echo "Available targets:"
	@echo "  parse         Parse $${WOD} -> $${OUT}/out.json"
	@echo "  lint          Lint $${WOD} with catalog"
	@echo "  run           Simulate/run $${WOD} (text timeline)"
	@echo "  export-html   Export $${WOD} -> $${OUT}/wod.html"
	@echo "  export-ics    Export $${WOD} -> $${OUT}/wod.ics"
	@echo "  export-json   Export AST -> $${OUT}/wod.json"
	@echo "  check-spec    Lint strictly (treat WARNING as error)"
	@echo "  demo          Lint + export HTML/ICS/JSON with catalog"
	@echo "  venv          Create virtualenv in $(VENV)"
	@echo "  install       Install requirements into $(VENV)"
	@echo "  fmt           Format Python (black) and placeholder for WOD DSL"
	@echo "  test          Run pytest (if present)"
	@echo "  clean         Remove $${OUT} artifacts"
	@echo "Variables: WOD, CATALOG, TRACK, GENDER"

$(OUT):
	@mkdir -p $(OUT)

parse: | $(OUT)
	$(PY) $(WODC) parse $(WOD) -o $(OUT)/out.json

lint:
	$(PY) $(WODC) lint $(WOD) --catalog $(CATALOG) --track $(TRACK) --gender $(GENDER)

run:
	$(PY) $(WODC) run $(WOD) --format text

export-html: | $(OUT)
	$(PY) $(WODC) export $(WOD) --to html -o $(OUT)/wod.html

export-ics: | $(OUT)
	$(PY) $(WODC) export $(WOD) --to ics -o $(OUT)/wod.ics

export-json: | $(OUT)
	$(PY) $(WODC) export $(WOD) --to json -o $(OUT)/wod.json

# Strict spec check: fail on WARNING or ERROR
check-spec: | $(OUT)
	@set -e; \
	$(PY) $(WODC) lint $(WOD) --catalog $(CATALOG) --track $(TRACK) --gender $(GENDER) | tee $(OUT)/lint.txt; \
	if grep -qE "^WARNING\b" $(OUT)/lint.txt; then \
	  echo "Spec check failed: warnings present" >&2; exit 2; \
	fi

# Demo: lint + export all artifacts with catalog/track/gender
demo: | $(OUT)
	$(PY) $(WODC) lint $(WOD) --catalog $(CATALOG) --track $(TRACK) --gender $(GENDER)
	$(PY) $(WODC) export $(WOD) --to html -o $(OUT)/wod.html --catalog $(CATALOG) --track $(TRACK) --gender $(GENDER)
	$(PY) $(WODC) export $(WOD) --to ics -o $(OUT)/wod.ics --catalog $(CATALOG) --track $(TRACK) --gender $(GENDER)
	$(PY) $(WODC) export $(WOD) --to json -o $(OUT)/wod.json --catalog $(CATALOG) --track $(TRACK) --gender $(GENDER)

test:
	@command -v pytest >/dev/null 2>&1 && pytest -q || echo "pytest not installed or no tests."

clean:
	@rm -rf $(OUT)

# --- Environment & tooling ---
venv:
	@test -d $(VENV) || $(PY) -m venv $(VENV)
	@echo "Virtualenv ready at $(VENV)"

install: venv
	$(PIP) install -U pip
	$(PIP) install -r requirements.txt

# --- Formatting ---
fmt: fmt-py fmt-wod

fmt-py:
	@if command -v black >/dev/null 2>&1; then \
	  echo "Running system black..."; black wodc_merged.py; \
	elif [ -x "$(VENV)/bin/black" ]; then \
	  echo "Running venv black..."; $(VENV)/bin/black wodc_merged.py; \
	else \
	  echo "black not found. Run 'make install' to install dev tools."; \
	fi

# Placeholder for WOD DSL formatting until 'wodc fmt' exists
fmt-wod:
	$(PY) $(WODC) fmt $(WOD) -i
