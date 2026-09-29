PY ?= python3
VENV ?= .venv
# works from a checkout without installing: the package lives in src/
WODC ?= PYTHONPATH=src $(PY) -m wodcraft.cli

.PHONY: help install test lint bundle swift-resources swift-test check

help:
	@echo "install         create .venv and install the package with its dev extras"
	@echo "test            pytest"
	@echo "lint            ruff + mypy"
	@echo "check           the whole gate: tests, library, schema, lint"
	@echo "bundle          write the JSON bundle an application embeds (bundle/)"
	@echo "swift-resources refresh swift/WODCraftKit resources from this implementation"
	@echo "swift-test      swift test in swift/WODCraftKit"
	@echo "swift-diff      compile the same sources with both implementations and compare"

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
	$(WODC) bundle bundle

check: test
	$(WODC) check src/wodcraft/library/*/*.wod examples/*.wod
	$(WODC) fmt --check src/wodcraft/library/*/*.wod examples/*.wod
	PYTHONPATH=src $(PY) spec/validate_schema.py
	$(MAKE) lint

swift-resources:
	$(WODC) bundle swift/WODCraftKit/Sources/WODCraftKit/Resources
	@rm -f swift/WODCraftKit/Sources/WODCraftKit/Resources/bundle.json
	@rm -rf swift/WODCraftKit/Tests/WODCraftKitTests/Resources/conformance
	@cp -R spec/conformance swift/WODCraftKit/Tests/WODCraftKitTests/Resources/
	$(PY) scripts/generate_swift_view_fixtures.py
	@echo "Swift resources refreshed"

swift-test:
	cd swift/WODCraftKit && swift test

swift-diff:
	cd swift/WODCraftKit && swift build -c release --product wodcraftc
	$(PY) scripts/differential_check.py "$$(cd swift/WODCraftKit && swift build -c release --show-bin-path)/wodcraftc" --cases 400
