# Contributing to EduBridge AI

Thank you for helping improve this HackOverflow 10.0 project from Team AAAlpha.

## Local setup

Follow the Windows PowerShell steps in `README.md` to create a virtual environment, install dependencies, initialize the database, and run tests.

## Working conventions

- Keep the recommendation engine deterministic and documented. Do not describe rule-based scoring as a trained model.
- Prefer parameterized SQL in `database/db.py` helpers. Do not concatenate user input into SQL.
- Store quiz answer keys only on the server. The quiz JSON API must not include `correct_option` before submission.
- Dashboard, analysis, and progress views must read SQLite. Do not hardcode performance statistics.
- Add or update tests in `tests/` when you change scoring, plan generation, or validation.
- Do not commit `.env`, `instance/`, virtual environments, or personal data.

## Pull requests

1. Describe the problem and the change.
2. Note how you tested it (`pytest` and any manual checks).
3. Keep secrets and generated databases out of the diff.

## Code of conduct

Be respectful in issues and reviews. This repository is a student hackathon project.
