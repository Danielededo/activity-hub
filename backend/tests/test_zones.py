"""Heart-rate zones: the histogram, the bands derived from it, and the load."""

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.config import settings
from app.models import User, Workout
from app.services.zones import (
    MAX_SAMPLE_GAP_S,
    ZONES,
    distribute,
    edwards_load,
    heart_rate_seconds,
    resolve_max_heart_rate,
    workout_zones,
    zone_bands,
)

EPOCH = datetime(2026, 6, 22, 6, 30, tzinfo=UTC)


@dataclass(slots=True)
class Sample:
    timestamp: datetime | None
    heart_rate: int | None


def beats(pairs, start=EPOCH):
    """Samples from (heart rate, seconds until the next sample) pairs."""
    samples = []
    moment = start
    for rate, gap in pairs:
        samples.append(Sample(moment, rate))
        moment += timedelta(seconds=gap)
    # A closing sample, so every pair above has a next one to be measured against.
    samples.append(Sample(moment, pairs[-1][0] if pairs else None))
    return samples


# -- the histogram -------------------------------------------------------


def test_each_sample_is_credited_with_the_time_to_the_next():
    histogram = heart_rate_seconds(beats([(140, 10), (150, 20)]))

    assert histogram == {140: 10.0, 150: 20.0}


def test_the_last_sample_is_credited_with_nothing():
    """There is no next sample, so there is no interval it can describe."""
    samples = [Sample(EPOCH, 140), Sample(EPOCH + timedelta(seconds=10), 199)]

    assert heart_rate_seconds(samples) == {140: 10.0}


def test_the_same_rate_accumulates():
    histogram = heart_rate_seconds(beats([(140, 10), (140, 15)]))

    assert histogram[140] == 25.0


def test_a_pause_is_not_time_at_that_heart_rate():
    """A twenty minute coffee break is not twenty minutes of easy work."""
    histogram = heart_rate_seconds(beats([(140, 10), (95, 1_200), (150, 10)]))

    assert 95 not in histogram
    assert histogram == {140: 10.0, 150: 10.0}


def test_the_gap_ceiling_is_generous_enough_for_a_coarse_file():
    """A minute between samples is already coarse; the cap sits well past it."""
    assert MAX_SAMPLE_GAP_S >= 120


def test_samples_without_a_heart_rate_are_skipped():
    samples = [
        Sample(EPOCH, 140),
        Sample(EPOCH + timedelta(seconds=10), None),
        Sample(EPOCH + timedelta(seconds=20), 150),
        Sample(EPOCH + timedelta(seconds=30), 150),
    ]

    # The None sample drops out, so 140 is measured against the next timed
    # reading that has a rate — 20 s later, not 10.
    assert heart_rate_seconds(samples) == {140: 20.0, 150: 10.0}


def test_samples_without_a_timestamp_are_skipped():
    samples = [Sample(None, 140), Sample(None, 150)]

    assert heart_rate_seconds(samples) == {}


def test_an_empty_track_has_no_histogram():
    assert heart_rate_seconds([]) == {}


def test_backwards_timestamps_do_not_subtract_time():
    samples = [
        Sample(EPOCH + timedelta(seconds=60), 140),
        Sample(EPOCH, 150),
        Sample(EPOCH + timedelta(seconds=70), 160),
    ]

    histogram = heart_rate_seconds(samples)

    assert all(seconds > 0 for seconds in histogram.values())
    assert 140 not in histogram


# -- the bands -----------------------------------------------------------


def test_bands_sit_at_percentages_of_the_maximum():
    bands = zone_bands(200)

    assert [band.min_bpm for band in bands] == [100, 120, 140, 160, 180]


def test_the_top_band_has_no_ceiling():
    """A configured maximum lower than reality must not drop the beats above it."""
    bands = zone_bands(200)

    assert bands[-1].max_bpm is None
    assert bands[0].max_bpm == 119


def test_the_bands_leave_no_gap_between_them():
    bands = zone_bands(187)

    for lower, upper in zip(bands, bands[1:], strict=False):
        assert lower.max_bpm + 1 == upper.min_bpm


