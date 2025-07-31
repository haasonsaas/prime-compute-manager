# Installation Guide

## Quick Install (Recommended)

The easiest way to install Prime Compute Manager is using the provided install script:

```bash
./install.sh
```

This will:
- ✅ Check Python version (3.8+ required)
- ✅ Create a virtual environment
- ✅ Install all dependencies including Textual
- ✅ Create convenient launcher scripts
- ✅ Create a macOS app (on macOS)
- ✅ Test the installation

## After Installation

### Using the Launcher

The installer creates a `pcm-launcher.sh` script that handles virtual environment activation:

```bash
# Launch the interactive TUI
./pcm-launcher.sh tui

# List GPU resources
./pcm-launcher.sh resources list

# Create a pod
./pcm-launcher.sh pods create --gpu-type H100_80GB --count 2 --name my-pod

# Get help
./pcm-launcher.sh --help
```

### macOS App

On macOS, you can double-click `PCM.app` to launch the TUI directly.

### Global Access

To use `pcm-launcher.sh` from anywhere:

```bash
export PATH="$PATH:$(pwd)"
```

Add this to your `~/.bashrc` or `~/.zshrc` to make it permanent.

## Prerequisites

Before using Prime Compute Manager, you need to:

1. **Install prime-cli** (if not already installed):
   ```bash
   pip install prime-cli
   ```

2. **Authenticate with PrimeIntellect**:
   ```bash
   prime login
   ```

## Manual Installation

If you prefer to install manually:

```bash
# Create virtual environment
python3 -m venv .venv

# Activate it
source .venv/bin/activate

# Install the package
pip install -e .

# Run PCM
pcm --help
```

## Uninstalling

To remove the installation (keeping source code):

```bash
./uninstall.sh
```

This removes:
- Virtual environment
- Launcher scripts
- macOS app
- Python cache files

## Troubleshooting

### "prime-cli not found"
Install it with: `pip install prime-cli`

### "Authentication required"
Run: `prime login`

### "Python 3.8+ required"
Install Python 3.8 or higher from [python.org](https://python.org)

### TUI doesn't start
Make sure Textual is installed: `pip install textual>=0.63.0`

## Features After Installation

- 🎯 **Interactive TUI**: Beautiful terminal interface for GPU management
- 🔍 **Resource Discovery**: Find GPUs across multiple providers
- 🚀 **Pod Management**: Create and monitor compute pods
- 📊 **Real-time Updates**: Auto-refresh every 30 seconds
- ⌨️ **Keyboard Shortcuts**: Quick navigation (r=refresh, c=create, q=quit)