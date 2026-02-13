# CDO Vertex Dashboard

Main dashboard and control interface for CDO Vertex darts devices. Provides system monitoring, Autodarts integration, and device management.

## Features

- 📊 Real-time system monitoring (CPU, memory, network)
- 🎯 Autodarts manager integration
- ⚙️ Device settings and configuration
- 🔄 Automatic updates
- 📱 Responsive web interface
- 🔌 REST API backend

## Architecture

```
dashboard/
├── backend/
│   ├── app.py                  # Flask application entry point
│   ├── routes/                 # API endpoints
│   ├── services/               # Business logic
│   ├── autodarts_manager.py    # Autodarts integration
│   ├── system_monitor.py       # System metrics
│   ├── settings_manager.py     # Configuration
│   ├── requirements.txt        # Python dependencies
│   └── config/                 # Configuration files
├── frontend/
│   └── dist/                   # Built frontend assets
├── data/                       # Runtime data (SQLite, logs)
├── start.sh                    # Service startup script
└── health-check.sh             # Health validation
```

## Installation

### Via CDO Vertex Deployment System (Recommended)

Dashboard is automatically installed on first boot after WiFi connection.

Manual update:
```bash
sudo cdo-update dashboard
```

### Manual Installation

```bash
# Download latest release
wget https://github.com/cdo-darts/dashboard/releases/latest/download/dashboard-*.tar.gz
wget https://github.com/cdo-darts/dashboard/releases/latest/download/SHA256SUMS

# Verify checksum
sha256sum -c SHA256SUMS

# Extract
tar -xzf dashboard-*.tar.gz
cd dashboard-*/

# Run
./start.sh
```

## Development

### Prerequisites

- Python 3.9+
- Node.js 16+ (for frontend development)

### Backend Setup

```bash
# Clone repository
git clone https://github.com/cdo-darts/dashboard.git
cd dashboard/backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run backend
python3 app.py
```

Backend runs on `http://localhost:5000`

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Development server
npm run dev

# Build for production
npm run build
# Output goes to frontend/dist/
```

## API Endpoints

### System Monitoring

- `GET /api/system/status` - Current system status
- `GET /api/system/metrics` - System metrics (CPU, memory, etc.)

### Autodarts

- `GET /api/autodarts/status` - Autodarts connection status
- `POST /api/autodarts/connect` - Connect to Autodarts
- `POST /api/autodarts/disconnect` - Disconnect

### Settings

- `GET /api/settings` - Get all settings
- `POST /api/settings` - Update settings

### Updates

- `GET /api/updates/status` - Check for available updates
- `POST /api/updates/install` - Install available updates

## Configuration

Backend configuration in `backend/settings.py`:

```python
# Flask settings
FLASK_HOST = '0.0.0.0'
FLASK_PORT = 5000
DEBUG = False

# Autodarts settings
AUTODARTS_API_URL = 'https://api.autodarts.io'

# System settings
MONITOR_INTERVAL = 5  # seconds
```

## Environment Variables

- `LOG_LEVEL` - Logging level (DEBUG, INFO, WARNING, ERROR)
- `FLASK_ENV` - Flask environment (production, development)
- `STATIC_DIR` - Frontend static files directory

## Systemd Service

Installed at: `/etc/systemd/system/cdo-vertex-dashboard.service`

```bash
# Status
sudo systemctl status cdo-vertex-dashboard

# Logs
journalctl -u cdo-vertex-dashboard -f

# Restart
sudo systemctl restart cdo-vertex-dashboard
```

## Deployment

### Creating a Release

```bash
# Build frontend first
cd frontend
npm run build

# Tag version
git tag v0.1.0
git push origin v0.1.0

# GitHub Actions will automatically:
# 1. Create tarball (includes frontend/dist)
# 2. Generate SHA256SUMS
# 3. Create GitHub release
```

### Pre-release Checklist

- [ ] Frontend built and committed to `frontend/dist/`
- [ ] Backend dependencies updated in `requirements.txt`
- [ ] Version bumped in appropriate files
- [ ] Changelog updated
- [ ] Tests passing

## Testing

```bash
# Backend tests
cd backend
python3 -m pytest

# API testing
bash test_api.sh
```

## Troubleshooting

### Dashboard not loading
```bash
# Check if service is running
sudo systemctl status cdo-vertex-dashboard

# Check logs
journalctl -u cdo-vertex-dashboard -n 50

# Verify frontend files exist
ls -la frontend/dist/
```

### API errors
```bash
# Check Python dependencies
cd backend
source venv/bin/activate
pip list

# Test connectivity
curl http://localhost:5000/api/system/status
```

### Update issues
```bash
# Check update status
cat /var/lib/cdo/update-status.json

# Manual update
sudo cdo-update dashboard

# Rollback if needed
sudo cdo-rollback dashboard
```

## Directory Structure

### Data Directory (`/var/lib/cdo/dashboard`)

- `settings.db` - SQLite database for settings
- `logs/` - Application logs
- `cache/` - Temporary cache files

### Installation Directory (`/opt/cdo/dashboard`)

```
/opt/cdo/dashboard/
├── current -> releases/0.1.0
├── releases/
│   ├── 0.1.0/
│   └── 0.2.0/
└── VERSION
```

## Performance

Typical resource usage:
- CPU: ~2-5% idle, ~10-15% during updates
- Memory: ~40-60 MB
- Disk: ~100 MB

## Security

- Runs as dedicated user via systemd DynamicUser
- Protected filesystem access (read-only system files)
- CORS configured for localhost only
- No external network access required

## License

Proprietary - CDO Darts LLC

## Support

For issues, contact support@cdo-darts.com
