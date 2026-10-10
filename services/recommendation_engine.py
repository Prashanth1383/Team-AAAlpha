"""
Rule-based recommendation engine.

This module does not use a trained machine-learning model. It ranks topics from
quiz scores, matches catalog resources, and allocates study days using
deterministic rules. A future ML model could replace ranking or duration
estimates after enough labeled outcome data exists.
"""

from __future__ import annotations

from typing import Any

from flask import current_app

from database.db import get_db, query_all, query_one, utc_now
from services.validation import ValidationError, validate_preferences


def list_resources(
    track: str | None = None,
    topic: str | None = None,
    difficulty: str | None = None,
    query: str | None = None,
) -> list[dict[str, Any]]:
    sql = "SELECT * FROM learning_resources WHERE 1=1"
    params: list[Any] = []
    if track:
        sql += " AND track = ?"
        params.append(track)
    if topic:
        sql += " AND topic = ?"
        params.append(topic)
    if difficulty:
        sql += " AND difficulty = ?"
        params.append(difficulty)
    if query:
        sql += " AND (title LIKE ? OR description LIKE ? OR topic LIKE ?)"
        like = f"%{query}%"
        params.extend([like, like, like])
    sql += " ORDER BY track ASC, topic ASC, title ASC"
    return [dict(row) for row in query_all(sql, params)]


def _resource_for_topic(
    track: str,
    topic: str,
    experience_level: str,
    used_ids: set[int],
) -> dict[str, Any] | None:
    candidates = list_resources(track=track, topic=topic)
    if not candidates:
        candidates = list_resources(track=track)
    if not candidates:
        return None

    preferred = [r for r in candidates if r["difficulty"] == experience_level]
    pool = preferred or candidates
    unused = [r for r in pool if r["id"] not in used_ids]
    chosen = unused[0] if unused else pool[0]
    used_ids.add(int(chosen["id"]))
    return chosen


