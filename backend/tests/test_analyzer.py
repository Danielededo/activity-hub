"""Metric derivation and aggregate reporting."""

import hashlib
from datetime import UTC, datetime, timedelta

import pytest

from app.models import User, Workout
from app.services.analyzer import (
    ELEVATION_NOISE_THRESHOLD_M,
    compute_metrics,
    elevation_change,
    haversine_distance,
    track_distance,
    user_summary,
    weekly_summary,
)
from app.services.parsers import GpxParser, TcxParser
from app.services.parsers.base_parser import ParsedTrackPoint, ParsedWorkout


def point(sequence: int, **kwargs) -> ParsedTrackPoint:
    return ParsedTrackPoint(sequence=sequence, **kwargs)


def test_haversine_against_known_distance():
    # Turin to Milan, roughly 126 km.
    metres = haversine_distance(45.0703, 7.6869, 45.4642, 9.1900)
    assert metres == pytest.approx(126_000, rel=0.02)


def test_haversine_is_zero_for_identical_points():
    assert haversine_distance(45.0, 7.0, 45.0, 7.0) == pytest.approx(0.0)


def test_track_distance_sums_consecutive_hops():
    points = [
        point(0, latitude=45.000, longitude=7.000),
        point(1, latitude=45.001, longitude=7.000),
        point(2, latitude=45.002, longitude=7.000),
    ]
    # One degree of latitude is ~111 km, so 0.001 deg is ~111 m per hop.
    assert track_distance(points) == pytest.approx(222, rel=0.01)


def test_track_distance_ignores_points_without_position():
    points = [
        point(0, latitude=45.000, longitude=7.000),
        point(1, heart_rate=150),
        point(2, latitude=45.001, longitude=7.000),
    ]
    assert track_distance(points) == pytest.approx(111, rel=0.01)


def test_track_distance_drops_implausible_jumps():
    """A dropped GPS signal should not add hundreds of kilometres."""
    points = [
        point(0, latitude=45.000, longitude=7.000),
        point(1, latitude=46.000, longitude=8.000),  # ~130 km teleport
        point(2, latitude=46.001, longitude=8.000),
    ]
    assert track_distance(points) == pytest.approx(111, rel=0.01)


def test_elevation_change_splits_gain_and_loss():
    points = [
        point(0, elevation=100.0),
        point(1, elevation=150.0),
        point(2, elevation=120.0),
        point(3, elevation=140.0),
    ]
    gain, loss = elevation_change(points)

    assert gain == pytest.approx(70.0)
    assert loss == pytest.approx(30.0)


def test_elevation_change_filters_gps_jitter():
    jitter = ELEVATION_NOISE_THRESHOLD_M / 2
    points = [point(index, elevation=100.0 + (jitter if index % 2 else 0)) for index in range(50)]
    gain, loss = elevation_change(points)

    assert gain == 0.0
    assert loss == 0.0


def test_elevation_change_handles_missing_samples():
    points = [point(0, elevation=None), point(1, elevation=200.0), point(2, elevation=None)]
    assert elevation_change(points) == (0.0, 0.0)


def test_compute_metrics_prefers_file_totals(sample_tcx):
    """Garmin measures distance better than integrating GPS positions."""
    parsed = TcxParser().parse(sample_tcx)
    metrics = compute_metrics(parsed)

    assert metrics.total_distance == pytest.approx(12000.0)
    assert metrics.total_time == pytest.approx(1800.0)
    assert metrics.avg_heart_rate == 142
    assert metrics.max_heart_rate == 171
    # Cadence is not stated at lap level, so it is averaged over the samples.
    assert metrics.avg_cadence == round((80 + 90 + 94 + 85) / 4)


def test_compute_metrics_derives_gpx_distance(sample_gpx):
    parsed = GpxParser().parse(sample_gpx)
    metrics = compute_metrics(parsed)

    assert metrics.total_distance > 0
    assert metrics.total_time == pytest.approx(900.0)
    assert metrics.avg_heart_rate == round((128 + 152 + 160) / 3)
    assert metrics.max_heart_rate == 160
    assert metrics.total_elevation_gain == pytest.approx(20.0)
    assert metrics.total_elevation_loss == pytest.approx(15.0)


