"""Fitness, fatigue and form: the daily walk, and the series over it."""

import hashlib
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.config import settings
from app.models import User, Workout
from app.services.form import FATIGUE_DAYS, FITNESS_DAYS, build_series, decay, user_form

#: 60 minutes at 150 bpm against a maximum of 200 is an hour in zone three,
#: which Edwards weights three times: a load of exactly 180.
HOUR_IN_ZONE_THREE = {"150": 3_600.0}
HOUR_LOAD = 180.0
MAX_HR = 200


def day(offset: int, *, today=None):
    """A date `offset` days before today, in the configured zone."""
    base = today or datetime.now(settings.timezone).date()
    return base - timedelta(days=offset)


# -- the decay constant --------------------------------------------------


def test_the_decay_is_exponential_not_the_reciprocal():
    # 1 - e^(-1/7) is 0.1331, not 1/7 = 0.1429. They look interchangeable and
    # are 7% apart, which compounds over a season into a visibly wrong line.
    assert decay(FATIGUE_DAYS) == pytest.approx(0.133_122, abs=1e-6)
    assert decay(FITNESS_DAYS) == pytest.approx(0.023_528, abs=1e-6)
    assert decay(FATIGUE_DAYS) < 1 / FATIGUE_DAYS


def test_fatigue_moves_further_than_fitness_on_the_same_day():
    assert decay(FATIGUE_DAYS) > decay(FITNESS_DAYS)


# -- the daily walk ------------------------------------------------------


def test_every_calendar_day_gets_an_entry_including_the_empty_ones():
    first = datetime(2026, 6, 1).date()
    series = build_series({first: HOUR_LOAD}, first, first + timedelta(days=9))

    assert len(series) == 10
    assert [point.day for point in series] == [first + timedelta(days=n) for n in range(10)]
    assert [point.load for point in series][1:] == [0.0] * 9


def test_a_rest_day_lowers_both_averages():
    """The property that iterating over activities instead of days would break.

    Walking activities would step the averages only on days that had one, so a
    rest week would hold its level instead of decaying — the series would rise
    at every session and never fall between them.
    """
    first = datetime(2026, 6, 1).date()
    series = build_series({first: HOUR_LOAD}, first, first + timedelta(days=3))

    fitness = [point.fitness for point in series]
    fatigue = [point.fatigue for point in series]
    assert fitness[1] < fitness[0]
    assert fatigue[1] < fatigue[0]
    assert fitness == sorted(fitness, reverse=True)
    assert fatigue == sorted(fatigue, reverse=True)


def test_form_reports_yesterday_not_today():
    """Freshness *before* the session, which is the question being asked.

    Using today's own figures would fold a session into its own readiness
    score, so a hard morning would report that you were already tired when you
    set out.
    """
    first = datetime(2026, 6, 1).date()
    series = build_series({first: HOUR_LOAD}, first, first + timedelta(days=2))

    # Day one: nothing had happened yet, so form is neutral even though the day
    # itself was hard.
    assert series[0].form == pytest.approx(0.0)
    assert series[0].load == HOUR_LOAD
    # Day two carries yesterday's cost.
    assert series[1].form < 0


def test_a_long_rest_brings_form_back_up_and_the_averages_down():
    first = datetime(2026, 1, 1).date()
    series = build_series({first: HOUR_LOAD}, first, first + timedelta(days=120))
    last = series[-1]

    assert last.fatigue < 0.01
    assert last.fitness < HOUR_LOAD * 0.1
    # Fatigue decays six times faster, so a long rest leaves fitness above it
    # and form positive — the taper.
    assert last.form > 0
    assert last.fitness > last.fatigue


def test_a_steady_block_settles_with_fatigue_near_fitness():
    first = datetime(2026, 1, 1).date()
    loads = {first + timedelta(days=n): 60.0 for n in range(200)}
    series = build_series(loads, first, first + timedelta(days=199))
    last = series[-1]

    # Both averages converge on the daily load, so form settles near zero:
    # training exactly as much as you are used to is neither a build nor a rest.
    assert last.fitness == pytest.approx(60.0, rel=0.05)
    assert last.fatigue == pytest.approx(60.0, rel=0.01)
    assert abs(last.form) < 5


# -- the series over stored activities ------------------------------------


