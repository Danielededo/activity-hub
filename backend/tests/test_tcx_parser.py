"""TCX parser behaviour."""

from datetime import UTC, datetime

import pytest

from app.services.parsers import ParserError, TcxParser, get_parser
from app.services.parsers.gpx_parser import GpxParser


def test_parses_header_fields(sample_tcx):
    workout = TcxParser().parse(sample_tcx, filename="ride.tcx")

    assert workout.source == "garmin"
    assert workout.file_format == "tcx"
    assert workout.sport_type == "cycling"  # Garmin says "Biking"
    assert workout.start_time == datetime(2026, 5, 4, 6, 30, tzinfo=UTC)
    assert workout.name == "Cycling 2026-05-04"


def test_uses_lap_totals(sample_tcx):
    workout = TcxParser().parse(sample_tcx)

    assert workout.total_distance == pytest.approx(12000.0)
    assert workout.total_time == pytest.approx(1800.0)
    assert workout.avg_heart_rate == 142
    assert workout.max_heart_rate == 171


def test_parses_track_points(sample_tcx):
    points = TcxParser().parse(sample_tcx).track_points

    assert len(points) == 4
    assert [point.sequence for point in points] == [0, 1, 2, 3]
    first = points[0]
    assert first.latitude == pytest.approx(45.07)
    assert first.longitude == pytest.approx(7.6869)
    assert first.elevation == pytest.approx(240.0)
    assert first.heart_rate == 120
    assert first.cadence == 80


def test_reads_cadence_from_running_extensions(sample_tcx):
    """The third point has no <Cadence>, only ns3:RunCadence."""
    points = TcxParser().parse(sample_tcx).track_points

    assert points[2].cadence == 94


def test_raw_data_keeps_file_metadata_only(sample_tcx):
    raw = TcxParser().parse(sample_tcx).raw_data

    assert raw["creator"] == "Garmin Edge 530"
    assert raw["author"] == "Garmin Connect"
    assert raw["declared_sport"] == "Biking"
    assert raw["lap_count"] == 1
    assert raw["track_point_count"] == 4
    assert raw["laps"][0]["calories"] == 420
    # The samples themselves are rows in track_points, not JSON.
    assert "track_points" not in raw


def test_missing_activity_is_rejected():
    with pytest.raises(ParserError, match="No <Activity>"):
        TcxParser().parse(b"<TrainingCenterDatabase><Activities/></TrainingCenterDatabase>")


def test_malformed_xml_is_rejected():
    with pytest.raises(ParserError, match="Malformed XML"):
        TcxParser().parse(b"<TrainingCenterDatabase><Activities>")


def test_empty_file_is_rejected():
    with pytest.raises(ParserError, match="empty"):
        TcxParser().parse(b"   ")


def test_activity_without_timestamps_is_rejected():
    content = b"""<TrainingCenterDatabase><Activities>
      <Activity Sport="Running"><Lap><TotalTimeSeconds>10</TotalTimeSeconds></Lap></Activity>
    </Activities></TrainingCenterDatabase>"""
    with pytest.raises(ParserError, match="start time"):
        TcxParser().parse(content)


def test_notes_become_the_workout_name():
    content = b"""<TrainingCenterDatabase><Activities>
      <Activity Sport="Running"><Id>2026-05-04T06:30:00Z</Id>
        <Notes>Interval session</Notes></Activity>
    </Activities></TrainingCenterDatabase>"""
    assert TcxParser().parse(content).name == "Interval session"


def test_factory_selects_by_extension_and_by_content(sample_tcx, sample_gpx):
    assert isinstance(get_parser("ride.tcx", sample_tcx), TcxParser)
    assert isinstance(get_parser("run.gpx", sample_gpx), GpxParser)
    # No extension: fall back to sniffing the root element.
    assert isinstance(get_parser(None, sample_tcx), TcxParser)
    assert isinstance(get_parser("upload", sample_gpx), GpxParser)
