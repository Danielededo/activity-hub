"""The track-point series behind a route map or a heart-rate trace."""

import hashlib
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import insert

from app.config import settings
from app.models import TrackPoint, User, Workout


def make_workout(db_session, user_id: int, point_count: int) -> int:
    workout = Workout(
        user_id=user_id,
        source="garmin",
        name="Long ride",
        sport_type="cycling",
        start_time=datetime(2026, 6, 1, 6, 0, tzinfo=UTC),
        total_distance=40_000.0,
        total_time=7_200.0,
        total_elevation_gain=500.0,
        total_elevation_loss=500.0,
        file_format="tcx",
        file_hash=hashlib.sha256(f"{user_id}:{point_count}".encode()).hexdigest(),
        raw_data={},
    )
    db_session.add(workout)
    db_session.flush()

    if point_count:
        db_session.execute(
            insert(TrackPoint),
            [
                {
                    "workout_id": workout.id,
                    "sequence": index,
                    "timestamp": workout.start_time + timedelta(seconds=index),
                    "latitude": 45.07 + index * 1e-5,
                    "longitude": 7.68 + index * 1e-5,
                    "elevation": 240.0 + index % 50,
                    "heart_rate": 120 + index % 40,
                    "cadence": 80 + index % 10,
                }
                for index in range(point_count)
            ],
        )
    db_session.commit()
    return workout.id


@pytest.fixture
def rider(db_session):
    user = User(first_name="Rider")
    db_session.add(user)
    db_session.commit()
    return user


def series(client, workout_id: int, user_id: int, **params):
    query = "&".join(f"{k}={v}" for k, v in params.items())
    suffix = f"&{query}" if query else ""
    return client.get(f"/api/workouts/{workout_id}/track-points?user_id={user_id}{suffix}")


# -- the whole track -----------------------------------------------------


def test_a_short_track_comes_back_whole(client, db_session, rider):
    workout_id = make_workout(db_session, rider.id, 120)

    body = series(client, workout_id, rider.id).json()

    assert body["total"] == 120
    assert body["returned"] == 120
    assert body["stride"] == 1
    assert len(body["items"]) == 120


def test_samples_carry_what_a_map_and_a_trace_need(client, db_session, rider):
    workout_id = make_workout(db_session, rider.id, 10)

    first = series(client, workout_id, rider.id).json()["items"][0]

    assert first["latitude"] is not None and first["longitude"] is not None
    assert first["heart_rate"] is not None
    assert first["elevation"] is not None
    assert first["timestamp"] is not None
    assert first["sequence"] == 0


def test_samples_are_ordered_by_sequence(client, db_session, rider):
    workout_id = make_workout(db_session, rider.id, 300)

    sequences = [item["sequence"] for item in series(client, workout_id, rider.id).json()["items"]]

    assert sequences == sorted(sequences)


# -- downsampling --------------------------------------------------------


def test_a_long_track_is_downsampled(client, db_session, rider):
    workout_id = make_workout(db_session, rider.id, 3_600)

    body = series(client, workout_id, rider.id, max_points=500).json()

    # 3600 samples into a budget of 500 gives a stride of 8: every eighth
    # sample is 450 of them, plus the final one, which 8 does not divide.
    assert body["total"] == 3_600
    assert body["stride"] == 8
    assert body["returned"] == 451


def test_the_budget_is_a_ceiling_not_a_target(client, db_session, rider):
    """A uniform stride cannot land on the budget exactly.

    Rounding the stride down would hit it more closely but overshoot the cap,
    which is the one thing it must not do — so undershooting is correct.
    """
    workout_id = make_workout(db_session, rider.id, 3_600)

    for budget in (100, 250, 500, 1_000, 2_000):
        body = series(client, workout_id, rider.id, max_points=budget).json()
        assert body["returned"] <= budget + 1, budget
        assert body["returned"] > budget / 2, budget


def test_downsampling_keeps_the_last_sample(client, db_session, rider):
    """A truncated line would show the ride ending somewhere it did not."""
    workout_id = make_workout(db_session, rider.id, 1_001)

    items = series(client, workout_id, rider.id, max_points=100).json()["items"]

    assert items[0]["sequence"] == 0
    assert items[-1]["sequence"] == 1_000


def test_a_generous_budget_returns_everything(client, db_session, rider):
    workout_id = make_workout(db_session, rider.id, 900)

    body = series(client, workout_id, rider.id, max_points=5_000).json()

    assert body["stride"] == 1
    assert body["returned"] == 900


@pytest.mark.parametrize("max_points", [1, 0, -5, settings.max_track_points + 1])
def test_an_out_of_range_budget_is_rejected(client, db_session, rider, max_points):
    workout_id = make_workout(db_session, rider.id, 10)

    assert series(client, workout_id, rider.id, max_points=max_points).status_code == 422


# -- edges and ownership -------------------------------------------------


def test_a_workout_without_samples_returns_an_empty_series(client, db_session, rider):
    workout_id = make_workout(db_session, rider.id, 0)

    body = series(client, workout_id, rider.id).json()

    assert body == {
        "workout_id": workout_id,
        "total": 0,
        "returned": 0,
        "stride": 1,
        "items": [],
    }


def test_another_users_samples_are_not_readable(client, db_session, rider):
    workout_id = make_workout(db_session, rider.id, 10)
    other = User(first_name="Mallory")
    db_session.add(other)
    db_session.commit()

    assert series(client, workout_id, other.id).status_code == 404


def test_an_unknown_workout_is_404(client, rider):
    assert series(client, 9_999, rider.id).status_code == 404


def test_a_user_id_is_required(client, db_session, rider):
    workout_id = make_workout(db_session, rider.id, 10)

    assert client.get(f"/api/workouts/{workout_id}/track-points").status_code == 422
