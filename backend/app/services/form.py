"""Fitness, fatigue and form: exponential averages of daily training load.

Three numbers over one series of daily training impulses:

* **fitness** — the 42-day exponential average. What the training of the last
  six weeks has built, decaying slowly.
* **fatigue** — the 7-day exponential average. What this week has cost, decaying
  fast.
* **form** — fitness minus fatigue. Positive means rested for what has been
  built; negative means buried under recent work.

The daily impulse is Edwards' TRIMP, the same figure the zone breakdown
reports, so a week's load here and a week's load there are the same number.

Derived on request rather than stored, for the same reason zones are: the load
of an activity depends on a maximum heart rate that moves, and a stored series
would describe the athlete you used to be.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from math import exp
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Workout
from app.services.analyzer import local_start_date
from app.services.zones import distribute, edwards_load, resolve_max_heart_rate

#: Time constants in days: six weeks for fitness, one for fatigue.
#:
#: The pair Coggan popularised and every training tool since has used. They are
#: not arbitrary — six weeks is roughly how long an adaptation takes to bank and
#: a week is roughly how long the tiredness from a session lasts — but they are
#: also not measured for *you*, which is why the chart is read as a shape rather
#: than as five significant figures.
FITNESS_DAYS = 42
FATIGUE_DAYS = 7


def decay(time_constant: int) -> float:
    """The fraction of the gap to today's load that one day closes.

    The exponential form, `1 - e^(-1/τ)`, not the `1/τ` approximation that
    looks the same at a glance. At τ=7 they differ by 7%, which compounds over
    a season into a fatigue line that is visibly wrong.
    """
    return 1.0 - exp(-1.0 / time_constant)


@dataclass(slots=True)
class DayPoint:
    """One calendar day of the series."""

    day: date
    load: float
    fitness: float
    fatigue: float
    form: float


def _daily_loads(
    db: Session, user_id: int, max_heart_rate: int, zone: ZoneInfo
) -> dict[date, float]:
    """Edwards' TRIMP per local calendar day, for every activity that has one.

    Two activities on the same day add up: the body does not know they were two
    files.
    """
    rows = db.execute(
        select(Workout.start_time, Workout.utc_offset_minutes, Workout.hr_seconds).where(
            Workout.user_id == user_id, Workout.hr_seconds.is_not(None)
        )
    ).all()

    loads: dict[date, float] = defaultdict(float)
    for start_time, offset_minutes, histogram in rows:
        if not histogram:
            continue
        bands, _ = distribute(histogram, max_heart_rate)
        day = local_start_date(start_time, offset_minutes, zone)
        loads[day] += edwards_load(bands)
    return dict(loads)


def _untracked(db: Session, user_id: int, since: date, zone: ZoneInfo) -> int:
    """Activities in the window that earned no load at all.

    Worth counting rather than ignoring. An activity with nothing to distribute
    contributes no load, so it does not merely go missing from the chart — it
    reads as a rest day, which *lowers* fatigue and lifts form. A hard strapless
    week comes out looking like a taper.

    Both empty cases count, because both read the same way on the chart: `{}` is
    an activity whose histogram was computed and found no heart rate, and NULL
    is one uploaded before the histogram existed. Testing for NULL alone missed
    every strapless activity there is — the storage layer writes the empty dict,
    which is the whole point of the null-versus-empty distinction — so the
    caveat this count exists to raise could never fire.
    """
    rows = db.execute(
        select(Workout.start_time, Workout.utc_offset_minutes, Workout.hr_seconds).where(
            Workout.user_id == user_id
        )
    ).all()
    return sum(
        1
        for start_time, offset, histogram in rows
        if not histogram and local_start_date(start_time, offset, zone) >= since
    )


def build_series(loads: dict[date, float], first: date, last: date) -> list[DayPoint]:
    """Walk every calendar day from `first` to `last`, stepping both averages.

    Every day, not every activity. A rest week has to *lower* fitness and
    fatigue, and iterating over activities would skip exactly the days where
    that happens — the series would rise at each session and never fall between
    them.

    Form is yesterday's fitness minus yesterday's fatigue, which is the
    convention every training tool uses and the one that answers the question
    actually being asked: how fresh am I *before* today's session. Using today's
    figures would fold the session into its own readiness score, so a hard
    morning would report that you were tired before you started it.
    """
    fitness_step = decay(FITNESS_DAYS)
    fatigue_step = decay(FATIGUE_DAYS)

    fitness = 0.0
    fatigue = 0.0
    series: list[DayPoint] = []

    day = first
    while day <= last:
        form = fitness - fatigue
        load = loads.get(day, 0.0)
        fitness += (load - fitness) * fitness_step
        fatigue += (load - fatigue) * fatigue_step
        series.append(DayPoint(day=day, load=load, fitness=fitness, fatigue=fatigue, form=form))
        day += timedelta(days=1)

    return series


def _empty(user_id: int, days: int, max_hr: int | None, source: str) -> dict:
    return {
        "user_id": user_id,
        "max_heart_rate": max_hr,
        "max_heart_rate_source": source,
        "days": days,
        "series": [],
        "warmup_days": 0,
        "untracked_activities": 0,
    }


def user_form(db: Session, user_id: int, days: int = 90, zone: ZoneInfo | None = None) -> dict:
    """The last `days` days of fitness, fatigue and form.

    The averages are walked from the *first activity ever*, not from the start
    of the window, and only the window is returned. Starting at the window would
    start both averages at zero, so the first six weeks of any chart would show
    fitness climbing out of nothing — an artefact of where the chart begins
    rather than anything that happened. `warmup_days` says how much history ran
    in before the window, so a genuinely cold start is still visible as one.
    """
    tz = zone or settings.timezone
    max_hr, source = resolve_max_heart_rate(db, user_id)
    if max_hr is None:
        return _empty(user_id, days, max_hr, source)

    loads = _daily_loads(db, user_id, max_hr, tz)
    if not loads:
        return _empty(user_id, days, max_hr, source)

    today = datetime.now(tz).date()
    first_activity = min(loads)
    # An activity dated after today — a file with a clock set wrong — must not
    # shorten the series to nothing.
    last = max(today, max(loads))
    window_start = last - timedelta(days=days - 1)

    series = build_series(loads, min(first_activity, window_start), last)
    windowed = [point for point in series if point.day >= window_start]

    return {
        "user_id": user_id,
        "max_heart_rate": max_hr,
        "max_heart_rate_source": source,
        "days": days,
        "series": [
            {
                "day": point.day,
                "load": point.load,
                "fitness": point.fitness,
                "fatigue": point.fatigue,
                "form": point.form,
            }
            for point in windowed
        ],
        "warmup_days": max(0, (window_start - first_activity).days),
        "untracked_activities": _untracked(db, user_id, window_start, tz),
    }


__all__ = [
    "FATIGUE_DAYS",
    "FITNESS_DAYS",
    "DayPoint",
    "build_series",
    "decay",
    "user_form",
]
