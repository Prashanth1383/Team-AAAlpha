"""Recommendation engine and study-plan tests."""

from __future__ import annotations


def _setup_scored_student(client, app, all_correct: bool = False):
    client.post(
        "/goals",
        data={
            "track": "Web Development",
            "experience_level": "beginner",
            "daily_minutes": "60",
            "target_days": "10",
        },
    )
    with app.app_context():
        from database.db import query_all

        questions = query_all(
            "SELECT id, correct_option, topic FROM quiz_questions WHERE track = ? ORDER BY id LIMIT 8",
            ("Web Development",),
        )
    answers = []
    for row in questions:
        if all_correct or row["topic"] == "HTML":
            selected = row["correct_option"]
        else:
            selected = "A" if row["correct_option"] != "A" else "B"
        answers.append({"question_id": row["id"], "selected_option": selected})
    submit = client.post("/api/quiz/submit", json={"track": "Web Development", "answers": answers})
    assert submit.status_code == 201
    return submit.get_json()["result"]


def test_recommendation_ranks_weaker_topics_first(app, client):
    result = _setup_scored_student(client, app, all_correct=False)
    from services.recommendation_engine import generate_plan, rank_topics
    from services.analytics_service import get_preferences
    from database.db import query_one

    with app.app_context():
        student = query_one("SELECT id FROM students")
        prefs = get_preferences(student["id"])
        ranked = rank_topics(result["topic_results"])
        assert ranked[0]["score_percent"] <= ranked[-1]["score_percent"]
        plan = generate_plan(student["id"], prefs, result["topic_results"], result["attempt_id"])
        assert len(plan["tasks"]) == 10
        weak_topics = [t["topic"] for t in ranked if t["score_percent"] < 75]
        planned_topics = [task["topic"] for task in plan["tasks"]]
        if weak_topics:
            assert any(topic in planned_topics for topic in weak_topics)
        assert "adaptable" in plan["summary"].lower() or "guide" in plan["summary"].lower()


def test_study_plan_creation_and_no_duplicates(client, app):
    _setup_scored_student(client, app, all_correct=True)
    first = client.post("/api/study-plan/generate", json={})
    second = client.post("/api/study-plan/generate", json={})
    assert first.status_code == 201
    assert second.status_code == 201
    from database.db import query_one

    with app.app_context():
        plans = query_one("SELECT COUNT(*) AS c FROM study_plans")
        assert plans["c"] == 1
        tasks = query_one("SELECT COUNT(*) AS c FROM study_tasks")
        assert tasks["c"] == 10


def test_task_completion(client, app):
    _setup_scored_student(client, app, all_correct=True)
    client.post("/api/study-plan/generate", json={})
    from database.db import query_one

    with app.app_context():
        task = query_one("SELECT id FROM study_tasks ORDER BY id LIMIT 1")
        task_id = task["id"]
    response = client.post(f"/api/tasks/{task_id}/complete", json={"completed": True})
    assert response.status_code == 200
    body = response.get_json()
    assert body["plan"]["completed_count"] == 1
    with app.app_context():
        stored = query_one("SELECT is_completed FROM study_tasks WHERE id = ?", (task_id,))
        assert stored["is_completed"] == 1


def test_missing_task(client):
    response = client.post("/api/tasks/9999/complete", json={"completed": True})
    assert response.status_code == 400


def test_resource_search(client):
    response = client.get("/api/resources?q=python")
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["count"] >= 1
    titles = " ".join(item["title"].lower() for item in payload["resources"])
    assert "python" in titles
    empty = client.get("/api/resources?q=zzznomatchxyz")
    assert empty.get_json()["count"] == 0


def test_plan_requires_quiz(client):
    client.post(
        "/goals",
        data={
            "track": "Java Programming",
            "experience_level": "intermediate",
            "daily_minutes": "40",
            "target_days": "7",
        },
    )
    response = client.post("/api/study-plan/generate", json={})
    assert response.status_code == 400
