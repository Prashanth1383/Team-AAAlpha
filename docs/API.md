# API

JSON endpoints live under `/api`. State-changing calls require header `X-CSRFToken` when CSRF protection is enabled (the default outside tests).

Successful payloads include `"ok": true`. Failures include `"ok": false` and `"error"`.

| Method | Path | Purpose | Success |
| --- | --- | --- | --- |
| GET | `/health` | Process health check | 200 |
| GET | `/api/health` | JSON health check | 200 |
| GET | `/api/quiz?track=` | Questions without answer keys | 200 |
| POST | `/api/quiz/submit` | Score and store an attempt | 201 |
| POST | `/api/goals` | Save learning preferences | 200 |
| POST | `/api/study-plan/generate` | Replace the current study plan | 201 |
| POST | `/api/tasks/<id>/complete` | Mark a task complete or incomplete | 200 |
| GET | `/api/resources` | Search/filter resources (`q`, `track`, `topic`, `difficulty`) | 200 |
| GET | `/api/progress` | Historical scores and plan completion | 200 |
| GET | `/api/dashboard` | Dashboard statistics | 200 |
| POST | `/api/profile` | Update display name and preferences | 200 |

## Example: submit quiz

```json
{
  "track": "Python Programming",
  "answers": [
    {"question_id": 1, "selected_option": "B"}
  ]
}
```

## Example: complete task

```json
{"completed": true}
```

HTML pages (not JSON) include `/`, `/dashboard`, `/goals`, `/quiz`, `/analysis`, `/analysis/<id>`, `/study-plan`, `/resources`, `/progress`, and `/profile`.