def add_workout(db_session, user_id, *, start_time, hr_seconds=None, max_hr=MAX_HR, offset=None):
    workout = Workout(
        user_id=user_id,
        source="strava",
        name="Session",
        sport_type="running",
        start_time=start_time,
        utc_offset_minutes=offset,
        total_distance=10_000.0,
        total_time=3_600.0,
        total_elevation_gain=100.0,
        total_elevation_loss=100.0,
        avg_heart_rate=150,
        max_heart_rate=max_hr,
        file_format="gpx",
        file_hash=hashlib.sha256(f"{user_id}:{start_time}:{hr_seconds}".encode()).hexdigest(),
        raw_data={},
        hr_seconds=hr_seconds,
    )
    db_session.add(workout)
    db_session.commit()
    return workout


@pytest.fixture
def rider(db_session):
    rider = User(first_name="Rider")
    db_session.add(rider)
    db_session.commit()
    return rider


def at(days_ago: int, hour: int = 9) -> datetime:
    """A UTC moment `days_ago` days back, mid-morning so no zone shifts the date."""
    return datetime.combine(day(days_ago), datetime.min.time(), tzinfo=UTC).replace(hour=hour)


def test_two_sessions_on_one_day_add_up(db_session, rider):
    add_workout(db_session, rider.id, start_time=at(1, hour=7), hr_seconds=HOUR_IN_ZONE_THREE)
    add_workout(db_session, rider.id, start_time=at(1, hour=18), hr_seconds=HOUR_IN_ZONE_THREE)

    result = user_form(db_session, rider.id, days=7)
    yesterday = next(point for point in result["series"] if point["day"] == day(1))

    # The body does not know they were two files.
    assert yesterday["load"] == pytest.approx(2 * HOUR_LOAD)


def test_the_window_starts_warm_when_there_is_history_behind_it(db_session, rider):
    for days_ago in range(30, 60):
        add_workout(db_session, rider.id, start_time=at(days_ago), hr_seconds=HOUR_IN_ZONE_THREE)

    result = user_form(db_session, rider.id, days=7)
    first_day = result["series"][0]

    # Nothing inside the window, yet fitness is carried into it. Starting the
    # walk at the window would show it climbing out of a zero that only means
    # "this is where the chart begins".
    assert first_day["load"] == 0.0
    assert first_day["fitness"] > 10
    assert result["warmup_days"] > 40


def test_a_genuinely_cold_start_says_so(db_session, rider):
    add_workout(db_session, rider.id, start_time=at(2), hr_seconds=HOUR_IN_ZONE_THREE)

    result = user_form(db_session, rider.id, days=90)

    assert result["warmup_days"] == 0
    assert result["series"][0]["fitness"] == pytest.approx(0.0)


def test_the_series_runs_to_today_even_after_months_off(db_session, rider):
    add_workout(db_session, rider.id, start_time=at(200), hr_seconds=HOUR_IN_ZONE_THREE)

    result = user_form(db_session, rider.id, days=30)

    assert len(result["series"]) == 30
    assert result["series"][-1]["day"] == day(0)
    # The decay has to be visible: the point of the chart is that fitness falls
    # when you stop.
    assert result["series"][-1]["fitness"] < 1


def test_activities_with_no_strap_are_counted_not_hidden(db_session, rider):
    """The empty histogram is the case that matters, and it is the common one.

    A strapless activity is stored with `{}` — computed, nothing to record — not
    with NULL. Counting NULL alone found none of them, so the caveat this figure
    exists to raise could never fire on a real library.
    """
    add_workout(db_session, rider.id, start_time=at(1), hr_seconds=HOUR_IN_ZONE_THREE)
    add_workout(db_session, rider.id, start_time=at(2), hr_seconds={})
    add_workout(db_session, rider.id, start_time=at(3), hr_seconds={})
    # NULL means "never computed", which reads on the chart exactly the same
    # way, so it counts too.
    add_workout(db_session, rider.id, start_time=at(4), hr_seconds=None)
    # Outside the window, so not this window's problem.
    add_workout(db_session, rider.id, start_time=at(40), hr_seconds={})

    result = user_form(db_session, rider.id, days=7)

    assert result["untracked_activities"] == 3


