#!/usr/bin/env bash
# =============================================================================
# CDO Vertex Dashboard - Backend Setup Script
# =============================================================================
# Run: sudo bash scripts/setup.sh
# Works whether you run it from your repo folder or from /opt/...
# =============================================================================

set -euo pipefail

APP_DIR="/opt/cdo-vertex-dashboard/backend"
SERVICE_NAME="cdo-vertex-dashboard"
VENV_DIR="${APP_DIR}/venv"

# Use the invoking user when run via sudo, fallback to "pi"
RUN_USER="${SUDO_USER:-pi}"
RUN_GROUP="${RUN_USER}"

echo "=== CDO Vertex Dashboard Backend Setup ==="

# --- 1. Ensure we're running as root ---
if [[ "${EUID}" -ne 0 ]]; then
  echo "Error: Please run with sudo"
  exit 1
fi

# --- 2. Install system dependencies ---
echo "[1/7] Installing system dependencies..."
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip wireless-tools > /dev/null

# --- 3. Create application directory structure ---
echo "[2/7] Setting up application directory..."
mkdir -p "${APP_DIR}"
mkdir -p "${APP_DIR}/data"

# --- 4. Copy files into /opt if script is being run from elsewhere ---
# scripts/setup.sh -> repo backend root should be one level up from scripts/
SCRIPT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

copy_if_exists() {
  local src="$1"
  local dst="$2"
  if [[ -e "${src}" ]]; then
    cp -a "${src}" "${dst}"
  fi
}

echo "[3/7] Syncing application files (if needed)..."
if [[ "${SCRIPT_ROOT}" != "${APP_DIR}" ]]; then
  echo "  Source: ${SCRIPT_ROOT}"
  echo "  Target: ${APP_DIR}"

  # Copy core files
  copy_if_exists "${SCRIPT_ROOT}/app.py" "${APP_DIR}/"
  copy_if_exists "${SCRIPT_ROOT}/requirements.txt" "${APP_DIR}/"

  # Copy folders if present
  for d in config routes services utils; do
    if [[ -d "${SCRIPT_ROOT}/${d}" ]]; then
      rm -rf "${APP_DIR:?}/${d}"
      cp -a "${SCRIPT_ROOT}/${d}" "${APP_DIR}/"
    fi
  done
else
  echo "  Running from ${APP_DIR}, no copy required."
fi

# Sanity check: requirements.txt must exist
if [[ ! -f "${APP_DIR}/requirements.txt" ]]; then
  echo "Error: ${APP_DIR}/requirements.txt not found"
  echo "Fix: run this script from the backend project folder that contains requirements.txt or ensure files exist in ${APP_DIR}"
  exit 1
fi

# --- 5. Create / update virtual environment and install dependencies ---
echo "[4/7] Setting up Python virtual environment..."
if [[ ! -d "${VENV_DIR}" ]]; then
  python3 -m venv "${VENV_DIR}"
fi

"${VENV_DIR}/bin/pip" install --upgrade pip -q
"${VENV_DIR}/bin/pip" install -r "${APP_DIR}/requirements.txt" -q

# --- 6. Set permissions ---
echo "[5/7] Setting file permissions..."
chown -R "${RUN_USER}:${RUN_GROUP}" "${APP_DIR}"

# --- 7. Create systemd service ---
echo "[6/7] Creating systemd service..."
cat > "/etc/systemd/system/${SERVICE_NAME}.service" <<EOF
[Unit]
Description=CDO Vertex Dashboard Backend
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${RUN_USER}
Group=${RUN_GROUP}
WorkingDirectory=${APP_DIR}
Environment="PATH=${VENV_DIR}/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=${VENV_DIR}/bin/python ${APP_DIR}/app.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

echo "[7/7] Enabling and starting service..."
systemctl daemon-reload
systemctl enable "${SERVICE_NAME}" >/dev/null
systemctl restart "${SERVICE_NAME}"

echo ""
echo "=== Setup Complete ==="
echo "  Service status: systemctl status ${SERVICE_NAME}"
echo "  View logs:      journalctl -u ${SERVICE_NAME} -f"
echo "  API endpoint:   http://$(hostname).local:5001/api/health"
echo ""
