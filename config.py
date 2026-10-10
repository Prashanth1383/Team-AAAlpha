"""Application configuration."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent


class Config:
    """Default configuration for local development."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")
    DATABASE_PATH = Path(
        os.environ.get("DATABASE_PATH", BASE_DIR / "instance" / "edubridge.db")
    )
    if not DATABASE_PATH.is_absolute():
        DATABASE_PATH = BASE_DIR / DATABASE_PATH

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true"
    WTF_CSRF_ENABLED = True
    MAX_CONTENT_LENGTH = 1 * 1024 * 1024

    TRACKS = (
        "Python Programming",
        "Java Programming",
        "Web Development",
        "Data Structures and Algorithms",
        "Data Analysis",
    )
    EXPERIENCE_LEVELS = ("beginner", "intermediate", "advanced")
    MIN_DAILY_MINUTES = 15
    MAX_DAILY_MINUTES = 240
    MIN_TARGET_DAYS = 7
    MAX_TARGET_DAYS = 90
    QUIZ_QUESTION_LIMIT = 8

    SCORE_NEEDS_PRACTICE = 50
    SCORE_DEVELOPING = 75


class TestConfig(Config):
    """Isolated configuration for automated tests."""

    TESTING = True
    SECRET_KEY = "test-secret-key"
    WTF_CSRF_ENABLED = False
    SESSION_COOKIE_SECURE = False
