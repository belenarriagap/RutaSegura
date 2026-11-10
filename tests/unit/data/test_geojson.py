"""Conversión de geometría a GeoJSON y de vuelta."""

from __future__ import annotations

import pytest

from rutasegura.data.geojson import (
    feature_dumps,
    feature_loads,
    point_from_geojson,
    point_to_geojson,
    polygon_from_geojson,
    polygon_to_geojson,
    segment_from_geojson,
    segment_to_geojson,
)
from rutasegura.domain import Point, Polygon, Segment


def test_point_round_trip() -> None:
    point = Point(1.5, -2.25)
    assert point_from_geojson(point_to_geojson(point)) == point


def test_segment_round_trip() -> None:
    segment = Segment(Point(0, 0), Point(10.5, 3))
    assert segment_from_geojson(segment_to_geojson(segment)) == segment


def test_polygon_ring_is_closed_and_round_trips() -> None:
    polygon = Polygon((Point(0, 0), Point(4, 0), Point(4, 3)))
    geometry = polygon_to_geojson(polygon)
    ring = geometry["coordinates"][0]
    assert ring[0] == ring[-1]
    assert len(ring) == 4
    assert polygon_from_geojson(geometry) == polygon


def test_feature_keeps_properties_and_unicode() -> None:
    text = feature_dumps(point_to_geojson(Point(0, 0)), {"nombre": "Salida Ñ"})
    assert "Salida Ñ" in text
    geometry, props = feature_loads(text)
    assert props == {"nombre": "Salida Ñ"}
    assert geometry["type"] == "Point"


def test_wrong_geometry_type_is_rejected() -> None:
    with pytest.raises(ValueError, match="LineString"):
        segment_from_geojson(point_to_geojson(Point(0, 0)))
    with pytest.raises(ValueError, match="dos puntos"):
        segment_from_geojson({"type": "LineString", "coordinates": [[0, 0], [1, 1], [2, 2]]})
    with pytest.raises(ValueError, match="Feature"):
        feature_loads('{"type": "Point", "coordinates": [0, 0]}')
