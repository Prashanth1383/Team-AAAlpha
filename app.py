"""EduBridge AI Flask application factory."""

from __future__ import annotations

import logging
import secrets
from pathlib import Path

from flask import Flask, jsonify, render_template, request, session

from config import Config
from database.db import (
    ensure_student_for_user,
    get_or_create_demo_student,
    init_app as init_database,
    query_one,
)
from services.validation import ValidationError


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    if not app.config.get("TESTING"):
        logging.basicConfig(level=logging.INFO)

    init_database(app)

    if not app.config.get("TESTING"):
        db_path = Path(app.config["DATABASE_PATH"])
        database_exists = db_path.exists()
        with app.app_context():
            from database.db import init_schema
            from database.seed import seed_database

            init_schema(app)
            quiz_count = query_one("SELECT COUNT(*) AS c FROM quiz_questions")
            if not database_exists or (quiz_count is not None and int(quiz_count["c"]) == 0):
                seed_database()

    from routes.api import api_bp
    from routes.pages import pages_bp

    app.register_blueprint(pages_bp)
    app.register_blueprint(api_bp, url_prefix="/api")

    @app.before_request
    def prepare_request() -> None:
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_hex(32)

        if session.get("user_id"):
            user = query_one("SELECT * FROM app_users WHERE id = ?", (session["user_id"],))
            if user is None:
                session.pop("user_id", None)
                session.pop("student_id", None)
            else:
                session["student_id"] = ensure_student_for_user(int(user["id"]), str(user["username"]))
        elif app.config.get("TESTING") and "student_id" not in session:
            student = get_or_create_demo_student()
            session["student_id"] = int(student["id"])
        elif "student_id" not in session and request.endpoint not in {
            "pages.landing",
            "pages.health",
            "pages.login",
            "pages.signup",
            "pages.logout",
            "api.health",
            "static",
        }:
            student = get_or_create_demo_student()
            session["student_id"] = int(student["id"])

        if request.method in {"POST", "PUT", "PATCH", "DELETE"} and app.config.get(
            "WTF_CSRF_ENABLED", True
        ):
            token = request.form.get("csrf_token") or request.headers.get("X-CSRFToken")
            if not token or not secrets.compare_digest(token, session.get("csrf_token", "")):
                if _wants_json():
                    return jsonify({"ok": False, "error": "Invalid or missing CSRF token."}), 400
                return render_template("error.html", code=400, message="Invalid form token. Refresh and try again."), 400

        return None

    @app.context_processor
    def inject_globals() -> dict:
        return {
            "csrf_token": session.get("csrf_token", ""),
            "is_demo": True,
        }

    @app.errorhandler(404)
    def not_found(_error):  # type: ignore[no-untyped-def]
        if _wants_json():
            return jsonify({"ok": False, "error": "Not found."}), 404
        return render_template("error.html", code=404, message="That page was not found."), 404

    @app.errorhandler(405)
    def method_not_allowed(_error):  # type: ignore[no-untyped-def]
        if _wants_json():
            return jsonify({"ok": False, "error": "Method not allowed."}), 405
        return render_template("error.html", code=405, message="That action is not allowed."), 405

    @app.errorhandler(ValidationError)
    def handle_validation(error: ValidationError):
        if _wants_json():
            return jsonify({"ok": False, "error": error.message, "field": error.field}), 400
        return render_template("error.html", code=400, message=error.message), 400

    @app.errorhandler(500)
    def server_error(error):  # type: ignore[no-untyped-def]
        app.logger.exception("Unhandled server error: %s", error)
        if _wants_json():
            return jsonify({"ok": False, "error": "Something went wrong. Try again."}), 500
        return render_template("error.html", code=500, message="Something went wrong. Try again."), 500

    return app


def _wants_json() -> bool:
    if request.path.startswith("/api/"):
        return True
    accept = request.headers.get("Accept", "")
    return "application/json" in accept and "text/html" not in accept


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host="127.0.0.1", port=5000)
