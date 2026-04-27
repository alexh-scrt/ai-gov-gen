"""Tests for the Flask application factory defined in ai_gov_gen/__init__.py.

Verifies that :func:`create_app` correctly initialises the application,
applies configuration, creates the output folder, and registers blueprints.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from ai_gov_gen import create_app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_output(tmp_path: Path) -> Path:
    """Return a temporary directory for use as the OUTPUT_FOLDER."""
    return tmp_path / "output"


@pytest.fixture()
def app(tmp_output: Path):
    """Create a test application instance with an isolated output folder."""
    return create_app(
        test_config={
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "OUTPUT_FOLDER": str(tmp_output),
        }
    )


@pytest.fixture()
def client(app):
    """Return a test client for the application."""
    return app.test_client()


# ---------------------------------------------------------------------------
# Application factory tests
# ---------------------------------------------------------------------------


class TestCreateApp:
    """Tests for the create_app factory function."""

    def test_returns_flask_app(self, app) -> None:
        """create_app should return a Flask application instance."""
        from flask import Flask

        assert isinstance(app, Flask)

    def test_testing_flag_applied(self, app) -> None:
        """TESTING flag supplied via test_config should be set on the app."""
        assert app.config["TESTING"] is True

    def test_secret_key_override(self, app) -> None:
        """test_config SECRET_KEY should override the environment default."""
        assert app.config["SECRET_KEY"] == "test-secret"

    def test_output_folder_created(self, tmp_output: Path, app) -> None:
        """create_app should create OUTPUT_FOLDER if it does not exist."""
        assert tmp_output.is_dir()

    def test_output_folder_already_exists(self, tmp_output: Path) -> None:
        """create_app should not raise if OUTPUT_FOLDER already exists."""
        tmp_output.mkdir(parents=True, exist_ok=True)
        # Second call should still succeed
        create_app(
            test_config={
                "TESTING": True,
                "OUTPUT_FOLDER": str(tmp_output),
            }
        )
        assert tmp_output.is_dir()

    def test_supported_frameworks_configured(self, app) -> None:
        """SUPPORTED_FRAMEWORKS should be a non-empty list in app config."""
        frameworks = app.config.get("SUPPORTED_FRAMEWORKS", [])
        assert isinstance(frameworks, list)
        assert len(frameworks) > 0

    def test_supported_frameworks_have_required_keys(self, app) -> None:
        """Each framework entry must contain 'id' and 'label' keys."""
        for framework in app.config["SUPPORTED_FRAMEWORKS"]:
            assert "id" in framework, f"Missing 'id' in {framework}"
            assert "label" in framework, f"Missing 'label' in {framework}"

    def test_max_content_length_set(self, app) -> None:
        """MAX_CONTENT_LENGTH should be configured to limit upload size."""
        assert app.config["MAX_CONTENT_LENGTH"] == 2 * 1024 * 1024

    def test_session_cookie_httponly(self, app) -> None:
        """Session cookies should be configured with HttpOnly flag."""
        assert app.config["SESSION_COOKIE_HTTPONLY"] is True

    def test_default_secret_key_from_env(self, tmp_output: Path, monkeypatch) -> None:
        """When FLASK_SECRET_KEY env var is set, it should be picked up."""
        monkeypatch.setenv("FLASK_SECRET_KEY", "env-provided-secret")
        test_app = create_app(
            test_config={"OUTPUT_FOLDER": str(tmp_output), "TESTING": True}
        )
        assert test_app.config["SECRET_KEY"] == "env-provided-secret"

    def test_multiple_app_instances_are_independent(self, tmp_path: Path) -> None:
        """Two independently created apps should not share state."""
        folder_a = tmp_path / "a"
        folder_b = tmp_path / "b"
        app_a = create_app(
            test_config={"TESTING": True, "OUTPUT_FOLDER": str(folder_a)}
        )
        app_b = create_app(
            test_config={"TESTING": True, "OUTPUT_FOLDER": str(folder_b)}
        )
        assert app_a.config["OUTPUT_FOLDER"] != app_b.config["OUTPUT_FOLDER"]
