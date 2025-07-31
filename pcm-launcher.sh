#!/bin/bash
# Prime Compute Manager Launcher

# Find the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Activate virtual environment
# shellcheck disable=SC1091
source "$SCRIPT_DIR/.venv/bin/activate"

# Check if prime-cli is installed
if ! command -v prime &> /dev/null; then
    echo "❌ Error: prime-cli is not installed!"
    echo ""
    echo "Please install it first:"
    echo "   pip install prime-cli"
    echo ""
    echo "After installing, authenticate with:"
    echo "   prime login"
    exit 1
fi

# Check if prime-cli is authenticated
if ! prime pods list &> /dev/null 2>&1; then
    echo "⚠️  Please authenticate with prime-cli first:"
    echo "   Run: prime login"
    echo
fi

# Run pcm with all arguments
pcm "$@"
