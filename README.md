# Activity Hub

Self-hosted fitness aggregator. Upload TCX/GPX files, store them in PostgreSQL,
query your training through a REST API and a React dashboard.

No authentication and no external integrations: single-user deployment, with the
user identified by a `user_id` query parameter.

## Stack

- **Backend** — FastAPI, SQLAlchemy 2.0, Alembic, PostgreSQL
- **Parsers** — TCX (Garmin) and GPX (Strava, Komoot, and other exporters)
- **Frontend** — React, Vite, Tailwind, Recharts

Units are metric throughout: metres for distance and elevation, seconds for time.

## Planned phases

| Phase | Scope | State |
| --- | --- | --- |
| 1 | FastAPI backend, parsers, analyzer, migrations, tests | not started |
| 2 | React + Vite + Tailwind dashboard | not started |
| 3 | docker-compose and Helm chart | not started |
