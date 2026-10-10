"""HTML page routes."""

from __future__ import annotations

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for

from database.db import (
    authenticate_user,
    create_app_user,
    ensure_student_for_user,
    query_one,
    utc_now,
)
from services.analytics_service import (
    dashboard_payload,
    get_preferences,
    progress_payload,
    save_preferences,
)
from services.quiz_service import classify_topics, get_attempt, latest_attempt, list_questions_for_track, next_steps
from services.recommendation_engine import get_current_plan, list_resources
from services.validation import ValidationError, band_label, validate_display_name, validate_preferences

pages_bp = Blueprint("pages", __name__)


def _student():
    row = query_one("SELECT * FROM students WHERE id = ?", (session["student_id"],))
    if row is None:
        raise ValidationError("Demo profile not found. Reinitialize the database.")
    return dict(row)


@pages_bp.get("/")
def landing():
    return render_template("index.html")


@pages_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        if not username or not password:
            flash("Username and password are required.", "error")
            return render_template("login.html", form={"username": username}), 400

        user = authenticate_user(username, password)
        if user is None:
            flash("Invalid username or password.", "error")
            return render_template("login.html", form={"username": username}), 400

        session["user_id"] = int(user["id"])
        session["student_id"] = ensure_student_for_user(int(user["id"]), str(user["username"]))
        flash("Welcome back! You are signed in.", "success")
        return redirect(url_for("pages.dashboard"))
    return render_template("login.html", form={})


@pages_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        confirm_password = request.form.get("confirm_password") or ""

        if len(username) < 3:
            flash("Username must be at least 3 characters long.", "error")
            return render_template("signup.html", form={"username": username}), 400
        if len(password) < 6:
            flash("Password must be at least 6 characters long.", "error")
            return render_template("signup.html", form={"username": username}), 400
        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template("signup.html", form={"username": username}), 400

        try:
            user = create_app_user(username, password)
        except ValueError as exc:
            flash(str(exc), "error")
            return render_template("signup.html", form={"username": username}), 400

        session["user_id"] = int(user["id"])
        session["student_id"] = ensure_student_for_user(int(user["id"]), str(user["username"]))
        flash("Account created successfully. Your study space is ready.", "success")
        return redirect(url_for("pages.dashboard"))
    return render_template("signup.html", form={})


@pages_bp.get("/logout")
def logout():
    session.clear()
    flash("You have been signed out.", "success")
    return redirect(url_for("pages.login"))


@pages_bp.get("/health")
def health():
    return {"ok": True, "service": "edubridge-ai"}, 200


@pages_bp.get("/dashboard")
def dashboard():
    student = _student()
    payload = dashboard_payload(student["id"], student["display_name"])
    return render_template("dashboard.html", **payload, band_label=band_label)


@pages_bp.route("/goals", methods=["GET", "POST"])
def goals():
    student = _student()
    prefs = get_preferences(student["id"])
    if request.method == "POST":
        try:
            data = validate_preferences(request.form.to_dict())
        except ValidationError as exc:
            flash(exc.message, "error")
            return render_template(
                "goals.html",
                preferences=prefs,
                tracks=current_app.config["TRACKS"],
                levels=current_app.config["EXPERIENCE_LEVELS"],
                form=request.form,
            ), 400
        save_preferences(student["id"], data, utc_now())
        flash("Learning goal saved. You can take a diagnostic quiz next.", "success")
        return redirect(url_for("pages.dashboard"))
    return render_template(
        "goals.html",
        preferences=prefs,
        tracks=current_app.config["TRACKS"],
        levels=current_app.config["EXPERIENCE_LEVELS"],
        form=prefs or {},
    )


@pages_bp.get("/quiz")
def quiz():
    student = _student()
    prefs = get_preferences(student["id"])
    if prefs is None:
        flash("Choose a learning goal before starting a quiz.", "error")
        return redirect(url_for("pages.goals"))
    questions = list_questions_for_track(prefs["track"])
    if not questions:
        flash("No quiz questions are available for this track yet.", "error")
        return redirect(url_for("pages.dashboard"))
    return render_template("quiz.html", preferences=prefs, questions=questions)


@pages_bp.get("/analysis")
@pages_bp.get("/analysis/<int:attempt_id>")
def analysis(attempt_id: int | None = None):
    student = _student()
    if attempt_id is None:
        payload = latest_attempt(student["id"])
        if payload is None:
            flash("Complete a quiz to see skill-gap analysis.", "error")
            return redirect(url_for("pages.quiz"))
    else:
        payload = get_attempt(attempt_id, student["id"])
        if payload is None:
            flash("That quiz attempt was not found.", "error")
            return redirect(url_for("pages.dashboard"))
    classified = classify_topics(payload["topic_results"])
    return render_template(
        "analysis.html",
        attempt=payload["attempt"],
        topic_results=payload["topic_results"],
        details=payload["details"],
        classified=classified,
        next_steps=next_steps(classified),
        band_label=band_label,
    )


@pages_bp.get("/study-plan")
def study_plan():
    student = _student()
    prefs = get_preferences(student["id"])
    plan = get_current_plan(student["id"])
    latest = latest_attempt(student["id"])
    return render_template(
        "study_plan.html",
        preferences=prefs,
        current_plan=plan,
        has_quiz=latest is not None,
    )


@pages_bp.get("/resources")
def resources():
    student = _student()
    prefs = get_preferences(student["id"])
    query = (request.args.get("q") or "").strip()
    topic = (request.args.get("topic") or "").strip() or None
    difficulty = (request.args.get("difficulty") or "").strip() or None
    track = (request.args.get("track") or "").strip() or None
    items = list_resources(track=track, topic=topic, difficulty=difficulty, query=query or None)
    all_resources = list_resources()
    topics = sorted({item["topic"] for item in all_resources})
    difficulties = sorted({item["difficulty"] for item in all_resources})
    tracks = sorted({item["track"] for item in all_resources})
    return render_template(
        "resources.html",
        resources=items,
        topics=topics,
        difficulties=difficulties,
        tracks=tracks,
        selected={"q": query, "topic": topic or "", "difficulty": difficulty or "", "track": track or ""},
        preferences=prefs,
    )


@pages_bp.get("/progress")
def progress():
    student = _student()
    payload = progress_payload(student["id"])
    return render_template("progress.html", **payload, band_label=band_label)


@pages_bp.route("/profile", methods=["GET", "POST"])
def profile():
    student = _student()
    prefs = get_preferences(student["id"])
    if request.method == "POST":
        form = request.form.to_dict()
        try:
            name = validate_display_name(form)
            data = validate_preferences(form)
        except ValidationError as exc:
            flash(exc.message, "error")
            return render_template(
                "profile.html",
                student=student,
                preferences=prefs,
                form=form,
                tracks=current_app.config["TRACKS"],
                levels=current_app.config["EXPERIENCE_LEVELS"],
            ), 400
        from database.db import get_db

        db = get_db()
        db.execute("UPDATE students SET display_name = ? WHERE id = ?", (name, student["id"]))
        db.commit()
        save_preferences(student["id"], data, utc_now())
        flash("Profile preferences saved.", "success")
        return redirect(url_for("pages.profile"))
    return render_template(
        "profile.html",
        student=student,
        preferences=prefs,
        form={**(prefs or {}), "display_name": student["display_name"]},
        tracks=current_app.config["TRACKS"],
        levels=current_app.config["EXPERIENCE_LEVELS"],
    )
