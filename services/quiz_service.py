"""Quiz retrieval, scoring, and topic analysis."""

from __future__ import annotations

import random
from collections import defaultdict
from typing import Any

from flask import current_app

from database.db import get_db, query_all, query_one, utc_now
from services.validation import ValidationError, band_for_score


def list_questions_for_track(track: str, shuffle: bool = True) -> list[dict[str, Any]]:
    rows = query_all(
        """
        SELECT id, track, topic, question_text, option_a, option_b, option_c, option_d
        FROM quiz_questions
        WHERE track = ?
        ORDER BY id ASC
        """,
        (track,),
    )
    questions = [dict(row) for row in rows]
    limit = current_app.config["QUIZ_QUESTION_LIMIT"]
    if shuffle and not current_app.config.get("TESTING"):
        random.shuffle(questions)
    return questions[:limit]


def get_question_map(question_ids: list[int]) -> dict[int, Any]:
    if not question_ids:
        return {}
    placeholders = ",".join("?" for _ in question_ids)
    rows = query_all(
        f"""
        SELECT id, track, topic, question_text, option_a, option_b, option_c, option_d,
               correct_option, explanation
        FROM quiz_questions
        WHERE id IN ({placeholders})
        """,
        question_ids,
    )
    return {int(row["id"]): dict(row) for row in rows}


def score_answers(track: str, answers: list[dict[str, Any]]) -> dict[str, Any]:
    if not answers:
        raise ValidationError("Submit at least one answer.", "answers")

    question_ids: list[int] = []
    selected_by_id: dict[int, str] = {}
    for item in answers:
        try:
            qid = int(item.get("question_id"))
        except (TypeError, ValueError):
            raise ValidationError("Each answer needs a valid question_id.", "answers")
        selected = str(item.get("selected_option", "")).upper()
        if selected not in {"A", "B", "C", "D"}:
            raise ValidationError("Each answer must be A, B, C, or D.", "answers")
        if qid in selected_by_id:
            raise ValidationError("Duplicate answers for the same question are not allowed.", "answers")
        question_ids.append(qid)
        selected_by_id[qid] = selected

    questions = get_question_map(question_ids)
    if len(questions) != len(question_ids):
        raise ValidationError("One or more questions were not found.", "answers")

    details = []
    topic_stats: dict[str, dict[str, int]] = defaultdict(lambda: {"correct": 0, "total": 0})
    correct_count = 0

    for qid in question_ids:
        question = questions[qid]
        if question["track"] != track:
            raise ValidationError("A question does not belong to the selected track.", "answers")
        selected = selected_by_id[qid]
        is_correct = selected == question["correct_option"]
        if is_correct:
            correct_count += 1
        topic_stats[question["topic"]]["total"] += 1
        if is_correct:
            topic_stats[question["topic"]]["correct"] += 1
        details.append(
            {
                "question_id": qid,
                "topic": question["topic"],
                "question_text": question["question_text"],
                "option_a": question["option_a"],
                "option_b": question["option_b"],
                "option_c": question["option_c"],
                "option_d": question["option_d"],
                "selected_option": selected,
                "correct_option": question["correct_option"],
                "is_correct": is_correct,
                "explanation": question["explanation"],
            }
        )

    total = len(question_ids)
    score_percent = round((correct_count / total) * 100, 2)
    topic_results = []
    for topic, stats in sorted(topic_stats.items()):
        percent = round((stats["correct"] / stats["total"]) * 100, 2)
        topic_results.append(
            {
                "topic": topic,
                "correct_count": stats["correct"],
                "total_count": stats["total"],
                "score_percent": percent,
                "band": band_for_score(percent),
            }
        )

    return {
        "track": track,
        "score_percent": score_percent,
        "total_questions": total,
        "correct_count": correct_count,
        "details": details,
        "topic_results": topic_results,
    }


def save_attempt(student_id: int, scored: dict[str, Any]) -> int:
    db = get_db()
    try:
        cursor = db.execute(
            """
            INSERT INTO quiz_attempts (
                student_id, track, score_percent, total_questions, correct_count, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                student_id,
                scored["track"],
                scored["score_percent"],
                scored["total_questions"],
                scored["correct_count"],
                utc_now(),
            ),
        )
        attempt_id = int(cursor.lastrowid)
        for detail in scored["details"]:
            db.execute(
                """
                INSERT INTO quiz_attempt_answers (
                    attempt_id, question_id, selected_option, is_correct
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    attempt_id,
                    detail["question_id"],
                    detail["selected_option"],
                    1 if detail["is_correct"] else 0,
                ),
            )
        for topic in scored["topic_results"]:
            db.execute(
                """
                INSERT INTO topic_results (
                    attempt_id, topic, correct_count, total_count, score_percent, band
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    attempt_id,
                    topic["topic"],
                    topic["correct_count"],
                    topic["total_count"],
                    topic["score_percent"],
                    topic["band"],
                ),
            )
        db.commit()
        return attempt_id
    except Exception:
        db.rollback()
        raise


def get_attempt(attempt_id: int, student_id: int) -> dict[str, Any] | None:
    attempt = query_one(
        "SELECT * FROM quiz_attempts WHERE id = ? AND student_id = ?",
        (attempt_id, student_id),
    )
    if attempt is None:
        return None
    topics = query_all(
        "SELECT topic, correct_count, total_count, score_percent, band FROM topic_results WHERE attempt_id = ? ORDER BY score_percent ASC, topic ASC",
        (attempt_id,),
    )
    answers = query_all(
        """
        SELECT a.question_id, a.selected_option, a.is_correct,
               q.topic, q.question_text, q.option_a, q.option_b, q.option_c, q.option_d,
               q.correct_option, q.explanation
        FROM quiz_attempt_answers a
        JOIN quiz_questions q ON q.id = a.question_id
        WHERE a.attempt_id = ?
        ORDER BY a.id ASC
        """,
        (attempt_id,),
    )
    return {
        "attempt": dict(attempt),
        "topic_results": [dict(row) for row in topics],
        "details": [dict(row) for row in answers],
    }


def classify_topics(topic_results: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    strong = [t for t in topic_results if t["band"] == "good_progress"]
    developing = [t for t in topic_results if t["band"] == "developing"]
    weak = [t for t in topic_results if t["band"] == "needs_practice"]
    return {"strong": strong, "developing": developing, "needs_practice": weak}


def latest_attempt(student_id: int) -> dict[str, Any] | None:
    row = query_one(
        """
        SELECT * FROM quiz_attempts
        WHERE student_id = ?
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """,
        (student_id,),
    )
    if row is None:
        return None
    return get_attempt(int(row["id"]), student_id)


def next_steps(classified: dict[str, list[dict[str, Any]]]) -> list[str]:
    steps = []
    if classified["needs_practice"]:
        names = ", ".join(t["topic"] for t in classified["needs_practice"])
        steps.append(f"Schedule focused practice on: {names}.")
    if classified["developing"]:
        names = ", ".join(t["topic"] for t in classified["developing"])
        steps.append(f"Continue guided exercises for: {names}.")
    if classified["strong"]:
        names = ", ".join(t["topic"] for t in classified["strong"])
        steps.append(f"Keep {names} sharp with short revision and mixed practice.")
    if not steps:
        steps.append("Take a diagnostic quiz to generate topic-level next steps.")
    steps.append("Generate or refresh a study plan so daily tasks match these results.")
    return steps
