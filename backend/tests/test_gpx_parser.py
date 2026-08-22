"""GPX parser behaviour."""

from datetime import UTC, datetime

import pytest

from app.services.parsers import GpxParser, ParserError, UnsupportedFileError, get_parser


def test_parses_header_fields(sample_gpx):
    workout = GpxParser().parse(sample_gpx, filename="run.gpx")

    assert workout.source == "strava"  # creator="StravaGPX"
    assert workout.file_format == "gpx"
    assert workout.name == "Morning Run"
    assert workout.sport_type == "running"
    assert workout.start_time == datetime(2026, 5, 5, 7, 0, tzinfo=UTC)


def test_elapsed_time_comes_from_timestamps(sample_gpx):
    workout = GpxParser().parse(sample_gpx)

    assert workout.total_time == pytest.approx(900.0)  # 07:00 -> 07:15
    # GPX states no distance; the analyzer derives it from positions.
    assert workout.total_distance is None


def test_parses_track_point_extensions(sample_gpx):
    points = GpxParser().parse(sample_gpx).track_points

    assert len(points) == 4
    assert points[0].heart_rate == 128
    assert points[0].cadence == 82
    assert points[0].elevation == pytest.approx(240.0)
    # The last point has no <extensions> block at all.
    assert points[3].heart_rate is None
    assert points[3].cadence is None


def test_source_detection_by_creator():
    parser = GpxParser()
    assert parser._source("komoot - https://www.komoot.de") == "komoot"
    assert parser._source("StravaGPX Android") == "strava"
    assert parser._source("Garmin Connect") == "garmin"
    assert parser._source(None) == "gpx"


@pytest.mark.parametrize(
    ("declared", "expected"),
    [("Ride", "cycling"), ("9", "running"), ("hike", "hiking"), ("", "other"), ("yoga", "yoga")],
)
def test_sport_aliases(declared, expected):
    content = f"""<gpx creator="test" xmlns="http://www.topografix.com/GPX/1/1"><trk>
      <type>{declared}</type>
      <trkseg><trkpt lat="45.0" lon="7.0"><time>2026-05-05T07:00:00Z</time></trkpt></trkseg>
    </trk></gpx>""".encode()
    assert GpxParser().parse(content).sport_type == expected


def test_track_without_points_is_rejected():
    content = b"""<gpx creator="test" xmlns="http://www.topografix.com/GPX/1/1">
      <trk><name>Empty</name><trkseg/></trk></gpx>"""
    with pytest.raises(ParserError, match="no track points"):
        GpxParser().parse(content)


def test_file_without_track_is_rejected():
    content = b"""<gpx creator="test" xmlns="http://www.topografix.com/GPX/1/1">
      <wpt lat="45.0" lon="7.0"/></gpx>"""
    with pytest.raises(ParserError, match="No <trk>"):
        GpxParser().parse(content)


def test_untimed_track_falls_back_to_metadata_time():
    content = b"""<gpx creator="test" xmlns="http://www.topografix.com/GPX/1/1">
      <metadata><time>2026-01-02T08:00:00Z</time></metadata>
      <trk><trkseg>
        <trkpt lat="45.0" lon="7.0"><ele>100</ele></trkpt>
        <trkpt lat="45.001" lon="7.001"><ele>105</ele></trkpt>
      </trkseg></trk></gpx>"""
    workout = GpxParser().parse(content)

    assert workout.start_time == datetime(2026, 1, 2, 8, 0, tzinfo=UTC)
    assert workout.total_time is None
    assert [point.sequence for point in workout.track_points] == [0, 1]


def test_unknown_extension_is_rejected():
    with pytest.raises(UnsupportedFileError, match="Unsupported file"):
        get_parser("workout.csv", b"not xml at all")
