.DEFAULT_GOAL := help
SHELL := /bin/sh

VENV    ?= .venv
ifeq ($(OS),Windows_NT)
PYTHON  ?= $(VENV)/Scripts/python.exe
else
PYTHON  ?= $(VENV)/bin/python
endif
PYTEST  := $(PYTHON) -m pytest
COV_MIN ?= 85

.PHONY: help install install-dev demo run single-cycle autonomous status clock agents \
        memory graveyard tournament test test-unit test-fast architecture-test contract-test \
        integration-test property-test regression-test e2e-test coverage lint lint-fix \
        typecheck security check clean reset docker-build docker-run

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# --- setup ------------------------------------------------------------------

install: ## Create the virtualenv and install the package with dev extras
	python -m venv $(VENV)
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e ".[dev]"

install-dev: install ## Alias for install

# --- running ----------------------------------------------------------------

demo: ## Run one complete creative cycle offline and print the winner
	$(PYTHON) -m creative_brain.cli.main demo

single-cycle: ## Run exactly one cycle with structured logs
	$(PYTHON) -m creative_brain.cli.main --mock start --single-cycle

autonomous: ## Keep the runtime alive continuously (Ctrl-C shuts down gracefully)
	$(PYTHON) -m creative_brain.cli.main --mock start --autonomous

run: single-cycle ## Alias for single-cycle

status: ## Show the current state of the mind
	$(PYTHON) -m creative_brain.cli.main status

clock: ## Show the circadian state
	$(PYTHON) -m creative_brain.cli.main clock status

agents: ## List every declared agent
	$(PYTHON) -m creative_brain.cli.main agents list

memory: ## Inspect memory
	$(PYTHON) -m creative_brain.cli.main memory inspect

graveyard: ## Inspect buried ideas
	$(PYTHON) -m creative_brain.cli.main graveyard inspect

tournament: ## Inspect the latest tournament
	$(PYTHON) -m creative_brain.cli.main tournament inspect

# --- quality ----------------------------------------------------------------

test: ## Run the whole test suite
	$(PYTEST)

test-fast: ## Run everything except the end-to-end scenarios
	$(PYTEST) -m "not e2e"

test-unit: ## Unit tests only
	$(PYTEST) tests/unit

architecture-test: ## Prove the domain has no outward dependencies
	$(PYTEST) tests/architecture -v

contract-test: ## Prove every adapter satisfies its port
	$(PYTEST) tests/contract

integration-test: ## Repositories, event bus, scheduler, prompts, CLI
	$(PYTEST) tests/integration

property-test: ## Invariants under generated input
	$(PYTEST) tests/property

regression-test: ## The guarantees this system must never break
	$(PYTEST) tests/regression

e2e-test: ## The full creative cycle, end to end
	$(PYTEST) tests/e2e

coverage: ## Run the suite with a coverage floor on domain + application
	$(PYTEST) --cov=creative_brain.domain --cov=creative_brain.application \
		--cov-report=term-missing:skip-covered --cov-fail-under=$(COV_MIN)

lint: ## Check formatting and style
	$(PYTHON) -m ruff check src tests
	$(PYTHON) -m ruff format --check src tests

lint-fix: ## Fix what can be fixed automatically
	$(PYTHON) -m ruff check --fix src tests
	$(PYTHON) -m ruff format src tests

typecheck: ## Static type checking
	$(PYTHON) -m mypy

security: ## Look for committed secrets and obvious risks
	$(PYTHON) scripts/check_secrets.py

check: lint typecheck test architecture-test coverage security ## Everything CI runs

# --- housekeeping -----------------------------------------------------------

clean: ## Remove caches and build artifacts
	$(PYTHON) scripts/clean.py

reset: ## Wipe generated memory, outputs and logs (CORE_DNA is never touched)
	$(PYTHON) scripts/reset_state.py

# --- containers -------------------------------------------------------------

docker-build: ## Build the container image
	docker build -t pedroarte-creative-brain:latest .

docker-run: ## Run one demo cycle inside the container
	docker compose run --rm creative-brain
