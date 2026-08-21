"""Generate synthetic TCX and GPX activities for demos and manual testing.

Synthetic rather than downloaded on purpose. A real GPX track is personal
data — it usually starts at somebody's front door — so vendoring one into an
MIT repository is a privacy problem before it is a licensing one. Generating
also means the awkward cases (no heart rate, no timestamps, a stated UTC
offset) can be produced deliberately instead of hoped for.

Output is deterministic for a given --seed, so regenerating produces the same
bytes and the committed demo set stays stable.

    python -m scripts.generate_demo_data --out ../demo/activities --weeks 8
"""

from __future__ import annotations

import argparse
import math
import random
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

EARTH_RADIUS_M = 6_371_008.8

#: Where the routes start. Turin, matching the coordinates used in the tests.
ORIGIN_LAT, ORIGIN_LON = 45.0703, 7.6869
BASE_ELEVATION_M = 240.0


@dataclass(frozen=True)
class SportProfile:
    """How a sport behaves, roughly, for the purposes of a plausible file."""

    name: str
    tcx_sport: str  # the TCX Sport_t vocabulary is narrow
    gpx_type: str
    speed_ms: float
    speed_jitter: float
    duration_range: tuple[int, int]  # seconds
    heart_rate_base: int
    cadence_base: int | None
    cadence_jitter: int = 6


PROFILES = (
    SportProfile("cycling", "Biking", "cycling", 7.2, 1.4, (2400, 9000), 132, 84),
    SportProfile("running", "Running", "running", 3.1, 0.35, (1500, 4800), 148, 86, 3),
    SportProfile("hiking", "Other", "hiking", 1.3, 0.25, (3600, 12000), 112, None),
)

#: Sport mix, in PROFILES order (cycling, running, hiking).
WEEKDAY_MIX = (25, 70, 5)
WEEKEND_MIX = (55, 20, 25)

TCX_DEVICES = ("Garmin Edge 530", "Garmin Forerunner 265", "Garmin Fenix 7")
GPX_CREATORS = ("StravaGPX Android", "StravaGPX iPhone", "komoot - https://www.komoot.com")


@dataclass
class Sample:
    seconds: int
    latitude: float
    longitude: float
    elevation: float
    distance: float
    heart_rate: int | None
    cadence: int | None


@dataclass
class Activity:
    profile: SportProfile
    name: str
    start: datetime
    utc_offset_minutes: int | None
    samples: list[Sample] = field(default_factory=list)
    #: Deliberate gaps, so the parsers get exercised on real-world messiness.
    omit_heart_rate: bool = False
    omit_timestamps: bool = False

    @property
    def duration(self) -> int:
        return self.samples[-1].seconds if self.samples else 0

    @property
    def distance(self) -> float:
        return self.samples[-1].distance if self.samples else 0.0

    @property
    def heart_rates(self) -> list[int]:
        return [s.heart_rate for s in self.samples if s.heart_rate is not None]

    def timestamp(self, seconds: int) -> str:
        """ISO-8601 for a sample, in the activity's own stated form."""
        moment = self.start + timedelta(seconds=seconds)
        if self.utc_offset_minutes is None:
            return moment.strftime("%Y-%m-%dT%H:%M:%SZ")
        shifted = moment + timedelta(minutes=self.utc_offset_minutes)
        sign = "+" if self.utc_offset_minutes >= 0 else "-"
        hours, minutes = divmod(abs(self.utc_offset_minutes), 60)
        return f"{shifted.strftime('%Y-%m-%dT%H:%M:%S')}{sign}{hours:02d}:{minutes:02d}"


# -- route and physiology ------------------------------------------------


