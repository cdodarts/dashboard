"""
CDO Vertex Dashboard - Main Flask Application
===============================================
Entry point for the Flask REST API backend.
Provides system monitoring, Autodarts management,
and user settings functionality.
"""

import os
import logging
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from flask_apscheduler import APScheduler

# Configure logging
log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler = APScheduler()


def create_app():
    """Application factory pattern - creates and configures the Flask app."""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    static_dir = os.environ.get(
        "DASHBOARD_STATIC_ROOT",
        os.path.join(base_dir, "frontend", "dist"),
    )

    app = Flask(__name__, static_folder=static_dir, static_url_path="")

    # Load configuration
    from config.settings import Config
    app.config.from_object(Config)

    # Enable CORS for all /api/* routes
    CORS(app, resources={
        r"/api/*": {
            "origins": "*",
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"]
        }
    })

    # Register blueprints
    from routes.system import bp as system_bp
    from routes.autodarts import bp as autodarts_bp
    from routes.settings import bp as settings_bp
    from routes.modules import bp as modules_bp
    from routes.detectors import bp as detectors_bp

    app.register_blueprint(system_bp)
    app.register_blueprint(autodarts_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(modules_bp)
    app.register_blueprint(detectors_bp)

    # Health check endpoint
    @app.route('/api/health', methods=['GET'])
    def health_check():
        """Health check endpoint to verify the API is running."""
        return jsonify({
            'status': 'healthy',
            'service': 'cdo-vertex-dashboard',
            'version': '1.0.0'
        })

    @app.route("/")
    def serve_index():
        """Serve the dashboard frontend."""
        if not os.path.exists(os.path.join(static_dir, "index.html")):
            return jsonify({"error": "frontend not found"}), 404
        return send_from_directory(static_dir, "index.html")

    @app.route("/<path:path>")
    def serve_static(path):
        """Serve static assets or fall back to index for SPA routes."""
        if path.startswith("api/"):
            return jsonify({"error": "not found"}), 404

        candidate = os.path.join(static_dir, path)
        if os.path.isfile(candidate):
            return send_from_directory(static_dir, path)

        if os.path.exists(os.path.join(static_dir, "index.html")):
            return send_from_directory(static_dir, "index.html")

        return jsonify({"error": "frontend not found"}), 404

    # Initialize and start scheduler
    _init_scheduler(app)

    logger.info("CDO Vertex Dashboard backend initialized successfully")
    return app


def _init_scheduler(app):
    """Initialize the APScheduler with configured background tasks."""
    try:
        from services.scheduler import SchedulerService

        scheduler.init_app(app)
        scheduler.start()

        # Register the auto-update check job
        scheduler_service = SchedulerService(scheduler)
        scheduler_service.register_auto_update_job()

        logger.info("Background scheduler started successfully")
    except Exception as e:
        logger.error(f"Failed to initialize scheduler: {e}")


if __name__ == '__main__':
    app = create_app()
    app.run(
        host='0.0.0.0',
        port=80,
        debug=os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    )
