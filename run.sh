#!/bin/bash

# Navigate to project directory
cd "$(dirname "$0")"

# Activate virtual environment
if [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "Virtual environment 'venv' not found. Please create it first using 'python3 -m venv venv'."
    exit 1
fi

# Run the Flask app
echo "Starting CMFit application..."
python app.py