def _step(lat: float, lon: float, heading_deg: float, metres: float) -> tuple[float, float]:
    """Move `metres` along `heading_deg` from a coordinate."""
    heading = math.radians(heading_deg)
    d_lat = (metres * math.cos(heading)) / EARTH_RADIUS_M
    d_lon = (metres * math.sin(heading)) / (EARTH_RADIUS_M * math.cos(math.radians(lat)))
    return lat + math.degrees(d_lat), lon + math.degrees(d_lon)


def _elevation(distance_m: float, total_m: float, climb_m: float) -> float:
    """A single smooth climb-and-descent over the route."""
    if total_m <= 0:
        return BASE_ELEVATION_M
    progress = distance_m / total_m
    return BASE_ELEVATION_M + climb_m * math.sin(math.pi * progress)


def build_samples(
    rng: random.Random, profile: SportProfile, duration: int, step_seconds: int
) -> list[Sample]:
    """Walk a route, accumulating position, elevation and effort."""
    speed = max(0.5, rng.gauss(profile.speed_ms, profile.speed_jitter))
    # The nominal length, which shapes the elevation profile. The distance
    # actually walked comes out a little different, because the pace varies
    # step by step below.
    total_distance = speed * duration
    climb = rng.uniform(40.0, 600.0)

    # The per-step pace noise comes from its own generator, seeded from figures
    # this activity has already drawn. Taking it from `rng` would consume
    # numbers the schedule downstream depends on, so adding pace variation
    # would silently reshuffle which activities exist at all — different dates,
    # sports and filenames, from a change that was meant to touch only the
    # samples inside them.
    jitter = random.Random(f"{duration}:{speed:.6f}:{climb:.6f}")

    lat, lon = ORIGIN_LAT + rng.uniform(-0.02, 0.02), ORIGIN_LON + rng.uniform(-0.02, 0.02)
    heading = rng.uniform(0.0, 360.0)
    distance = 0.0
    previous_elevation = _elevation(0.0, total_distance, climb)

    samples: list[Sample] = []
    for seconds in range(0, duration + 1, step_seconds):
        elevation = _elevation(distance, total_distance, climb)
        grade = (elevation - previous_elevation) / max(1.0, speed * step_seconds)

        # Vary the pace within the activity: slower up, quicker down, with a
        # little noise. One speed for a whole ride made every segment identical,
        # which left anything that reads speed — a pace chart, a route coloured
        # by it — with nothing to show on the demo set. Tying it to the grade
        # also makes the pace agree with the elevation profile beside it.
        step_speed = max(0.8, speed * min(1.6, max(0.45, 1.0 - 7.0 * grade)))
        step_speed *= max(0.75, min(1.25, jitter.gauss(1.0, 0.07)))

        # Warm up over the first five minutes, then drift upwards, and work
        # harder uphill. Clamped to a plausible human range.
        warmup = min(1.0, 0.55 + seconds / 300.0)
        drift = 6.0 * (seconds / max(1, duration))
        heart_rate = profile.heart_rate_base * warmup + drift + grade * 220 + rng.gauss(0, 2.5)

        cadence = None
        if profile.cadence_base is not None:
            cadence = int(round(rng.gauss(profile.cadence_base, profile.cadence_jitter)))
            cadence = max(0, min(140, cadence))

        samples.append(
            Sample(
                seconds=seconds,
                latitude=round(lat, 6),
                longitude=round(lon, 6),
                elevation=round(elevation, 1),
                distance=round(distance, 1),
                heart_rate=max(80, min(190, int(round(heart_rate)))),
                cadence=cadence,
            )
        )

        heading += rng.gauss(0.0, 7.0)
        lat, lon = _step(lat, lon, heading, step_speed * step_seconds)
        distance += step_speed * step_seconds
        previous_elevation = elevation

    return samples


# -- schedule ------------------------------------------------------------

NAMES = {
    "cycling": ("Morning ride", "Hill repeats", "Long ride", "Commute", "Evening spin"),
    "running": ("Easy run", "Interval session", "Long run", "Tempo run", "Recovery jog"),
    "hiking": ("Ridge walk", "Forest loop", "Summit hike"),
}


