"""Quiz retrieval and scoring tests."""

from __future__ import annotations


def _save_python_goal(client):
    client.post(
        "/goals",
        data={
            "track": "Python Programming",
            "experience_level": "beginner",
            "daily_minutes": "30",
            "target_days": "7",
        },
    )


def test_quiz_retrieval_hides_answers(client):
    _save_python_goal(client)
    response = client.get("/api/quiz?track=Python Programming")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["questions"]
    for question in payload["questions"]:
        assert "correct_option" not in question
        assert "explanation" not in question
        assert "question_text" in question


def test_quiz_page_renders(client):
    _save_python_goal(client)
    response = client.get("/quiz")
    assert response.status_code == 200
    assert b"Diagnostic quiz" in response.data


def test_correct_and_incorrect_scoring(app, client):
    _save_python_goal(client)
    with app.app_context():
        from database.db import query_all

        questions = query_all(
            "SELECT id, correct_option FROM quiz_questions WHERE track = ? ORDER BY id LIMIT 8",
            ("Python Programming",),
        )
    answers = []
    for index, row in enumerate(questions):
        selected = row["correct_option"] if index % 2 == 0 else ("B" if row["correct_option"] != "B" else "A")
        answers.append({"question_id": row["id"], "selected_option": selected})

    from services.quiz_service import score_answers

    with app.app_context():
        scored = score_answers("Python Programming", answers)
    expected_correct = sum(1 for index, _ in enumerate(questions) if index % 2 == 0)
    assert scored["correct_count"] == expected_correct
    assert scored["total_questions"] == len(questions)
    assert scored["score_percent"] == round(expected_correct / len(questions) * 100, 2)
    assert scored["topic_results"]


def test_topic_band_thresholds(app):
    from services.validation import band_for_score

    with app.app_context():
        assert band_for_score(49.9) == "needs_practice"
        assert band_for_score(50) == "developing"
        assert band_for_score(74.9) == "developing"
        assert band_for_score(75) == "good_progress"


def test_quiz_submit_persists_attempt(client, app):
    _save_python_goal(client)
    with app.app_context():
        from database.db import query_all

        questions = query_all(
            "SELECT id, correct_option FROM quiz_questions WHERE track = ? ORDER BY id LIMIT 8",
            ("Python Programming",),
        )
    answers = [
        {"question_id": row["id"], "selected_option": row["correct_option"]} for row in questions
    ]
    response = client.post("/api/quiz/submit", json={"track": "Python Programming", "answers": answers})
    assert response.status_code == 201
    body = response.get_json()
    assert body["result"]["score_percent"] == 100
    attempt_id = body["result"]["attempt_id"]
    page = client.get(f"/analysis/{attempt_id}")
    assert page.status_code == 200
    assert b"100" in page.data


def test_invalid_answer_option(app):
    from services.quiz_service import score_answers
    from services.validation import ValidationError

    with app.app_context():
        from database.db import query_one

        question = query_one("SELECT id FROM quiz_questions LIMIT 1")
        try:
            score_answers(
                "Python Programming",
                [{"question_id": question["id"], "selected_option": "Z"}],
            )
            assert False, "expected validation error"
        except ValidationError:
            pass


def test_missing_attempt_returns_message(client):
    response = client.get("/analysis/9999", follow_redirects=True)
    assert response.status_code == 200
    assert b"was not found" in response.data
