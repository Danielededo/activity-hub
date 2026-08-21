"""The heart-rate histogram backfill."""

from datetime import timedelta

import pytest
from sqlalchemy import select, update

from app.models import Workout
from scripts.backfill_hr_zones import backfill
from tests.test_zones import EPOCH, gpx_with_heart_rate, gpx_without_heart_rate, upload


@pytest.fixture
def stored_before_the_column(client, user, db_session):
    """Two activities as they would look before migration 0006 was applied.

    One with a strap and one without, because the pair is what the null/empty
    distinction exists for.
    """
    first = upload(client, user["id"], gpx_with_heart_rate([140, 150, 160, 170]), "run.gpx")
    # A day apart: the same sport starting at the same moment is caught as the
    # same session exported twice, which is the point of that check.
    second = upload(
        client, user["id"], gpx_without_heart_rate(start=EPOCH + timedelta(days=1)), "phone.gpx"
    )
    assert (first.status_code, second.status_code) == (201, 201)

    db_session.execute(update(Workout).values(hr_seconds=None))
    db_session.commit()
    return user


def histograms(db_session):
    return db_session.execute(select(Workout.id, Workout.hr_seconds)).all()


def test_it_fills_in_activities_that_have_none(stored_before_the_column, db_session):
    outcome = backfill(db_session)

    assert outcome.considered == 2
    assert outcome.filled == 1
    assert outcome.without_heart_rate == 1
    assert all(row.hr_seconds is not None for row in histograms(db_session))


def test_the_figures_match_what_the_upload_path_computes(stored_before_the_column, db_session):
    backfill(db_session)

    filled = [row.hr_seconds for row in histograms(db_session) if row.hr_seconds]

    # Three ten-second intervals across four samples.
    assert filled == [{"140": 10.0, "150": 10.0, "160": 10.0}]


def test_an_activity_without_a_strap_is_visited_once_and_then_left_alone(
    stored_before_the_column, db_session
):
    """The improvement over the personal-bests backfill.

    There, "no rows" could not distinguish "not computed" from "computed, and
    there was nothing", so every strapless activity was rescanned on every run.
    Here an empty histogram records that the question has been asked.
    """
    backfill(db_session)

    second = backfill(db_session)

    assert second.considered == 0


def test_recompute_redoes_everything(stored_before_the_column, db_session):
    backfill(db_session)

    outcome = backfill(db_session, recompute=True)

    assert outcome.considered == 2
    assert outcome.filled == 1


def test_it_commits_in_batches(stored_before_the_column, db_session):
    outcome = backfill(db_session, batch=1)

    assert outcome.considered == 2
    assert all(row.hr_seconds is not None for row in histograms(db_session))
