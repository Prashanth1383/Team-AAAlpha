"""JSON API routes."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request, session

from database.db import query_all, query_one, utc_now
from services.analytics_service import dashboard_payload, get_preferences, progress_payload, save_preferences
from services.quiz_service import list_questions_for_track, save_attempt, score_answers
from services.recommendation_engine import (
    generate_plan,
    get_current_plan,
    list_resources,
    replace_saved_plan,
    set_task_completed,
)
from services.validation import ValidationError, validate_display_name, validate_preferences

api_bp = Blueprint("api", __name__)


def _student_id() -> int:
    return int(session["student_id"])


def _json() -> dict:
    payload = request.get_json(silent=True)
    if payload is None:
        raise ValidationError("Expected a JSON body.")
    if not isinstance(payload, dict):
        raise ValidationError("JSON body must be an object.")
    return payload


@api_bp.get("/health")
def health():
    return jsonify({"ok": True, "service": "edubridge-ai"}), 200


@api_bp.get("/quiz")
def get_quiz():
    prefs = get_preferences(_student_id())
    track = request.args.get("track") or (prefs["track"] if prefs else None)
    if not track:
        raise ValidationError("A learning track is required.", "track")
    if track not in current_app.config["TRACKS"]:
        raise ValidationError("Unknown learning track.", "track")
    questions = list_questions_for_track(track)
    return jsonify({"ok": True, "track": track, "questions": questions})


@api_bp.post("/quiz/submit")
def submit_quiz():
    prefs = get_preferences(_student_id())
    data = _json()
    track = data.get("track") or (prefs["track"] if prefs else None)
    if not track:
        raise ValidationError("A learning track is required.", "track")
    if track not in current_app.config["TRACKS"]:
        raise ValidationError("Unknown learning track.", "track")
    answers = data.get("answers")
    if not isinstance(answers, list):
        raise ValidationError("answers must be a list.", "answers")
    scored = score_answers(track, answers)
    attempt_id = save_attempt(_student_id(), scored)
    scored["attempt_id"] = attempt_id
    return jsonify({"ok": True, "result": scored}), 201


@api_bp.post("/goals")
def save_goals():
    data = validate_preferences(_json())
    save_preferences(_student_id(), data, utc_now())
    return jsonify({"ok": True, "preferences": data})


@api_bp.post("/study-plan/generate")
def generate_study_plan():
    student_id = _student_id()
    prefs = get_preferences(student_id)
    if prefs is None:
        raise ValidationError("Save a learning goal before generating a plan.")
    latest = query_one(
        """
        SELECT id FROM quiz_attempts
        WHERE student_id = ?
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """,
        (student_id,),
    )
    if latest is None:
        raise ValidationError("Complete a diagnostic quiz before generating a plan.")
    topic_results = [
        dict(row)
        for row in query_all(
            """
            SELECT topic, correct_count, total_count, score_percent, band
            FROM topic_results
            WHERE attempt_id = ?
            """,
            (latest["id"],),
        )
    ]
    plan = generate_plan(student_id, dict(prefs), topic_results, int(latest["id"]))
    plan_id = replace_saved_plan(plan)
    stored = get_current_plan(student_id)
    return jsonify({"ok": True, "plan_id": plan_id, "plan": stored, "ranked_topics": plan["ranked_topics"]}), 201


@api_bp.post("/tasks/<int:task_id>/complete")
def complete_task(task_id: int):
    data = request.get_json(silent=True) or {}
    completed = bool(data.get("completed", True))
    plan = set_task_completed(_student_id(), task_id, completed)
    return jsonify({"ok": True, "plan": plan})


@api_bp.get("/resources")
def search_resources():
    items = list_resources(
        track=request.args.get("track") or None,
        topic=request.args.get("topic") or None,
        difficulty=request.args.get("difficulty") or None,
        query=request.args.get("q") or None,
    )
    return jsonify({"ok": True, "resources": items, "count": len(items)})


@api_bp.get("/progress")
def progress():
    return jsonify({"ok": True, **progress_payload(_student_id())})


@api_bp.get("/dashboard")
def dashboard():
    student = query_one("SELECT * FROM students WHERE id = ?", (_student_id(),))
    if student is None:
        raise ValidationError("Demo profile not found.")
    return jsonify({"ok": True, **dashboard_payload(int(student["id"]), student["display_name"])})


@api_bp.post("/profile")
def update_profile():
    data = _json()
    name = validate_display_name(data)
    prefs = validate_preferences(data)
    from database.db import get_db

    db = get_db()
    db.execute("UPDATE students SET display_name = ? WHERE id = ?", (name, _student_id()))
    db.commit()
    save_preferences(_student_id(), prefs, utc_now())
    return jsonify({"ok": True, "display_name": name, "preferences": prefs})
