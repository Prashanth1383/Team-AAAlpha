"""Analytics and progress calculation tests."""

from __future__ import annotations


def test_progress_empty_state(client):
    response = client.get("/progress")
    assert response.status_code == 200
    assert b"No quiz history yet" in response.data


def test_dashboard_uses_stored_scores(client, app):
    client.post(
        "/goals",
        data={
            "track": "Data Analysis",
            "experience_level": "beginner",
            "daily_minutes": "30",
            "target_days": "7",
        },
    )
    with app.app_context():
        from database.db import query_all

        questions = query_all(
            "SELECT id, correct_option FROM quiz_questions WHERE track = ? ORDER BY id LIMIT 8",
            ("Data Analysis",),
        )
    answers = [{"question_id": q["id"], "selected_option": q["correct_option"]} for q in questions]
    client.post("/api/quiz/submit", json={"track": "Data Analysis", "answers": answers})
    dash = client.get("/api/dashboard")
    payload = dash.get_json()
    assert payload["quizzes_completed"] == 1
    assert payload["average_score"] == 100
    page = client.get("/dashboard")
    assert page.status_code == 200
    assert b"100" in page.data


def test_profile_update_persists(client, app):
    response = client.post(
        "/profile",
        data={
            "display_name": "Prashanth",
            "track": "Python Programming",
            "experience_level": "advanced",
            "daily_minutes": "90",
            "target_days": "21",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Prashanth" in response.data
    from database.db import query_one

    with app.app_context():
        student = query_one("SELECT display_name FROM students")
        prefs = query_one("SELECT * FROM learning_preferences")
        assert student["display_name"] == "Prashanth"
        assert prefs["experience_level"] == "advanced"
        assert prefs["daily_minutes"] == 90


def test_progress_percent_after_tasks(client, app):
    client.post(
        "/goals",
        data={
            "track": "Python Programming",
            "experience_level": "beginner",
            "daily_minutes": "30",
            "target_days": "7",
        },
    )
    with app.app_context():
        from database.db import query_all

        questions = query_all(
            "SELECT id, correct_option FROM quiz_questions WHERE track = ? ORDER BY id LIMIT 8",
            ("Python Programming",),
        )
    answers = [{"question_id": q["id"], "selected_option": q["correct_option"]} for q in questions]
    client.post("/api/quiz/submit", json={"track": "Python Programming", "answers": answers})
    client.post("/api/study-plan/generate", json={})
    from database.db import query_all as qa
    from services.analytics_service import progress_payload
    from database.db import query_one

    with app.app_context():
        tasks = qa("SELECT id FROM study_tasks ORDER BY id")
        student = query_one("SELECT id FROM students")
    client.post(f"/api/tasks/{tasks[0]['id']}/complete", json={"completed": True})
    with app.app_context():
        payload = progress_payload(student["id"])
        assert payload["has_history"] is True
        assert payload["current_plan"]["completed_count"] == 1
        expected = round((1 / payload["current_plan"]["total_count"]) * 100, 2)
        assert payload["current_plan"]["completion_percent"] == expected
