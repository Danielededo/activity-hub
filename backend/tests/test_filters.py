"""Filtering and searching the activity list."""

import hashlib
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from app.config import settings
from app.models import User, Workout
from app.services.filters import day_window, escape_like, workout_filters

ROME = ZoneInfo("Europe/Rome")


def add_workout(db_session, user_id, *, name, sport, start_time):
    db_session.add(
        Workout(
            user_id=user_id,
            source="strava",
            name=name,
            sport_type=sport,
            start_time=start_time,
            utc_offset_minutes=None,
            total_distance=10_000.0,
            total_time=3_600.0,
            total_elevation_gain=100.0,
            total_elevation_loss=100.0,
            file_format="gpx",
            file_hash=hashlib.sha256(f"{user_id}:{name}:{start_time}".encode()).hexdigest(),
            raw_data={},
        )
    )
    db_session.commit()


def at(year, month, day, hour=9):
    return datetime(year, month, day, hour, tzinfo=UTC)


@pytest.fixture
def library(client, user, db_session):
    """A small library with distinct names, sports and dates to filter over."""
    add_workout(
        db_session, user["id"], name="Morning Ride", sport="cycling", start_time=at(2026, 7, 1)
    )
    add_workout(
        db_session, user["id"], name="Hill Repeats", sport="running", start_time=at(2026, 7, 15)
    )
    add_workout(
        db_session, user["id"], name="Evening ride home", sport="cycling", start_time=at(2026, 8, 2)
    )
    add_workout(
        db_session, user["id"], name="Monte Bianco", sport="hiking", start_time=at(2026, 8, 20)
    )
    return user


def names(response):
    return [item["name"] for item in response.json()["items"]]


def listing(client, user_id, **params):
    return client.get("/api/workouts", params={"user_id": user_id, **params})


# -- escaping a search term ----------------------------------------------


def test_a_percent_sign_is_escaped():
    """Unescaped, `%` is the LIKE wildcard and the search matches everything."""
    assert escape_like("50%") == "50\\%"


def test_an_underscore_is_escaped():
    assert escape_like("a_b") == "a\\_b"


def test_a_backslash_is_escaped_first():
    """Escaping it last would double-escape what the other rules just added."""
    assert escape_like("a\\%b") == "a\\\\\\%b"


def test_an_ordinary_term_is_left_alone():
    assert escape_like("Morning Ride") == "Morning Ride"


# -- the local day window ------------------------------------------------


def test_a_single_day_spans_that_whole_day():
    lower, upper = day_window(at(2026, 7, 1).date(), at(2026, 7, 1).date(), ZoneInfo("UTC"))

    assert lower == datetime(2026, 7, 1, tzinfo=UTC)
    # Midnight the next day: half-open in SQL, inclusive to the caller.
    assert upper == datetime(2026, 7, 2, tzinfo=UTC)


def test_the_window_is_resolved_in_the_given_zone():
    """Midnight in Rome in July is 22:00 the previous day in UTC."""
    lower, upper = day_window(at(2026, 7, 1).date(), at(2026, 7, 1).date(), ROME)

    assert lower == datetime(2026, 6, 30, 22, tzinfo=UTC)
    assert upper == datetime(2026, 7, 1, 22, tzinfo=UTC)


def test_absent_bounds_stay_absent():
    assert day_window(None, None) == (None, None)


def test_one_sided_windows():
    lower, upper = day_window(at(2026, 7, 1).date(), None, ZoneInfo("UTC"))
    assert lower is not None and upper is None

    lower, upper = day_window(None, at(2026, 7, 1).date(), ZoneInfo("UTC"))
    assert lower is None and upper is not None


def test_the_user_is_always_a_criterion():
    """Every list query is scoped to its owner, filters or no filters."""
    assert len(workout_filters(1)) == 1


# -- filtering over HTTP -------------------------------------------------


def test_no_filters_returns_everything(client, library):
    assert listing(client, library["id"]).json()["total"] == 4


