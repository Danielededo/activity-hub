"""The backfill script, for activities stored before bests were computed."""

from datetime import timedelta

import pytest
from sqlalchemy import delete, select

from app.models import WorkoutBest
from scripts.backfill_bests import backfill
from tests.test_records import EPOCH, even_pace, gpx_with_distance


def upload(client, user_id, content, filename):
    return client.post(
        f"/api/upload?user_id={user_id}",
        files={"file": (filename, content, "application/octet-stream")},
    )


@pytest.fixture
def stored_without_bests(client, user, db_session):
    """Two activities as they would look before migration 0005 was applied."""
    upload(client, user["id"], gpx_with_distance(even_pace(20, 100, 5)), "run.gpx")
    upload(
        client,
        user["id"],
        gpx_with_distance(even_pace(20, 100, 6), name="Slower", start=EPOCH + timedelta(days=1)),
        "slower.gpx",
    )
    db_session.execute(delete(WorkoutBest))
    db_session.commit()
    return user


def stored_bests(db_session):
    return db_session.execute(select(WorkoutBest.workout_id, WorkoutBest.duration_s)).all()


def test_it_fills_in_activities_that_have_none(stored_without_bests, db_session):
    assert stored_bests(db_session) == []

    outcome = backfill(db_session)

    assert outcome.considered == 2
    assert outcome.filled == 2
    assert len(stored_bests(db_session)) == 2


def test_it_reads_the_track_points_that_were_stored(stored_without_bests, db_session):
    """The figures must match what the upload path would have computed."""
    backfill(db_session)

    durations = sorted(row.duration_s for row in stored_bests(db_session))

    assert durations[0] == pytest.approx(50.0, abs=1.0)
    assert durations[1] == pytest.approx(60.0, abs=1.0)


def test_running_it_again_changes_nothing(stored_without_bests, db_session):
    """An interrupted run has to be safe to restart."""
    backfill(db_session)
    before = sorted(stored_bests(db_session))

    second = backfill(db_session)

    assert second.considered == 0
    assert sorted(stored_bests(db_session)) == before


def test_recompute_replaces_rather_than_duplicating(stored_without_bests, db_session):
    """The unique constraint would refuse a second opinion; this clears first."""
    backfill(db_session)

    outcome = backfill(db_session, recompute=True)

    assert outcome.considered == 2
    assert len(stored_bests(db_session)) == 2


def test_an_activity_too_short_for_a_record_is_counted_not_skipped(client, user, db_session):
    upload(client, user["id"], gpx_with_distance(even_pace(3, 100, 5)), "jog.gpx")
    db_session.execute(delete(WorkoutBest))
    db_session.commit()

    outcome = backfill(db_session)

    assert outcome.considered == 1
    assert outcome.filled == 0
    assert outcome.without_bests == 1


def test_it_commits_in_batches(stored_without_bests, db_session):
    """A long run should not lose everything if it is stopped part way."""
    outcome = backfill(db_session, batch=1)

    assert outcome.filled == 2
    assert len(stored_bests(db_session)) == 2
