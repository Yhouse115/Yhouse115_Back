# AGENTS.md

## Repository Responsibility

This repository owns the WhyHouse FastAPI backend. It exposes API endpoints and owns backend-side calculations for apartment-centered child infrastructure, walkability, route, and safety insights.

The frontend repository is separate. Cross-service local execution is coordinated through `docker-compose.yml` and the shared `whyhouse-network` network.

## Architecture Rules

- Keep the app rooted at `app/`; do not add a nested `backend/` directory because this repository is already the backend service root.
- Put HTTP route definitions in `app/api/routes/`.
- Put request and response DTOs in `app/schemas/`.
- Put business, distance, radius, route, and safety scoring logic in `app/services/`.
- Put data access behind `app/repositories/`.
- Put database connection/session setup in `app/db/`.
- Put persistence models in `app/models/`.
- Put runtime configuration in `app/core/config.py`.
- Put cross-cutting helpers such as logging in `app/utils/`.
- Avoid creating empty future modules unless a current change needs them.

## Data Ownership

- The backend owns normalized API responses and calculation outputs.
- Raw external datasets should not be committed unless they are small, public, and intentionally used as test fixtures.
- Local data exports, logs, generated files, secrets, and virtual environments must remain untracked.

## Code Standards

- Use Python 3.12.
- Load runtime configuration through environment variables and `app.core.config.Settings`.
- Keep route handlers thin; route modules should validate input and delegate meaningful work to services.
- Keep service code independent from FastAPI objects unless the HTTP boundary truly needs them.
- Use structured JSON logs through `app.utils.logging`.

## Test Standards

- Add tests under `tests/`.
- Test route contracts with FastAPI `TestClient`.
- Add service-level tests when distance, radius, route, or safety calculation logic is introduced.
- Keep fixtures small and place them under `tests/resources/` only when real fixture files are needed.

## Documentation Standards

- Keep README focused on purpose, setup commands, and links.
- Put architecture details in `docs/backend-architecture.md`.
- Put endpoint contracts in `docs/api-contract.md`.
- Put project scope and current phase in `docs/project-summary.md`.
- Put source dataset boundaries in `docs/data-scope.md`.
- Create `docs/troubleshooting.md` only after there is a real repeated issue or setup failure worth documenting.
- Create ADRs under `docs/adr/NNNN-title.md` only when a durable architectural decision has alternatives and consequences.