def test_filtering_from_a_date(client, library):
    response = listing(client, library["id"], date_from="2026-08-01")

    assert response.json()["total"] == 2
    assert names(response) == ["Monte Bianco", "Evening ride home"]


def test_filtering_to_a_date_includes_that_day(client, library):
    """`date_to` reads as inclusive: an activity on the boundary is in."""
    response = listing(client, library["id"], date_to="2026-07-15")

    assert names(response) == ["Hill Repeats", "Morning Ride"]


def test_filtering_to_a_single_day(client, library):
    response = listing(client, library["id"], date_from="2026-07-15", date_to="2026-07-15")

    assert names(response) == ["Hill Repeats"]


def test_a_reversed_range_is_refused(client, library):
    response = listing(client, library["id"], date_from="2026-08-01", date_to="2026-07-01")

    assert response.status_code == 422
    assert "date_from" in response.json()["detail"]


def test_the_window_follows_the_configured_zone(client, library, monkeypatch):
    """The bounds are local dates, not UTC dates.

    09:00 UTC on 1 July is 22:00 on 30 June eleven hours west, so from that
    zone the activity belongs to June — which is what a person there would
    expect a June filter to return, and the reason the bounds are resolved in
    the display zone rather than compared as UTC dates.
    """
    monkeypatch.setattr(settings, "display_timezone", "Pacific/Midway")

    on_the_first = listing(client, library["id"], date_from="2026-07-01", date_to="2026-07-01")
    the_day_before = listing(client, library["id"], date_from="2026-06-30", date_to="2026-06-30")

    assert on_the_first.json()["total"] == 0
    assert names(the_day_before) == ["Morning Ride"]


def test_searching_by_name_is_case_insensitive(client, library):
    response = listing(client, library["id"], q="ride")

    assert sorted(names(response)) == ["Evening ride home", "Morning Ride"]


def test_searching_matches_a_substring_anywhere(client, library):
    assert names(listing(client, library["id"], q="repeat")) == ["Hill Repeats"]


def test_a_wildcard_in_the_search_matches_nothing_literal(client, library):
    """`%` must be a character to look for, not "match everything"."""
    assert listing(client, library["id"], q="%").json()["total"] == 0


def test_an_underscore_in_the_search_is_literal(client, library):
    """`_` matches any one character in LIKE; here it should match none."""
    assert listing(client, library["id"], q="Mo_te").json()["total"] == 0
    assert listing(client, library["id"], q="Monte").json()["total"] == 1


def test_a_blank_search_is_no_search(client, library):
    assert listing(client, library["id"], q="   ").json()["total"] == 4


def test_filters_combine(client, library):
    response = listing(
        client, library["id"], sport_type="cycling", q="ride", date_from="2026-08-01"
    )

    assert names(response) == ["Evening ride home"]


def test_a_combination_that_matches_nothing_is_empty_not_an_error(client, library):
    response = listing(client, library["id"], sport_type="hiking", q="ride")

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "limit": 20, "offset": 0}


def test_the_total_counts_matches_not_the_library(client, library):
    """A pager built on an unfiltered total would offer pages that are empty."""
    body = listing(client, library["id"], sport_type="cycling", limit=1).json()

    assert body["total"] == 2
    assert len(body["items"]) == 1


def test_paging_through_a_filtered_result(client, library):
    first = listing(client, library["id"], sport_type="cycling", limit=1, offset=0)
    second = listing(client, library["id"], sport_type="cycling", limit=1, offset=1)

    assert names(first) == ["Evening ride home"]
    assert names(second) == ["Morning Ride"]


def test_filters_do_not_reach_another_users_activities(client, library, db_session):
    """The owner check is not one filter among several: it always applies."""
    mallory = User(first_name="Mallory")
    db_session.add(mallory)
    db_session.commit()
    add_workout(
        db_session, mallory.id, name="Morning Ride", sport="cycling", start_time=at(2026, 7, 1)
    )

    assert listing(client, library["id"], q="Morning Ride").json()["total"] == 1
    assert listing(client, mallory.id, q="Morning Ride").json()["total"] == 1
    assert listing(client, mallory.id, q="Hill").json()["total"] == 0
