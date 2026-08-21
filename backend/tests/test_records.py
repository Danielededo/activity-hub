"""Personal bests: the window scan, and the records endpoint over it."""

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select

from app.models import User, Workout, WorkoutBest
from app.services.analyzer import haversine_distance
from app.services.records import STANDARD_DISTANCES, fastest_windows, user_records

#: Metres in one degree of latitude, by the same formula the code uses, so a
#: synthetic track can be laid out to an exact spacing.
METRES_PER_DEGREE = haversine_distance(0.0, 0.0, 1.0, 0.0)

EPOCH = datetime(2026, 6, 1, 6, 0, tzinfo=UTC)


@dataclass(slots=True)
class Sample:
    """Stands in for a parsed or stored track point."""

    timestamp: datetime | None
    latitude: float | None
    longitude: float | None


def straight_track(segments, start=EPOCH):
    """A track heading due north, built from (metres, seconds) hops.

    The first sample is the origin; each segment adds one sample that far on
    and that many seconds later, so the pace of each stretch is exact.
    """
    samples = [Sample(start, 0.0, 7.0)]
    latitude = 0.0
    moment = start
    for metres, seconds in segments:
        latitude += metres / METRES_PER_DEGREE
        moment += timedelta(seconds=seconds)
        samples.append(Sample(moment, latitude, 7.0))
    return samples


def even_pace(count, metres, seconds):
    """`count` identical hops."""
    return [(metres, seconds)] * count


def test_the_synthetic_track_is_laid_out_to_the_metre():
    """Guards the helper every window test below is measured against."""
    assert 111_194 < METRES_PER_DEGREE < 111_196


# -- the window scan -----------------------------------------------------


def test_a_flat_kilometre_is_its_own_best():
    # Ten 100 m hops of five seconds each: a kilometre in fifty seconds.
    track = straight_track(even_pace(10, 100, 5))

    windows = fastest_windows(track)

    assert windows[1_000] == pytest.approx(50.0, abs=0.5)


def test_only_distances_the_activity_reached_are_reported():
    track = straight_track(even_pace(60, 100, 5))  # 6 km

    windows = fastest_windows(track)

    assert set(windows) == {1_000, 5_000}


def test_the_fastest_stretch_wins_not_the_average():
    """A hard middle kilometre in an otherwise easy run is the record."""
    track = straight_track(even_pace(10, 100, 6) + even_pace(10, 100, 3) + even_pace(10, 100, 6))

    windows = fastest_windows(track)

    # The quick kilometre took 30 s; the whole 3 km averages 50 s per km.
    assert windows[1_000] == pytest.approx(30.0, abs=1.0)


def test_the_window_is_interpolated_between_samples():
    """A best must not depend on how often the watch wrote a point.

    Four samples 400 m apart: no pair is exactly a kilometre. Taking the first
    sample past the target would answer 30 s, the time for 1,200 m. The true
    kilometre ends at the last sample and starts 200 m in, half way through the
    first hop, which is 25 s.
    """
    track = straight_track(even_pace(3, 400, 10))

    assert fastest_windows(track)[1_000] == pytest.approx(25.0, abs=0.1)


def test_a_pause_does_not_become_a_record():
    """Standing still adds time and no distance, so it cannot win."""
    track = straight_track(even_pace(10, 100, 5) + [(0.0, 600.0)] + even_pace(10, 100, 5))

    assert fastest_windows(track)[1_000] == pytest.approx(50.0, abs=0.5)


def test_a_lost_signal_does_not_become_a_record():
    """A five kilometre jump in one second is a dropped signal, not a sprint."""
    track = straight_track(even_pace(5, 100, 5) + [(5_000.0, 1.0)] + even_pace(5, 100, 5))

    windows = fastest_windows(track)

    # The jump contributes no distance, so the kilometre is the 1,000 m
    # actually travelled — which took the whole activity, not a second.
    assert windows[1_000] == pytest.approx(51.0, abs=1.0)


