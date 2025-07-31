#!/bin/bash
# Prime Compute Manager - One-click installer
# This script sets up everything needed to run PCM

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Print colored output
print_status() {
    echo -e "${BLUE}[*]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

# Header
echo
echo "🚀 Prime Compute Manager Installer"
echo "=================================="
echo

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ]; then
    print_error "Please run this script from the prime-compute-manager directory"
    exit 1
fi

# Check Python version
print_status "Checking Python version..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d'.' -f1)
    PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d'.' -f2)

    if [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -ge 8 ]; then
        print_success "Python $PYTHON_VERSION found"
    else
        print_error "Python 3.8+ required, found $PYTHON_VERSION"
        exit 1
    fi
else
    print_error "Python 3 not found. Please install Python 3.8 or higher"
    exit 1
fi

# Check if prime-cli is already installed globally
print_status "Checking for prime-cli..."
if command -v prime &> /dev/null; then
    print_success "prime-cli is already installed globally"
    PRIME_LOGGED_IN=$(prime pods list 2>&1 | grep -q "error" && echo "no" || echo "yes")
    if [ "$PRIME_LOGGED_IN" = "no" ]; then
        print_warning "You need to log in to prime-cli first"
        print_warning "Run: prime login"
    else
        print_success "prime-cli is authenticated"
    fi
else
    print_warning "prime-cli not found globally"
fi

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    print_status "Creating virtual environment..."
    python3 -m venv .venv
    print_success "Virtual environment created"
else
    print_success "Virtual environment already exists"
fi

# Activate virtual environment
print_status "Activating virtual environment..."
# shellcheck disable=SC1091
source .venv/bin/activate

# Upgrade pip
print_status "Upgrading pip..."
pip install --upgrade pip --quiet

# Install the package with all dependencies
print_status "Installing Prime Compute Manager..."
pip install -e . --quiet
print_success "Prime Compute Manager installed"

# Create convenient launcher script
print_status "Creating launcher script..."
cat > pcm-launcher.sh << 'EOF'
#!/bin/bash
# Prime Compute Manager Launcher

# Find the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Activate virtual environment
source "$SCRIPT_DIR/.venv/bin/activate"

# Check if prime-cli is authenticated
if ! prime pods list &> /dev/null; then
    echo "⚠️  Please authenticate with prime-cli first:"
    echo "   Run: prime login"
    echo
fi

# Run pcm with all arguments
pcm "$@"
EOF

chmod +x pcm-launcher.sh
print_success "Launcher script created"

# Create desktop launcher (macOS)
if [[ "$OSTYPE" == "darwin"* ]]; then
    print_status "Creating macOS app launcher..."
    mkdir -p PCM.app/Contents/MacOS
    cat > PCM.app/Contents/Info.plist << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>pcm-tui</string>
    <key>CFBundleIdentifier</key>
    <string>com.primeintellect.pcm</string>
    <key>CFBundleName</key>
    <string>Prime Compute Manager</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
</dict>
</plist>
EOF

    cat > PCM.app/Contents/MacOS/pcm-tui << EOF
#!/bin/bash
cd "$(dirname "\$0")/../../../"
./pcm-launcher.sh tui
EOF
    chmod +x PCM.app/Contents/MacOS/pcm-tui
    print_success "macOS app created (PCM.app)"
fi

# Test installation
print_status "Testing installation..."
if .venv/bin/pcm --version &> /dev/null; then
    print_success "Installation test passed"
else
    print_error "Installation test failed"
    exit 1
fi

# Summary
echo
echo "✨ Installation Complete!"
echo "========================"
echo
echo "📋 Quick Start Commands:"
echo
echo "  ./pcm-launcher.sh tui              # Launch interactive TUI"
echo "  ./pcm-launcher.sh resources list   # List GPU resources"
echo "  ./pcm-launcher.sh pods list        # List active pods"
echo
echo "🎯 Or add to PATH for global access:"
echo "  export PATH=\"\$PATH:$(pwd)\""
echo "  pcm-launcher.sh tui"
echo
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "🖥️  macOS Users: Double-click PCM.app to launch the TUI"
    echo
fi
echo "📚 For more info: ./pcm-launcher.sh --help"
echo

# Check prime-cli auth status one more time
if ! command -v prime &> /dev/null || ! prime pods list &> /dev/null 2>&1; then
    echo
    print_warning "Remember to authenticate prime-cli before using PCM:"
    echo "  1. Install prime-cli: pip install prime-cli"
    echo "  2. Authenticate: prime login"
    echo
fi

print_success "Ready to use! Try: ./pcm-launcher.sh tui"