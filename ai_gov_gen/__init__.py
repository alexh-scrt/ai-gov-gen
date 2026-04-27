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
from datetime import datetime
from pathlib import Path
from typing import Optional

from flask import Flask, render_template


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
    # Register template globals and filters
    # ------------------------------------------------------------------
    _register_template_globals(app)

    # ------------------------------------------------------------------
    # Register error handlers
    # ------------------------------------------------------------------
    _register_error_handlers(app)

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
    try:
        from ai_gov_gen.routes import main_bp  # noqa: PLC0415

        app.register_blueprint(main_bp)
        logger.debug("Registered blueprint: %s", main_bp.name)
    except ImportError as exc:
        logger.warning(
            "routes.py could not be imported — blueprint registration skipped. "
            "Error: %s",
            exc,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "Unexpected error registering blueprints: %s", exc, exc_info=True
        )
        raise


def _register_template_globals(app: Flask) -> None:
    """Register Jinja2 global variables and custom filters.

    Injects commonly needed values (current year, app version, etc.) into
    every template context so that base templates and child templates can
    reference them without requiring explicit ``render_template`` kwargs.

    Also registers custom Jinja2 filters for convenience formatting.

    Args:
        app: The Flask application instance.
    """

    @app.context_processor
    def inject_now() -> dict:
        """Inject the current datetime into all templates as ``now``."""
        return {"now": datetime.utcnow()}

    @app.context_processor
    def inject_app_meta() -> dict:
        """Inject application metadata into all templates."""
        return {
            "app_name": "AI Gov Gen",
            "app_version": "0.1.0",
            "app_description": (
                "Automated AI governance documentation generator aligned with "
                "NIST AI RMF, HKS AI Risk Framework, CMMC, and Lloyd's market standards."
            ),
        }

    # ---------------------------------------------------------------------------
    # Custom Jinja2 filters
    # ---------------------------------------------------------------------------

    @app.template_filter("risk_colour")
    def risk_colour_filter(risk_level: str) -> str:
        """Return a Bootstrap colour name for a given risk level string.

        Args:
            risk_level: One of ``Low``, ``Medium``, ``High``, ``Critical``.

        Returns:
            Bootstrap contextual colour string (e.g. ``"success"``).
        """
        mapping = {
            "Low": "success",
            "Medium": "warning",
            "High": "danger",
            "Critical": "dark",
        }
        return mapping.get(risk_level, "secondary")

    @app.template_filter("risk_icon")
    def risk_icon_filter(risk_level: str) -> str:
        """Return a Bootstrap Icons class name for a given risk level.

        Args:
            risk_level: One of ``Low``, ``Medium``, ``High``, ``Critical``.

        Returns:
            Bootstrap Icons icon class string (e.g. ``"bi-check-circle-fill"``).
        """
        mapping = {
            "Low": "bi-check-circle-fill",
            "Medium": "bi-exclamation-circle-fill",
            "High": "bi-exclamation-triangle-fill",
            "Critical": "bi-x-octagon-fill",
        }
        return mapping.get(risk_level, "bi-circle")

    @app.template_filter("status_colour")
    def status_colour_filter(status: str) -> str:
        """Return a CSS class suffix for an SSP implementation status string.

        Args:
            status: Implementation status string.

        Returns:
            CSS class suffix string.
        """
        mapping = {
            "Implemented": "implemented",
            "Partially Implemented": "partially",
            "Planned": "planned",
            "Not Implemented": "not-implemented",
            "Not Applicable": "not-applicable",
        }
        return mapping.get(status, "not-implemented")

    @app.template_filter("percentage")
    def percentage_filter(value: float, decimals: int = 1) -> str:
        """Format a float as a percentage string.

        Args:
            value: Float value (0–100).
            decimals: Number of decimal places.

        Returns:
            Formatted string such as ``"42.5%"``.
        """
        try:
            return f"{float(value):.{decimals}f}%"
        except (TypeError, ValueError):
            return "0.0%"

    @app.template_filter("score_bar_width")
    def score_bar_width_filter(score: float) -> str:
        """Clamp a risk score to [0, 100] and return as a CSS width string.

        Args:
            score: Normalised score float.

        Returns:
            CSS width string such as ``"42.5%"``.
        """
        try:
            clamped = max(0.0, min(100.0, float(score)))
            return f"{clamped:.1f}%"
        except (TypeError, ValueError):
            return "0%"

    logger.debug("Template globals and filters registered.")


