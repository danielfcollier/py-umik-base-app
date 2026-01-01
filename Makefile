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

.PHONY: all default help clean clean-all venv install lint format check test list-audio-devices get-umik-id calibrate-umik spell-check real-time-meter real-time-meter-default-mic real-time-meter-umik record record-default-mic record-umik test coverage test-publish metrics-analyzer batch-analyze plot-view plot-save enhance-audio test-end-to-end lock setup

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
	@$(UV) sync --extra dev
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
	@echo -e "✅ Ready! Try running 'umik-real-time-meter --help' to verify it works."

# ==============================================================================
# Audio Device Management
# ==============================================================================

list-audio-devices: ## List available audio input devices.
ifeq ($(SILENT),)
	@echo -e "$(GREEN)>>> Listing audio input devices...$(NC)"
endif
	@PYTHONPATH=$(SCRIPT_DIR) $(PYTHON) $(APP_DIR)/list_audio_devices.py

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
	@PYTHONPATH=$(SCRIPT_DIR) $(PYTHON) $(APP_DIR)/umik1_calibrator.py "${F}"

# ==============================================================================
# Real Time Meter
# ==============================================================================

real-time-meter: real-time-meter-umik ## Run the real time meter using the UMIK-1 (Default alias)

real-time-meter-umik: ## Run the real time meter using the UMIK-1. Requires F=<cal_file>. Use HELP=--help for usage.
ifeq ($(HELP),--help)
	@echo -e "$(YELLOW)>>> Showing help for real_time_meter.py...$(NC)"
	@$(PYTHON) $(APP_DIR)/real_time_meter.py --help
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
	@PYTHONPATH=$(SCRIPT_DIR) $(PYTHON) $(APP_DIR)/real_time_meter.py $(HELP) --device-id $(ID) --calibration-file "$(F)"
endif

real-time-meter-default-mic: ## Run the real time meter using the system default microphone. Use HELP=--help for usage.
ifeq ($(HELP),--help)
	@echo -e "$(YELLOW)>>> Showing help for real_time_meter.py...$(NC)"
	@$(PYTHON) $(APP_DIR)/real_time_meter.py --help
else
	@echo -e "$(YELLOW)>>> Running Real Time Meter with default system microphone...$(NC)"
	@PYTHONPATH=$(SCRIPT_DIR) $(PYTHON) $(APP_DIR)/real_time_meter.py $(HELP)
endif

# ==============================================================================
# Recording
# ==============================================================================

record: record-umik ## Record audio using the UMIK-1 (Default alias)

record-umik: ## Record audio using the UMIK-1. Requires F=<cal_file>. Optional: OUT=<path>.
ifeq ($(HELP),--help)
	@echo -e "$(YELLOW)>>> Showing help for basic_recorder.py...$(NC)"
	@PYTHONPATH=$(SCRIPT_DIR) $(PYTHON) $(APP_DIR)/basic_recorder.py --help
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
	@PYTHONPATH=$(SCRIPT_DIR) $(PYTHON) $(APP_DIR)/basic_recorder.py $(HELP) \
		--device-id $(ID) \
		--calibration-file "$(F)" \
		--output-dir "$(OUT)"
endif

record-default-mic: ## Record audio using the system default microphone. Optional: OUT=<path>.
ifeq ($(HELP),--help)
	@echo -e "$(YELLOW)>>> Showing help for basic_recorder.py...$(NC)"
	@PYTHONPATH=$(SCRIPT_DIR) $(PYTHON) $(APP_DIR)/basic_recorder.py --help
else
	@echo -e "$(YELLOW)>>> Recording with default system microphone...$(NC)"
	@echo -e "$(GREEN)>>> Recording to $(OUT)...$(NC)"
	@PYTHONPATH=$(SCRIPT_DIR) $(PYTHON) $(APP_DIR)/basic_recorder.py $(HELP) \
		--output-dir "$(OUT)"
endif

# ==============================================================================
# Analysis & Metrics
# ==============================================================================

metrics-analyzer: ## Analyze a WAV file. Requires IN=<path>. Optional: F=<cal_file>, CSV_OUT=<csv_path>.
ifeq ($(HELP),--help)
	@echo -e "$(YELLOW)>>> Showing help for metrics_analyzer.py...$(NC)"
	@PYTHONPATH=$(SRC_DIR) $(PYTHON) -m umik_base_app.apps.metrics_analyzer --help