def test_there_are_five_bands_weighted_one_to_five():
    assert [weight for _, _, _, weight in ZONES] == [1, 2, 3, 4, 5]


# -- spreading a histogram over them -------------------------------------


def test_time_below_the_first_zone_is_reported_not_folded_in():
    """Standing at a junction is real time, and it is not easy training.

    Folding it into zone one would inflate exactly the zone people read as
    "I did my easy work", so it is counted separately instead.
    """
    bands, below = distribute({"80": 300.0, "150": 600.0}, 200)

    assert below == 300.0
    assert sum(band.seconds for band in bands) == 600.0


def test_a_beat_above_the_maximum_lands_in_the_top_zone():
    bands, below = distribute({"210": 60.0}, 200)

    assert bands[-1].seconds == 60.0
    assert below == 0.0


def test_a_beat_exactly_on_a_boundary_takes_the_higher_zone():
    bands, _ = distribute({"140": 60.0}, 200)

    assert bands[2].seconds == 60.0
    assert bands[1].seconds == 0.0


def test_string_and_integer_keys_are_both_understood():
    """JSON gives back string keys; the computation gives integers."""
    from_json, _ = distribute({"150": 60.0}, 200)
    in_memory, _ = distribute({150: 60.0}, 200)

    assert [b.seconds for b in from_json] == [b.seconds for b in in_memory]


# -- the load ------------------------------------------------------------


def test_edwards_load_weights_minutes_by_zone():
    bands = zone_bands(200)
    bands[0].seconds = 600.0  # ten minutes at weight 1
    bands[4].seconds = 600.0  # ten minutes at weight 5

    assert edwards_load(bands) == pytest.approx(60.0)


def test_an_hour_of_easy_work_is_worth_less_than_an_hour_hard():
    easy = zone_bands(200)
    easy[1].seconds = 3_600.0
    hard = zone_bands(200)
    hard[3].seconds = 3_600.0

    assert edwards_load(hard) > edwards_load(easy)


# -- where the maximum comes from ----------------------------------------


def add_workout(db_session, user_id, *, max_hr=None, start_time=EPOCH, hr_seconds=None):
    workout = Workout(
        user_id=user_id,
        source="strava",
        name="Session",
        sport_type="running",
        start_time=start_time,
        utc_offset_minutes=None,
        total_distance=10_000.0,
        total_time=3_600.0,
        total_elevation_gain=100.0,
        total_elevation_loss=100.0,
        avg_heart_rate=max_hr,
        max_heart_rate=max_hr,
        file_format="gpx",
        file_hash=hashlib.sha256(f"{user_id}:{start_time}:{max_hr}".encode()).hexdigest(),
        raw_data={},
        hr_seconds=hr_seconds,
    )
    db_session.add(workout)
    db_session.commit()
    return workout


def test_the_configured_maximum_wins(db_session, monkeypatch):
    user = User(first_name="Rider")
    db_session.add(user)
    db_session.commit()
    add_workout(db_session, user.id, max_hr=170)
    monkeypatch.setattr(settings, "max_heart_rate", 195)

    assert resolve_max_heart_rate(db_session, user.id) == (195, "configured")


def test_the_observed_maximum_is_used_when_none_is_configured(db_session):
    user = User(first_name="Rider")
    db_session.add(user)
    db_session.commit()
    add_workout(db_session, user.id, max_hr=170)
    add_workout(db_session, user.id, max_hr=188, start_time=EPOCH + timedelta(days=1))

    assert resolve_max_heart_rate(db_session, user.id) == (188, "observed")


def test_a_library_with_no_heart_rate_has_no_maximum(db_session):
    user = User(first_name="Rider")
    db_session.add(user)
    db_session.commit()
    add_workout(db_session, user.id, max_hr=None)

    assert resolve_max_heart_rate(db_session, user.id) == (None, "unknown")


