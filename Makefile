################################################################################
# Author: Daniel Collier
# GitHub: https://github.com/danielfcollier
# Year: 2025
################################################################################

SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

PYTHON  := .venv/bin/python3
PIP     := .venv/bin/pip
UV      := uv

CSPELL_VERSION = "latest"

SCRIPT_DIR      := $(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))
SRC_DIR         := $(SCRIPT_DIR)/src
DOCS_DIR        := $(SCRIPT_DIR)/docs
APP_DIR         := $(SRC_DIR)/umik_base_app/apps
SCRIPTS_DIR     := $(SRC_DIR)/scripts

# Calibration file path (MUST be set when calling relevant targets)
# Example: make calibrate-umik F="path/to/cal.txt"
F ?= "umik-1/7175488.txt"
OUT ?= "recordings/"
CSV_OUT ?= 
PLOT_OUT ?=
MP3_OUT ?=

SILENT ?=
HELP   ?=

# Styling
GREEN  := \033[0;32m
YELLOW := \033[0;33m
RED    := \033[0;31m
NC     := \033[0m # No Color

.PHONY: all default help clean clean-all venv install lint format check test list-audio-devices get-umik-id calibrate-umik spell-check real-time-meter real-time-meter-default-mic real-time-meter-umik record record-default-mic record-umik test coverage test-publish metrics-analyzer batch-analyze plot-view plot-save enhance-audio convert-audio test-end-to-end lock setup bump-patch bump-minor bump-major install-build-deps vendor build-deb test-deb publish-deb

default: help

help: ## Show this help message.
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ==============================================================================
# Setup & Maintenance
# ==============================================================================

all: install ## Install project dependencies.

clean: ## Remove cache
	@.venv/bin/pip cache purge
	@find . -name "*.pyc" | xargs rm -rf
	@find . -name "*.pyo" | xargs rm -rf
	@find . -name "__pycache__" -type d | xargs rm -rf
	@find . -name "*.coverage" | xargs rm -rf

clean-all: clean ## Remove temporary files and directories.
	@echo -e "$(GREEN)>>> Cleaning up...$(NC)"
	@rm -rf .venv
	@rm -rf .ruff_cache
	@rm -rf .pytest_cache
	@rm -rf .mypy_cache
	@rm -rf build dist *.egg-info
	@echo -e "$(GREEN)>>> Cleanup complete.$(NC)"

venv: ## Create a virtual environment.
	@echo -e "$(GREEN)>>> Creating virtual environment in .venv...$(NC)"
	@python3 -m venv .venv
	@echo -e "$(GREEN)>>> Virtual environment created. Activate with 'source .venv/bin/activate'$(NC)"
	@echo -e "$(GREEN)>>> Now run 'make install'$(NC)"

setup: ## Install system dependencies.
	@echo -e "$(GREEN)>>> Installing system dependencies...$(NC)"
	@sudo apt update && sudo apt install -y libportaudio2 libsndfile1 ffmpeg -y
	@echo -e "$(GREEN)>>> System dependencies installed.$(NC)"

install: setup venv ## Install project dependencies from pyproject.toml
	@echo -e "$(GREEN)>>> Installing production dependencies...$(NC)"
	@$(UV) sync --group dev
	@echo -e "$(GREEN)>>> All dependencies installed.$(NC)"
	@$(UV) lock
	@echo -e "$(GREEN)>>> Lock file updated.$(NC)"

lock: ## Update the lock file for dependencies.
	@echo -e "$(GREEN)>>> Updating lock file...$(NC)"
	@$(UV) lock
	@echo -e "$(GREEN)>>> Lock file updated.$(NC)"

lint: ## Check code style and errors with Ruff.
	@echo -e "$(GREEN)>>> Running Ruff linter...$(NC)"
	@$(PYTHON) -m ruff check $(SRC_DIR)

format: ## Format code with Ruff formatter.
	@echo -e "$(GREEN)>>> Running Ruff formatter...$(NC)"
	@$(PYTHON) -m ruff format $(SRC_DIR)
	@$(PYTHON) -m ruff check $(SRC_DIR) --fix

check: lint test ## Run all checks.
	@echo -e "$(GREEN)>>> All checks passed.$(NC)"

test: ## Run unit tests with pytest.
	@echo -e "$(GREEN)>>> Running unit tests...$(NC)"
	@$(PYTHON) -m pytest -m "not integration"

test-integration: ## Run integration tests
	@echo -e "$(GREEN)>>> Running integration tests...$(NC)"
	@$(PYTHON) -m pytest -m "integration"

coverage: ## Run tests and generate coverage report.
	@echo -e "$(GREEN)>>> Running tests with coverage...$(NC)"
	@$(PYTHON) -m pytest --cov=src --cov-report=term-missing --cov-report=html

spell-check: ## Spell check project.
	@echo -e "$(GREEN)*** Checking project for miss spellings... ***$(NC)"
	@grep . cspell.txt | sort -u > .cspell.txt && mv .cspell.txt cspell.txt
	@docker run --quiet -v ${PWD}:/workdir ghcr.io/streetsidesoftware/cspell:$(CSPELL_VERSION) lint -c cspell.json --no-progress --unique $(SRC_DIR) $(DOCS_DIR) || exit 0  
	@echo -e "$(GREEN)*** Project is correctly written! ***$(NC)"

test-end-to-end: ## Run the end-to-end tests shell script.
	@echo -e "$(GREEN)>>> Running end-to-end tests...$(NC)"
	@if [ -f "tests_end-to-end.sh" ]; then \
		bash tests_end-to-end.sh; \
	else \
		echo -e "$(RED)Error: tests_end-to-end.sh not found in root directory.$(NC)"; \
		exit 1; \
	fi

test-publish: clean ## Build package, verify content, and install locally to test
	@echo "🚀 Building package..."
	$(UV) build
	@echo -e "📦 Verifying package content (sdist)..."
	@tar -tf dist/*.tar.gz | sort
	@echo -e "🔧 Installing in editable mode to test entry points..."
	@$(UV) pip install -e .
	@echo -e "✅ Ready! Try running 'audio-tools-meter --help' to verify it works."

# ==============================================================================
# Audio Device Management
# ==============================================================================

list-audio-devices: ## List available audio input devices.
ifeq ($(SILENT),)
	@echo -e "$(GREEN)>>> Listing audio input devices...$(NC)"
endif
	@$(UV) run audio-tools-devices

get-umik-id: ## Attempt to find and print the ID of the UMIK-1 microphone. Use SILENT=1 for raw output.
ifeq ($(SILENT),)
	@echo -e "$(GREEN)>>> Searching for UMIK-1 device ID...$(NC)"
endif
	@id=$$($(MAKE) --no-print-directory list-audio-devices SILENT=$(SILENT) | grep -i "UMIK-1" | awk '{ print $$2 }' || true); \
	if [ -z "$$id" ]; then \
		echo "Error: UMIK-1 device not found!" >&2; \
		exit 1; \
	fi; \
	echo -n "$$id"

calibrate-umik:  ## Run the calibration test script.
ifndef F
	$(error Calibration file path not set. Use 'make calibrate-umik F="<path/to/calibration_file.txt>"')
endif
	@echo -e "$(GREEN)--- Running Calibration Test ---$(NC)"
	@echo "Calibration File: ${F}"
	@echo "--------------------------------"
	@$(UV) run audio-tools-calibrate "${F}"

# ==============================================================================
# Real Time Meter
# ==============================================================================

real-time-meter: real-time-meter-umik ## Run the real time meter using the UMIK-1 (Default alias)

real-time-meter-umik: ## Run the real time meter using the UMIK-1. Requires F=<cal_file>. Use HELP=--help for usage.
ifeq ($(HELP),--help)
	@echo -e "$(YELLOW)>>> Showing help for real_time_meter.py...$(NC)"
	@$(UV) run audio-tools-meter --help
else
	@echo -e "$(YELLOW)>>> Attempting to run Real Time Meter with UMIK-1...$(NC)"
	$(eval ID := $(shell $(MAKE) --no-print-directory get-umik-id SILENT=1))
	@if [ -z "$(ID)" ]; then \
		echo -e "$(RED)>>> ERROR: Could not automatically find UMIK-1 device ID.$(NC)"; \
		echo -e "$(YELLOW)    Please check 'make list-audio-devices' and ensure the microphone is connected.$(NC)"; \
		exit 1; \
	fi
ifndef F
	$(error Calibration file path not set. Use 'make real-time-meter-umik F="<path/to/calibration_file.txt>"')
endif
	@$(UV) run audio-tools-meter $(HELP) --device-id $(ID) --calibration-file "$(F)"
endif

real-time-meter-default-mic: ## Run the real time meter using the system default microphone. Use HELP=--help for usage.
ifeq ($(HELP),--help)
	@echo -e "$(YELLOW)>>> Showing help for real_time_meter.py...$(NC)"
	@$(UV) run audio-tools-meter --help
else
	@echo -e "$(YELLOW)>>> Running Real Time Meter with default system microphone...$(NC)"
	@$(UV) run audio-tools-meter $(HELP)
endif

# ==============================================================================
# Recording
# ==============================================================================

record: record-umik ## Record audio using the UMIK-1 (Default alias)

record-umik: ## Record audio using the UMIK-1. Requires F=<cal_file>. Optional: OUT=<path>.
ifeq ($(HELP),--help)
	@echo -e "$(YELLOW)>>> Showing help for basic_recorder.py...$(NC)"
	@$(UV) run audio-tools-record --help
else
	@echo -e "$(YELLOW)>>> Attempting to record with UMIK-1...$(NC)"
	$(eval ID := $(shell $(MAKE) --no-print-directory get-umik-id SILENT=1))
	@if [ -z "$(ID)" ]; then \
		echo -e "$(RED)>>> ERROR: Could not automatically find UMIK-1 device ID.$(NC)"; \
		echo -e "$(YELLOW)    Please check 'make list-audio-devices' and ensure the microphone is connected.$(NC)"; \
		exit 1; \
	fi
ifndef F
	$(error Calibration file path not set. Use 'make record-umik F="<path/to/calibration_file.txt>"')
endif
	@echo -e "$(GREEN)>>> Recording to path $(OUT)...$(NC)"
	@$(UV) run audio-tools-record $(HELP) \
		--device-id $(ID) \
		--calibration-file "$(F)" \
		--output-dir "$(OUT)"
endif

record-default-mic: ## Record audio using the system default microphone. Optional: OUT=<path>.
ifeq ($(HELP),--help)
	@echo -e "$(YELLOW)>>> Showing help for basic_recorder.py...$(NC)"
	@$(UV) run audio-tools-record --help
else
	@echo -e "$(YELLOW)>>> Recording with default system microphone...$(NC)"
	@echo -e "$(GREEN)>>> Recording to $(OUT)...$(NC)"
	@$(UV) run audio-tools-record $(HELP) \
		--output-dir "$(OUT)"
endif

# ==============================================================================
# Analysis & Metrics
# ==============================================================================

metrics-analyzer: ## Analyze a WAV file. Requires IN=<path>. Optional: F=<cal_file>, CSV_OUT=<csv_path>.
ifeq ($(HELP),--help)
	@echo -e "$(YELLOW)>>> Showing help for metrics_analyzer.py...$(NC)"
	@$(UV) run audio-tools-analyze --help
else
	@if [ -z "$(IN)" ]; then \
		echo -e "$(RED)>>> ERROR: Input file not set. Use 'make metrics-analyzer IN=recordings/file.wav'$(NC)"; \
		exit 1; \
	fi
	@echo -e "$(YELLOW)>>> Analyzing audio file: $(IN)...$(NC)"
	$(if $(F),@echo -e "$(GREEN)>>> Using Calibration: $(F)$(NC)")
	@$(UV) run audio-tools-analyze "$(IN)" \
		$(if $(F),--calibration-file "$(F)") \
		$(if $(CSV_OUT),--output-file "$(CSV_OUT)")
endif

batch-analyze: ## Batch analyze a directory. Requires DIR=<path>. Optional: F=<cal_file>, CSV_OUT=<csv_path>.
ifeq ($(HELP),--help)
	@echo -e "$(YELLOW)>>> Showing help for audio_batch_analysis.py...$(NC)"
	@$(UV) run audio-tools-batch --help
else
	@if [ -z "$(DIR)" ]; then \
		echo -e "$(RED)>>> ERROR: Input directory not set. Use 'make batch-analyze DIR=recordings/'$(NC)"; \
		exit 1; \
	fi
	@echo -e "$(YELLOW)>>> Batch processing directory: $(DIR)...$(NC)"
	$(if $(F),@echo -e "$(GREEN)>>> Using Calibration: $(F)$(NC)")
	@$(UV) run audio-tools-batch "$(DIR)" \
		$(if $(F),--calibration-file "$(F)") \
		$(if $(CSV_OUT),--output-file "$(CSV_OUT)")
endif

# ==============================================================================
# Visualization
# ==============================================================================

plot-view: ## View metrics chart. Requires IN=<csv_path>. Optional: METRICS="dbfs lufs".
ifeq ($(HELP),--help)
	@echo -e "$(YELLOW)>>> Showing help for metrics_plotter.py...$(NC)"
	@$(UV) run audio-tools-plot --help
else
	@if [ -z "$(IN)" ]; then \
		echo -e "$(RED)>>> ERROR: Input CSV not set. Use 'make plot-view IN=analysis.csv'$(NC)"; \
		exit 1; \
	fi
	@echo -e "$(YELLOW)>>> Opening plot viewer...$(NC)"
	@$(UV) run audio-tools-plot "$(IN)" \
		$(if $(METRICS),--metrics $(METRICS))
endif

plot-save: ## Save metrics chart. Requires IN=<csv_path>. Optional: PLOT_OUT=<png_path>, METRICS="...".
ifeq ($(HELP),--help)
	@echo -e "$(YELLOW)>>> Showing help for metrics_plotter.py...$(NC)"
	@$(UV) run audio-tools-plot --help
else
	@if [ -z "$(IN)" ]; then \
		echo -e "$(RED)>>> ERROR: Input CSV not set. Use 'make plot-save IN=analysis.csv'$(NC)"; \
		exit 1; \
	fi
	@echo -e "$(YELLOW)>>> Generating plot image...$(NC)"
	@$(UV) run audio-tools-plot "$(IN)" \
		--save $(if $(PLOT_OUT),"$(PLOT_OUT)") \
		$(if $(METRICS),--metrics $(METRICS))
endif

# ==============================================================================
# Audio Enhancement
# ==============================================================================

enhance-audio: ## Filter audio to enhance voice and save as MP3. Requires IN=<path>. Optional: MP3_OUT=<mp3_path>, LOW=<hz>, HIGH=<hz>.
ifeq ($(HELP),--help)
	@echo -e "$(YELLOW)>>> Showing help for enhance_voice.py...$(NC)"
	@$(UV) run audio-tools-enhance --help
else
	@if [ -z "$(IN)" ]; then \
		echo -e "$(RED)>>> ERROR: Input file not set. Use 'make enhance-audio IN=recordings/file.wav'$(NC)"; \
		exit 1; \
	fi
	@echo -e "$(YELLOW)>>> Enhancing audio file: $(IN)...$(NC)"
	@$(UV) run audio-tools-enhance "$(IN)" \
		$(if $(MP3_OUT),--out "$(MP3_OUT)") \
		$(if $(LOW),--low $(LOW)) \
		$(if $(HIGH),--high $(HIGH))
endif

# ==============================================================================
# Audio Conversion
# ==============================================================================

convert-audio: ## Convert WAV files. Requires IN=<path>. Optional: FMT=ogg|mp3|aac, OUT=<dir>.
ifeq ($(HELP),--help)
	@$(UV) run audio-tools-convert --help
else
	@if [ -z "$(IN)" ]; then \
		echo -e "$(RED)>>> ERROR: Input not set. Use 'make convert-audio IN=recordings/file.wav'$(NC)"; \
		exit 1; \
	fi
	@echo -e "$(YELLOW)>>> Converting: $(IN)...$(NC)"
	@$(UV) run audio-tools-convert "$(IN)" \
		$(if $(FMT),-f $(FMT)) \
		$(if $(OUT),-o "$(OUT)")
endif

# ==============================================================================
# VERSION BUMPING
# ==============================================================================
CURRENT_VERSION := $(shell grep '^version' pyproject.toml | head -1 | sed 's/.*"\(.*\)"/\1/')
MAJOR := $(word 1,$(subst ., ,$(CURRENT_VERSION)))
MINOR := $(word 2,$(subst ., ,$(CURRENT_VERSION)))
PATCH := $(word 3,$(subst ., ,$(CURRENT_VERSION)))

bump-patch: ## Bump patch version (0.1.0 → 0.1.1)
	$(eval NEW_VERSION := $(MAJOR).$(MINOR).$(shell echo $$(($(PATCH)+1))))
	@sed -i 's/^version = "$(CURRENT_VERSION)"/version = "$(NEW_VERSION)"/' pyproject.toml
	@sed -i 's/__version__ = "$(CURRENT_VERSION)"/__version__ = "$(NEW_VERSION)"/' src/umik_base_app/_version.py
	@printf "%s\n" "Bumped version: $(CURRENT_VERSION) → $(NEW_VERSION)"

bump-minor: ## Bump minor version (0.1.0 → 0.2.0)
	$(eval NEW_VERSION := $(MAJOR).$(shell echo $$(($(MINOR)+1))).0)
	@sed -i 's/^version = "$(CURRENT_VERSION)"/version = "$(NEW_VERSION)"/' pyproject.toml
	@sed -i 's/__version__ = "$(CURRENT_VERSION)"/__version__ = "$(NEW_VERSION)"/' src/umik_base_app/_version.py
	@printf "%s\n" "Bumped version: $(CURRENT_VERSION) → $(NEW_VERSION)"

bump-major: ## Bump major version (0.1.0 → 1.0.0)
	$(eval NEW_VERSION := $(shell echo $$(($(MAJOR)+1))).0.0)
	@sed -i 's/^version = "$(CURRENT_VERSION)"/version = "$(NEW_VERSION)"/' pyproject.toml
	@sed -i 's/__version__ = "$(CURRENT_VERSION)"/__version__ = "$(NEW_VERSION)"/' src/umik_base_app/_version.py
	@printf "%s\n" "Bumped version: $(CURRENT_VERSION) → $(NEW_VERSION)"

# ==============================================================================
# DEB PACKAGING
# ==============================================================================
DISTRO ?= noble

install-build-deps: ## Install system dependencies for building .deb packages
	sudo apt-get update
	sudo apt-get install -y build-essential debhelper dh-python python3-all python3-setuptools

vendor: ## Populate umik_base_app/vendor with dependencies from uv.lock
	@printf "%s\n" "Vendoring dependencies from uv.lock..."
	mkdir -p src/umik_base_app/vendor
	touch src/umik_base_app/vendor/__init__.py
	uv export --no-dev --frozen --format requirements-txt | grep -v "file://" > requirements.frozen.txt
	uv pip install -r requirements.frozen.txt --target src/umik_base_app/vendor --python 3.12
	rm requirements.frozen.txt
	@printf "%s\n" "Vendor populated successfully."

build-deb: clean-all vendor ## Build .deb package
	@printf "%s\n" "Building .deb package..."
	@bash build_deb.sh

test-deb: ## Test .deb in a clean Docker container (DISTRO=noble|jammy)
	@printf "%s\n" "Testing package in Docker (ubuntu:$(DISTRO))..."
	@docker run --rm -v $$(pwd):/dist ubuntu:$(DISTRO) sh -c "\
		export DEBIAN_FRONTEND=noninteractive && \
		apt-get update && \
		apt-get install -y /dist/deb_dist/*.deb && \
		printf '%s\n' '--- CLI Help ---' && \
		umik --help"

publish-deb: ## Publish .deb to S3 APT repository (BUCKET=... required)
	@if [ -z "$(BUCKET)" ]; then \
		printf "%s\n" "Error: BUCKET=... required. Usage: make publish-deb BUCKET=my-bucket"; \
		exit 1; \
	fi
	@set -a && . ./.env && set +a && \
	uv run --group publish python publish_repo.py \
		"$$(find deb_dist -name '*.deb' -type f | head -1)" $(BUCKET)
