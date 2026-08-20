"""The demo dataset, and the generator that produces it.

Demo data that does not parse is worse than none, so both the committed files
and freshly generated output go through the real parsers and analyzer.
"""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.services.analyzer import compute_metrics
from app.services.parsers import parse_file
from scripts.generate_demo_data import build_activities

DEMO_DIR = Path(__file__).resolve().parents[2] / "demo" / "activities"
ENDING = datetime(2026, 6, 28, tzinfo=UTC)


def generated(**overrides) -> list[tuple[str, str]]:
    kwargs = {
        "seed": 20260504,
        "weeks": 2,
        "step_seconds": 120,
        "ending": ENDING,
        "edge_cases": True,
    }
    return build_activities(**{**kwargs, **overrides})


# -- the generator -------------------------------------------------------


def test_every_generated_file_parses():
    files = generated()

    assert len(files) > 5
    for filename, content in files:
        parsed = parse_file(filename, content.encode())
        assert parsed.track_points, filename
        assert parsed.start_time.tzinfo is not None, filename


def test_generated_metrics_are_plausible():
    for filename, content in generated():
        parsed = parse_file(filename, content.encode())
        metrics = compute_metrics(parsed)

        assert metrics.total_distance >= 0, filename
        assert metrics.total_elevation_gain >= 0, filename
        if metrics.avg_heart_rate is not None:
            # A human, not a sensor glitch.
            assert 60 <= metrics.avg_heart_rate <= 200, filename
        if metrics.avg_cadence is not None:
            assert 0 <= metrics.avg_cadence <= 140, filename


def test_the_same_seed_produces_the_same_bytes():
    """Regenerating must not churn the committed files."""
    assert generated() == generated()


def test_a_different_seed_produces_different_data():
    assert generated() != generated(seed=99)


def test_both_formats_are_produced():
    formats = {name.rsplit(".", 1)[1] for name, _ in generated()}

    assert formats == {"tcx", "gpx"}


def test_generated_activities_are_distinct_sessions():
    """Nothing in the set should collide with the duplicate rules."""
    starts = set()
    for filename, content in generated():
        parsed = parse_file(filename, content.encode())
        key = (parsed.sport_type, parsed.start_time)
        assert key not in starts, f"{filename} duplicates another activity"
        starts.add(key)


# -- the committed set ---------------------------------------------------


def demo_files() -> list[Path]:
    return sorted(p for p in DEMO_DIR.iterdir() if p.suffix in {".tcx", ".gpx"})


@pytest.mark.skipif(not DEMO_DIR.is_dir(), reason="demo/activities is not checked out")
def test_committed_demo_files_parse():
    files = demo_files()

    assert len(files) >= 10, "the committed demo set looks truncated"
    for path in files:
        parsed = parse_file(path.name, path.read_bytes())
        compute_metrics(parsed)


@pytest.mark.skipif(not DEMO_DIR.is_dir(), reason="demo/activities is not checked out")
def test_the_committed_set_is_varied_enough_to_demo():
    parsed = [parse_file(p.name, p.read_bytes()) for p in demo_files()]

    assert {p.file_format for p in parsed} == {"tcx", "gpx"}
    assert len({p.sport_type for p in parsed}) >= 3
    assert len({p.source for p in parsed}) >= 2
    # Weekly charts need more than one week of history to show a trend.
    assert len({p.start_time.isocalendar()[1] for p in parsed}) >= 4
    assert any(p.utc_offset_minutes is not None for p in parsed)


@pytest.mark.skipif(not DEMO_DIR.is_dir(), reason="demo/activities is not checked out")
@pytest.mark.parametrize(
    ("filename", "check"),
    [
        ("edge-no-heart-rate.gpx", lambda p, m: m.avg_heart_rate is None),
        (
            "edge-no-point-timestamps.gpx",
            lambda p, m: all(s.timestamp is None for s in p.track_points),
        ),
        ("edge-stated-utc-offset.tcx", lambda p, m: p.utc_offset_minutes == 120),
        ("edge-single-point.gpx", lambda p, m: len(p.track_points) == 1),
        ("edge-tcx-sport-other.tcx", lambda p, m: p.sport_type == "other"),
    ],
)
def test_edge_cases_exercise_what_they_claim(filename, check):
    path = DEMO_DIR / filename
    parsed = parse_file(path.name, path.read_bytes())

    assert check(parsed, compute_metrics(parsed)), filename


@pytest.mark.skipif(not DEMO_DIR.is_dir(), reason="demo/activities is not checked out")
def test_an_untimed_route_still_yields_a_distance():
    """No timestamps means no duration, but the geometry is still there."""
    path = DEMO_DIR / "edge-no-point-timestamps.gpx"
    metrics = compute_metrics(parse_file(path.name, path.read_bytes()))

    assert metrics.total_time == 0.0
    assert metrics.total_distance > 0
