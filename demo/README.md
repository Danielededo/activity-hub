# Demo data

Synthetic TCX and GPX activities: five weeks of training plus a set of
deliberately awkward files.

## Why synthetic

Real GPS traces are personal data. A GPX exported from someone's watch
normally starts at their front door, so vendoring real files into a public
repository is a privacy problem before it is a licensing one. Generating also
means the awkward cases can be produced on purpose instead of hoped for.

## Loading it

With the API running and a user created:

```bash
curl -X POST http://localhost:8000/api/users/ \
  -H 'Content-Type: application/json' \
  -d '{"username":"demo","email":"demo@example.com"}'

./demo/load.sh                      # defaults to user 1 on localhost:8000
API=http://host:8000/api USER_ID=2 ./demo/load.sh
```

The script reports one line per file and tolerates `409 Conflict`, so it is
safe to re-run.

## Regenerating

```bash
cd backend
python -m scripts.generate_demo_data --out ../demo/activities --clean \
    --weeks 5 --step-seconds 60           # exactly what is committed here
```

Output is deterministic for a given `--seed`, and `--ending` is pinned so the
committed files stay stable — which also means they age. The committed block
ends **2026-06-28**, so a weekly chart run much later shows empty recent weeks.
For a dashboard that looks alive, regenerate with `--ending today`. For something closer to real data — a full
training year sampled every ten seconds, about 15 MB — write it somewhere
untracked:

```bash
python -m scripts.generate_demo_data --out ../demo/generated \
    --weeks 26 --step-seconds 10 --ending today
```

`demo/generated/` is gitignored. The committed set is sampled every 60 seconds
to keep it a few hundred KB rather than megabytes.

## What is in here

Five weeks of cycling, running and hiking, alternating between Garmin-flavoured
TCX and Strava/Komoot-flavoured GPX, with plausible heart rate, cadence and
elevation profiles. A few files state a real UTC offset instead of `Z`.

The `edge-*` files exist to exercise what real exports get wrong:

| File | What it exercises |
| --- | --- |
| `edge-no-heart-rate.gpx` | A watch worn without a strap: no `hr` extension at all |
| `edge-no-point-timestamps.gpx` | A planned route — timestamps only in `metadata`, none per point |
| `edge-stated-utc-offset.tcx` | `+02:00` instead of `Z`, so the local hour is knowable |
| `edge-single-point.gpx` | An aborted activity: one track point, zero distance |
| `edge-tcx-sport-other.tcx` | TCX has no hiking in its vocabulary, so a hike arrives as `Other` |