def test_compute_metrics_on_an_empty_track():
    parsed = ParsedWorkout(
        source="gpx",
        file_format="gpx",
        name="Empty",
        sport_type="other",
        start_time=datetime(2026, 5, 1, tzinfo=UTC),
    )
    metrics = compute_metrics(parsed)

    assert metrics.total_distance == 0.0
    assert metrics.total_time == 0.0
    assert metrics.avg_heart_rate is None
    assert metrics.avg_cadence is None


# -- aggregate reporting ------------------------------------------------


def make_workout(user_id: int, start_time: datetime, **kwargs) -> Workout:
    defaults = {
        "source": "garmin",
        "name": "Test",
        "sport_type": "cycling",
        # Unique per fixture row: the real hash comes from the uploaded bytes.
        "file_hash": hashlib.sha256(f"{user_id}:{start_time}:{kwargs}".encode()).hexdigest(),
        "total_distance": 10_000.0,
        "total_time": 3600.0,
        "total_elevation_gain": 100.0,
        "total_elevation_loss": 100.0,
        "file_format": "tcx",
        "raw_data": {},
    }
    return Workout(user_id=user_id, start_time=start_time, **{**defaults, **kwargs})


@pytest.fixture
def populated(db_session):
    user = User(first_name="Rider")
    db_session.add(user)
    db_session.flush()

    now = datetime.now(UTC)
    db_session.add_all(
        [
            make_workout(user.id, now - timedelta(days=1), avg_heart_rate=140, max_heart_rate=170),
            make_workout(
                user.id,
                now - timedelta(days=8),
                sport_type="running",
                total_distance=8_000.0,
                total_time=2_400.0,
                avg_heart_rate=150,
                max_heart_rate=182,
            ),
            make_workout(
                user.id, now - timedelta(days=9), total_distance=42_000.0, total_time=7_200.0
            ),
        ]
    )
    db_session.commit()
    return user


def test_user_summary_totals(db_session, populated):
    summary = user_summary(db_session, populated.id)

    assert summary["workout_count"] == 3
    assert summary["total_distance"] == pytest.approx(60_000.0)
    assert summary["total_time"] == pytest.approx(13_200.0)
    assert summary["total_elevation_gain"] == pytest.approx(300.0)
    assert summary["avg_distance"] == pytest.approx(20_000.0)
    assert summary["avg_duration"] == pytest.approx(4_400.0)
    assert summary["avg_heart_rate"] == pytest.approx(145.0)  # nulls excluded
    assert summary["max_heart_rate"] == 182


def test_user_summary_breaks_down_by_sport(db_session, populated):
    summary = user_summary(db_session, populated.id)
    by_sport = {row["sport_type"]: row for row in summary["by_sport"]}

    assert by_sport["cycling"]["workout_count"] == 2
    assert by_sport["cycling"]["total_distance"] == pytest.approx(52_000.0)
    assert by_sport["running"]["workout_count"] == 1


def test_user_summary_points_at_the_longest_workout(db_session, populated):
    summary = user_summary(db_session, populated.id)
    longest = db_session.get(Workout, summary["longest_workout_id"])

    assert longest.total_distance == pytest.approx(42_000.0)


def test_user_summary_for_a_user_without_workouts(db_session):
    user = User(first_name="Newcomer")
    db_session.add(user)
    db_session.commit()

    summary = user_summary(db_session, user.id)

    assert summary["workout_count"] == 0
    assert summary["total_distance"] == 0.0
    assert summary["avg_distance"] == 0.0
    assert summary["avg_heart_rate"] is None
    assert summary["longest_workout_id"] is None
    assert summary["by_sport"] == []


def test_weekly_summary_zero_fills_quiet_weeks(db_session, populated):
    result = weekly_summary(db_session, populated.id, weeks=4)

    assert result["weeks"] == 4
    assert len(result["buckets"]) == 4
    # Buckets run oldest to newest, one per ISO week.
    assert [bucket["week_start"] for bucket in result["buckets"]] == sorted(
        bucket["week_start"] for bucket in result["buckets"]
    )
    assert sum(bucket["workout_count"] for bucket in result["buckets"]) == 3
    assert result["buckets"][0]["workout_count"] == 0


def test_weekly_summary_excludes_older_weeks(db_session, populated):
    result = weekly_summary(db_session, populated.id, weeks=1)

    # Only the most recent week is in range: the two 8-9 day old rides drop out.
    assert sum(bucket["workout_count"] for bucket in result["buckets"]) <= 1