def plan(
    rng: random.Random, weeks: int, ending: datetime
) -> Iterator[tuple[SportProfile, datetime, str]]:
    """Three to four sessions a week, ending on `ending`."""
    first_monday = (ending - timedelta(weeks=weeks - 1)).date()
    first_monday -= timedelta(days=first_monday.weekday())

    for week in range(weeks):
        days = sorted(rng.sample(range(7), rng.choice((3, 3, 4))))
        for day in days:
            date = first_monday + timedelta(weeks=week, days=day)
            if date > ending.date():
                continue
            # A recognisable training week: short runs midweek, the long ride
            # and the occasional hike at the weekend.
            weekend = day >= 5
            weights = WEEKEND_MIX if weekend else WEEKDAY_MIX
            profile = rng.choices(PROFILES, weights=weights, k=1)[0]
            hour = rng.choice((8, 9, 10)) if weekend else rng.choice((6, 7, 18, 19))
            start = datetime(
                date.year, date.month, date.day, hour, rng.choice((0, 15, 30, 45)), tzinfo=UTC
            )
            yield profile, start, rng.choice(NAMES[profile.name])


# -- writers -------------------------------------------------------------


def to_tcx(activity: Activity) -> str:
    """Garmin-flavoured TCX: one lap, a Creator device and an Author."""
    rng = random.Random(activity.name + activity.start.isoformat())
    heart_rates = activity.heart_rates
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<TrainingCenterDatabase xmlns="http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"'
        ' xmlns:ns3="http://www.garmin.com/xmlschemas/ActivityExtension/v2"'
        ' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">',
        "  <Activities>",
        f'    <Activity Sport="{activity.profile.tcx_sport}">',
        f"      <Id>{activity.timestamp(0)}</Id>",
        f'      <Lap StartTime="{activity.timestamp(0)}">',
        f"        <TotalTimeSeconds>{activity.duration}.0</TotalTimeSeconds>",
        f"        <DistanceMeters>{activity.distance}</DistanceMeters>",
        f"        <Calories>{int(activity.duration * rng.uniform(0.16, 0.24))}</Calories>",
    ]
    if heart_rates:
        average = round(sum(heart_rates) / len(heart_rates))
        lines += [
            f"        <AverageHeartRateBpm><Value>{average}</Value></AverageHeartRateBpm>",
            f"        <MaximumHeartRateBpm><Value>{max(heart_rates)}</Value></MaximumHeartRateBpm>",
        ]
    lines += [
        "        <Intensity>Active</Intensity>",
        f"        <Notes>{escape(activity.name)}</Notes>",
        "        <Track>",
    ]

    running = activity.profile.gpx_type == "running"
    for sample in activity.samples:
        lines.append("          <Trackpoint>")
        if not activity.omit_timestamps:
            lines.append(f"            <Time>{activity.timestamp(sample.seconds)}</Time>")
        lines += [
            "            <Position>",
            f"              <LatitudeDegrees>{sample.latitude}</LatitudeDegrees>",
            f"              <LongitudeDegrees>{sample.longitude}</LongitudeDegrees>",
            "            </Position>",
            f"            <AltitudeMeters>{sample.elevation}</AltitudeMeters>",
            f"            <DistanceMeters>{sample.distance}</DistanceMeters>",
        ]
        if sample.heart_rate is not None:
            lines.append(
                f"            <HeartRateBpm><Value>{sample.heart_rate}</Value></HeartRateBpm>"
            )
        if sample.cadence is not None:
            # Running dynamics live under an extension; cycling cadence does not.
            if running:
                lines.append(
                    "            <Extensions><ns3:TPX>"
                    f"<ns3:RunCadence>{sample.cadence}</ns3:RunCadence>"
                    "</ns3:TPX></Extensions>"
                )
            else:
                lines.append(f"            <Cadence>{sample.cadence}</Cadence>")
        lines.append("          </Trackpoint>")

    lines += [
        "        </Track>",
        "      </Lap>",
        '      <Creator xsi:type="Device_t">',
        f"        <Name>{escape(rng.choice(TCX_DEVICES))}</Name>",
        "      </Creator>",
        "    </Activity>",
        "  </Activities>",
        '  <Author xsi:type="Application_t"><Name>Garmin Connect</Name></Author>',
        "</TrainingCenterDatabase>",
        "",
    ]
    return "\n".join(lines)


