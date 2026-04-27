"""AI Gov Gen Flask application factory.

This module initialises the Flask application, configures it from environment
variables, and registers all blueprints.  Import and call :func:`create_app`
to obtain a configured :class:`flask.Flask` instance.

Typical usage::

    from ai_gov_gen import create_app
    app = create_app()
    app.run()

Or via the Flask CLI::

    flask --app ai_gov_gen run --debug
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from flask import Flask


logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default configuration values
# ---------------------------------------------------------------------------

_DEFAULT_SECRET_KEY = "dev-secret-change-me"  # noqa: S105  (placeholder only)
_DEFAULT_OUTPUT_FOLDER = Path("output")


def create_app(test_config: Optional[dict] = None) -> Flask:
    """Create and configure the Flask application.

    This is the application factory used by Flask's built-in discovery
    mechanism (``flask --app ai_gov_gen``) and by the test suite.

    Args:
        test_config: Optional mapping of configuration overrides applied
            *after* the environment-based configuration.  Primarily used
            by the test suite to supply an in-memory or temporary
            configuration without touching environment variables.

    Returns:
        A fully configured :class:`flask.Flask` application instance with
        all blueprints registered.

    Raises:
        RuntimeError: If a required directory cannot be created.
    """
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )

    # ------------------------------------------------------------------
    # Load configuration
    # ------------------------------------------------------------------
    _configure_app(app, test_config)

    # ------------------------------------------------------------------
    # Ensure output directory exists
    # ------------------------------------------------------------------
    _ensure_output_folder(app)

    # ------------------------------------------------------------------
    # Register blueprints
    # ------------------------------------------------------------------
    _register_blueprints(app)

    # ------------------------------------------------------------------
    # Configure logging
    # ------------------------------------------------------------------
    _configure_logging(app)

    logger.info(
        "AI Gov Gen application created (ENV=%s)",
        app.config.get("ENV", "production"),
    )

    return app


def _configure_app(app: Flask, test_config: Optional[dict]) -> None:
    """Apply layered configuration to the Flask app.

    Configuration is applied in the following priority order (highest last):
    1. Built-in defaults
    2. Environment variables
    3. ``test_config`` overrides (when provided)

    Args:
        app: The Flask application instance to configure.
        test_config: Optional dict of configuration overrides.
    """
    # Built-in defaults
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("FLASK_SECRET_KEY", _DEFAULT_SECRET_KEY),
        OUTPUT_FOLDER=str(
            os.environ.get("AI_GOV_GEN_UPLOAD_FOLDER", _DEFAULT_OUTPUT_FOLDER)
        ),
        # Session configuration
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        # Maximum questionnaire payload size: 2 MB
        MAX_CONTENT_LENGTH=2 * 1024 * 1024,
        # Framework options exposed to templates
        SUPPORTED_FRAMEWORKS=[
            {"id": "nist_ai_rmf", "label": "NIST AI RMF"},
            {"id": "hks", "label": "HKS AI Risk Framework"},
            {"id": "cmmc_l2", "label": "CMMC Level 2"},
            {"id": "lloyds", "label": "Lloyd's Market AI Guidelines"},
            {"id": "enterprise", "label": "Enterprise Generic"},
        ],
    )

    # Override with explicit test configuration when provided
    if test_config is not None:
        app.config.from_mapping(test_config)


def _ensure_output_folder(app: Flask) -> None:
    """Create the output folder if it does not already exist.

    The output folder is used by the exporter to store generated DOCX and
    PDF files before they are streamed to the client.

    Args:
        app: The configured Flask application whose ``OUTPUT_FOLDER`` config
            value specifies the target directory path.

    Raises:
        RuntimeError: If the directory cannot be created due to a permission
            error or other OS-level issue.
    """
    output_path = Path(app.config["OUTPUT_FOLDER"])
    try:
        output_path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise RuntimeError(
            f"Cannot create output folder '{output_path}': {exc}"
        ) from exc


def _register_blueprints(app: Flask) -> None:
    """Import and register all Flask blueprints with the application.

    Each feature area is encapsulated in its own blueprint defined in
    ``ai_gov_gen/routes.py``.  This function is the single registration
    point so that :func:`create_app` stays clean.

    Args:
        app: The Flask application instance on which blueprints will be
            registered.
    """
    # Import here to avoid circular imports at module load time
    try:
        from ai_gov_gen.routes import main_bp  # noqa: PLC0415

        app.register_blueprint(main_bp)
        logger.debug("Registered blueprint: %s", main_bp.name)
    except ImportError:
        # routes.py is generated in a later phase; skip gracefully during
        # early scaffolding so the factory can still be imported.
        logger.warning(
            "routes.py not found — blueprint registration skipped. "
            "This is expected during initial scaffolding (Phase 1)."
        )


def _configure_logging(app: Flask) -> None:
    """Set up application-level logging.

    In debug mode all log levels are emitted; in production mode only
    WARNING and above are shown.

    Args:
        app: The Flask application instance.
    """
    log_level = logging.DEBUG if app.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    # Suppress noisy WeasyPrint font warnings unless debugging
    if not app.debug:
        logging.getLogger("weasyprint").setLevel(logging.ERROR)
        logging.getLogger("fontTools").setLevel(logging.ERROR)
