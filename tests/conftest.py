"""Shared test fixtures. Tests use a temporary SQLite file."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from app import create_app
from database.db import init_schema
from database.seed import seed_database


@pytest.fixture()
def app():
    handle, path = tempfile.mkstemp(suffix=".db")
    os.close(handle)
    application = create_app(
        {
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "SECRET_KEY": "test-secret-key",
            "DATABASE_PATH": Path(path),
            "SESSION_COOKIE_SECURE": False,
        }
    )
    with application.app_context():
        init_schema(application)
        seed_database()
    yield application
    os.unlink(path)


@pytest.fixture()
def client(app):
    return app.test_client()
