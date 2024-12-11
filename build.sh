#!/bin/bash
set -e

# Install requirements
pip install -r requirements.txt

# Run build script
python build.py

# Show result
echo "Build complete! Executable is in dist/ directory"
ls -l dist/ 