#!/bin/bash

# ==============================================================================
# Author: Daniel Collier
# GitHub: https://github.com/danielfcollier
# Year: 2025
# ==============================================================================

# ==============================================================================
# 1. CONFIGURATION & SETUP
# ==============================================================================
CAL_FILE="umik-1/7175488.txt"
RECORDING_DIR="test_recordings"
TEST_WAV="${RECORDING_DIR}/integration_test.wav"
TEST_CSV="${RECORDING_DIR}/integration_test.csv"
TEST_PLOT="${RECORDING_DIR}/integration_test.png"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# # Force Matplotlib to use Headless backend (Fixes display errors in tests)
# export MPLBACKEND=Agg

EXIT_CODE=0
TEST_TIME="4s"

# Helper: Loggers
log() { echo -e "${BLUE}[TEST]${NC} $1"; }
pass() { echo -e "${GREEN}✔ PASS${NC}"; }
fail() { echo -e "${RED}✖ FAIL${NC}"; EXIT_CODE=1; }
warn() { echo -e "${YELLOW}⚠ SKIP${NC} $1"; }

# Helper: Run command with timeout (for infinite apps like meter/recorder)
# Returns SUCCESS (0) if app runs and is killed by timeout.
# Returns FAIL (1) if app crashes immediately.
run_app() {
    local duration=$1
    shift
    local cmd="$@"
    
    log "Running: $cmd (Timeout: ${duration})"

    # Run with timeout. Exit 124 = Timed out (Success for us).
    timeout "$duration" $cmd > /dev/null 2>&1
    local status=$?

    if [ $status -eq 124 ]; then
        pass
    elif [ $status -eq 0 ]; then
        # Some apps (like help/list) exit 0 naturally. 
        pass
    else
        echo -e "${RED}App crashed with exit code $status${NC}"
        # We allow fail for UMIK tests if hardware missing, but we want to see the error.
        return 1
    fi
    return 0
}

# Ensure Virtual Env
if [ ! -d ".venv" ]; then
    echo "Virtual environment not found. Run 'make install' first."
    exit 1
fi

mkdir -p "$RECORDING_DIR"

# ==============================================================================
# 2. DISCOVERY TESTS
# ==============================================================================
echo -e "\n${YELLOW}=== Phase 1: Discovery (Make vs Pip) ===${NC}"

# A. Make Commands
log "Checking 'make list-audio-devices'..."
make list-audio-devices > /dev/null && pass || fail

log "Checking 'make get-umik-id'..."
# This might fail if UMIK isn't plugged in, so we capture output but don't hard fail script
if make get-umik-id SILENT=1 > /dev/null 2>&1; then
    pass
    HAS_UMIK=true
else
    warn "(No UMIK-1 detected via Make)"
    HAS_UMIK=false
fi

# B. Pip Commands
log "Checking 'umik-list-devices'..."
umik-list-devices > /dev/null && pass || fail

log "Checking 'umik-list-devices --only'..."
if umik-list-devices --only > /dev/null 2>&1; then
    pass
else
    warn "(No UMIK-1 detected via Pip)"
fi

# ==============================================================================
# 3. CALIBRATION TESTS
# ==============================================================================
echo -e "\n${YELLOW}=== Phase 2: Calibration (Make vs Pip) ===${NC}"

if [ ! -f "$CAL_FILE" ]; then
    warn "Calibration file '$CAL_FILE' not found. Skipping Phase 2."
else
    # A. Make
    log "Checking 'make calibrate-umik'..."
    make calibrate-umik F="$CAL_FILE" > /dev/null && pass || fail

    # B. Pip
    log "Checking 'umik-calibrate'..."
    umik-calibrate "$CAL_FILE" > /dev/null && pass || fail
fi

# ==============================================================================
# 4. RUNTIME APP TESTS (Recorder & Meter)
# ==============================================================================
echo -e "\n${YELLOW}=== Phase 3: Runtime Scenarios ===${NC}"

# ------------------------------------------------------------------------------
# SCENARIO A: Default Microphone (No Calibration)
# ------------------------------------------------------------------------------
echo -e "${BLUE}>> Scenario A: Default Microphone${NC}"

# Make
run_app ${TEST_TIME} make real-time-meter-default-mic || fail
run_app ${TEST_TIME} make record-default-mic OUT="$RECORDING_DIR/make_def" || fail

# Pip
run_app ${TEST_TIME} umik-real-time-meter --default || fail
run_app ${TEST_TIME} umik-recorder --default --output-dir "$RECORDING_DIR" || fail


# ------------------------------------------------------------------------------
# SCENARIO B: UMIK-1 (Explicit Argument)
# ------------------------------------------------------------------------------
echo -e "${BLUE}>> Scenario B: UMIK-1 (Explicit Argument)${NC}"

