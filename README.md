# Activity Hub

[![CI](https://github.com/Danielededo/activity-hub/actions/workflows/ci.yml/badge.svg)](https://github.com/Danielededo/activity-hub/actions/workflows/ci.yml)

Self-hosted training log. Feed it the TCX and GPX files your watch or Strava
exports, and get your history back as numbers and charts that stay on your own
machine.

One user, no accounts, no external services, no telemetry. Units are metric
throughout.

## Quick start

You need **Docker with Compose v2**. Nothing else — the images build themselves.

```bash
git clone https://github.com/Danielededo/activity-hub.git
cd activity-hub
cp .env.example .env          # then change POSTGRES_PASSWORD
docker compose up --build     # first run takes a few minutes
```

Open <http://localhost:8080>. The dashboard asks for your name once, and that is
the whole of setup. Then feed it your activities: drop files on the upload box,
pick a folder, or hand it the entire `.zip` your watch or Strava exported.

To try it without your own data, load the bundled demo set:

```bash
./demo/load.sh                # 22 synthetic activities over five weeks
```

## What you get

- **Upload TCX and GPX** — one file, a folder, a drag and drop, or the whole
  export as a `.zip`. Garmin, Strava, Komoot and anything else that writes
  standard files. Re-uploading is safe: files already stored are skipped, and
  each file is reported separately as it lands.
- **Lifetime totals** — distance, moving time, elevation, heart rate, with
  per-sport breakdowns.
- **Weekly trend** over any window from 8 to 52 weeks.
- **Heart-rate zones and training load** — how much time goes into each of five
  zones, per activity and per week, with Edwards' TRIMP as the load figure.
- **Personal bests** — the fastest 1 km, 5 km, 10 km, half marathon and
  marathon you have ever covered, per sport, each naming the activity that set
  it. Plus the furthest, longest and biggest-climbing activity of each sport,
  and totals by year.
- **Every activity in a table** with pace or speed depending on the sport, in
  the activity's own local time.
- **Filter and search** by sport, date range and name, with paging over the
  result.
- **Per-activity detail** — the route coloured by speed, with traces for heart
  rate, cadence and elevation. Hovering the route reports how far in, how long
  in, and how fast at that point.
- **Duplicate detection** that catches the same session exported twice from two
  different services, not just the same file twice.
- **Export** — the summary as CSV and every activity as GPX in one zip, both
  honouring whatever filters are set. The zip this app writes is a zip it can
  read back.

## Your data

Everything lives in one PostgreSQL volume, `activity-hub_pgdata`. Nothing is
sent anywhere.

**`docker compose down -v` deletes it.** The `-v` removes volumes, which means
your entire history. `docker compose down` without it is safe, and so is
`docker compose stop`.

Back it up before you need to:

```bash
docker compose exec -T postgres \
  sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' > activity-hub-backup.sql
```

And to restore into a fresh stack:

```bash
docker compose exec -T postgres \
  sh -c 'psql -U "$POSTGRES_USER" "$POSTGRES_DB"' < activity-hub-backup.sql
```

The uploaded files themselves are not kept — each one is parsed into a workout
plus its samples, and the original is discarded. Keep your exports if you want
them.

## Updating

```bash
git pull
docker compose up -d --build
```

Schema migrations run automatically when the API container starts, so there is
no separate step. The volume is untouched.

One exception, once: personal bests are computed when a file is uploaded, so
activities stored before that feature existed have none until they are filled
in.

```bash
docker compose exec backend python -m scripts.backfill_bests
```

It reads one activity at a time, is safe to interrupt and safe to re-run — it
only looks at activities with no bests yet. `--recompute` redoes every
activity, which is only needed if the window calculation itself changes.

The heart-rate histogram behind the zones is the same story:

```bash
docker compose exec backend python -m scripts.backfill_hr_zones
```

This one is strictly better behaved. It records an empty histogram for an
activity that carried no heart rate, so "never looked at" and "looked at,
nothing there" are different states and a strapless activity is visited once
rather than rescanned on every run.

## API

Interactive docs at <http://localhost:8000/docs> when the stack is up.

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/api/health` | 503 when the database is unreachable |
| GET | `/api/users/me` | The profile; 404 before one exists |
| POST | `/api/users/` | Creates the profile; 409 if one already exists |
| GET | `/api/users/{id}` | |
| GET | `/api/workouts?user_id=X` | `limit`, `offset`, and optional `sport_type`, `date_from`, `date_to`, `q`; newest first |
| GET | `/api/workouts/{id}?user_id=X` | Includes `raw_data` and `track_point_count`; 404 if owned by someone else |
| GET | `/api/workouts/{id}/track-points?user_id=X` | Samples for a route map or HR trace, downsampled to `max_points` |
| DELETE | `/api/workouts/{id}?user_id=X` | Cascades to track points; 404 if owned by someone else |
| POST | `/api/upload?user_id=X` | Multipart `file`: one `.tcx` or `.gpx` |
| POST | `/api/upload/archive?user_id=X` | Multipart `file`: a `.zip` export. Returns counts plus a per-file outcome |
| GET | `/api/analysis/{user_id}` | Lifetime totals plus a per-sport breakdown |
| GET | `/api/analysis/{user_id}/weekly?weeks=12` | One bucket per local week, quiet weeks zero-filled |
| GET | `/api/analysis/{user_id}/records` | Per-sport records and distance bests, plus totals by local year |
| GET | `/api/analysis/{user_id}/zones?weeks=12` | Time in each heart-rate zone, lifetime and by week, with load |
| GET | `/api/workouts/{id}/zones?user_id=X` | One activity's time in zone and the load it earned |
| GET | `/api/workouts/{id}/export.gpx?user_id=X` | This activity as GPX, rebuilt from its samples |
| GET | `/api/export/activities.csv?user_id=X` | One row per activity; takes the same filters as the list |
| GET | `/api/export/activities.zip?user_id=X` | Every matching activity as a GPX file, in one zip |

Upload failures are explicit: `404` unknown user, `400` empty file, `409`
already stored, `413` over the size limit, `422` unreadable or unsupported file.

## One user, no authentication

The deployment serves exactly one person: whoever is self-hosting it. On first
run `GET /api/users/me` answers 404, the dashboard asks for a name, and that is
the whole of setup — no id to configure, and no placeholder profile invented on
your behalf.

The profile is only a name. With one user and no authentication there is
nothing to log in as and nothing to send mail to, so there is no username and
no email; the surname is optional, because plenty of people go by one name.
`POST /api/users/` refuses a second profile: `/users/me` resolves to the lowest
id, so an extra row would simply be invisible.

Activity files cannot supply the name. GPX 1.1 has a slot for it
(`metadata/author/name`) and TCX has none — its `Author` is the application and
its `Creator` is the device — and in practice the big exporters leave it empty
anyway, which is the right call for personal data.

`user_id` stays in the schema and on every endpoint. It is not a security
boundary — without authentication nothing here is — it scopes data, and the
ownership checks stop accidental cross-reads rather than attacks. Keeping it
costs nothing and leaves the door open to a second person.

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

### Importing an archive

`POST /api/upload/archive` takes the zip a service exports and stores every
activity in it, reporting each file as `stored`, `duplicate`, `skipped` or
`failed`. A real export is full of CSVs and images, so those are *skipped*, not
errors; and one corrupt file does not stop the other three hundred.

An archive from a user is hostile input, so the reader guards the three ways
that goes wrong. **Zip bombs**: both the declared uncompressed total and each
member are capped, and every read is bounded, so a header that lies cannot turn
into memory use either. **Member floods**: the entry count is capped.
**Nested archives**: refused rather than recursed into. Path traversal is absent
by construction — members are read into memory, never extracted to disk, so
there is no path to traverse.

Members are processed one at a time, and that is load-bearing rather than merely
simple: the near-duplicate check reads before it writes, so two files describing
the same session could both pass it if they were handled at once — and the unique
constraint would not catch them either, since their bytes differ.

### Duplicate detection

Two questions, answered separately.

`(user_id, file_hash)` is unique, so the same bytes cannot be stored twice
whatever the file is named — exact, and enforced by the database.

That misses the same ride exported from Garmin as TCX and from Strava as GPX:
different bytes, different `source`, one session. Those are recognised by what
they describe — same sport, starting within `DUPLICATE_WINDOW_SECONDS` — which
no constraint can express, so the check lives in the service layer. A brick
session still works: a ride and a run at the same time are different sports.

## What the dashboard shows, and why

Lifetime totals as stat tiles, weekly distance as a bar chart, distance per
sport, an upload box that reports each file separately, and a table of every
activity. Opening one draws its route and traces its heart rate, cadence and
elevation.

Choices worth knowing about:

- **Weekly distance is bars, not a line.** The weeks are discrete buckets; a
  line between them would imply a continuous quantity nobody measured, and a
  quiet week is a real zero.
- **Heart rate, cadence and elevation get a chart each.** Two measures of
  different scale on two y-axes make the crossing point an artefact of the axis
  ranges, and readers take it to mean something. The two body measures sit
  together and the terrain that explains them comes after.
- **Cadence is reported as recorded, in the sport's own unit.** Cycling is
  crank revolutions per minute. On foot, TCX `RunCadence` and GPX `cad` are
  written per leg, so the figure is strides per minute — roughly half the
  steps-per-minute a watch shows. It is not doubled to match: nothing in either
  format says which convention a file used, and an exporter that already counts
  both feet would then read twice as fast as the run was.
- **An activity with no cadence sensor gets no cadence chart** rather than a
  flat line at zero, which would say the sensor read nothing rather than that
  there was no sensor.
- **The route has no basemap.** Tiles would mean asking a third party for the
  map of wherever you exercise, which is the opposite of the point of
  self-hosting. What a bare line can still say is the shape of the ride and
  where on it you were moving, so it says both.
- **The route is coloured by speed**, in five steps of one hue, from the
  activity's own slowest stretch to its fastest. Quantiles of that activity
  rather than absolute bands: the question is where you were quick *on this
  ride*, and fixed thresholds would paint a whole hike in one step. The legend
  names both ends in the sport's unit, so the colours still read in absolute
  terms.
- **If the two ends of the ramp would print the same figure, there is no ramp.**
  Five shades of a number that does not change is decoration, so a steady ride
  goes back to a plain line.
- **A stretch whose speed is unknown is grey, not blue.** The app's
  single-series blue happens to be the middle step of the ramp, so painting an
  unmeasured stretch with it would read as "average pace" rather than "not
  measured". Anything faster than 120 km/h counts as a lost fix, not a speed.
- **Start and finish are told apart by shape**, a disc and a square in text ink.
  Green against red is the obvious choice and fails outright for a red-green
  reader: those two sit 4.1 ΔE apart under simulated deuteranopia, where 8 is
  the target. A route that finishes where it began gets **one** marker labelled
  as both, because two of them sat on top of each other — and a loop is the
  commonest shape of ride.
- **The drawing is sized to the route, not to a square.** It used to be fitted
  into a square and then letterboxed into a panel that is never square, so a
  broad route was drawn at the height of the panel with half the width empty: a
  wide loop used 42% of its panel and now uses 91%. The scale stays uniform
  either way — shape is never distorted, only the space it is given changes.
- **Sport colours come from a validated palette** and are assigned in fixed
  order. Two of the light-mode hues fall below 3:1 on white, so everything
  painted with them carries a visible label — identity is never colour alone.
- **Metric only, no unit toggle.** Runners get minutes per kilometre, cyclists
  get km/h.
- **Times are the activity's own local time**, from the UTC offset its file
  stated, in 24-hour form.
- **Upload results appear as each file lands**, with a running count. A few
  hundred files used to mean minutes of silence, which is indistinguishable
  from a hang.
- **Filter dates are local dates.** `date_from` and `date_to` are resolved in
  `DISPLAY_TIMEZONE`, so asking for July returns July where you were, not July
  in Greenwich. `date_to` is inclusive.
- **The sport filter lists only sports you have recorded**, with counts, and
  the counts stay unfiltered — narrowing the list should not make the options
  disappear from under you.
- **Deleting asks twice.** There is no undo and the track points go with it, so
  the destructive click is the second one — and Cancel is where the Delete
  button just was, so a double-click cancels.
- **The export is two formats because one is not enough.** GPX carries the
  samples and has nowhere to put a device's own totals — a TCX states its
  distance and average heart rate per lap, and a reader of the GPX has to
  recompute both from the positions. So the CSV carries the figures this app
  stored and the GPX carries the samples behind them. A test asserts the gap
  rather than leaving it to be discovered.
- **Downloads are links, not buttons.** The browser streams the file straight to
  disk with the name the server chose; pulling the bytes into JavaScript first
  would buy nothing and fall over on exactly the export big enough to matter.
- **A GPX filename is the date, the sport and the id**, never the activity name.
  A name can hold anything at all, and a zip full of files named after user
  input is a zip nobody can unpack safely.
- **Zones are derived on request, not stored.** What is stored is the histogram
  — how many seconds at each beat per minute — because zones hang off a maximum
  heart rate that *moves*: one harder session and every previous activity's
  zones shift. Stored zones would describe the athlete you used to be.
- **The maximum says where it came from.** Configured, or the highest beat any
  activity recorded. Observed is a floor rather than a maximum: a peak nobody
  has pushed to reads low and lifts every zone, so the panel prints which one it
  used instead of asking you to trust it.
- **Time below zone one is reported, never folded in.** Warming up and standing
  at a junction are real time and not easy training; adding them to Z1 would
  inflate exactly the zone people read as "I did my easy work".
- **A gap longer than two minutes is not time at that heart rate.** It is a
  pause or a lost signal, so it is dropped rather than credited — which is also
  why a file sampled less often than that contributes no time in zone at all.
- **Load is Edwards' TRIMP**: minutes in a zone weighted by the zone, one
  through five. Banister's needs a resting heart rate and a sex-specific
  exponential that this app does not ask for; Edwards' needs only the zones.
- **A personal best is the fastest stretch, not the average.** The 5 km best is
  the quickest any five kilometres were covered inside any activity, found by
  sliding a window over the samples — so a hard middle kilometre of an easy run
  is still a record. The window is interpolated between samples, or the answer
  would depend on how often the watch happened to write a point.
- **Standing still and losing signal cannot set a record.** A pause adds time
  and no distance; a hop longer than a plausible step adds time and no distance
  either. Both would otherwise read as impossibly fast.
- **Bests are computed at upload, not on request.** That is the one moment the
  samples are already in memory. Answering later would mean re-reading every
  track point of every activity for a figure that never changes.
- **Window distances come from the positions, not from the file's own total.** A
  wheel-measured total is the better number for the activity as a whole, but it
  says nothing about *where inside* the activity a kilometre was, which is what
  a window needs.
- **A tie keeps the earlier activity.** Riding the same loop to the metre should
  not move the date a record was set.
- **Every record names the activity that holds it**, and opening it fetches that
  activity: a figure with nothing behind it cannot be checked.

## Demo data

`demo/activities/` holds five weeks of synthetic training plus files that
exercise the awkward cases — no heart rate, no per-point timestamps, a stated
UTC offset, a single point, a hike that TCX can only call `Other`. Synthetic
rather than downloaded because a real GPX track starts at somebody's front
door.

```bash
./demo/load.sh                # into a running stack
cd backend && python -m scripts.generate_demo_data --help
```

See [demo/README.md](demo/README.md) for regenerating, and for a full training
year written somewhere untracked.

## Development

Docker is enough to run it; these are for working on it. You need **Python
3.11** and **Node 22**.

```bash
# API — http://localhost:8000, docs at /docs
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env             # point DATABASE_URL at a PostgreSQL instance
alembic upgrade head
uvicorn app.main:app --reload
```

```bash
# Dashboard — http://localhost:5173, proxying /api to :8000
cd frontend
npm install
npm run dev
```

The dev server proxies `/api`, and the nginx image serves the API on the same
origin, so the browser never makes a cross-origin request and CORS never comes
into it either way.

For a headless setup that never opens a browser, `python -m scripts.ensure_user`
creates the profile from `DEFAULT_FIRST_NAME` instead of the first-run screen.

### Tests

```bash
cd backend && ruff check . && pytest          # 168 tests, no database needed
cd frontend && npm run lint && npm test       # 57 tests, jsdom
```

The backend suite runs against in-memory SQLite, so there is nothing to
provision: `JSONB` and `BIGSERIAL` fall back to portable types outside
PostgreSQL.

### CI

`.github/workflows/ci.yml` runs on every push to `main` and every pull request:

| Job | What it proves |
| --- | --- |
| Lint and test | `ruff check` is clean and the backend suite passes |
| Migrations on PostgreSQL | The schema applies to a real PostgreSQL 16, `alembic check` finds no drift from the models, and the downgrade path works |
| Frontend lint, test and build | ESLint is clean, the jsdom suite passes, and the bundle builds |
| Images and compose stack | Both images build, the stack comes up health-gated, and a profile plus an upload round-trips through the dashboard's own origin |

The last two exercise what the unit suites cannot: the actual `JSONB` and
`BIGSERIAL` DDL, the image's migrate-then-serve entrypoint, and the nginx proxy
that makes same-origin requests possible.

## Deployment

`docker compose` is the whole deployment story, on purpose. This is a
single-user application that fits on one machine — a NAS, a VPS, a server in a
cupboard — and it builds its own images, so there is nothing to publish to a
registry and no credentials to keep anywhere.

A Helm chart lived here briefly. It was removed rather than kept "just in case":
600 lines guessing at a cluster's storage class, ingress class and secret
conventions is a liability if nobody runs it, and a chart written when those
things are actually known would be a better chart. It is in the git history if
that day comes.

## Repository layout

```
backend/
├── app/
│   ├── main.py            FastAPI app, CORS, router wiring
│   ├── config.py          pydantic-settings, reads .env
│   ├── database.py        engine, session factory, declarative base
│   ├── models/            User, Workout, TrackPoint, WorkoutBest
│   ├── schemas/           request/response models
│   ├── routers/           health, users, workouts, upload, analysis, export
│   └── services/
│       ├── analyzer.py    metric derivation and aggregate reporting
│       ├── records.py     the window scan, and records over it
│       ├── zones.py       the heart-rate histogram, and zones over it
│       ├── exports.py     CSV, GPX and the zip of them
│       └── parsers/       base, TCX, GPX, factory
├── alembic/               migrations
├── scripts/               demo data generator, profile bootstrap, two backfills
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

demo/                      synthetic activities and a loader
docker-compose.yml         the whole stack
```

Repository-level files: `LICENSE`, `.gitignore`, `.editorconfig` (shared
indentation rules across Python, JS and YAML) and `.github/workflows/ci.yml`.

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
