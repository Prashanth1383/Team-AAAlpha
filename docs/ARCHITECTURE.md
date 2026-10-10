# Architecture

EduBridge AI is a Flask application with server-rendered pages, a small JSON API, and SQLite persistence.

The workspace did not contain official HackOverflow 10.0 theme files. This document describes the implemented application only.

## Layers

- **Templates / static files** — HTML pages, CSS design system, and JavaScript for quiz navigation, charts, and task completion.
- **Routes** — `routes/pages.py` renders pages and HTML forms. `routes/api.py` returns JSON.
- **Services** — quiz scoring, rule-based recommendations, analytics, and validation.
- **Database** — SQLite schema, connection helpers, and seed data.

## Request flow

1. A local demo student row is created on first authenticated-style request (any page other than the public landing/health routes in normal mode).
2. The student saves learning preferences.
3. The quiz page loads questions without answer keys.
4. Submission scores answers on the server, stores an attempt, and stores topic results.
5. The recommendation engine ranks topics, selects catalog resources, and writes a study plan.
6. Dashboard and progress pages query stored attempts and tasks.

## Recommendation engine

The engine is **rule-based**, not a trained machine-learning model.

Inputs: learning track, experience level, daily minutes, target days, and topic scores from the latest quiz.

Rules:

- Score bands: below 50% needs focused practice, 50–74% developing, 75%+ good progress.
- Weaker topics receive about 60% of plan days.
- Remaining days mix revision and stronger topics.
- Resources are chosen from `learning_resources` by track and topic, preferring matching difficulty.

A future ML model could predict time-to-improve or resource usefulness after the project has enough labeled outcomes (completed tasks plus later quiz scores). That work is not included in this MVP.

## Security notes

- CSRF tokens are required for state-changing requests when CSRF is enabled.
- Output is Jinja-escaped by default.
- Sessions are HTTP-only with SameSite Lax.
- This is a local demo with a single profile. It has not had a production security review.
