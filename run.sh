#!/bin/bash
# Convenience script to run NotebookLM Generator

# Activate virtual environment
source "$(dirname "$0")/venv/bin/activate"

# Run the tool
python -m src.main "$@"
