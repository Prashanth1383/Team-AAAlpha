"""Progress and dashboard calculations from stored data."""

from __future__ import annotations

from typing import Any

from database.db import query_all, query_one
from services.quiz_service import classify_topics, latest_attempt
from services.recommendation_engine import get_current_plan


def get_preferences(student_id: int) -> dict[str, Any] | None:
    row = query_one(
        "SELECT * FROM learning_preferences WHERE student_id = ?",
        (student_id,),
    )
    return dict(row) if row else None


def save_preferences(student_id: int, prefs: dict[str, Any], updated_at: str) -> None:
    existing = get_preferences(student_id)
    from database.db import get_db

    db = get_db()
    if existing:
        db.execute(
            """
            UPDATE learning_preferences
            SET track = ?, experience_level = ?, daily_minutes = ?, target_days = ?, updated_at = ?
            WHERE student_id = ?
            """,
            (
                prefs["track"],
                prefs["experience_level"],
                prefs["daily_minutes"],
                prefs["target_days"],
                updated_at,
                student_id,
            ),
        )
    else:
        db.execute(
            """
            INSERT INTO learning_preferences (
                student_id, track, experience_level, daily_minutes, target_days, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                student_id,
                prefs["track"],
                prefs["experience_level"],
                prefs["daily_minutes"],
                prefs["target_days"],
                updated_at,
            ),
        )
    db.commit()


def quiz_history(student_id: int) -> list[dict[str, Any]]:
    rows = query_all(
        """
        SELECT id, track, score_percent, total_questions, correct_count, created_at
        FROM quiz_attempts
        WHERE student_id = ?
        ORDER BY created_at ASC, id ASC
        """,
        (student_id,),
    )
    return [dict(row) for row in rows]


def dashboard_payload(student_id: int, student_name: str) -> dict[str, Any]:
    prefs = get_preferences(student_id)
    history = quiz_history(student_id)
    latest = latest_attempt(student_id)
    plan = get_current_plan(student_id)

    completed = len(history)
    average = round(sum(item["score_percent"] for item in history) / completed, 2) if completed else None
    weak_topics = []
    if latest:
        classified = classify_topics(latest["topic_results"])
        weak_topics = classified["needs_practice"] + classified["developing"]

    suggested = suggested_next_action(prefs, history, plan)
    return {
        "student_name": student_name,
        "preferences": prefs,
        "quizzes_completed": completed,
        "average_score": average,
        "weak_topics": weak_topics,
        "recent_attempts": list(reversed(history[-5:])),
        "score_history": history,
        "current_plan": plan,
        "suggested_next_action": suggested,
    }


def topic_progress(student_id: int) -> list[dict[str, Any]]:
    rows = query_all(
        """
        SELECT tr.topic, tr.score_percent, tr.band, a.created_at, a.id AS attempt_id
        FROM topic_results tr
        JOIN quiz_attempts a ON a.id = tr.attempt_id
        WHERE a.student_id = ?
        ORDER BY a.created_at ASC, a.id ASC, tr.topic ASC
        """,
        (student_id,),
    )
    latest_by_topic: dict[str, dict[str, Any]] = {}
    for row in rows:
        latest_by_topic[row["topic"]] = dict(row)
    return sorted(latest_by_topic.values(), key=lambda item: item["score_percent"])


def progress_payload(student_id: int) -> dict[str, Any]:
    history = quiz_history(student_id)
    plan = get_current_plan(student_id)
    prefs = get_preferences(student_id)
    return {
        "score_history": history,
        "topic_progress": topic_progress(student_id),
        "current_plan": plan,
        "suggested_next_action": suggested_next_action(prefs, history, plan),
        "has_history": bool(history),
    }


def suggested_next_action(
    prefs: dict[str, Any] | None,
    history: list[dict[str, Any]],
    plan: dict[str, Any] | None,
) -> str:
    if prefs is None:
        return "Set a learning goal so quizzes and study plans match your track."
    if not history:
        return "Take a diagnostic quiz to measure topic-level starting points."
    if plan is None:
        return "Generate a study plan from your latest quiz analysis."
    incomplete = [task for task in plan["tasks"] if not task["is_completed"]]
    if incomplete:
        next_task = incomplete[0]
        return (
            f"Continue with Day {next_task['day_number']}: {next_task['topic']} "
            f"({next_task['estimated_minutes']} minutes)."
        )
    return "All current study tasks are complete. Retake a quiz to refresh the plan."