if [ "$HAS_UMIK" = true ] && [ -f "$CAL_FILE" ]; then
    # Make (Requires F=...)
    run_app ${TEST_TIME} make real-time-meter-umik-1 F="$CAL_FILE" || fail
    run_app ${TEST_TIME} make record-umik-1 F="$CAL_FILE" OUT="$RECORDING_DIR/make_arg" || fail

    # Pip (Requires --calibration-file)
    run_app ${TEST_TIME} umik-real-time-meter --calibration-file "$CAL_FILE" || fail
    run_app ${TEST_TIME} umik-recorder --calibration-file "$CAL_FILE" --output-dir "$RECORDING_DIR" || fail
else
    warn "Skipping Scenario B (Missing Hardware or Cal File)"
fi


# ------------------------------------------------------------------------------
# SCENARIO C: UMIK-1 (Environment Variable)
# ------------------------------------------------------------------------------
echo -e "${BLUE}>> Scenario C: UMIK-1 (Environment Variable - Pip Only)${NC}"

if [ "$HAS_UMIK" = true ] && [ -f "$CAL_FILE" ]; then
    # Set Env
    export CALIBRATION_FILE="$CAL_FILE"
    
    # Pip (Should auto-detect file from Env)
    run_app ${TEST_TIME} umik-real-time-meter || fail
    run_app ${TEST_TIME} umik-recorder --output-dir "$RECORDING_DIR" || fail

    # Clean Env
    unset CALIBRATION_FILE
    pass
else
    warn "Skipping Scenario C (Missing Hardware or Cal File)"
fi

# ==============================================================================
# 5. ANALYSIS & PLOTTING TESTS
# ==============================================================================
echo -e "\n${YELLOW}=== Phase 4: Analysis & Plotting ===${NC}"

SAMPLE_WAV="sample_recording.wav"

# 1. Prepare Test WAV
# We use the provided sample file (if available) or generate a clean sine wave.
# This avoids using empty/corrupt files from Phase 3 which cause the Plotter to crash.
if [ -f "$SAMPLE_WAV" ]; then
    log "Using provided sample file: $SAMPLE_WAV"
    cp "$SAMPLE_WAV" "$TEST_WAV"
else
    log "Sample file '$SAMPLE_WAV' not found. Generating synthetic 440Hz sine wave..."
    # Generates a 1-second sine wave to ensure valid, non-zero CSV data
    python3 -c "import scipy.io.wavfile as w; import numpy as n; fs=48000; t=n.linspace(0, 1, fs); data=(n.sin(2*n.pi*440*t)*32767).astype(n.int16); w.write('$TEST_WAV', fs, data)"
fi

# A. Metrics Analyzer
echo -e "${BLUE}>> Metrics Analyzer${NC}"

# Make (Default)
log "Checking 'make metrics-analyzer' (Default)..."
make metrics-analyzer IN="$TEST_WAV" CSV_OUT="$TEST_CSV" > /dev/null && pass || fail

# Make (Calibrated)
if [ -f "$CAL_FILE" ]; then
    log "Checking 'make metrics-analyzer' (Calibrated)..."
    make metrics-analyzer IN="$TEST_WAV" F="$CAL_FILE" CSV_OUT="$TEST_CSV" > /dev/null && pass || fail
fi

# Pip (Default)
log "Checking 'umik-metrics-analyzer'..."
umik-metrics-analyzer "$TEST_WAV" --output-file "$TEST_CSV" > /dev/null && pass || fail


# B. Metrics Plotter
echo -e "${BLUE}>> Metrics Plotter${NC}"

# Check if CSV is valid (not empty) before plotting to avoid misleading crashes
if [ -s "$TEST_CSV" ]; then
    log "Checking 'make plot-save'..."
    make plot-save IN="$TEST_CSV" PLOT_OUT="$TEST_PLOT" > /dev/null && pass || fail

    log "Checking 'umik-metrics-plot'..."
    umik-metrics-plot "$TEST_CSV" --save "$TEST_PLOT" > /dev/null && pass || fail
else
    echo -e "${RED}✖ FAIL: CSV analysis failed, cannot run plot tests.${NC}"
    EXIT_CODE=1
fi

# ==============================================================================
# CLEANUP
# ==============================================================================
rm -rf "$RECORDING_DIR"

if [ $EXIT_CODE -eq 0 ]; then
    echo -e "\n${GREEN}All Integration Tests Completed Successfully! 🚀${NC}"
    exit 0
else
    echo -e "\n${RED}Some tests failed. Check logs above for details.${NC}"
    exit 1
fi