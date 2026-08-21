# Activity Hub

[![CI](https://github.com/Danielededo/activity-hub/actions/workflows/ci.yml/badge.svg)](https://github.com/Danielededo/activity-hub/actions/workflows/ci.yml)

Self-hosted fitness aggregator. Upload TCX/GPX files, store them in PostgreSQL,
query your training through a REST API and (from phase 2) a React dashboard.

No authentication and no external integrations: single-user deployment, with the
user identified by a `user_id` query parameter.

## Status

| Phase | Scope | State |
| --- | --- | --- |
| 1 | FastAPI backend, parsers, analyzer, migrations, tests | done |
| 2 | React + Vite + Tailwind dashboard | done |
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

cp .env.example .env             # point DATABASE_URL at your PostgreSQL instance
alembic upgrade head             # create the schema
uvicorn app.main:app --reload
```

The dashboard asks who you are on first run, so there is nothing else to set
up. For a headless deployment that never opens a browser, `python -m
scripts.ensure_user` creates the profile from `DEFAULT_FIRST_NAME`.

The API is then on http://localhost:8000, with interactive docs at `/docs`.

## Running the dashboard

```bash
cd frontend
npm install
npm run dev            # http://localhost:5173, proxying /api to :8000
```

The dev server proxies `/api`, and the nginx image serves the API on the same
origin, so the browser never makes a cross-origin request and CORS never comes
into it. On first run the dashboard asks for your name; after that it goes
straight to your training.

```bash
npm run lint
npm test               # 43 tests, jsdom
npm run build
docker build -t activity-hub-web ./frontend   # nginx, API_URL at container start
```

### What the dashboard shows

Lifetime totals as stat tiles, weekly distance as a bar chart, distance per
sport, an upload box that reports each file separately, and a table of every
activity. Opening one draws its route, its heart rate and its elevation.

Some choices worth knowing about:

- **Weekly distance is bars, not a line.** The weeks are discrete buckets; a
  line between them would imply a continuous quantity nobody measured, and a
  quiet week is a real zero.
- **Heart rate and elevation get a chart each.** Two measures of different
  scale on two y-axes make the crossing point an artefact of the axis ranges,
  and readers take it to mean something.
- **The route has no basemap.** Tiles would mean asking a third party for the
  map of wherever you exercise, which is the opposite of the point of
  self-hosting. The line is the shape of the ride.
- **Sport colours come from a validated palette** and are assigned in fixed
  order. Two of the light-mode hues fall below 3:1 on white, so everything
  painted with them carries a visible label — identity is never colour alone.
- **Metric only, no unit toggle.** Runners get minutes per kilometre, cyclists
  get km/h.
- **Times are the activity's own local time**, from the UTC offset its file
  stated, in 24-hour form.

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

### CI

`.github/workflows/ci.yml` runs on every push to `main` and every pull request:

| Job | What it proves |
| --- | --- |
| Lint and test | `ruff check` is clean and all tests pass |
| Migrations on PostgreSQL | The schema applies to a real PostgreSQL 16, `alembic check` finds no drift from the models, and the downgrade path works |
| Docker image | The image builds, and a container started against PostgreSQL migrates itself and reports healthy |

The last two exercise what the SQLite test suite cannot: the actual `JSONB` and
`BIGSERIAL` DDL, and the image's migrate-then-serve entrypoint.

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
| GET | `/api/users/me` | The profile; 404 before one exists |
| POST | `/api/users/` | Creates the profile; 409 if one already exists |
| GET | `/api/users/{id}` | |
| GET | `/api/workouts?user_id=X` | `limit`, `offset`, optional `sport_type`; newest first |
| GET | `/api/workouts/{id}?user_id=X` | Includes `raw_data` and `track_point_count`; 404 if owned by someone else |
| GET | `/api/workouts/{id}/track-points?user_id=X` | Samples for a route map or HR trace, downsampled to `max_points` |
| DELETE | `/api/workouts/{id}?user_id=X` | Cascades to track points; 404 if owned by someone else |
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

Timestamps are stored as UTC. TCX and GPX normally write `Z`, which fixes the
instant but says nothing about the local hour, so any offset the file *does*
state is kept in `utc_offset_minutes` and `DISPLAY_TIMEZONE` is the fallback.
Weekly totals are bucketed by local week: a 00:30 Monday ride in Rome belongs
to that Monday, not to the Sunday it falls on in UTC.

`workouts.raw_data` holds file-level metadata only — creator, author, lap
summaries, counts. The samples live in `track_points`, so nothing is stored
twice.

### Duplicate detection

Two questions, answered separately.

`(user_id, file_hash)` is unique, so the same bytes cannot be stored twice
whatever the file is named — exact, and enforced by the database.

That misses the same ride exported from Garmin as TCX and from Strava as GPX:
different bytes, different `source`, one session. Those are recognised by what
they describe — same sport, starting within `DUPLICATE_WINDOW_SECONDS` — which
no constraint can express, so the check lives in the service layer. A brick
session still works: a ride and a run at the same time are different sports.

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
├── alembic/               migrations
├── scripts/               demo data generator, profile bootstrap
└── tests/                 parsers, analyzer, API

frontend/
├── src/
│   ├── App.jsx            first-run screen or dashboard
│   ├── theme.js           the validated sport palette, both modes
│   ├── api/client.js      every call this app makes
│   ├── utils/formatters.js  metric formatting
│   └── components/        Dashboard, StatsCards, TrendChart, WorkoutTable,
│                          UploadForm, WorkoutDetail, RouteMap, TraceChart
├── nginx.conf             serves the build, proxies /api
└── tests/                 formatters, palette, components
```

Repository-level files: `LICENSE`, `.gitignore`, `.editorconfig` (shared
indentation rules across Python, JS and YAML) and `.github/workflows/ci.yml`.

## One user, no authentication

The deployment serves exactly one person: whoever is self-hosting it. On first
run `GET /api/users/me` answers 404, the dashboard asks for a name, and that is
the whole of setup — no id to configure, and no placeholder profile invented on
your behalf.

The profile is only a name. With one user and no authentication there is
nothing to log in as and nothing to send mail to, so there is no username and
no email; the surname is optional, because plenty of people go by one name.
`POST /api/users/` refuses a second profile: /users/me resolves to the lowest
id, so an extra row would simply be invisible.

Activity files cannot supply the name. GPX 1.1 has a slot for it
(`metadata/author/name`) and TCX has none — its `Author` is the application and
its `Creator` is the device — and in practice the big exporters leave it empty
anyway, which is the right call for personal data.

`user_id` stays in the schema and on every endpoint. It is not a security
boundary — without authentication nothing here is — it scopes data, and the
ownership checks stop accidental cross-reads rather than attacks. Keeping it
costs nothing and leaves the door open to a second person.

## Demo data

`demo/activities/` holds five weeks of synthetic training plus files that
exercise the awkward cases — no heart rate, no per-point timestamps, a stated
UTC offset, a single point, a hike that TCX can only call `Other`. Synthetic
rather than downloaded because a real GPX track starts at somebody's front
door.

```bash
./demo/load.sh                                  # into a running API
cd backend && python -m scripts.generate_demo_data --help
```

See [demo/README.md](demo/README.md) for regenerating, and for a full training
year written somewhere untracked.

## Contributing

`main` is the default branch and is never committed to directly. Each change
lands as a pull request, and CI must be green before it merges.

```bash
git switch -c my-change main
# ... work ...
cd backend && ruff check . && pytest
```

Environment files are the one thing to watch: `.env.example` is tracked, every
real `.env` is ignored. Never commit credentials.

## License

Released under the [MIT License](LICENSE).