def _register_error_handlers(app: Flask) -> None:
    """Register application-level HTTP error handlers.

    These handlers catch HTTP errors that propagate above the Blueprint
    level (e.g. errors raised outside of request contexts, or errors not
    handled by the Blueprint's own ``app_errorhandler`` decorators).

    We also register handlers at the app level as belt-and-suspenders so
    that plain Flask error responses always receive a styled template
    rather than the default Werkzeug HTML.

    Args:
        app: The Flask application instance.
    """

    @app.errorhandler(400)
    def bad_request(error: Exception) -> tuple[str, int]:
        """Handle 400 Bad Request errors."""
        logger.warning("400 Bad Request: %s", error)
        return (
            _render_error_page(
                error_code=400,
                error_title="Bad Request",
                error_message=(
                    "The server could not understand your request. "
                    "Please check your input and try again."
                ),
            ),
            400,
        )

    @app.errorhandler(403)
    def forbidden(error: Exception) -> tuple[str, int]:
        """Handle 403 Forbidden errors."""
        logger.warning("403 Forbidden: %s", error)
        return (
            _render_error_page(
                error_code=403,
                error_title="Access Forbidden",
                error_message=(
                    "You do not have permission to access this resource."
                ),
            ),
            403,
        )

    @app.errorhandler(404)
    def not_found(error: Exception) -> tuple[str, int]:
        """Handle 404 Not Found errors."""
        logger.debug("404 Not Found: %s", error)
        return (
            _render_error_page(
                error_code=404,
                error_title="Page Not Found",
                error_message=(
                    "The page you requested could not be found. "
                    "Please check the URL or return to the home page."
                ),
            ),
            404,
        )

    @app.errorhandler(405)
    def method_not_allowed(error: Exception) -> tuple[str, int]:
        """Handle 405 Method Not Allowed errors."""
        logger.warning("405 Method Not Allowed: %s", error)
        return (
            _render_error_page(
                error_code=405,
                error_title="Method Not Allowed",
                error_message=(
                    "The HTTP method used is not allowed for this endpoint."
                ),
            ),
            405,
        )

    @app.errorhandler(413)
    def request_too_large(error: Exception) -> tuple[str, int]:
        """Handle 413 Request Entity Too Large errors."""
        logger.warning("413 Request Too Large: %s", error)
        return (
            _render_error_page(
                error_code=413,
                error_title="Request Too Large",
                error_message=(
                    "The submitted form data exceeded the maximum allowed size (2 MB). "
                    "Please reduce the size of your answers and try again."
                ),
            ),
            413,
        )

    @app.errorhandler(500)
    def internal_error(error: Exception) -> tuple[str, int]:
        """Handle 500 Internal Server Error responses."""
        logger.exception("Internal server error: %s", error)
        return (
            _render_error_page(
                error_code=500,
                error_title="Internal Server Error",
                error_message=(
                    "An unexpected error occurred on the server. "
                    "The error has been logged. Please try again or "
                    "contact support if the problem persists."
                ),
            ),
            500,
        )

    @app.errorhandler(503)
    def service_unavailable(error: Exception) -> tuple[str, int]:
        """Handle 503 Service Unavailable errors."""
        logger.error("503 Service Unavailable: %s", error)
        return (
            _render_error_page(
                error_code=503,
                error_title="Service Unavailable",
                error_message=(
                    "The service is temporarily unavailable. "
                    "Please try again in a few moments."
                ),
            ),
            503,
        )

    logger.debug("Application-level error handlers registered.")


def _render_error_page(
    error_code: int,
    error_title: str,
    error_message: str,
) -> str:
    """Render the error page template, with a plain-text fallback.

    Attempts to render ``error.html``; if that template is missing (e.g.
    during initial scaffolding) falls back to a minimal HTML string so
    the error handler never itself raises an exception.

    Args:
        error_code: HTTP status code integer.
        error_title: Short human-readable error title.
        error_message: Longer descriptive message for the user.

    Returns:
        Rendered HTML string.
    """
    try:
        return render_template(
            "error.html",
            error_code=error_code,
            error_title=error_title,
            error_message=error_message,
            title=f"{error_code} — {error_title}",
        )
    except Exception:  # noqa: BLE001
        # Fallback — minimal styled HTML that does not depend on any template
        return (
            f"<!DOCTYPE html><html lang='en'><head>"
            f"<meta charset='UTF-8'/>"
            f"<meta name='viewport' content='width=device-width,initial-scale=1'/>"
            f"<title>{error_code} — {error_title}</title>"
            f"<style>"
            f"body{{font-family:system-ui,sans-serif;background:#f8f9fa;color:#212529;"
            f"display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;}}"
            f".box{{background:#fff;border:1px solid #dee2e6;border-radius:.5rem;"
            f"padding:3rem 2rem;max-width:480px;text-align:center;box-shadow:0 2px 12px rgba(0,0,0,.08);}}"
            f"h1{{font-size:3rem;font-weight:800;color:#1a3a5c;margin:0 0 .5rem;}}"
            f"h2{{font-size:1.1rem;font-weight:700;margin:0 0 1rem;color:#212529;}}"
            f"p{{color:#6c757d;margin:0 0 1.5rem;}}"
            f"a{{display:inline-block;padding:.5rem 1.25rem;background:#1a3a5c;color:#fff;"
            f"border-radius:.375rem;text-decoration:none;font-weight:600;}}"
            f"</style></head><body>"
            f"<div class='box'>"
            f"<h1>{error_code}</h1>"
            f"<h2>{error_title}</h2>"
            f"<p>{error_message}</p>"
            f"<a href='/'>Return to Home</a>"
            f"</div></body></html>"
        )


def _configure_logging(app: Flask) -> None:
    """Set up application-level logging.

    In debug mode all log levels are emitted; in production mode only
    INFO and above are shown.

    Also suppresses chatty third-party loggers (WeasyPrint, fontTools)
    unless the application is running in debug mode.

    Args:
        app: The Flask application instance.
    """
    log_level = logging.DEBUG if app.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    # Suppress noisy WeasyPrint font / CSS warnings in production
    if not app.debug:
        logging.getLogger("weasyprint").setLevel(logging.ERROR)
        logging.getLogger("weasyprint.progress").setLevel(logging.ERROR)
        logging.getLogger("fontTools").setLevel(logging.ERROR)
        logging.getLogger("fontTools.subset").setLevel(logging.ERROR)
        logging.getLogger("PIL").setLevel(logging.WARNING)

    logger.debug("Logging configured at level %s.", logging.getLevelName(log_level))