def to_gpx(activity: Activity) -> str:
    """Strava/Komoot-flavoured GPX, with heart rate under gpxtpx."""
    rng = random.Random(activity.name + activity.start.isoformat())
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<gpx creator={quoteattr(rng.choice(GPX_CREATORS))} version="1.1"'
        ' xmlns="http://www.topografix.com/GPX/1/1"'
        ' xmlns:gpxtpx="http://www.garmin.com/xmlschemas/TrackPointExtension/v1">',
        "  <metadata>",
    ]
    if not activity.omit_timestamps:
        lines.append(f"    <time>{activity.timestamp(0)}</time>")
    lines += [
        f"    <name>{escape(activity.name)}</name>",
        "  </metadata>",
        "  <trk>",
        f"    <name>{escape(activity.name)}</name>",
        f"    <type>{activity.profile.gpx_type}</type>",
        "    <trkseg>",
    ]
    for sample in activity.samples:
        lines.append(f'      <trkpt lat="{sample.latitude}" lon="{sample.longitude}">')
        lines.append(f"        <ele>{sample.elevation}</ele>")
        if not activity.omit_timestamps:
            lines.append(f"        <time>{activity.timestamp(sample.seconds)}</time>")
        if sample.heart_rate is not None or sample.cadence is not None:
            parts = []
            if sample.heart_rate is not None:
                parts.append(f"<gpxtpx:hr>{sample.heart_rate}</gpxtpx:hr>")
            if sample.cadence is not None:
                parts.append(f"<gpxtpx:cad>{sample.cadence}</gpxtpx:cad>")
            lines.append(
                "        <extensions><gpxtpx:TrackPointExtension>"
                + "".join(parts)
                + "</gpxtpx:TrackPointExtension></extensions>"
            )
        lines.append("      </trkpt>")
    lines += ["    </trkseg>", "  </trk>", "</gpx>", ""]
    return "\n".join(lines)


# -- assembly ------------------------------------------------------------


def strip_heart_rate(activity: Activity) -> Activity:
    for sample in activity.samples:
        sample.heart_rate = None
    activity.omit_heart_rate = True
    return activity


def build_activities(
    seed: int, weeks: int, step_seconds: int, ending: datetime, edge_cases: bool
) -> list[tuple[str, str]]:
    """Return (filename, content) pairs for a whole training block."""
    rng = random.Random(seed)
    files: list[tuple[str, str]] = []
    seen: dict[str, int] = {}

    for index, (profile, start, name) in enumerate(plan(rng, weeks, ending)):
        duration = rng.randrange(*profile.duration_range, step_seconds)
        activity = Activity(
            profile=profile,
            name=name,
            start=start,
            # Most exporters write 'Z'; some state a real offset.
            utc_offset_minutes=120 if index % 5 == 4 else None,
        )
        activity.samples = build_samples(rng, profile, duration, step_seconds)

        # Alternate formats so both parsers get a workout — except hiking,
        # which TCX can only call "Other". That quirk gets its own edge case
        # rather than muddying the sport breakdown in the demo.
        as_tcx = index % 2 == 0 and profile.gpx_type != "hiking"
        if not as_tcx and index % 7 == 3:
            strip_heart_rate(activity)  # a watch worn without a strap

        stem = f"{start.date().isoformat()}-{profile.name}"
        seen[stem] = seen.get(stem, 0) + 1
        if seen[stem] > 1:
            stem = f"{stem}-{seen[stem]}"

        if as_tcx:
            files.append((f"{stem}.tcx", to_tcx(activity)))
        else:
            files.append((f"{stem}.gpx", to_gpx(activity)))

    if edge_cases:
        files.extend(build_edge_cases(ending, step_seconds))
    return files


