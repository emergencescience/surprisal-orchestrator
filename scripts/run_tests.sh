#!/bin/bash
# Pre-commit quality check script for Surprisal Orchestrator

set -e # Exit on any error

echo "--- 🔍 Running Linting (Ruff) ---"
source venv/bin/activate
export PYTHONPATH=$PYTHONPATH:.
ruff check .

echo "--- 🧪 Running Integration & Unit Tests with Coverage ---"
# Note: Root project uses pytest with configuration from pyproject.toml
# Enforcing 80% coverage threshold
pytest -v --cov=. --cov-fail-under=80

echo "--- 📄 Exporting OpenAPI Specification ---"
python scripts/export_openapi.py

echo "--- ✅ All Quality Checks Passed ---"
exit 0
