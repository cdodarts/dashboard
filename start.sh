#!/bin/bash
# CDO Vertex Dashboard - Startup Script
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/backend"

echo "Starting CDO Vertex Dashboard..."

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install/update dependencies
echo "Installing dependencies..."
pip install --quiet -r requirements.txt

# Ensure data directory exists
mkdir -p "$SCRIPT_DIR/data"
mkdir -p /var/lib/cdo/dashboard

# Set environment
export FLASK_APP=app.py
export FLASK_ENV=production

# Start the Dashboard
echo "Dashboard backend starting..."
exec python3 app.py
