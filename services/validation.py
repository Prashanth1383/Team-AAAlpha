"""Shared input validation for forms and JSON APIs."""

from __future__ import annotations

from typing import Any

from flask import current_app


class ValidationError(ValueError):
    """Raised when user input fails validation."""

    def __init__(self, message: str, field: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.field = field


def require_string(data: dict[str, Any], field: str, allowed: tuple[str, ...] | None = None) -> str:
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field.replace('_', ' ').title()} is required.", field)
    value = value.strip()
    if allowed and value not in allowed:
        raise ValidationError(f"Invalid value for {field.replace('_', ' ')}.", field)
    return value


def require_int(data: dict[str, Any], field: str, minimum: int, maximum: int) -> int:
    raw = data.get(field)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise ValidationError(f"{field.replace('_', ' ').title()} must be a whole number.", field)
    if value < minimum or value > maximum:
        raise ValidationError(
            f"{field.replace('_', ' ').title()} must be between {minimum} and {maximum}.",
            field,
        )
    return value


def validate_preferences(data: dict[str, Any]) -> dict[str, Any]:
    cfg = current_app.config
    track = require_string(data, "track", cfg["TRACKS"])
    experience_level = require_string(data, "experience_level", cfg["EXPERIENCE_LEVELS"])
    daily_minutes = require_int(
        data, "daily_minutes", cfg["MIN_DAILY_MINUTES"], cfg["MAX_DAILY_MINUTES"]
    )
    target_days = require_int(
        data, "target_days", cfg["MIN_TARGET_DAYS"], cfg["MAX_TARGET_DAYS"]
    )
    return {
        "track": track,
        "experience_level": experience_level,
        "daily_minutes": daily_minutes,
        "target_days": target_days,
    }


def validate_display_name(data: dict[str, Any]) -> str:
    name = require_string(data, "display_name")
    if len(name) > 80:
        raise ValidationError("Display name must be 80 characters or fewer.", "display_name")
    return name


def band_for_score(score_percent: float) -> str:
    threshold_practice = current_app.config["SCORE_NEEDS_PRACTICE"]
    threshold_developing = current_app.config["SCORE_DEVELOPING"]
    if score_percent < threshold_practice:
        return "needs_practice"
    if score_percent < threshold_developing:
        return "developing"
    return "good_progress"


def band_label(band: str) -> str:
    return {
        "needs_practice": "Needs focused practice",
        "developing": "Developing",
        "good_progress": "Good progress",
    }.get(band, band)
