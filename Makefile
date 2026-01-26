SHELL := /bin/sh

.DEFAULT_GOAL := help

PYTHON ?= python3
PROVIDER ?= $(STEWARD_PROVIDER)
MODEL ?= $(STEWARD_MODEL)
PROVIDER := $(if $(PROVIDER),$(PROVIDER),azure)
MODEL := $(if $(MODEL),$(MODEL),gpt-5-mini)
ENV_FILE ?= .env
ifneq (,$(wildcard $(ENV_FILE)))
include $(ENV_FILE)
ENV_VARS := $(shell sed -n 's/^\([A-Za-z0-9_][A-Za-z0-9_]*\)=.*/\1/p' $(ENV_FILE))
export $(ENV_VARS)
endif

.PHONY: help install test lint clean scenario inception

help: ## Show targets
	@grep -E '^[a-zA-Z_-]+:.*?##' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "%-16s %s\n", $$1, $$2}'

install: ## Install Python dependencies (editable)
	$(PYTHON) -m pip install -e .

test: ## Run pytest suite with coverage
	$(PYTHON) -m pytest -q

lint: ## Run ruff lint
	ruff check .

scenario: ## Run a sample steward scenario (list workspace files)
	@echo "== Steward scenario: list workspace files =="
	STEWARD_ALLOW_EXECUTE=1 $(PYTHON) -m steward.cli --provider $(PROVIDER) --model $(MODEL) "List files in the workspace" --pretty

inception: ## Run a meta scenario inside sandbox/
	@echo "== Steward scenario (sandbox): list files =="
	STEWARD_ALLOW_EXECUTE=1 $(PYTHON) -m steward.cli --provider $(PROVIDER) --model $(MODEL) --pretty --sandbox sandbox "Create a project for an LLM harness to test models in an environment that mimics what GitHub Copilot sees, including common tools"

clean: ## Remove temp artifacts and sandbox outputs
	find . -maxdepth 1 -type f \( -name '.steward-plan.json' -o -name '.steward-plan.json.lock' -o -name '.steward-log.jsonl' -o -name '.steward-exec-audit.log' \) -delete
	find . -maxdepth 1 -type d -name '.pytest_cache' -prune -exec rm -r {} +
	find . -maxdepth 1 -type d -name '*.egg-info' -prune -exec rm -r {} +
	find . -type d -name '__pycache__' -prune -exec rm -r {} +
	@test -d sandbox && find sandbox -type d -name '__pycache__' -prune -exec rm -r {} + || true
	@test -d sandbox && find sandbox -maxdepth 1 -type f \( -name '.steward-plan.json' -o -name '.steward-plan.json.lock' -o -name '.steward-log.jsonl' -o -name '.steward-exec-audit.log' \) -delete || true
