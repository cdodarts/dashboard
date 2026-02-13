# CDO Vertex Dashboard - Backend

Flask-based REST API backend for the CDO Vertex Raspberry Pi dashboard. Provides system monitoring, Autodarts management, and user settings.

## Quick Start

### Automated Setup (Raspberry Pi)
```bash
sudo bash scripts/setup.sh
```

### Manual Setup
```bash
cd /opt/cdo-vertex-dashboard/backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create data directory
mkdir -p data

# Run
python app.py
```

The API will be available at `http://cdo-vertex.local:5001`.

## API Endpoints

### Health
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |

### System Monitoring
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/system/status` | Full system overview |
| GET | `/api/system/cpu` | CPU usage |
| GET | `/api/system/memory` | Memory usage |
| GET | `/api/system/disk` | Disk usage |
| GET | `/api/system/temperature` | Pi temperature |
| GET | `/api/system/network` | Network interfaces |
| GET | `/api/system/wifi` | WiFi signal strength |
| GET | `/api/system/uptime` | System uptime |
| GET | `/api/system/hostname` | Hostname info |

### Autodarts Management
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/autodarts/status` | Installation & service status |
| POST | `/api/autodarts/install` | Install Autodarts |
| POST | `/api/autodarts/update` | Update Autodarts |
| GET | `/api/autodarts/check-update` | Check for updates |
| POST | `/api/autodarts/service/start` | Start service |
| POST | `/api/autodarts/service/stop` | Stop service |
| POST | `/api/autodarts/service/restart` | Restart service |
| GET | `/api/autodarts/logs?lines=50` | Get service logs |

### Settings
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/settings` | Get all settings |
| POST | `/api/settings` | Update settings (merge) |
| GET | `/api/settings/auto-update` | Get auto-update settings |
| POST | `/api/settings/auto-update` | Update auto-update settings |
| POST | `/api/settings/reset` | Reset to defaults |

## Service Management

```bash
# Status
sudo systemctl status cdo-vertex-dashboard

# Logs
journalctl -u cdo-vertex-dashboard -f

# Restart
sudo systemctl restart cdo-vertex-dashboard
```

## Project Structure

```
backend/
├── app.py                     # Flask application entry point
├── requirements.txt           # Python dependencies
├── config/settings.py         # Application configuration
├── routes/
│   ├── system.py              # System monitoring endpoints
│   ├── autodarts.py           # Autodarts management endpoints
│   └── settings.py            # User settings endpoints
├── services/
│   ├── system_monitor.py      # System metrics collection
│   ├── autodarts_manager.py   # Autodarts integration
│   ├── settings_manager.py    # Settings persistence
│   └── scheduler.py           # Background task scheduler
├── utils/helpers.py           # Shared utility functions
├── data/settings.json         # User settings (auto-created)
└── scripts/
    ├── setup.sh               # Automated setup
    └── test_api.sh            # API test suite
```

## Adding New Features

1. Create a service in `services/`
2. Create a route blueprint in `routes/`
3. Register the blueprint in `app.py`

No existing code needs to change.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `INFO` | Logging level |
| `FLASK_DEBUG` | `false` | Debug mode |
| `SECRET_KEY` | (built-in) | Flask secret key |
| `CDO_VERTEX_BASE_DIR` | `/opt/cdo-vertex-dashboard` | Base directory |
| `AUTODARTS_MANAGER_PATH` | `/opt/autodarts-manager` | Autodarts manager path |

## Testing

```bash
bash scripts/test_api.sh
# Or against a specific host:
bash scripts/test_api.sh http://cdo-vertex.local:5001
```
