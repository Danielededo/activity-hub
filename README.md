# Activity Hub

Self-hosted fitness aggregator. Upload TCX/GPX files, store them in PostgreSQL,
query your training through a REST API and (from phase 2) a React dashboard.

No authentication and no external integrations: single-user deployment, with the
user identified by a `user_id` query parameter.

## Status

| Phase | Scope | State |
| --- | --- | --- |
| 1 | FastAPI backend, parsers, analyzer, migrations, tests | done |
| 2 | React + Vite + Tailwind dashboard | not started |
| 3 | docker-compose and Helm chart | not started |

## Stack

- **Backend** — FastAPI, SQLAlchemy 2.0, Alembic, PostgreSQL
- **Parsers** — TCX (Garmin) and GPX (Strava, Komoot, and other exporters), via lxml
- **Frontend** — React, Vite, Tailwind, Recharts (phase 2)

Units are metric throughout: metres for distance and elevation, seconds for time.

## Running the backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env        # point DATABASE_URL at your PostgreSQL instance
alembic upgrade head        # create the schema
uvicorn app.main:app --reload
```

The API is then on http://localhost:8000, with interactive docs at `/docs`.

### Tests

```bash
cd backend
pytest                                   # 67 tests, no database required
pytest --cov=app --cov-report=term-missing
ruff check .
```

The suite runs against an in-memory SQLite database, so there is nothing to
provision. `JSONB` and `BIGSERIAL` columns fall back to portable types outside
PostgreSQL.

### Docker

```bash
docker build -t activity-hub-api ./backend
docker run -p 8000:8000 -e DATABASE_URL=... activity-hub-api
```

The image runs `alembic upgrade head` before starting uvicorn, so a fresh
volume comes up ready.

## API

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/api/health` | 503 when the database is unreachable |
| POST | `/api/users/` | 409 on a duplicate username or email |
| GET | `/api/users/{id}` | |
| GET | `/api/workouts?user_id=X` | `limit`, `offset`, optional `sport_type`; newest first |
| GET | `/api/workouts/{id}` | Includes `raw_data` and `track_point_count` |
| DELETE | `/api/workouts/{id}` | Cascades to track points |
| POST | `/api/upload?user_id=X` | Multipart `file`: one `.tcx` or `.gpx` |
| GET | `/api/analysis/{user_id}` | Lifetime totals plus a per-sport breakdown |
| GET | `/api/analysis/{user_id}/weekly?weeks=12` | One bucket per ISO week, quiet weeks zero-filled |

Upload failures are explicit: `404` unknown user, `400` empty file, `409`
already stored, `413` over the size limit, `422` unreadable or unsupported file.

## How a file becomes a workout

1. `parser_factory` picks a parser by extension, falling back to sniffing the
   XML root element.
2. The parser produces a `ParsedWorkout`: header fields, any totals the file
   states itself, and one `ParsedTrackPoint` per sample. Element lookups are
   namespace-agnostic, so vendor variations do not need special cases.
3. `analyzer.compute_metrics` fills the gaps. It trusts the file's own totals
   when present — Garmin measures distance with a wheel or footpod, which beats
   integrating GPS positions — and otherwise derives distance with the haversine
   formula, discarding implausible jumps from dropped signal. Elevation gain and
   loss ignore changes under 1 m as GPS jitter.
4. The workout row is written with the summary columns, and the samples are
   inserted into `track_points` in a single multi-row statement.

`workouts.raw_data` holds file-level metadata only — creator, author, lap
summaries, counts. The samples live in `track_points`, so nothing is stored
twice.

### Duplicate detection

`(user_id, start_time, source)` is unique. Re-uploading the same activity
returns `409` rather than a second copy, whatever the file is named.

## Repository layout

```
backend/
├── app/
│   ├── main.py            FastAPI app, CORS, router wiring
│   ├── config.py          pydantic-settings, reads .env
│   ├── database.py        engine, session factory, declarative base
│   ├── models/            User, Workout, TrackPoint
│   ├── schemas/           request/response models
│   ├── routers/           health, users, workouts, upload, analysis
│   └── services/
│       ├── analyzer.py    metric derivation and aggregate reporting
│       └── parsers/       base, TCX, GPX, factory
├── alembic/               migrations (0001 creates the whole schema)
└── tests/                 parsers, analyzer, API
```
