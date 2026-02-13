#!/bin/bash
# CDO Vertex Dashboard - Health Check
set -euo pipefail

# Check if the backend directory exists
if [ ! -d "backend" ]; then
    echo "ERROR: backend directory not found"
    exit 1
fi

# Check if app.py exists
if [ ! -f "backend/app.py" ]; then
    echo "ERROR: backend/app.py not found"
    exit 1
fi

# Check if frontend dist exists
if [ ! -d "frontend/dist" ]; then
    echo "WARNING: frontend/dist not found (optional)"
fi

# Check if Python dependencies can be imported
cd backend
if ! python3 -c "import flask, flask_cors, flask_apscheduler, psutil, requests" 2>/dev/null; then
    echo "ERROR: Required Python packages not installed"
    exit 1
fi

echo "Health check passed"
exit 0
