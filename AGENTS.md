# AGENTS.md
## Repository Overview
- Primary app: FastAPI backend in `src/geneweaver/api`
- Tests live in `tests/`
- Shared Python workspace packages live in `packages/core`, `packages/db`, and `packages/client`
- Separate frontend app lives in `ui/`
- Legacy code lives in `legacy/`; avoid changing it unless the task explicitly targets legacy behavior
## Setup
- Install backend dependencies with `poetry install`
- Run the backend with `poetry run uvicorn geneweaver.api.main:app --reload`
- Install frontend dependencies with `cd ui && npm install`
- Run the frontend with `cd ui && npm run dev`
## Validation
- Lint backend changes with `ruff src tests --fix` and `black src tests`
- Run backend tests with `pytest tests --cov=geneweaver.api --cov-report term --cov-report html`
- For UI tasks, run the smallest relevant test or build command from `ui/`
- Prefer the smallest relevant test target first, then broaden only as needed
## Editing Guidance
- Keep changes minimal and scoped to the requested task
- Fix root causes instead of layering on one-off patches
- Match the style of the area you edit
- Check for nested `AGENTS.md` files before editing subdirectories; the most specific file in scope wins
- Update documentation when behavior or developer workflow changes
## Guardrails
- Do not change version numbers, deployment configuration, or CI behavior unless explicitly asked
- Do not touch `legacy/` unless the request is specifically about that code
- For backend changes, avoid tests that require a live DB, running webserver, or external APIs
- Use mocks or fixtures for external dependencies
- Keep generated files and dependency directories out of git; the root `.gitignore` already exists
