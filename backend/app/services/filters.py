"""Turning list-endpoint query parameters into SQL criteria.

Kept out of the router so the two parts that are easy to get wrong — escaping
a search term and deciding which calendar day an instant belongs to — can be
tested without going through HTTP.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.sql.elements import ColumnElement

from app.config import settings
from app.models import Workout

#: Passed to SQL LIKE so an escaped wildcard is read as a literal.
LIKE_ESCAPE = "\\"


def escape_like(term: str) -> str:
    """Neutralise LIKE wildcards in a user's search term.

    Without this, searching for `50%` matches every activity, and `_` matches
    any single character — so the search silently does something other than
    what was typed. The backslash has to go first, or it would escape the
    escapes added after it.
    """
    for special in (LIKE_ESCAPE, "%", "_"):
        term = term.replace(special, LIKE_ESCAPE + special)
    return term


def day_window(
    date_from: date | None, date_to: date | None, zone: ZoneInfo | None = None
) -> tuple[datetime | None, datetime | None]:
    """The UTC instants bounding a local calendar range, `date_to` included.

    Start times are stored in UTC, but a person filtering for "1–31 July" means
    July where they were, not July in Greenwich. Both bounds are therefore
    resolved in the configured display zone and converted, which keeps the
    comparison a plain range over an indexed column.

    The upper bound is the midnight *after* `date_to`, so the range is
    half-open in SQL while reading as inclusive to the caller — 1 July to
    1 July returns that day rather than nothing.

    An activity whose file stated an offset far from the configured zone can
    land on the neighbouring day at the boundary. Filtering exactly per row
    would mean computing each row's local date in SQL, which no longer uses the
    index; for choosing a date range that trade is not worth making.
    """
    zone = zone or settings.timezone
    lower = (
        datetime.combine(date_from, time.min, tzinfo=zone).astimezone(UTC)
        if date_from is not None
        else None
    )
    upper = (
        datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=zone).astimezone(UTC)
        if date_to is not None
        else None
    )
    return lower, upper


def workout_filters(
    user_id: int,
    *,
    sport_type: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    query: str | None = None,
    zone: ZoneInfo | None = None,
) -> list[ColumnElement[bool]]:
    """SQL criteria for one user's activity list, narrowed by whatever was asked.

    Returned as a list so the count and the page share exactly the same
    predicate: a total that disagreed with the rows would make the pager lie.
    """
    criteria: list[ColumnElement[bool]] = [Workout.user_id == user_id]

    if sport_type:
        criteria.append(Workout.sport_type == sport_type)

    lower, upper = day_window(date_from, date_to, zone)
    if lower is not None:
        criteria.append(Workout.start_time >= lower)
    if upper is not None:
        criteria.append(Workout.start_time < upper)

    term = (query or "").strip()
    if term:
        criteria.append(Workout.name.ilike(f"%{escape_like(term)}%", escape=LIKE_ESCAPE))

    return criteria
