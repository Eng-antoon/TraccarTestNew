#!/bin/bash
# Exit on error
set -e

# Create a virtual environment
python -m venv venv

# Activate the virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run your script
python server.py