def build_edge_cases(ending: datetime, step_seconds: int) -> list[tuple[str, str]]:
    """Files that exercise what real exports get wrong or leave out.

    Spread across the block rather than bunched at the end, so they do not
    distort the last week of the trend chart.
    """
    rng = random.Random(0xED6E)
    cycling, running, hiking = PROFILES
    cases: list[tuple[str, str]] = []

    no_hr = Activity(cycling, "Ride without a strap", ending - timedelta(days=3), None)
    no_hr.samples = build_samples(rng, cycling, 1800, step_seconds)
    cases.append(("edge-no-heart-rate.gpx", to_gpx(strip_heart_rate(no_hr))))

    untimed = Activity(hiking, "Planned route", ending - timedelta(days=11), None)
    untimed.samples = build_samples(rng, hiking, 3600, step_seconds)
    untimed.omit_timestamps = True
    # A planned route has no clock at all, only metadata.
    gpx = to_gpx(untimed).replace(
        "  <metadata>\n", f"  <metadata>\n    <time>{untimed.timestamp(0)}</time>\n", 1
    )
    cases.append(("edge-no-point-timestamps.gpx", gpx))

    offset = Activity(running, "Late evening run", ending - timedelta(days=18), 120)
    offset.samples = build_samples(rng, running, 2400, step_seconds)
    cases.append(("edge-stated-utc-offset.tcx", to_tcx(offset)))

    as_other = Activity(hiking, "Hike exported to TCX", ending - timedelta(days=31), None)
    as_other.samples = build_samples(rng, hiking, 2400, step_seconds)
    # Real Garmin exports do this: the TCX Sport_t vocabulary has no hiking,
    # so a hike arrives as Sport="Other" and the sport is simply lost.
    cases.append(("edge-tcx-sport-other.tcx", to_tcx(as_other)))

    single = Activity(cycling, "Aborted ride", ending - timedelta(days=25), None)
    single.samples = build_samples(rng, cycling, 0, step_seconds)
    cases.append(("edge-single-point.gpx", to_gpx(single)))

    return cases


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("../demo/activities"))
    parser.add_argument("--weeks", type=int, default=8)
    parser.add_argument("--seed", type=int, default=20260504)
    parser.add_argument(
        "--step-seconds",
        type=int,
        default=30,
        help="Sample interval. 30s keeps committed files small; 1s is realistic.",
    )
    parser.add_argument(
        "--ending",
        default="2026-06-28",
        help='Last day of the block: an ISO date, or "today". Pinned by default so '
        "the committed demo set stays reproducible.",
    )
    parser.add_argument("--no-edge-cases", action="store_true")
    parser.add_argument("--clean", action="store_true", help="Remove existing files first")
    args = parser.parse_args()

    if args.ending == "today":
        ending = datetime.now(UTC)
    else:
        ending = datetime.fromisoformat(args.ending).replace(tzinfo=UTC)
    files = build_activities(
        args.seed, args.weeks, args.step_seconds, ending, not args.no_edge_cases
    )

    args.out.mkdir(parents=True, exist_ok=True)
    if args.clean:
        for existing in sorted(args.out.glob("*.tcx")) + sorted(args.out.glob("*.gpx")):
            existing.unlink()

    total = 0
    for filename, content in files:
        path = args.out / filename
        path.write_text(content, encoding="utf-8")
        total += len(content)
    print(f"{len(files)} files, {total / 1024:.0f} KiB total, in {args.out}")


if __name__ == "__main__":
    main()