def test_zones_are_not_frozen_when_the_maximum_moves(db_session):
    """The reason the histogram is stored and the zones are not.

    A harder session raises the observed maximum, and every earlier activity's
    zones have to move with it. Stored zones would still describe the athlete
    somebody used to be.
    """
    user = User(first_name="Rider")
    db_session.add(user)
    db_session.commit()
    session = add_workout(db_session, user.id, max_hr=170, hr_seconds={"150": 600.0})

    before = workout_zones(db_session, session)
    add_workout(
        db_session, user.id, max_hr=200, start_time=EPOCH + timedelta(days=1), hr_seconds={}
    )
    db_session.expire_all()
    after = workout_zones(db_session, db_session.get(Workout, session.id))

    # 150 bpm is 88% of a 170 maximum — threshold — and 75% of 200, which is
    # tempo. Same activity, same samples, a zone lower.
    assert [b["zone"] for b in before["zones"] if b["seconds"]] == [4]
    assert [b["zone"] for b in after["zones"] if b["seconds"]] == [3]


def test_a_null_histogram_is_sql_null_not_the_json_value_null(db_session):
    """The distinction the backfill is built on, pinned at the database.

    SQLAlchemy stores Python None in a JSON column as the JSON *value* `null`
    by default, which `IS NULL` does not match — so "never computed" and
    "computed, nothing found" become indistinguishable and the backfill either
    rescans everything forever or skips everything. The column is declared with
    none_as_null for exactly this reason.
    """
    user = User(first_name="Rider")
    db_session.add(user)
    db_session.commit()
    never = add_workout(db_session, user.id, hr_seconds=None)
    empty = add_workout(db_session, user.id, start_time=EPOCH + timedelta(days=1), hr_seconds={})

    unseen = (
        db_session.execute(select(Workout.id).where(Workout.hr_seconds.is_(None))).scalars().all()
    )

    assert unseen == [never.id]
    assert empty.id not in unseen


# -- over HTTP -----------------------------------------------------------


def gpx_with_heart_rate(rates, seconds=10, start=EPOCH, name="Session", sport="running"):
    """A GPX whose samples carry a heart rate at a fixed interval."""
    points = []
    moment = start
    latitude = 45.0
    for rate in rates:
        points.append(
            f'<trkpt lat="{latitude:.6f}" lon="7.0"><ele>240</ele>'
            f"<time>{moment.strftime('%Y-%m-%dT%H:%M:%SZ')}</time>"
            f"<extensions><gpxtpx:TrackPointExtension><gpxtpx:hr>{rate}</gpxtpx:hr>"
            f"</gpxtpx:TrackPointExtension></extensions></trkpt>"
        )
        moment += timedelta(seconds=seconds)
        latitude += 0.001
    body = "\n".join(points)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<gpx creator="StravaGPX" xmlns="http://www.topografix.com/GPX/1/1"
     xmlns:gpxtpx="http://www.garmin.com/xmlschemas/TrackPointExtension/v1">
  <trk><name>{name}</name><type>{sport}</type><trkseg>
{body}
  </trkseg></trk>
</gpx>
""".encode()


def gpx_without_heart_rate(start=EPOCH, seconds=10):
    """A phone-recorded track: positions and times, no strap."""
    points = []
    moment = start
    latitude = 45.0
    for _ in range(5):
        points.append(
            f'<trkpt lat="{latitude:.6f}" lon="7.0"><ele>240</ele>'
            f"<time>{moment.strftime('%Y-%m-%dT%H:%M:%SZ')}</time></trkpt>"
        )
        moment += timedelta(seconds=seconds)
        latitude += 0.001
    body = "\n".join(points)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<gpx creator="StravaGPX" xmlns="http://www.topografix.com/GPX/1/1">
  <trk><name>No strap</name><type>running</type><trkseg>
{body}
  </trkseg></trk>
</gpx>
""".encode()


def upload(client, user_id, content, filename):
    return client.post(
        f"/api/upload?user_id={user_id}",
        files={"file": (filename, content, "application/octet-stream")},
    )


def test_uploading_stores_the_histogram(client, user, db_session):
    upload(client, user["id"], gpx_with_heart_rate([140, 140, 150, 150]), "run.gpx")

    stored = db_session.execute(select(Workout.hr_seconds)).scalar_one()

    # Three intervals of ten seconds; the fourth sample has no successor.
    assert stored == {"140": 20.0, "150": 10.0}