def test_an_empty_histogram_contributes_no_load(db_session, rider):
    add_workout(db_session, rider.id, start_time=at(1), hr_seconds={})

    result = user_form(db_session, rider.id, days=7)

    assert result["series"] == []


def test_no_heart_rate_anywhere_is_an_empty_series(db_session, rider):
    add_workout(db_session, rider.id, start_time=at(1), hr_seconds=None, max_hr=None)

    result = user_form(db_session, rider.id, days=30)

    assert result["series"] == []
    assert result["max_heart_rate"] is None
    assert result["max_heart_rate_source"] == "unknown"


def test_a_maximum_but_no_histogram_is_still_an_empty_series(db_session, rider):
    # A library uploaded before the histogram existed: the maximum is known
    # from the activity's own summary, but nothing can be distributed.
    add_workout(db_session, rider.id, start_time=at(1), hr_seconds=None)

    result = user_form(db_session, rider.id, days=30)

    assert result["series"] == []
    assert result["max_heart_rate"] == MAX_HR


def test_the_day_follows_the_activity_stated_offset(db_session, rider):
    """A late-evening session belongs to its own local day, not to UTC's."""
    late = datetime.combine(day(1), datetime.min.time(), tzinfo=UTC).replace(hour=23, minute=30)
    add_workout(db_session, rider.id, start_time=late, hr_seconds=HOUR_IN_ZONE_THREE, offset=120)

    result = user_form(db_session, rider.id, days=7)
    loaded = [point["day"] for point in result["series"] if point["load"] > 0]

    # 23:30 UTC plus two hours is 01:30 the next day where the rider was.
    assert loaded == [day(0)]


def test_another_riders_training_is_not_counted(db_session, rider):
    stranger = User(first_name="Mallory")
    db_session.add(stranger)
    db_session.commit()
    add_workout(db_session, stranger.id, start_time=at(1), hr_seconds=HOUR_IN_ZONE_THREE)

    assert user_form(db_session, rider.id, days=7)["series"] == []


# -- through the API ------------------------------------------------------


def test_the_endpoint_reports_the_series(client, user, db_session):
    add_workout(db_session, user["id"], start_time=at(1), hr_seconds=HOUR_IN_ZONE_THREE)

    response = client.get(f"/api/analysis/{user['id']}/form", params={"days": 14})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["days"] == 14
    assert len(body["series"]) == 14
    assert set(body["series"][0]) == {"day", "load", "fitness", "fatigue", "form"}
    assert body["max_heart_rate_source"] == "observed"


def test_the_endpoint_refuses_a_window_it_cannot_serve(client, user):
    assert client.get(f"/api/analysis/{user['id']}/form", params={"days": 0}).status_code == 422
    assert client.get(f"/api/analysis/{user['id']}/form", params={"days": 5_000}).status_code == 422


def test_the_endpoint_does_not_invent_a_user(client):
    assert client.get("/api/analysis/999/form").status_code == 404


def test_the_configured_maximum_reaches_the_series(db_session, rider, monkeypatch):
    add_workout(db_session, rider.id, start_time=at(1), hr_seconds=HOUR_IN_ZONE_THREE)
    monkeypatch.setattr(settings, "max_heart_rate", 300)

    result = user_form(db_session, rider.id, days=7)
    yesterday = next(point for point in result["series"] if point["day"] == day(1))

    # The same hour at 150 bpm is zone three against a maximum of 200 and zone
    # one against 300, so it is worth 180 there and 60 here. The maximum moves
    # every load with it, which is why none of this is stored.
    assert result["max_heart_rate_source"] == "configured"
    assert yesterday["load"] == pytest.approx(60.0)
    assert yesterday["load"] < HOUR_LOAD


def test_the_zone_used_for_bucketing_is_the_one_passed_in(db_session, rider):
    """The window's days are local days, resolved in the zone given."""
    midway = ZoneInfo("Pacific/Midway")  # UTC-11
    early = datetime.now(UTC).replace(hour=6, minute=0) - timedelta(days=1)
    add_workout(db_session, rider.id, start_time=early, hr_seconds=HOUR_IN_ZONE_THREE)

    result = user_form(db_session, rider.id, days=7, zone=midway)
    loaded = [point["day"] for point in result["series"] if point["load"] > 0]

    assert loaded == [early.astimezone(midway).date()]
