#!/bin/bash
# Simple wrapper script for the Maia CLI
# This allows running 'maia' commands without the 'python -m' prefix

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Add the project root to PYTHONPATH
export PYTHONPATH="${SCRIPT_DIR}:${PYTHONPATH}"

# Run the maia module
python3 -m maia "$@" 