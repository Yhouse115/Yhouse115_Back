# Backend Architecture

## Runtime

- Language: Python 3.12
- Framework: FastAPI
- Dependency management: `requirements.txt`
- Local environment: `.venv` created by each developer and excluded from Git
- Local MSA runtime: `docker-compose.yml`

## Folder Responsibilities

```text
app/
  main.py                 FastAPI app factory and route registration
  api/routes/             HTTP endpoint definitions
  core/config.py          Environment-based runtime configuration
  clients/                External service client boundaries, including Naver Maps
  db/                     Database connection/session setup
  models/                 Persistence models
  schemas/                Request/response DTOs
  services/               Distance, radius, route, and safety business logic
  repositories/           Data access boundaries
  utils/                  Logging and shared helpers
docker/postgres/          Local PostGIS initialization scripts
.github/workflows/        GitHub Actions CI workflows
tests/                    Automated tests
docs/                     Current project, architecture, API, and data documents
```

## Module Boundary

Routes should stay thin and delegate calculations to services. Services should not depend on FastAPI request objects. Repositories own data access and should hide storage details from services.

Database access should go through `app/db/` and repository modules. Supabase is configured as the hosted product boundary, while local Docker uses a PostGIS-enabled PostgreSQL container through the same `DATABASE_URL` shape.

Naver Maps integration should stay behind `app/clients/naver_maps.py`. Feature code should request configuration or future client methods from that module instead of reading Naver credentials directly. Browser map rendering should use a separate frontend-safe key; backend settings are for server-side APIs such as geocoding and reverse geocoding.

## Docker Compose Boundary

The backend service builds from this repository. The frontend service is expected at `../WhyHouse_Front` by default and is attached to the same `whyhouse-network` network when the `msa` profile is enabled.

The compose stack includes a local `database` service based on `postgis/postgis:16-3.4`. This is for local development and CI-style connectivity checks; production should point `DATABASE_URL` and Supabase settings at the Supabase project.

## Future Documentation Locations

- Troubleshooting: create `docs/troubleshooting.md` after a real repeated setup, runtime, or integration issue exists.
- ADR: create `docs/adr/NNNN-title.md` when choosing among durable architecture alternatives.
- Development phases: create `docs/development-phases.md` when Phase 1 implementation tasks are defined.
