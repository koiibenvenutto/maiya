#!/bin/bash
# Simple wrapper script for the Maia CLI
# This allows running 'maia' commands without the 'python -m' prefix

# Get the directory of this script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Execute the maia CLI with any arguments passed to this script
python -m maia.cli "$@" 