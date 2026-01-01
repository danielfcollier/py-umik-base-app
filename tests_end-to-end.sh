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

EXIT_CODE=0
TEST_TIME="5s"

# Helper: Loggers
log() { echo -e "${BLUE}[TEST]${NC} $1"; }
pass() { echo -e "${GREEN}✔ PASS${NC}"; }
fail() { echo -e "${RED}✖ FAIL${NC}"; EXIT_CODE=1; }
warn() { echo -e "${YELLOW}⚠ SKIP${NC} $1"; }

# Helper: Run command with timeout
# Returns 0 (Pass) if it times out (124) or exits cleanly (0).
# Returns 1 (Fail) if it crashes.
run_app() {
    local duration=$1
    shift
    local cmd="$@"
    
    log "Running: $cmd (Timeout: ${duration})"
    timeout "$duration" $cmd > /dev/null 2>&1
    local status=$?

    if [ $status -eq 124 ] || [ $status -eq 0 ]; then
        pass
        return 0
    else
        echo -e "${RED}App crashed with exit code $status${NC}"
        return 1
    fi
}

# Ensure Virtual Env
if [ ! -d ".venv" ]; then
    echo "Virtual environment not found. Run 'make install' first."
    exit 1
fi

# Clean previous run
rm -rf "$RECORDING_DIR"
mkdir -p "$RECORDING_DIR"

# ==============================================================================
# 2. DISCOVERY & HARDWARE CHECK
# ==============================================================================
echo -e "\n${YELLOW}=== Phase 1: Discovery ===${NC}"

# Check for Physical UMIK-1
if uv run umik-list-devices --only > /dev/null 2>&1; then
    HAS_UMIK=true
    log "Physical UMIK-1 detected."
else
    HAS_UMIK=false
    warn "No UMIK-1 detected. Will skip hardware-specific tests."
fi

# ==============================================================================
# 3. RUNTIME: MONOLITHIC MODE
# ==============================================================================
echo -e "\n${YELLOW}=== Phase 2: Monolithic Runtime ===${NC}"

# A. Default Mic (Should always work if host has audio)
echo -e "${BLUE}>> Default Microphone${NC}"
run_app ${TEST_TIME} uv run umik-real-time-meter --default || fail
run_app ${TEST_TIME} uv run umik-recorder --default --output-dir "$RECORDING_DIR" || fail

# B. UMIK-1 (Only if present)
if [ "$HAS_UMIK" = true ] && [ -f "$CAL_FILE" ]; then
    echo -e "${BLUE}>> UMIK-1 Hardware${NC}"
    run_app ${TEST_TIME} uv run umik-recorder --calibration-file "$CAL_FILE" || fail
    run_app ${TEST_TIME} uv run umik-real-time-meter --calibration-file "$CAL_FILE" || fail
else
    warn "Skipping UMIK-1 Monolithic tests."
fi

# ==============================================================================
# 4. RUNTIME: DISTRIBUTED TOPOLOGY (ZMQ)
# ==============================================================================
echo -e "\n${YELLOW}=== Phase 3: Distributed Topology (ZMQ) ===${NC}"
# This tests the new Architecture: Producer -> [ZMQ] -> Consumer(s)

ZMQ_PORT=5556
ZMQ_HOST="127.0.0.1"

# Step 1: Start Producer in Background
# We use --default so it works on any machine.
log "Starting Producer Node (Default Mic)..."
uv run umik-real-time-meter --producer --default --zmq-port $ZMQ_PORT > /dev/null 2>&1 &
PRODUCER_PID=$!

# Give it a moment to bind socket
sleep 2

# Check if Producer is still alive
if ! kill -0 $PRODUCER_PID 2>/dev/null; then
    echo -e "${RED}Producer process died immediately! Check logs.${NC}"
    fail
else
    # Step 2a: Test Recorder as Consumer
    log ">> Testing Consumer: Recorder..."
    run_app ${TEST_TIME} uv run umik-recorder --consumer --zmq-host $ZMQ_HOST --zmq-port $ZMQ_PORT --output-dir "$RECORDING_DIR/zmq_rec"
    
    if [ $? -ne 0 ]; then fail; fi

    # Step 2b: Test Real-Time Meter as Consumer
    log ">> Testing Consumer: Real-Time Meter..."
    run_app ${TEST_TIME} uv run umik-real-time-meter --consumer --zmq-host $ZMQ_HOST --zmq-port $ZMQ_PORT
    
    if [ $? -ne 0 ]; then fail; fi
    
    # Step 3: Cleanup Producer
    kill $PRODUCER_PID 2>/dev/null
    wait $PRODUCER_PID 2>/dev/null
fi

# ==============================================================================
# 5. ANALYSIS & PLOTTING
# ==============================================================================
echo -e "\n${YELLOW}=== Phase 4: Analysis & Plotting ===${NC}"

SAMPLE_WAV="sample_recording.wav"

# Generate Dummy WAV if sample missing
if [ ! -f "$SAMPLE_WAV" ]; then
    log "Generating synthetic sine wave for analysis..."
    python3 -c "import scipy.io.wavfile as w; import numpy as n; fs=48000; t=n.linspace(0, 1, fs); data=(n.sin(2*n.pi*440*t)*32767).astype(n.int16); w.write('$TEST_WAV', fs, data)"
else
    cp "$SAMPLE_WAV" "$TEST_WAV"
fi

# Metrics Analysis
log "Running Analyzer..."
run_app ${TEST_TIME} uv run umik-metrics-analyzer "$TEST_WAV" --output-file "$TEST_CSV" || fail

# Verify CSV creation
if [ ! -s "$TEST_CSV" ]; then
    echo -e "${RED}Analysis failed: CSV file not created or empty.${NC}"
    fail
fi

# Plotting
log "Running Plotter..."
run_app ${TEST_TIME} uv run umik-metrics-plotter "$TEST_CSV" --save "$TEST_PLOT" || fail

# Verify Plot creation
if [ -f "$TEST_PLOT" ]; then
    log "Plot created successfully at $TEST_PLOT"
else
    echo -e "${RED}Plotting failed: Image file not created.${NC}"
    fail
fi

# ==============================================================================
# CLEANUP
# ==============================================================================
# Optional: Comment out next line to inspect results on failure
rm -rf "$RECORDING_DIR"

if [ $EXIT_CODE -eq 0 ]; then
    echo -e "\n${GREEN}All End-to-End Tests Completed Successfully! 🚀${NC}"
    exit 0
else
    echo -e "\n${RED}Tests Failed.${NC}"
    exit 1
fi