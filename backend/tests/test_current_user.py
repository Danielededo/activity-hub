"""The single user this deployment serves."""

from app.config import settings
from app.models import User
from scripts.ensure_user import ensure_user


def test_me_returns_the_only_user(client, user):
    response = client.get("/api/users/me")

    assert response.status_code == 200
    assert response.json()["id"] == user["id"]


def test_me_is_not_read_as_an_id(client, user):
    """The literal route must win over /{user_id}."""
    assert client.get("/api/users/me").json()["username"] == user["username"]


def test_me_explains_itself_when_no_user_exists(client):
    response = client.get("/api/users/me")

    assert response.status_code == 404
    assert "ensure_user" in response.json()["detail"]


def test_me_picks_the_lowest_id_when_several_exist(client, db_session, user):
    db_session.add(User(username="second", email="second@example.com"))
    db_session.commit()

    assert client.get("/api/users/me").json()["id"] == user["id"]


# -- the bootstrap script ------------------------------------------------


def test_ensure_user_creates_from_settings(db_session):
    created, outcome = ensure_user(db_session)

    assert outcome == "created"
    assert created.username == settings.default_username
    assert created.email == settings.default_email


def test_ensure_user_is_idempotent(db_session):
    first, _ = ensure_user(db_session)
    second, outcome = ensure_user(db_session)

    assert second.id == first.id
    assert outcome.startswith("already present")


def test_ensure_user_leaves_an_existing_user_alone(db_session):
    db_session.add(User(username="daniele", email="daniele@example.com"))
    db_session.commit()

    found, outcome = ensure_user(db_session)

    # It must not rename or duplicate whoever is already there.
    assert found.username == "daniele"
    assert outcome.startswith("already present")


def test_ensure_user_reports_an_unexpected_extra_user(db_session):
    db_session.add_all(
        [
            User(username="a", email="a@example.com"),
            User(username="b", email="b@example.com"),
        ]
    )
    db_session.commit()

    _, outcome = ensure_user(db_session)

    assert "2 users present" in outcome
