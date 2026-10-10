"""HTTP route tests."""

from __future__ import annotations


def test_app_starts(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json()["ok"] is True


def test_landing_page(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Your Learning Journey, Made Personal." in response.data
    assert b"Start Learning" in response.data


def test_database_initialization_creates_questions(app):
    from database.db import query_one

    with app.app_context():
        row = query_one("SELECT COUNT(*) AS c FROM quiz_questions")
        assert row["c"] >= 40
        resources = query_one("SELECT COUNT(*) AS c FROM learning_resources")
        assert resources["c"] >= 20
        student = query_one("SELECT * FROM students")
        assert student is not None


def test_goal_validation_rejects_invalid_minutes(client):
    response = client.post(
        "/goals",
        data={
            "track": "Python Programming",
            "experience_level": "beginner",
            "daily_minutes": "5",
            "target_days": "14",
        },
    )
    assert response.status_code == 400


def test_goal_save_persists(client, app):
    response = client.post(
        "/goals",
        data={
            "track": "Python Programming",
            "experience_level": "beginner",
            "daily_minutes": "45",
            "target_days": "14",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    from database.db import query_one

    with app.app_context():
        prefs = query_one("SELECT * FROM learning_preferences")
        assert prefs["track"] == "Python Programming"
        assert prefs["daily_minutes"] == 45


def test_api_missing_json_body(client):
    response = client.post("/api/goals", data="not-json", content_type="application/json")
    assert response.status_code == 400
    assert response.get_json()["ok"] is False


def test_health_api(client):
    response = client.get("/api/health")
    assert response.status_code == 200


def test_login_page_loads(client):
    response = client.get("/login")
    assert response.status_code == 200
    assert b"welcome back" in response.data.lower()


def test_signup_page_loads(client):
    response = client.get("/signup")
    assert response.status_code == 200
    assert b"create account" in response.data.lower()


def test_signup_and_login_flow(app):
    with app.test_client() as client:
        response = client.post(
            "/signup",
            data={"username": "demo_user", "password": "secret123", "confirm_password": "secret123"},
            follow_redirects=False,
        )
        assert response.status_code == 302

        response = client.post(
            "/login",
            data={"username": "demo_user", "password": "secret123"},
            follow_redirects=False,
        )
        assert response.status_code == 302
        with client.session_transaction() as session:
            assert session.get("user_id") is not None


def test_unknown_page(client):
    response = client.get("/definitely-missing")
    assert response.status_code == 404
