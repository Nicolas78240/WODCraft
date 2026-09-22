PY ?= python3
VENV ?= .venv

.PHONY: help install test lint bundle swift-resources swift-test check

help:
	@echo "install         create .venv and install the package with its dev extras"
	@echo "test            pytest"
	@echo "lint            ruff + mypy"
	@echo "check           the whole gate: tests, library, schema, lint"
	@echo "bundle          write the JSON bundle an application embeds (bundle/)"
	@echo "swift-resources refresh swift/WODCraftKit resources from this implementation"
	@echo "swift-test      swift test in swift/WODCraftKit"

install:
	$(PY) -m venv $(VENV)
	$(VENV)/bin/pip install -U pip
	$(VENV)/bin/pip install -e ".[dev,mcp,lsp]"

test:
	pytest

lint:
	ruff check src tests
	ruff format --check src tests
	mypy

bundle:
	wodc bundle bundle

check: test
	wodc check src/wodcraft/library/*/*.wod examples/*.wod
	wodc fmt --check src/wodcraft/library/*/*.wod examples/*.wod
	$(PY) spec/validate_schema.py
	$(MAKE) lint

swift-resources:
	wodc bundle swift/WODCraftKit/Sources/WODCraftKit/Resources
	@rm -f swift/WODCraftKit/Sources/WODCraftKit/Resources/bundle.json
	@rm -rf swift/WODCraftKit/Tests/WODCraftKitTests/Resources/conformance
	@cp -R spec/conformance swift/WODCraftKit/Tests/WODCraftKitTests/Resources/
	@echo "Swift resources refreshed"

swift-test:
	cd swift/WODCraftKit && swift test
