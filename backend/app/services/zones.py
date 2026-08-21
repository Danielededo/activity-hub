"""Heart-rate zones, and the training load that falls out of them.

Two halves, split for the same reason the personal bests are. The histogram —
how many seconds were spent at each heart rate — is computed once, when the
file is stored, because it is the part that needs the samples. Zones are
derived from it at query time, because they depend on a maximum heart rate that
*changes*: one harder session and every previous activity's zones move. Storing
the zones instead of the histogram would freeze them at whatever the maximum
happened to be on the day each file arrived.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Workout
from app.services.analyzer import local_start_date

#: Zone floors as a fraction of maximum heart rate, with Edwards' weighting.
#:
#: Five zones by percentage of maximum is the common split (Garmin, Polar and
#: most training books agree on it). The weights are Edwards' TRIMP: minutes in
#: a zone count once for zone one and five times for zone five. Edwards rather
#: than Banister's because Banister needs a resting heart rate and a
#: sex-specific exponential, neither of which this app asks for; Edwards needs
#: only the zones already being computed.
ZONES: tuple[tuple[int, str, float, int], ...] = (
    (1, "Recovery", 0.50, 1),
    (2, "Endurance", 0.60, 2),
    (3, "Tempo", 0.70, 3),
    (4, "Threshold", 0.80, 4),
    (5, "VO2 max", 0.90, 5),
)

#: The floor of zone one. Time below it is reported separately, never folded in.
LOWEST_FLOOR = ZONES[0][2]

#: A gap longer than this is a pause or a lost signal, not time at that heart
#: rate. Two minutes is well beyond any real sampling interval — a minute is
#: already coarse — so this only ever trims a stop, and a twenty minute coffee
#: break stops arriving as twenty minutes of zone one.
MAX_SAMPLE_GAP_S = 120.0


def heart_rate_seconds(points) -> dict[int, float]:
    """Seconds spent at each whole beat per minute.

    Keyed by bpm rather than by zone, and to the beat rather than to a band:
    the histogram has to outlive the zone boundaries that will be derived from
    it, and a five-beat bucket straddling a boundary would assign its whole
    contents to one side of it.

    Each sample is credited with the time until the next one, which is the only
    interval it can be said to describe. The last sample gets nothing — there is
    no next — which loses one interval out of thousands.
    """
    seconds: dict[int, float] = defaultdict(float)

    timed = [
        point for point in points if point.timestamp is not None and point.heart_rate is not None
    ]
    for current, following in zip(timed, timed[1:], strict=False):
        gap = (following.timestamp - current.timestamp).total_seconds()
        if 0 < gap <= MAX_SAMPLE_GAP_S:
            seconds[int(current.heart_rate)] += gap

    return dict(seconds)


@dataclass(slots=True)
class ZoneBand:
    """One zone, resolved against a particular maximum heart rate."""

    zone: int
    name: str
    min_bpm: int
    #: Inclusive. None for the top zone, which has no ceiling.
    max_bpm: int | None
    weight: int
    seconds: float = 0.0


def zone_bands(max_heart_rate: int) -> list[ZoneBand]:
    """The five zones in beats, for this maximum."""
    floors = [round(fraction * max_heart_rate) for _, _, fraction, _ in ZONES]
    bands = []
    for index, (zone, name, _, weight) in enumerate(ZONES):
        ceiling = floors[index + 1] - 1 if index + 1 < len(floors) else None
        bands.append(
            ZoneBand(zone=zone, name=name, min_bpm=floors[index], max_bpm=ceiling, weight=weight)
        )
    return bands


def distribute(histogram: dict[int, float], max_heart_rate: int) -> tuple[list[ZoneBand], float]:
    """Spread a histogram over the zones. Returns the bands and the time below them."""
    bands = zone_bands(max_heart_rate)
    below = 0.0

    for raw_bpm, raw_seconds in histogram.items():
        bpm = int(raw_bpm)
        seconds = float(raw_seconds)
        if bpm < bands[0].min_bpm:
            # Warming up, waiting at a junction, or standing still. Real time,
            # but not training, and folding it into zone one would inflate the
            # zone people read as easy work.
            below += seconds
            continue
        for band in reversed(bands):
            if bpm >= band.min_bpm:
                band.seconds += seconds
                break

    return bands, below


def edwards_load(bands: list[ZoneBand]) -> float:
    """Edwards' TRIMP: minutes in each zone, weighted by the zone."""
    return sum(band.seconds / 60.0 * band.weight for band in bands)


