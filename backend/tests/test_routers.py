"""End-to-end API behaviour against an in-memory database."""

from app.models import TrackPoint


def upload(client, user_id: int, content: bytes, filename: str):
    return client.post(
        f"/api/upload?user_id={user_id}",
        files={"file": (filename, content, "application/octet-stream")},
    )


# -- health --------------------------------------------------------------


def test_health_reports_ok(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_root_advertises_the_api(client):
    assert client.get("/").json()["api"] == "/api"


# -- users ---------------------------------------------------------------


def test_create_and_read_user(client):
    created = client.post("/api/users/", json={"first_name": "Ada", "last_name": "Lovelace"})
    assert created.status_code == 201
    body = created.json()
    assert body["first_name"] == "Ada"
    assert body["full_name"] == "Ada Lovelace"
    assert body["id"] > 0

    fetched = client.get(f"/api/users/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["last_name"] == "Lovelace"


def test_a_profile_without_a_surname(client):
    """Plenty of people go by one name; the surname is optional."""
    body = client.post("/api/users/", json={"first_name": "Prince"}).json()

    assert body["last_name"] is None
    assert body["full_name"] == "Prince"


def test_a_blank_surname_is_stored_as_absent(client):
    body = client.post("/api/users/", json={"first_name": "Ada", "last_name": "   "}).json()

    assert body["last_name"] is None


def test_a_second_profile_is_refused(client, user):
    """One deployment, one person: a second profile would just be invisible."""
    response = client.post("/api/users/", json={"first_name": "Someone"})

    assert response.status_code == 409
    assert "/api/users/me" in response.json()["detail"]


def test_a_blank_first_name_is_rejected(client):
    assert client.post("/api/users/", json={"first_name": "   "}).status_code == 422
    assert client.post("/api/users/", json={}).status_code == 422


def test_unknown_user_is_404(client):
    assert client.get("/api/users/9999").status_code == 404


# -- upload --------------------------------------------------------------


def test_upload_tcx(client, user, sample_tcx):
    response = upload(client, user["id"], sample_tcx, "ride.tcx")

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["source"] == "garmin"
    assert body["file_format"] == "tcx"
    assert body["sport_type"] == "cycling"
    assert body["total_distance"] == 12000.0
    assert body["max_heart_rate"] == 171
    assert body["track_point_count"] == 4
    assert body["raw_data"]["creator"] == "Garmin Edge 530"


def test_upload_persists_track_points(client, db_session, user, sample_gpx):
    workout_id = upload(client, user["id"], sample_gpx, "run.gpx").json()["id"]

    points = (
        db_session.query(TrackPoint)
        .filter(TrackPoint.workout_id == workout_id)
        .order_by(TrackPoint.sequence)
        .all()
    )
    assert len(points) == 4
    assert points[0].heart_rate == 128
    assert points[0].latitude is not None


def test_upload_rejects_a_duplicate_file(client, user, sample_tcx):
    assert upload(client, user["id"], sample_tcx, "ride.tcx").status_code == 201

    second = upload(client, user["id"], sample_tcx, "ride-copy.tcx")
    assert second.status_code == 409
    assert "identical file" in second.json()["detail"]


def test_upload_rejects_an_unknown_user(client, sample_tcx):
    assert upload(client, 4242, sample_tcx, "ride.tcx").status_code == 404


def test_upload_rejects_an_unsupported_extension(client, user):
    response = upload(client, user["id"], b"random bytes", "workout.fit")

    assert response.status_code == 422
    assert "Unsupported file" in response.json()["detail"]


def test_upload_rejects_malformed_xml(client, user):
    response = upload(client, user["id"], b"<gpx><trk>", "broken.gpx")

    assert response.status_code == 422
    assert "Malformed XML" in response.json()["detail"]


def test_upload_rejects_an_empty_file(client, user):
    assert upload(client, user["id"], b"", "empty.gpx").status_code == 400


def test_upload_rejects_an_oversized_file(client, user, monkeypatch, sample_tcx):
    from app.config import settings

    monkeypatch.setattr(settings, "max_upload_bytes", 10)
    assert upload(client, user["id"], sample_tcx, "ride.tcx").status_code == 413


# -- workouts ------------------------------------------------------------


def test_list_workouts_is_paginated(client, user, sample_tcx, sample_gpx):
    upload(client, user["id"], sample_tcx, "ride.tcx")
    upload(client, user["id"], sample_gpx, "run.gpx")

    response = client.get(f"/api/workouts?user_id={user['id']}&limit=1&offset=0")
    body = response.json()

    assert response.status_code == 200
    assert body["total"] == 2
    assert len(body["items"]) == 1
    # Newest first: the GPX run is a day later than the TCX ride.
    assert body["items"][0]["file_format"] == "gpx"
    assert (
        client.get(f"/api/workouts?user_id={user['id']}&limit=1&offset=1").json()["items"][0][
            "file_format"
        ]
        == "tcx"
    )


def test_list_workouts_filters_by_sport(client, user, sample_tcx, sample_gpx):
    upload(client, user["id"], sample_tcx, "ride.tcx")
    upload(client, user["id"], sample_gpx, "run.gpx")

    body = client.get(f"/api/workouts?user_id={user['id']}&sport_type=running").json()

    assert body["total"] == 1
    assert body["items"][0]["sport_type"] == "running"


def test_list_workouts_requires_a_user_id(client):
    assert client.get("/api/workouts").status_code == 422


def test_list_workouts_is_empty_for_another_user(client, user, other_user, sample_tcx):
    upload(client, user["id"], sample_tcx, "ride.tcx")

    assert client.get(f"/api/workouts?user_id={other_user['id']}").json()["total"] == 0


def test_get_workout_detail(client, user, sample_tcx):
    workout_id = upload(client, user["id"], sample_tcx, "ride.tcx").json()["id"]

    body = client.get(f"/api/workouts/{workout_id}?user_id={user['id']}").json()

    assert body["id"] == workout_id
    assert body["track_point_count"] == 4
    assert body["raw_data"]["lap_count"] == 1


def test_get_unknown_workout_is_404(client, user):
    assert client.get(f"/api/workouts/9999?user_id={user['id']}").status_code == 404


def test_get_workout_requires_a_user_id(client, user, sample_tcx):
    workout_id = upload(client, user["id"], sample_tcx, "ride.tcx").json()["id"]

    assert client.get(f"/api/workouts/{workout_id}").status_code == 422


def test_another_users_workout_is_not_readable(client, user, other_user, sample_tcx):
    """Owned by someone else must answer 404, not 403: no existence leak."""
    workout_id = upload(client, user["id"], sample_tcx, "ride.tcx").json()["id"]

    response = client.get(f"/api/workouts/{workout_id}?user_id={other_user['id']}")

    assert response.status_code == 404


def test_another_users_workout_is_not_deletable(client, db_session, user, other_user, sample_tcx):
    from app.models import Workout

    workout_id = upload(client, user["id"], sample_tcx, "ride.tcx").json()["id"]

    deleted = client.delete(f"/api/workouts/{workout_id}?user_id={other_user['id']}")

    assert deleted.status_code == 404
    assert db_session.get(Workout, workout_id) is not None  # still there


def test_delete_workout_removes_its_track_points(client, db_session, user, sample_tcx):
    workout_id = upload(client, user["id"], sample_tcx, "ride.tcx").json()["id"]

    assert client.delete(f"/api/workouts/{workout_id}?user_id={user['id']}").status_code == 204
    assert client.get(f"/api/workouts/{workout_id}?user_id={user['id']}").status_code == 404
    assert db_session.query(TrackPoint).filter(TrackPoint.workout_id == workout_id).count() == 0


def test_delete_unknown_workout_is_404(client, user):
    assert client.delete(f"/api/workouts/9999?user_id={user['id']}").status_code == 404


# -- analysis ------------------------------------------------------------


def test_analysis_summary(client, user, sample_tcx, sample_gpx):
    upload(client, user["id"], sample_tcx, "ride.tcx")
    upload(client, user["id"], sample_gpx, "run.gpx")

    body = client.get(f"/api/analysis/{user['id']}").json()

    assert body["workout_count"] == 2
    assert body["total_distance"] > 12000.0
    assert body["max_heart_rate"] == 171
    assert {row["sport_type"] for row in body["by_sport"]} == {"cycling", "running"}


def test_analysis_summary_for_an_unknown_user_is_404(client):
    assert client.get("/api/analysis/9999").status_code == 404


def test_weekly_analysis_returns_one_bucket_per_week(client, user):
    body = client.get(f"/api/analysis/{user['id']}/weekly?weeks=6").json()

    assert body["weeks"] == 6
    assert len(body["buckets"]) == 6
    assert all(bucket["workout_count"] == 0 for bucket in body["buckets"])


def test_weekly_analysis_rejects_an_out_of_range_window(client, user):
    assert client.get(f"/api/analysis/{user['id']}/weekly?weeks=0").status_code == 422
