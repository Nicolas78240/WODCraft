PY ?= python3
WOD ?= examples/language/team_realized_session.wod
OUT ?= out
VENV ?= .venv
PYBIN ?= $(VENV)/bin/python
PIP ?= $(VENV)/bin/pip

.PHONY: help venv install test clean catalog-build vnext-validate vnext-session vnext-results build-dist publish-testpypi publish-pypi fmt-py

help:
	@echo "Available targets:"
	@echo "  venv            Create virtualenv in $(VENV)"
	@echo "  install         Install requirements and package (editable)"
	@echo "  test            Run pytest"
	@echo "  catalog-build   Build movements catalog -> data/movements_catalog.json"
	@echo "  vnext-validate  Validate a .wod file (language-first)"
	@echo "  vnext-session   Compile session to JSON/ICS"
	@echo "  vnext-results   Aggregate team realized results"
	@echo "  build-dist      Build sdist+wheel into dist/"
	@echo "  publish-testpypi  Upload to TestPyPI (requires .pypirc.local)"
	@echo "  publish-pypi      Upload to PyPI (requires .pypirc.local)"
	@echo "Variables: file=<path>, modules=<dir>, format=json|ics"

$(OUT):
	@mkdir -p $(OUT)

venv:
	@test -d $(VENV) || $(PY) -m venv $(VENV)
	@echo "Virtualenv ready at $(VENV)"

install: venv
	$(PIP) install -U pip
	$(PIP) install -r requirements.txt || true
	$(PIP) install -e .

test:
	@command -v pytest >/dev/null 2>&1 && pytest -q || echo "pytest not installed or no tests."

clean:
	@rm -rf $(OUT) dist build *.egg-info

catalog-build:
	$(PY) -m wodcraft.cli catalog build

vnext-validate:
	wodc validate $(file)

vnext-session:
	wodc session $(file) --modules-path $(or $(modules),modules) --format $(or $(format),json)

vnext-results:
	wodc results $(file) --modules-path $(or $(modules),modules)

build-dist:
	$(PIP) install build twine
	$(PYBIN) -m build
	@echo "Dist built in ./dist"

publish-testpypi:
	@echo "Using .pypirc.local (TestPyPI)"
	@TWINE_PASSWORD=$$(awk -F= '/password/ {print $$2}' .pypirc.local | tr -d ' ') $(PYBIN) -m twine upload --repository testpypi dist/* -u __token__

publish-pypi:
	@echo "Using .pypirc.local (PyPI)"
	@TWINE_PASSWORD=$$(awk -F= '/password/ {print $$2}' .pypirc.local | tr -d ' ') $(PYBIN) -m twine upload dist/* -u __token__

# Python formatting (if black installed)
fmt-py:
	@if command -v black >/dev/null 2>&1; then \
	  echo "Running system black..."; black src scripts wodc_vnext tests; \
	elif [ -x "$(VENV)/bin/black" ]; then \
	  echo "Running venv black..."; $(VENV)/bin/black src scripts wodc_vnext tests; \
	else \
	  echo "black not found. Run 'make install' to install dev tools."; \
	fi