else
	@if [ -z "$(IN)" ]; then \
		echo -e "$(RED)>>> ERROR: Input file not set. Use 'make metrics-analyzer IN=recordings/file.wav'$(NC)"; \
		exit 1; \
	fi
	@echo -e "$(YELLOW)>>> Analyzing audio file: $(IN)...$(NC)"
	$(if $(F),@echo -e "$(GREEN)>>> Using Calibration: $(F)$(NC)")
	@PYTHONPATH=$(SRC_DIR) $(PYTHON) -m umik_base_app.apps.metrics_analyzer "$(IN)" \
		$(if $(F),--calibration-file "$(F)") \
		$(if $(CSV_OUT),--output-file "$(CSV_OUT)")
endif

batch-analyze: ## Batch analyze a directory. Requires DIR=<path>. Optional: F=<cal_file>, CSV_OUT=<csv_path>.
ifeq ($(HELP),--help)
	@echo -e "$(YELLOW)>>> Showing help for audio_batch_analysis.py...$(NC)"
	@PYTHONPATH=$(SRC_DIR) $(PYTHON) -m scripts.audio_batch_analysis --help
else
	@if [ -z "$(DIR)" ]; then \
		echo -e "$(RED)>>> ERROR: Input directory not set. Use 'make batch-analyze DIR=recordings/'$(NC)"; \
		exit 1; \
	fi
	@echo -e "$(YELLOW)>>> Batch processing directory: $(DIR)...$(NC)"
	$(if $(F),@echo -e "$(GREEN)>>> Using Calibration: $(F)$(NC)")
	@PYTHONPATH=$(SRC_DIR) $(PYTHON) -m scripts.audio_batch_analysis "$(DIR)" \
		$(if $(F),--calibration-file "$(F)") \
		$(if $(CSV_OUT),--output-file "$(CSV_OUT)")
endif

# ==============================================================================
# Visualization
# ==============================================================================

plot-view: ## View metrics chart. Requires IN=<csv_path>. Optional: METRICS="dbfs lufs".
ifeq ($(HELP),--help)
	@echo -e "$(YELLOW)>>> Showing help for metrics_plotter.py...$(NC)"
	@PYTHONPATH=$(SRC_DIR) $(PYTHON) -m umik_base_app.apps.metrics_plotter --help
else
	@if [ -z "$(IN)" ]; then \
		echo -e "$(RED)>>> ERROR: Input CSV not set. Use 'make plot-view IN=analysis.csv'$(NC)"; \
		exit 1; \
	fi
	@echo -e "$(YELLOW)>>> Opening plot viewer...$(NC)"
	@PYTHONPATH=$(SRC_DIR) $(PYTHON) -m umik_base_app.apps.metrics_plotter "$(IN)" \
		$(if $(METRICS),--metrics $(METRICS))
endif

plot-save: ## Save metrics chart. Requires IN=<csv_path>. Optional: PLOT_OUT=<png_path>, METRICS="...".
ifeq ($(HELP),--help)
	@echo -e "$(YELLOW)>>> Showing help for metrics_plotter.py...$(NC)"
	@PYTHONPATH=$(SRC_DIR) $(PYTHON) -m umik_base_app.apps.metrics_plotter --help
else
	@if [ -z "$(IN)" ]; then \
		echo -e "$(RED)>>> ERROR: Input CSV not set. Use 'make plot-save IN=analysis.csv'$(NC)"; \
		exit 1; \
	fi
	@echo -e "$(YELLOW)>>> Generating plot image...$(NC)"
	@PYTHONPATH=$(SRC_DIR) $(PYTHON) -m umik_base_app.apps.metrics_plotter "$(IN)" \
		--save $(if $(PLOT_OUT),"$(PLOT_OUT)") \
		$(if $(METRICS),--metrics $(METRICS))
endif

# ==============================================================================
# Audio Enhancement
# ==============================================================================

enhance-audio: ## Filter audio to enhance voice and save as MP3. Requires IN=<path>. Optional: MP3_OUT=<mp3_path>, LOW=<hz>, HIGH=<hz>.
ifeq ($(HELP),--help)
	@echo -e "$(YELLOW)>>> Showing help for enhance_voice.py...$(NC)"
	@PYTHONPATH=$(SCRIPT_DIR) $(PYTHON) -m src.scripts.enhance_voice --help
else
	@if [ -z "$(IN)" ]; then \
		echo -e "$(RED)>>> ERROR: Input file not set. Use 'make enhance-audio IN=recordings/file.wav'$(NC)"; \
		exit 1; \
	fi
	@echo -e "$(YELLOW)>>> Enhancing audio file: $(IN)...$(NC)"
	@PYTHONPATH=$(SCRIPT_DIR) $(PYTHON) -m src.scripts.enhance_voice "$(IN)" \
		$(if $(MP3_OUT),--out "$(MP3_OUT)") \
		$(if $(LOW),--low $(LOW)) \
		$(if $(HIGH),--high $(HIGH))
endif