def test_a_track_shorter_than_a_kilometre_has_no_bests():
    assert fastest_windows(straight_track(even_pace(5, 100, 5))) == {}


def test_a_track_without_timestamps_has_no_bests():
    """Without a clock the distance is known and the time is not."""
    track = [Sample(None, latitude, 7.0) for latitude in (0.0, 0.005, 0.010, 0.015)]

    assert fastest_windows(track) == {}


def test_a_track_without_positions_has_no_bests():
    track = [Sample(EPOCH + timedelta(seconds=n), None, None) for n in range(20)]

    assert fastest_windows(track) == {}


def test_an_empty_track_has_no_bests():
    assert fastest_windows([]) == {}


def test_samples_with_backwards_timestamps_are_dropped():
    """A handful of exporters write points out of order."""
    track = straight_track(even_pace(10, 100, 5))
    track.insert(5, Sample(EPOCH - timedelta(hours=1), 0.004, 7.0))

    windows = fastest_windows(track)

    assert windows[1_000] == pytest.approx(50.0, abs=0.5)


def test_the_distance_ladder_ascends():
    """fastest_windows stops at the first distance too long, so order matters."""
    metres = [value for _, value in STANDARD_DISTANCES]

    assert metres == sorted(metres)


# -- storing them at upload ----------------------------------------------


def upload(client, user_id, content, filename):
    return client.post(
        f"/api/upload?user_id={user_id}",
        files={"file": (filename, content, "application/octet-stream")},
    )


def gpx_with_distance(hops, name="Long run", sport="running", start=EPOCH):
    """A GPX long enough to earn a record, laid out to an exact pace."""
    points = []
    latitude = 0.0
    moment = start
    points.append(
        f'<trkpt lat="0.0" lon="7.0"><ele>100</ele><time>{moment.isoformat()}</time></trkpt>'
    )
    for metres, seconds in hops:
        latitude += metres / METRES_PER_DEGREE
        moment += timedelta(seconds=seconds)
        points.append(
            f'<trkpt lat="{latitude:.8f}" lon="7.0">'
            f"<ele>100</ele><time>{moment.isoformat()}</time></trkpt>"
        )
    body = "\n".join(points)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<gpx creator="StravaGPX" xmlns="http://www.topografix.com/GPX/1/1">
  <trk><name>{name}</name><type>{sport}</type><trkseg>
{body}
  </trkseg></trk>
