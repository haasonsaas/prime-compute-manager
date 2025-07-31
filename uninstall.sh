#!/bin/bash
# Prime Compute Manager - Uninstaller

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo
echo "🗑️  Prime Compute Manager Uninstaller"
echo "===================================="
echo

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ]; then
    echo -e "${RED}[✗]${NC} Please run this script from the prime-compute-manager directory"
    exit 1
fi

echo -e "${YELLOW}[!]${NC} This will remove:"
echo "    - Virtual environment (.venv)"
echo "    - Launcher script (pcm-launcher.sh)"
echo "    - macOS app (PCM.app) if present"
echo "    - Any __pycache__ directories"
echo
read -p "Continue? (y/N) " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Remove virtual environment
    if [ -d ".venv" ]; then
        echo -e "${YELLOW}[*]${NC} Removing virtual environment..."
        rm -rf .venv
    fi

    # Remove launcher script
    if [ -f "pcm-launcher.sh" ]; then
        echo -e "${YELLOW}[*]${NC} Removing launcher script..."
        rm -f pcm-launcher.sh
    fi

    # Remove macOS app
    if [ -d "PCM.app" ]; then
        echo -e "${YELLOW}[*]${NC} Removing macOS app..."
        rm -rf PCM.app
    fi

    # Clean up Python cache
    echo -e "${YELLOW}[*]${NC} Cleaning Python cache..."
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true

    echo
    echo -e "${GREEN}[✓]${NC} Uninstall complete!"
    echo
    echo "Note: The source code remains intact. To reinstall, run:"
    echo "  ./install.sh"
else
    echo -e "${YELLOW}[!]${NC} Uninstall cancelled"
fi