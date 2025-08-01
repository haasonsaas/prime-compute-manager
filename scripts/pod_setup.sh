#!/bin/bash
# PCM Pod setup script for GPU instances
# Assumes Ubuntu-based system with CUDA drivers installed

set -e

echo "=== Prime Compute Manager Pod Setup ==="

# Update and install basics
echo "Updating system packages..."
sudo apt update
sudo apt install -y python3-pip python3-venv curl wget

# Check if prime-cli is already installed
if command -v prime &> /dev/null; then
    echo "prime-cli is already installed"
else
    echo "Installing prime-cli..."
    pip3 install --user prime-cli
    
    # Add to PATH if not already there
    if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
        echo "export PATH=\"\$HOME/.local/bin:\$PATH\"" >> ~/.bashrc
        export PATH="$HOME/.local/bin:$PATH"
    fi
fi

# Create PCM environment file
echo "Creating PCM environment configuration..."
cat > ~/.pcm_env << 'EOF'
# Prime Compute Manager environment
# This file is sourced by PCM commands

# Add prime-cli to PATH
export PATH="$HOME/.local/bin:$PATH"

# Performance optimizations for prime-cli
export PRIME_CLI_NO_USAGE_STATS=1

# Set default editor
export EDITOR=${EDITOR:-nano}
EOF

# Source the environment
# shellcheck disable=SC1090
source ~/.pcm_env

# Add to bashrc if not already there
if ! grep -q "source ~/.pcm_env" ~/.bashrc; then
    echo "source ~/.pcm_env" >> ~/.bashrc
fi

# Test prime-cli installation
echo "Testing prime-cli installation..."
if command -v prime &> /dev/null; then
    echo "✓ prime-cli is available"
    prime --version || echo "prime-cli installed but may need authentication"
else
    echo "✗ prime-cli installation failed"
    exit 1
fi

# Check GPU availability
echo "Checking GPU availability..."
if command -v nvidia-smi &> /dev/null; then
    GPU_COUNT=$(nvidia-smi --query-gpu=name --format=csv,noheader | wc -l)
    echo "✓ Found $GPU_COUNT GPU(s):"
    nvidia-smi --query-gpu=name --format=csv,noheader | sed 's/^/  - /'
else
    echo "⚠ nvidia-smi not found - GPU functionality may be limited"
fi

# Create helpful aliases
echo "Creating helpful aliases..."
cat >> ~/.bashrc << 'EOF'

# PCM aliases
alias pcm-status='prime pods list'
alias pcm-resources='prime availability list'
alias gpu-status='nvidia-smi'
EOF

echo ""
echo "=== Setup Complete! ==="
echo ""
echo "Pod is ready for Prime Compute Manager operations."
echo "You can now use 'pcm' commands from your local machine."
echo ""
echo "Useful commands to try:"
echo "  prime --version          # Check prime-cli version"
echo "  prime login              # Authenticate with PrimeIntellect"
echo "  prime availability list  # List available resources"
echo "  prime pods list          # List your running pods"
echo ""
echo "Log out and back in, or run 'source ~/.bashrc' to reload environment."