def resolve_max_heart_rate(db: Session, user_id: int) -> tuple[int | None, str]:
    """The maximum to measure zones against, and where it came from.

    Configured wins; otherwise the highest beat any activity recorded. Observed
    is not tested: a maximum nobody has ever pushed to reads low, which makes
    every zone read high. Saying which one was used is the difference between a
    number somebody can correct and a number they have to trust.
    """
    if settings.max_heart_rate is not None:
        return settings.max_heart_rate, "configured"

    observed = db.execute(
        select(func.max(Workout.max_heart_rate)).where(Workout.user_id == user_id)
    ).scalar()
    return (int(observed), "observed") if observed else (None, "unknown")


def _empty(user_id: int, weeks: int, source: str) -> dict:
    return {
        "user_id": user_id,
        "max_heart_rate": None,
        "max_heart_rate_source": source,
        "weeks": weeks,
        "zones": [],
        "seconds_below_zones": 0.0,
        "total_load": 0.0,
        "weekly": [],
    }


def _band_dict(band: ZoneBand) -> dict:
    return {
        "zone": band.zone,
        "name": band.name,
        "min_bpm": band.min_bpm,
        "max_bpm": band.max_bpm,
        "seconds": band.seconds,
    }


def workout_zones(db: Session, workout: Workout) -> dict:
    """One activity's time in zone, and the load it earned."""
    max_hr, source = resolve_max_heart_rate(db, workout.user_id)
    if max_hr is None or not workout.hr_seconds:
        return {
            "workout_id": workout.id,
            "max_heart_rate": max_hr,
            "max_heart_rate_source": source,
            "zones": [],
            "seconds_below_zones": 0.0,
            "load": 0.0,
        }

    bands, below = distribute(workout.hr_seconds, max_hr)
    return {
        "workout_id": workout.id,
        "max_heart_rate": max_hr,
        "max_heart_rate_source": source,
        "zones": [_band_dict(band) for band in bands],
        "seconds_below_zones": below,
        "load": edwards_load(bands),
    }


def user_zones(db: Session, user_id: int, weeks: int = 12, zone: ZoneInfo | None = None) -> dict:
    """Lifetime time in zone, plus a week-by-week breakdown and daily load.

    The weekly buckets carry their own load, which is what a fitness-and-fatigue
    chart is built from: everything that needs a per-day training impulse can
    read it here rather than recomputing it.
    """
    tz = zone or settings.timezone
    max_hr, source = resolve_max_heart_rate(db, user_id)
    if max_hr is None:
        return _empty(user_id, weeks, source)

    today = datetime.now(tz).date()
    current_week_start = today - timedelta(days=today.weekday())
    first_week_start = current_week_start - timedelta(weeks=weeks - 1)

    rows = db.execute(
        select(Workout.start_time, Workout.utc_offset_minutes, Workout.hr_seconds).where(
            Workout.user_id == user_id, Workout.hr_seconds.is_not(None)
        )
    ).all()

    lifetime = zone_bands(max_hr)
    below_total = 0.0
    weekly: dict = defaultdict(lambda: {"seconds": defaultdict(float), "load": 0.0})

    for start_time, offset_minutes, histogram in rows:
        if not histogram:
            continue
        bands, below = distribute(histogram, max_hr)
        below_total += below
        for band, total in zip(lifetime, bands, strict=True):
            band.seconds += total.seconds

        started = local_start_date(start_time, offset_minutes, tz)
        week_start = started - timedelta(days=started.weekday())
        if week_start < first_week_start or week_start > current_week_start:
            continue
        bucket = weekly[week_start]
        for band in bands:
            bucket["seconds"][band.zone] += band.seconds
        bucket["load"] += edwards_load(bands)

    buckets = []
    for offset in range(weeks):
        week_start = first_week_start + timedelta(weeks=offset)
        entry = weekly.get(week_start)
        buckets.append(
            {
                "week_start": week_start,
                "load": entry["load"] if entry else 0.0,
                "seconds": [
                    {"zone": band.zone, "seconds": entry["seconds"][band.zone] if entry else 0.0}
                    for band in lifetime
                ],
            }
        )

    return {
        "user_id": user_id,
        "max_heart_rate": max_hr,
        "max_heart_rate_source": source,
        "weeks": weeks,
        "zones": [_band_dict(band) for band in lifetime],
        "seconds_below_zones": below_total,
        "total_load": edwards_load(lifetime),
        "weekly": buckets,
    }


__all__ = [
    "MAX_SAMPLE_GAP_S",
    "ZONES",
    "ZoneBand",
    "distribute",
    "edwards_load",
    "heart_rate_seconds",
    "resolve_max_heart_rate",
    "user_zones",
    "workout_zones",
    "zone_bands",
]