def rank_topics(topic_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = sorted(
        [dict(item) for item in topic_results],
        key=lambda item: (item["score_percent"], item["topic"]),
    )
    for index, item in enumerate(ranked, start=1):
        item["rank"] = index
        if item["score_percent"] < current_app.config["SCORE_NEEDS_PRACTICE"]:
            item["why"] = (
                f"{item['topic']} scored {item['score_percent']}%, which is below "
                f"{current_app.config['SCORE_NEEDS_PRACTICE']}% and is prioritized for focused practice."
            )
        elif item["score_percent"] < current_app.config["SCORE_DEVELOPING"]:
            item["why"] = (
                f"{item['topic']} scored {item['score_percent']}%. It is developing, so the plan "
                "includes guided practice and review."
            )
        else:
            item["why"] = (
                f"{item['topic']} scored {item['score_percent']}%. The plan keeps light revision "
                "so stronger topics are not dropped."
            )
    return ranked


def allocate_topics(ranked: list[dict[str, Any]], target_days: int) -> list[str]:
    if not ranked:
        return ["General review"] * target_days

    weak = [t for t in ranked if t["score_percent"] < current_app.config["SCORE_DEVELOPING"]]
    strong = [t for t in ranked if t["score_percent"] >= current_app.config["SCORE_DEVELOPING"]]
    if not weak:
        weak = ranked

    sequence: list[str] = []
    weak_days = max(1, round(target_days * 0.6))
    review_days = max(0, round(target_days * 0.25))
    remaining = target_days - weak_days - review_days
    if remaining < 0:
        weak_days = target_days
        review_days = 0
        remaining = 0

    def fill(days: int, pool: list[dict[str, Any]]) -> None:
        if not pool:
            pool = ranked
        for i in range(days):
            sequence.append(pool[i % len(pool)]["topic"])

    fill(weak_days, weak)
    fill(review_days, ranked)
    fill(remaining if remaining else 0, strong or ranked)

    while len(sequence) < target_days:
        sequence.append(weak[len(sequence) % len(weak)]["topic"])
    return sequence[:target_days]


def _objective(topic: str, experience_level: str, score: float | None) -> str:
    if score is None:
        return f"Build a foundation in {topic} at a {experience_level} pace."
    if score < 50:
        return f"Rebuild core ideas in {topic} with worked examples and short drills."
    if score < 75:
        return f"Strengthen {topic} with mixed practice and check understanding as you go."
    return f"Revise {topic} and apply it in a short mixed-practice set."


def generate_plan(
    student_id: int,
    preferences: dict[str, Any],
    topic_results: list[dict[str, Any]],
    attempt_id: int | None,
) -> dict[str, Any]:
    prefs = validate_preferences(preferences)
    ranked = rank_topics([dict(item) for item in topic_results])
    days = allocate_topics(ranked, prefs["target_days"])
    score_by_topic = {item["topic"]: item["score_percent"] for item in ranked}
    why_by_topic = {item["topic"]: item["why"] for item in ranked}

    used_resource_ids: set[int] = set()
    tasks = []
    for day_number, topic in enumerate(days, start=1):
        resource = _resource_for_topic(
            prefs["track"], topic, prefs["experience_level"], used_resource_ids
        )
        duration = min(prefs["daily_minutes"], 90)
        if prefs["experience_level"] == "beginner":
            duration = min(duration, max(30, prefs["daily_minutes"]))
        tasks.append(
            {
                "day_number": day_number,
                "topic": topic,
                "learning_objective": _objective(
                    topic, prefs["experience_level"], score_by_topic.get(topic)
                ),
                "estimated_minutes": duration,
                "resource_id": int(resource["id"]) if resource else None,
                "resource_title": resource["title"] if resource else "No catalog match yet",
                "resource_url": resource["url"] if resource else None,
                "rationale": why_by_topic.get(
                    topic,
                    f"{topic} is included to keep coverage across the selected track.",
                ),
            }
        )

    summary = (
        f"A {prefs['target_days']}-day learning guide for {prefs['track']} at "
        f"{prefs['experience_level']} level, using about {prefs['daily_minutes']} minutes a day. "
        "Weak topics receive more days; stronger topics stay in the rotation for revision. "
        "This is an adaptable study guide, not a guarantee of mastery."
    )
    return {
        "student_id": student_id,
        "attempt_id": attempt_id,
        "track": prefs["track"],
        "summary": summary,
        "ranked_topics": ranked,
        "tasks": tasks,
    }


def replace_saved_plan(plan: dict[str, Any]) -> int:
    """Replace the student's current plan to avoid duplicate active tasks."""
    db = get_db()
    student_id = plan["student_id"]
    try:
        existing = query_all(
            "SELECT id FROM study_plans WHERE student_id = ?",
            (student_id,),
        )
        for row in existing:
            db.execute("DELETE FROM study_tasks WHERE plan_id = ?", (row["id"],))
        db.execute("DELETE FROM study_plans WHERE student_id = ?", (student_id,))
        cursor = db.execute(
            """
            INSERT INTO study_plans (student_id, attempt_id, track, summary, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                student_id,
                plan["attempt_id"],
                plan["track"],
                plan["summary"],
                utc_now(),
            ),
        )
        plan_id = int(cursor.lastrowid)
        for task in plan["tasks"]:
            db.execute(
                """
                INSERT INTO study_tasks (
                    plan_id, day_number, topic, learning_objective, estimated_minutes,
                    resource_id, rationale, is_completed
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 0)
                """,
                (
                    plan_id,
                    task["day_number"],
                    task["topic"],
                    task["learning_objective"],
                    task["estimated_minutes"],
                    task["resource_id"],
                    task["rationale"],
                ),
            )
        db.commit()
        return plan_id
    except Exception:
        db.rollback()
        raise


def get_current_plan(student_id: int) -> dict[str, Any] | None:
    plan = query_one(
        """
        SELECT * FROM study_plans
        WHERE student_id = ?
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """,
        (student_id,),
    )
    if plan is None:
        return None
    tasks = query_all(
        """
        SELECT t.*, r.title AS resource_title, r.url AS resource_url, r.resource_type
        FROM study_tasks t
        LEFT JOIN learning_resources r ON r.id = t.resource_id
        WHERE t.plan_id = ?
        ORDER BY t.day_number ASC, t.id ASC
        """,
        (plan["id"],),
    )
    task_dicts = [dict(row) for row in tasks]
    total = len(task_dicts)
    completed = sum(1 for task in task_dicts if task["is_completed"])
    percent = round((completed / total) * 100, 2) if total else 0.0
    return {
        "plan": dict(plan),
        "tasks": task_dicts,
        "completed_count": completed,
        "total_count": total,
        "completion_percent": percent,
    }


def set_task_completed(student_id: int, task_id: int, completed: bool) -> dict[str, Any]:
    row = query_one(
        """
        SELECT t.id, t.plan_id, p.student_id
        FROM study_tasks t
        JOIN study_plans p ON p.id = t.plan_id
        WHERE t.id = ?
        """,
        (task_id,),
    )
    if row is None or int(row["student_id"]) != student_id:
        raise ValidationError("Study task not found.", "task_id")
    db = get_db()
    db.execute(
        """
        UPDATE study_tasks
        SET is_completed = ?, completed_at = ?
        WHERE id = ?
        """,
        (1 if completed else 0, utc_now() if completed else None, task_id),
    )
    db.commit()
    current = get_current_plan(student_id)
    if current is None:
        raise ValidationError("Study plan not found.", "task_id")
    return current
