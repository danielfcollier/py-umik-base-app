# Contributing to umik-base-app

Thank you for your interest in contributing to the **umik-base-app**! I welcome contributions to help improve this audio analysis framework.

This guide will help you set up your development environment and understand the workflows.

## 🛠️ Prerequisites

Before you begin, ensure you have the following installed on your system:

* **Python 3.12+**: [Download Python](https://www.python.org/downloads/)
* **uv**: An extremely fast Python package installer and resolver.
    * [Installation Guide for uv](https://github.com/astral-sh/uv) (e.g., `curl -LsSf https://astral.sh/uv/install.sh | sh`)
* **Make**: Standard build tool (usually pre-installed on Linux/macOS).

## 🚀 Setup

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/danielfcollier/py-umik-base-app.git
    cd py-umik-base-app
    ```

2.  **Install dependencies:**
    It's used `uv` to manage the virtual environment and dependencies efficiently. The `make install` command handles everything for you (syncing both production and development dependencies).
    ```bash
    make install
    ```
    *This creates a virtual environment in `.venv/`.*

3.  **Activate the environment:**
    ```bash
    source .venv/bin/activate
    ```

## 💻 Development Workflow

Use a `Makefile` to streamline common development tasks.

### Code Quality & Linting
Enforce strict code quality standards using **Ruff** (for linting and formatting) and **MyPy** (for static type checking).

* **Run Linter:** Checks for style violations and potential errors.
    ```bash
    make lint
    ```
* **Format Code:** Automatically fixes formatting issues.
    ```bash
    make format
    ```
* **Spell Check:** Checks for spelling errors in code and documentation.
    ```bash
    make spell-check
    ```

### Testing
Use `pytest` for unit testing and our custom shell script for end-to-end integration testing.

* **Run Unit Tests:**
    ```bash
    make test
    ```
* **Run Tests with Coverage Report:**
    This generates a coverage report to help identify untested code paths.
    ```bash
    make coverage
    ```
* **Run Integration Tests:**
    Verifies the entire application pipeline (CLI entry points, audio capture simulation, and file outputs) to ensure the system works as a whole.
    ```bash
    make test-integration
    ```

### Running the Basic Applications
You can run the built-in applications directly using `make` targets.

* **Real Time Meter:** Runs the real-time real time meter app.
    ```bash
    # Run with default settings (uses default mic)
    make real-time-meter-default-mic
    
    # Run specifically with a UMIK-1 (requires calibration file path in F variable)
    make real-time-meter-umik F="path/to/calib.txt"
    ```

* **Audio Recorder:** Runs the recording utility.
    ```bash
    # Record with default mic
    make record-default-mic
    
    # Record with UMIK-1 (requires calibration file)
    make record-umik F="path/to/calib.txt"
    ```

*(Note: Use `make help` to see all available commands).*

## 🏗️ Project Structure & Standards

* **Strict Typing:** Enforce static typing throughout the codebase using `mypy`. Please ensure all new functions and classes have type hints.
* **Formatting:** All code must be formatted with `ruff`. The CI pipeline will fail if code is not properly formatted.
* **CI Pipeline:** Every Pull Request runs the `make lint`, `make coverage`, `make spell-check`, and `make test-integration` targets via GitHub Actions. Ensure these pass locally before submitting your PR.

## 📝 Submitting a Pull Request

1.  Create a new branch for your feature or fix (`git checkout -b feature/my-new-feature`).
2.  Commit your changes (`git commit -am 'Add some feature'`).
3.  Push to the branch (`git push origin feature/my-new-feature`).
4.  Open a Pull Request against the `main` branch.

Happy Coding! 🎧