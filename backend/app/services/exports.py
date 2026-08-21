"""Getting the data back out, in formats something else can read.

A training log that can only be read by the thing that wrote it is a trap. The
CSV is for a spreadsheet, the GPX is for any other tool that reads activities —
and the GPX is written so that this app's own parser reads it back to the same
figures, which is the only definition of "exported correctly" worth having.
"""

from __future__ import annotations

import csv
import io
import zipfile
from collections.abc import Iterator
from datetime import UTC, timedelta
from xml.sax.saxutils import escape, quoteattr

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import TrackPoint, Workout

#: Columns of the activity CSV, in order, as (header, attribute).
CSV_COLUMNS: tuple[tuple[str, str], ...] = (
    ("id", "id"),
    ("name", "name"),
    ("sport", "sport_type"),
    ("source", "source"),
    ("file_format", "file_format"),
    ("start_time_utc", "start_time"),
    ("utc_offset_minutes", "utc_offset_minutes"),
    ("distance_m", "total_distance"),
    ("moving_time_s", "total_time"),
    ("elevation_gain_m", "total_elevation_gain"),
    ("elevation_loss_m", "total_elevation_loss"),
    ("avg_heart_rate", "avg_heart_rate"),
    ("max_heart_rate", "max_heart_rate"),
    ("avg_cadence", "avg_cadence"),
)

#: How many activities to pull from the database at a time while streaming.
CSV_CHUNK = 500

GPX_HEADER = """<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="Activity Hub"
     xmlns="http://www.topografix.com/GPX/1/1"
     xmlns:gpxtpx="http://www.garmin.com/xmlschemas/TrackPointExtension/v1">
"""


def _isoformat(moment, offset_minutes: int | None) -> str:
    """A timestamp in the offset the file originally stated, or in UTC.

    Writing the stated offset back rather than normalising everything to Z is
    what lets a round trip preserve the local hour an activity happened at —
    the thing the app went to trouble to keep in the first place.
    """
    aware = moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)
    if offset_minutes is None:
        return aware.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    shifted = aware.astimezone(UTC) + timedelta(minutes=offset_minutes)
    sign = "+" if offset_minutes >= 0 else "-"
    hours, minutes = divmod(abs(offset_minutes), 60)
    return f"{shifted.strftime('%Y-%m-%dT%H:%M:%S')}{sign}{hours:02d}:{minutes:02d}"


def activity_csv(db: Session, filters: list) -> Iterator[str]:
    """The activity list as CSV, a chunk of rows at a time.

    Streamed rather than assembled: a few thousand activities is a few hundred
    kilobytes of text, and there is no reason to hold all of it while the client
    reads the first line.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")

    def drain() -> str:
        text = buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)
        return text

    writer.writerow([header for header, _ in CSV_COLUMNS])
    yield drain()

    query = (
        select(Workout)
        .where(*filters)
        .order_by(Workout.start_time.desc(), Workout.id.desc())
        .execution_options(yield_per=CSV_CHUNK)
    )
    for workout in db.execute(query).scalars():
        row = []
        for _, attribute in CSV_COLUMNS:
            value = getattr(workout, attribute)
            if attribute == "start_time":
                value = _isoformat(value, None)
            elif isinstance(value, float):
                # A GPS-derived distance carries fifteen decimal places of
                # float, and a cell reading 12758.291778682977 metres looks
                # like a bug rather than a measurement. Centimetres is already
                # more precision than any of this deserves.
                value = round(value, 2)
            row.append("" if value is None else value)
        writer.writerow(row)
        if buffer.tell() > 32_768:
            yield drain()

    remaining = drain()
    if remaining:
        yield remaining


def workout_gpx(db: Session, workout: Workout) -> str:
    """One activity as GPX 1.1, with heart rate and cadence where recorded.

    Points with no position are dropped: a `trkpt` is defined by its latitude
    and longitude, so there is no way to write one. Everything else round-trips
    through this app's own parser, which is what the tests check.
    """
    points = db.execute(
        select(TrackPoint).where(TrackPoint.workout_id == workout.id).order_by(TrackPoint.sequence)
    ).scalars()

    lines = [GPX_HEADER]
    lines.append("  <metadata>\n")
    lines.append(f"    <name>{escape(workout.name)}</name>\n")
    lines.append(f"    <time>{_isoformat(workout.start_time, workout.utc_offset_minutes)}</time>\n")
    lines.append("  </metadata>\n")
    lines.append("  <trk>\n")
    # Escaped, not interpolated: an activity called "Hills & intervals" would
    # otherwise produce XML that nothing can parse, this app included.
    lines.append(f"    <name>{escape(workout.name)}</name>\n")
    lines.append(f"    <type>{escape(workout.sport_type)}</type>\n")
    lines.append("    <trkseg>\n")

    for point in points:
        if point.latitude is None or point.longitude is None:
            continue
        lines.append(
            f"      <trkpt lat={quoteattr(f'{point.latitude:.7f}')} "
            f"lon={quoteattr(f'{point.longitude:.7f}')}>\n"
        )
        if point.elevation is not None:
            lines.append(f"        <ele>{point.elevation:.2f}</ele>\n")
        if point.timestamp is not None:
            lines.append(
                f"        <time>{_isoformat(point.timestamp, workout.utc_offset_minutes)}</time>\n"
            )
        if point.heart_rate is not None or point.cadence is not None:
            lines.append("        <extensions>\n")
            lines.append("          <gpxtpx:TrackPointExtension>\n")
            if point.heart_rate is not None:
                lines.append(f"            <gpxtpx:hr>{point.heart_rate}</gpxtpx:hr>\n")
            if point.cadence is not None:
                lines.append(f"            <gpxtpx:cad>{point.cadence}</gpxtpx:cad>\n")
            lines.append("          </gpxtpx:TrackPointExtension>\n")
            lines.append("        </extensions>\n")
        lines.append("      </trkpt>\n")

    lines.append("    </trkseg>\n")
    lines.append("  </trk>\n")
    lines.append("</gpx>\n")
    return "".join(lines)


def gpx_filename(workout: Workout) -> str:
    """A filename that sorts by date and survives any filesystem.

    Only the date, the sport and the id: a name can hold anything at all, and a
    zip full of files named after user input is a zip nobody can unpack safely.
    The id keeps two activities on one day apart.
    """
    day = _isoformat(workout.start_time, workout.utc_offset_minutes)[:10]
    sport = "".join(c if c.isalnum() else "-" for c in workout.sport_type)
    return f"{day}-{sport}-{workout.id}.gpx"


def write_archive(db: Session, filters: list, target) -> int:
    """Write every matching activity into `target` as a zip of GPX files.

    Written to the caller's file object — a spooled temporary file in the route
    — rather than built in memory: a library of a few thousand activities is
    hundreds of megabytes of XML, and holding it all to serve one download is
    the kind of thing that takes a small server down.
    """
    written = 0
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        query = select(Workout).where(*filters).order_by(Workout.start_time, Workout.id)
        for workout in db.execute(query).scalars():
            archive.writestr(gpx_filename(workout), workout_gpx(db, workout))
            written += 1
    return written
