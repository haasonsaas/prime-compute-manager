#!/bin/bash
# Prime Compute Manager Launcher

# Find the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Activate virtual environment
# shellcheck disable=SC1091
source "$SCRIPT_DIR/.venv/bin/activate"

# Check if prime-cli is authenticated
if ! prime pods list &> /dev/null; then
    echo "⚠️  Please authenticate with prime-cli first:"
    echo "   Run: prime login"
    echo
fi

# Run pcm with all arguments
pcm "$@"