def test_an_upload_without_heart_rate_stores_an_empty_histogram(client, user, db_session):
    """Empty, not null: null would mean the backfill had never looked at it."""
    upload(client, user["id"], gpx_without_heart_rate(), "run.gpx")

    assert db_session.execute(select(Workout.hr_seconds)).scalar_one() == {}


def test_a_file_sampled_more_coarsely_than_the_cap_yields_no_histogram(client, user, db_session):
    """The cost of refusing to credit a pause, stated out loud.

    Every interval in a file sampled every five minutes is longer than the gap
    ceiling, so none of them counts and the activity contributes no time in
    zone. Its summary heart rate still counts towards the maximum. Real exports
    sample far more often than this — a minute is already coarse — so the trade
    is worth it, but it is a trade.
    """
    upload(client, user["id"], gpx_with_heart_rate([140, 150, 160], seconds=300), "sparse.gpx")

    assert db_session.execute(select(Workout.hr_seconds)).scalar_one() == {}


def test_one_activitys_zones_over_http(client, user):
    created = upload(client, user["id"], gpx_with_heart_rate([170] * 7), "run.gpx")
    workout_id = created.json()["id"]

    body = client.get(f"/api/workouts/{workout_id}/zones?user_id={user['id']}").json()

    assert body["max_heart_rate"] == 170
    assert body["max_heart_rate_source"] == "observed"
    # Everything at the observed maximum is, by definition, the top zone.
    assert [z["zone"] for z in body["zones"] if z["seconds"]] == [5]
    assert body["load"] > 0


def test_an_activity_without_heart_rate_reports_no_zones(client, user):
    created = upload(client, user["id"], gpx_without_heart_rate(), "run.gpx")
    workout_id = created.json()["id"]

    body = client.get(f"/api/workouts/{workout_id}/zones?user_id={user['id']}").json()

    assert body["zones"] == []
    assert body["load"] == 0.0


def test_another_users_activity_zones_are_not_readable(client, user, other_user, sample_tcx):
    created = upload(client, user["id"], sample_tcx, "ride.tcx")
    workout_id = created.json()["id"]

    response = client.get(f"/api/workouts/{workout_id}/zones?user_id={other_user['id']}")

    assert response.status_code == 404


def test_the_zone_summary_totals_a_library(client, user):
    upload(client, user["id"], gpx_with_heart_rate([120, 120, 120]), "easy.gpx")
    upload(
        client,
        user["id"],
        gpx_with_heart_rate([180, 180, 180], start=EPOCH + timedelta(days=1), name="Hard"),
        "hard.gpx",
    )

    body = client.get(f"/api/analysis/{user['id']}/zones").json()

    assert body["max_heart_rate"] == 180
    assert body["total_load"] > 0
    assert sum(z["seconds"] for z in body["zones"]) > 0


def test_the_weekly_buckets_are_zero_filled_and_carry_load(client, user):
    upload(client, user["id"], gpx_with_heart_rate([170] * 5, start=datetime.now(UTC)), "run.gpx")

    body = client.get(f"/api/analysis/{user['id']}/zones?weeks=6").json()

    assert len(body["weekly"]) == 6
    assert [len(bucket["seconds"]) for bucket in body["weekly"]] == [5] * 6
    assert body["weekly"][-1]["load"] > 0
    assert body["weekly"][0]["load"] == 0.0


def test_a_library_with_no_heart_rate_reports_no_zones(client, user):
    upload(client, user["id"], gpx_without_heart_rate(), "run.gpx")

    body = client.get(f"/api/analysis/{user['id']}/zones").json()

    assert body["max_heart_rate"] is None
    assert body["max_heart_rate_source"] == "unknown"
    assert body["zones"] == []


def test_zones_are_refused_for_an_unknown_user(client):
    assert client.get("/api/analysis/9999/zones").status_code == 404


def test_zones_do_not_leak_between_users(client, user, other_user, db_session):
    upload(client, user["id"], gpx_with_heart_rate([170] * 5), "mine.gpx")
    add_workout(db_session, other_user["id"], max_hr=200, hr_seconds={"199": 3_600.0})

    body = client.get(f"/api/analysis/{user['id']}/zones").json()

    assert body["max_heart_rate"] == 170
    assert body["total_load"] < 100
