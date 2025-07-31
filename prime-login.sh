#!/bin/bash
# Helper script to authenticate with prime-cli using the venv

# Find the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Activate virtual environment
# shellcheck disable=SC1091
source "$SCRIPT_DIR/.venv/bin/activate"

# Run prime login
.venv/bin/prime login