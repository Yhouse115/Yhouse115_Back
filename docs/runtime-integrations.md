# Runtime Integrations

This document summarizes local and shared runtime settings for backend developers.

## Environment Files

Create a local `.env` from `.env.example`.

```bash
cp .env.example .env
```

Do not commit `.env`, API keys, database passwords, or generated local runtime data.

## Supabase Cloud

Use Supabase Cloud as the shared team database and API project.

Required backend settings:

```env
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=
DATABASE_URL=
```

- `SUPABASE_ANON_KEY` is safe only under Row Level Security and explicit policies.
- `SUPABASE_SERVICE_ROLE_KEY` is backend-only and must never be exposed to frontend builds.
- `DATABASE_URL` is used by the backend for direct Postgres connectivity checks and future repository access.

Validate the backend sees the settings:

```bash
curl http://localhost:8000/api/v1/system/dependencies
```

Expected Supabase-ready status:

```json
{
  "database_configured": true,
  "database_connected": true,
  "supabase_configured": true,
  "supabase_admin_configured": true
}
```

## Local PostGIS

Docker Compose includes a local PostGIS container for offline backend development:

```bash
docker compose up -d --build backend
```

Default local DB settings:

```env
POSTGRES_DB=whyhouse
POSTGRES_USER=whyhouse
POSTGRES_PASSWORD=whyhouse
POSTGRES_PORT=5432
DATABASE_URL=postgresql://whyhouse:whyhouse@database:5432/whyhouse
```

This local DB is not the same as the Supabase CLI local stack.

For APIs that query transaction/building tables directly, point `DATABASE_URL`
at the hosted Supabase Postgres database instead of the local Docker database.
The Supabase REST keys are not enough for these SQL-backed endpoints.

```env
# Project Settings > Database > Connection string
DATABASE_URL=postgresql://postgres.<PROJECT_REF>:<DB_PASSWORD>@aws-0-ap-northeast-2.pooler.supabase.com:5432/postgres?sslmode=require
```

When running Docker Compose from the frontend directory, the backend service
loads `../Yhouse115_Back/.env`. Keep the Supabase Postgres connection string in
that file so the backend container connects to the hosted project.

## Supabase CLI

The `supabase/` directory is used for Supabase CLI project linking and schema migrations.

Common commands:

```bash
supabase login
supabase link --project-ref <project-ref>
supabase db pull
supabase start
```

Generated CLI runtime state such as `supabase/.temp` and `supabase/.branches` should stay untracked.

## Naver Maps

Backend settings for server-side Naver Maps APIs:

```env
NAVER_MAPS_CLIENT_ID=
NAVER_MAPS_CLIENT_SECRET=
NAVER_MAPS_GEOCODE_BASE_URL=https://maps.apigw.ntruss.com/map-geocode/v2
NAVER_MAPS_REVERSE_GEOCODE_BASE_URL=https://maps.apigw.ntruss.com/map-reversegeocode/v2
```

Frontend map rendering should use a browser-safe public key separately, such as `VITE_NAVER_MAPS_CLIENT_ID`. Never expose `NAVER_MAPS_CLIENT_SECRET` through frontend environment variables.

## CORS

Default local origins include Vite's common ports:

```env
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173
```

Add deployed frontend domains before production rollout.
