"""Test fixtures: an in-memory SQLite database and sample activity files."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app

SAMPLE_TCX = b"""<?xml version="1.0" encoding="UTF-8"?>
<TrainingCenterDatabase xmlns="http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"
                        xmlns:ns3="http://www.garmin.com/xmlschemas/ActivityExtension/v2">
  <Activities>
    <Activity Sport="Biking">
      <Id>2026-05-04T06:30:00Z</Id>
      <Lap StartTime="2026-05-04T06:30:00Z">
        <TotalTimeSeconds>1800.0</TotalTimeSeconds>
        <DistanceMeters>12000.0</DistanceMeters>
        <Calories>420</Calories>
        <AverageHeartRateBpm><Value>142</Value></AverageHeartRateBpm>
        <MaximumHeartRateBpm><Value>171</Value></MaximumHeartRateBpm>
        <Intensity>Active</Intensity>
        <Track>
          <Trackpoint>
            <Time>2026-05-04T06:30:00Z</Time>
            <Position>
              <LatitudeDegrees>45.070000</LatitudeDegrees>
              <LongitudeDegrees>7.686900</LongitudeDegrees>
            </Position>
            <AltitudeMeters>240.0</AltitudeMeters>
            <DistanceMeters>0.0</DistanceMeters>
            <HeartRateBpm><Value>120</Value></HeartRateBpm>
            <Cadence>80</Cadence>
          </Trackpoint>
          <Trackpoint>
            <Time>2026-05-04T06:35:00Z</Time>
            <Position>
              <LatitudeDegrees>45.080000</LatitudeDegrees>
              <LongitudeDegrees>7.696900</LongitudeDegrees>
            </Position>
            <AltitudeMeters>280.0</AltitudeMeters>
            <HeartRateBpm><Value>150</Value></HeartRateBpm>
            <Cadence>90</Cadence>
          </Trackpoint>
          <Trackpoint>
            <Time>2026-05-04T06:45:00Z</Time>
            <Position>
              <LatitudeDegrees>45.090000</LatitudeDegrees>
              <LongitudeDegrees>7.706900</LongitudeDegrees>
            </Position>
            <AltitudeMeters>250.0</AltitudeMeters>
            <HeartRateBpm><Value>171</Value></HeartRateBpm>
            <Extensions><ns3:TPX><ns3:RunCadence>94</ns3:RunCadence></ns3:TPX></Extensions>
          </Trackpoint>
          <Trackpoint>
            <Time>2026-05-04T07:00:00Z</Time>
            <Position>
              <LatitudeDegrees>45.100000</LatitudeDegrees>
              <LongitudeDegrees>7.716900</LongitudeDegrees>
            </Position>
            <AltitudeMeters>250.2</AltitudeMeters>
            <HeartRateBpm><Value>140</Value></HeartRateBpm>
            <Cadence>85</Cadence>
          </Trackpoint>
        </Track>
      </Lap>
      <Creator xsi:type="Device_t" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
        <Name>Garmin Edge 530</Name>
      </Creator>
    </Activity>
  </Activities>
  <Author xsi:type="Application_t" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
    <Name>Garmin Connect</Name>
  </Author>
</TrainingCenterDatabase>
"""

SAMPLE_GPX = b"""<?xml version="1.0" encoding="UTF-8"?>
<gpx creator="StravaGPX" version="1.1"
     xmlns="http://www.topografix.com/GPX/1/1"
     xmlns:gpxtpx="http://www.garmin.com/xmlschemas/TrackPointExtension/v1">
  <metadata>
    <time>2026-05-05T07:00:00Z</time>
  </metadata>
  <trk>
    <name>Morning Run</name>
    <type>running</type>
    <trkseg>
      <trkpt lat="45.070000" lon="7.686900">
        <ele>240.0</ele>
        <time>2026-05-05T07:00:00Z</time>
        <extensions><gpxtpx:TrackPointExtension>
          <gpxtpx:hr>128</gpxtpx:hr><gpxtpx:cad>82</gpxtpx:cad>
        </gpxtpx:TrackPointExtension></extensions>
      </trkpt>
      <trkpt lat="45.075000" lon="7.691900">
        <ele>260.0</ele>
        <time>2026-05-05T07:05:00Z</time>
        <extensions><gpxtpx:TrackPointExtension>
          <gpxtpx:hr>152</gpxtpx:hr><gpxtpx:cad>86</gpxtpx:cad>
        </gpxtpx:TrackPointExtension></extensions>
      </trkpt>
      <trkpt lat="45.080000" lon="7.696900">
        <ele>245.0</ele>
        <time>2026-05-05T07:10:00Z</time>
        <extensions><gpxtpx:TrackPointExtension>
          <gpxtpx:hr>160</gpxtpx:hr><gpxtpx:cad>88</gpxtpx:cad>
        </gpxtpx:TrackPointExtension></extensions>
      </trkpt>
      <trkpt lat="45.085000" lon="7.701900">
        <ele>245.3</ele>
        <time>2026-05-05T07:15:00Z</time>
      </trkpt>
    </trkseg>
  </trk>
</gpx>
"""


@pytest.fixture
def db_session():
    """A fresh in-memory database per test, shared across connections."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _record):
        # SQLite ignores ON DELETE CASCADE unless this pragma is set.
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def client(db_session):
    """TestClient wired to the in-memory database."""
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def user(client):
    response = client.post(
        "/api/users/", json={"username": "daniele", "email": "daniele@example.com"}
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def sample_tcx() -> bytes:
    return SAMPLE_TCX


@pytest.fixture
def sample_gpx() -> bytes:
    return SAMPLE_GPX
