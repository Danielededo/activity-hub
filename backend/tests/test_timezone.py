"""Local-time handling: stated offsets, and local week bucketing."""

import hashlib
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.models import User, Workout
from app.services.analyzer import local_start_date, weekly_summary
from app.services.parsers import GpxParser, TcxParser

ROME = ZoneInfo("Europe/Rome")

GPX_WITH_OFFSET = b"""<?xml version="1.0" encoding="UTF-8"?>
<gpx creator="komoot" xmlns="http://www.topografix.com/GPX/1/1">
  <trk><name>Evening Ride</name><type>cycling</type><trkseg>
    <trkpt lat="45.07" lon="7.68"><ele>240</ele><time>2026-05-04T08:30:00+02:00</time></trkpt>
    <trkpt lat="45.08" lon="7.69"><ele>250</ele><time>2026-05-04T09:00:00+02:00</time></trkpt>
  </trkseg></trk>
</gpx>
"""

TCX_WITH_OFFSET = b"""<?xml version="1.0" encoding="UTF-8"?>
<TrainingCenterDatabase xmlns="http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2">
  <Activities><Activity Sport="Running">
    <Id>2026-05-04T08:30:00+02:00</Id>
    <Lap StartTime="2026-05-04T08:30:00+02:00">
      <TotalTimeSeconds>1800</TotalTimeSeconds><DistanceMeters>5000</DistanceMeters>
    </Lap>
  </Activity></Activities>
</TrainingCenterDatabase>
"""


# -- parsing -------------------------------------------------------------


def test_gpx_keeps_a_stated_offset():
    workout = GpxParser().parse(GPX_WITH_OFFSET)

    assert workout.utc_offset_minutes == 120
    # The instant is still normalised to UTC.
    assert workout.start_time == datetime(2026, 5, 4, 6, 30, tzinfo=UTC)


def test_tcx_keeps_a_stated_offset():
    assert TcxParser().parse(TCX_WITH_OFFSET).utc_offset_minutes == 120


def test_a_z_timestamp_states_no_offset(sample_gpx, sample_tcx):
    """'Z' fixes the instant but says nothing about local time."""
    assert GpxParser().parse(sample_gpx).utc_offset_minutes is None
    assert TcxParser().parse(sample_tcx).utc_offset_minutes is None


# -- local dates ---------------------------------------------------------


def test_local_date_uses_the_stated_offset():
    """22:30 UTC on a Sunday is already Monday in Rome."""
    moment = datetime(2026, 5, 3, 22, 30, tzinfo=UTC)  # a Sunday

    assert local_start_date(moment, 120, ZoneInfo("UTC")) == moment.date() + timedelta(days=1)


def test_local_date_falls_back_to_the_configured_zone():
    moment = datetime(2026, 5, 3, 22, 30, tzinfo=UTC)

    assert local_start_date(moment, None, ROME).isoformat() == "2026-05-04"
    assert local_start_date(moment, None, ZoneInfo("UTC")).isoformat() == "2026-05-03"


def test_local_date_treats_a_naive_timestamp_as_utc():
    """SQLite hands back naive datetimes; they must not be read as local."""
    naive = datetime(2026, 5, 3, 22, 30)

    assert local_start_date(naive, None, ZoneInfo("UTC")).isoformat() == "2026-05-03"


# -- weekly bucketing ----------------------------------------------------


@pytest.fixture
def rider(db_session):
    user = User(username="rider", email="rider@example.com")
    db_session.add(user)
    db_session.flush()
    return user


def add_workout(db_session, user_id, start_time, offset):
    db_session.add(
        Workout(
            user_id=user_id,
            source="komoot",
            name="Test",
            sport_type="cycling",
            start_time=start_time,
            utc_offset_minutes=offset,
            total_distance=10_000.0,
            total_time=3_600.0,
            total_elevation_gain=100.0,
            total_elevation_loss=100.0,
            file_format="gpx",
            file_hash=hashlib.sha256(f"{user_id}:{start_time}:{offset}".encode()).hexdigest(),
            raw_data={},
        )
    )
    db_session.commit()


def test_an_activity_after_local_midnight_lands_in_the_new_week(db_session, rider):
    """00:30 Monday local is 22:30 Sunday UTC: bucketing by UTC loses a week."""
    today = datetime.now(UTC).date()
    monday = today - timedelta(days=today.weekday())
    # 00:30 on Monday at +02:00 == 22:30 on the preceding Sunday, UTC.
    started = datetime.combine(monday, datetime.min.time(), tzinfo=UTC) - timedelta(minutes=90)
    add_workout(db_session, rider.id, started, 120)

    buckets = {b["week_start"]: b for b in weekly_summary(db_session, rider.id, weeks=4)["buckets"]}

    assert buckets[monday]["workout_count"] == 1
    assert buckets[monday - timedelta(days=7)]["workout_count"] == 0


def test_without_an_offset_the_configured_zone_decides(db_session, rider):
    today = datetime.now(UTC).date()
    monday = today - timedelta(days=today.weekday())
    started = datetime.combine(monday, datetime.min.time(), tzinfo=UTC) - timedelta(minutes=90)
    add_workout(db_session, rider.id, started, None)

    in_rome = weekly_summary(db_session, rider.id, weeks=4, zone=ROME)["buckets"]
    in_utc = weekly_summary(db_session, rider.id, weeks=4, zone=ZoneInfo("UTC"))["buckets"]

    assert {b["week_start"]: b["workout_count"] for b in in_rome}[monday] == 1
    assert {b["week_start"]: b["workout_count"] for b in in_utc}[monday] == 0


def test_activities_outside_the_window_are_not_counted(db_session, rider):
    """The query is bounded to the window, so old history cannot leak in."""
    add_workout(db_session, rider.id, datetime(2020, 1, 1, 12, 0, tzinfo=UTC), None)

    result = weekly_summary(db_session, rider.id, weeks=4)

    assert sum(b["workout_count"] for b in result["buckets"]) == 0


# -- configuration -------------------------------------------------------


def test_an_unknown_timezone_is_rejected_at_boot():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, database_url="sqlite://", display_timezone="Mars/Olympus")


def test_a_known_timezone_is_accepted():
    parsed = Settings(_env_file=None, database_url="sqlite://", display_timezone="Europe/Rome")

    assert parsed.timezone == ROME