</gpx>
""".encode()


def test_uploading_stores_the_windows(client, user, db_session):
    upload(client, user["id"], gpx_with_distance(even_pace(20, 100, 5)), "run.gpx")

    stored = db_session.execute(select(WorkoutBest.distance_m, WorkoutBest.duration_s)).all()

    assert {row.distance_m for row in stored} == {1_000}
    assert dict(stored)[1_000] == pytest.approx(50.0, abs=1.0)


def test_a_short_upload_stores_no_windows(client, user, db_session):
    upload(client, user["id"], gpx_with_distance(even_pace(3, 100, 5)), "jog.gpx")

    assert db_session.execute(select(WorkoutBest.id)).all() == []


def test_deleting_an_activity_deletes_its_records(client, user, db_session):
    """The bests describe an activity; without it they are unattributable."""
    created = upload(client, user["id"], gpx_with_distance(even_pace(20, 100, 5)), "run.gpx")
    workout_id = created.json()["id"]
    assert db_session.execute(select(WorkoutBest.id)).all() != []

    assert client.delete(f"/api/workouts/{workout_id}?user_id={user['id']}").status_code == 204

    db_session.expire_all()
    assert db_session.execute(select(WorkoutBest.id)).all() == []


# -- the records endpoint ------------------------------------------------


def add_workout(
    db_session,
    user_id,
    *,
    name,
    sport,
    start_time,
    distance=10_000.0,
    duration=3_600.0,
    climb=100.0,
    offset=None,
):
    workout = Workout(
        user_id=user_id,
        source="strava",
        name=name,
        sport_type=sport,
        start_time=start_time,
        utc_offset_minutes=offset,
        total_distance=distance,
        total_time=duration,
        total_elevation_gain=climb,
        total_elevation_loss=climb,
        file_format="gpx",
        file_hash=hashlib.sha256(f"{user_id}:{name}:{start_time}".encode()).hexdigest(),
        raw_data={},
    )
    db_session.add(workout)
    db_session.commit()
    return workout


def add_best(db_session, workout_id, distance_m, duration_s):
    db_session.add(WorkoutBest(workout_id=workout_id, distance_m=distance_m, duration_s=duration_s))
    db_session.commit()


def records(client, user_id):
    return client.get(f"/api/analysis/{user_id}/records")


@pytest.fixture
def history(client, user, db_session):
    """Two sports, three years, and a 5 km best in each of two runs."""
    short_run = add_workout(
        db_session,
        user["id"],
        name="Parkrun",
        sport="running",
        start_time=datetime(2025, 6, 1, 8, tzinfo=UTC),
        distance=5_000.0,
        duration=1_500.0,
        climb=20.0,
    )
    long_run = add_workout(
        db_session,
        user["id"],
        name="Half",
        sport="running",
        start_time=datetime(2026, 4, 1, 8, tzinfo=UTC),
        distance=21_100.0,
        duration=7_200.0,
        climb=300.0,
    )
    add_workout(
        db_session,
        user["id"],
        name="Alpine day",
        sport="cycling",
        start_time=datetime(2026, 7, 1, 8, tzinfo=UTC),
        distance=120_000.0,
        duration=18_000.0,
        climb=2_400.0,
    )
    add_best(db_session, short_run.id, 5_000, 1_450.0)
    add_best(db_session, long_run.id, 5_000, 1_600.0)
    add_best(db_session, long_run.id, 1_000, 280.0)
    return user


def test_the_longest_activity_of_each_sport(client, history):
    body = records(client, history["id"]).json()
    by_sport = {entry["sport_type"]: entry for entry in body["by_sport"]}

    assert by_sport["running"]["longest_distance"]["workout_name"] == "Half"
    assert by_sport["running"]["longest_distance"]["value"] == pytest.approx(21_100.0)
    assert by_sport["cycling"]["longest_distance"]["workout_name"] == "Alpine day"


def test_the_biggest_climb_and_longest_time_of_each_sport(client, history):
    by_sport = {
        entry["sport_type"]: entry for entry in records(client, history["id"]).json()["by_sport"]
    }

    assert by_sport["running"]["biggest_climb"]["value"] == pytest.approx(300.0)
    assert by_sport["cycling"]["longest_duration"]["value"] == pytest.approx(18_000.0)


def test_records_carry_the_activity_they_belong_to(client, history):
    """A record with no activity behind it cannot be checked or opened."""
    by_sport = {
        entry["sport_type"]: entry for entry in records(client, history["id"]).json()["by_sport"]
    }
    holder = by_sport["cycling"]["longest_distance"]

    assert holder["workout_id"] > 0
    assert holder["start_time"].startswith("2026-07-01")
    assert "utc_offset_minutes" in holder


def test_the_fastest_window_wins_not_the_most_recent(client, history):
    running = next(
        entry
        for entry in records(client, history["id"]).json()["by_sport"]
        if entry["sport_type"] == "running"
    )
    best = {entry["distance_m"]: entry for entry in running["distance_bests"]}

    assert best[5_000]["duration_s"] == pytest.approx(1_450.0)
    assert best[5_000]["workout_name"] == "Parkrun"


def test_distance_bests_are_labelled_and_ordered(client, history):
    running = next(
        entry
        for entry in records(client, history["id"]).json()["by_sport"]
        if entry["sport_type"] == "running"
    )

    assert [entry["label"] for entry in running["distance_bests"]] == ["1 km", "5 km"]


def test_a_tie_keeps_the_activity_that_set_it_first(client, user, db_session):
    """Re-running the same loop to the second should not move the date."""
    first = add_workout(
        db_session,
        user["id"],
        name="Original",
        sport="running",
        start_time=datetime(2026, 1, 1, 8, tzinfo=UTC),
    )
    later = add_workout(
        db_session,
        user["id"],
        name="Repeat",
        sport="running",
        start_time=datetime(2026, 2, 1, 8, tzinfo=UTC),
    )
    add_best(db_session, first.id, 5_000, 1_500.0)
    add_best(db_session, later.id, 5_000, 1_500.0)

    running = records(client, user["id"]).json()["by_sport"][0]

    assert running["distance_bests"][0]["workout_name"] == "Original"


def test_a_sport_with_no_windows_still_reports_its_activity_records(client, history):
    """Cycling has no stored windows here; its longest ride is still a record."""
    cycling = next(
        entry
        for entry in records(client, history["id"]).json()["by_sport"]
        if entry["sport_type"] == "cycling"
    )

    assert cycling["distance_bests"] == []
    assert cycling["longest_distance"] is not None


def test_sports_are_ordered_by_how_much_you_do_them(client, history):
    body = records(client, history["id"]).json()

    assert [entry["sport_type"] for entry in body["by_sport"]] == ["running", "cycling"]
    assert body["by_sport"][0]["workout_count"] == 2


def test_yearly_totals_are_newest_first(client, history):
    body = records(client, history["id"]).json()

    assert [year["year"] for year in body["yearly"]] == [2026, 2025]
    assert body["yearly"][0]["workout_count"] == 2
    assert body["yearly"][0]["total_distance"] == pytest.approx(141_100.0)
    assert body["yearly"][1]["total_elevation_gain"] == pytest.approx(20.0)


def test_a_year_is_the_local_year(client, user, db_session, monkeypatch):
    """23:30 on 31 December in Rome belongs to that year, not to the next one."""
    from app.config import settings

    monkeypatch.setattr(settings, "display_timezone", "Europe/Rome")
    add_workout(
        db_session,
        user["id"],
        name="New Year's Eve ride",
        sport="cycling",
        # 22:30 UTC is 23:30 in Rome, still 2025.
        start_time=datetime(2025, 12, 31, 22, 30, tzinfo=UTC),
    )

    body = records(client, user["id"]).json()

    assert [year["year"] for year in body["yearly"]] == [2025]


def test_an_empty_library_reports_nothing_rather_than_failing(client, user):
    body = records(client, user["id"]).json()

    assert body == {"user_id": user["id"], "by_sport": [], "yearly": []}


def test_records_are_refused_for_an_unknown_user(client):
    assert records(client, 9_999).status_code == 404


def test_records_do_not_leak_between_users(client, history, db_session):
    mallory = User(first_name="Mallory")
    db_session.add(mallory)
    db_session.commit()
    theirs = add_workout(
        db_session,
        mallory.id,
        name="Someone else's marathon",
        sport="running",
        distance=42_200.0,
        start_time=datetime(2026, 5, 1, 8, tzinfo=UTC),
    )
    add_best(db_session, theirs.id, 5_000, 900.0)

    mine = next(
        entry
        for entry in records(client, history["id"]).json()["by_sport"]
        if entry["sport_type"] == "running"
    )

    assert mine["longest_distance"]["workout_name"] == "Half"
    assert mine["distance_bests"][1]["duration_s"] == pytest.approx(1_450.0)


def test_the_year_boundary_moves_with_the_zone(db_session, user):
    """The same instant is 2025 in Rome and 2026 in Auckland.

    Called directly rather than over HTTP, because the point is that the zone
    decides the answer, not that the endpoint passes it along.
    """
    add_workout(
        db_session,
        user["id"],
        name="New Year's Eve ride",
        sport="cycling",
        start_time=datetime(2025, 12, 31, 22, 30, tzinfo=UTC),
    )

    rome = user_records(db_session, user["id"], zone=ZoneInfo("Europe/Rome"))
    auckland = user_records(db_session, user["id"], zone=ZoneInfo("Pacific/Auckland"))

    assert [year["year"] for year in rome["yearly"]] == [2025]
    assert [year["year"] for year in auckland["yearly"]] == [2026]
