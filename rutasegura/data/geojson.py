"""Conversión entre la geometría del dominio y GeoJSON (texto guardado en SQLite)."""

from __future__ import annotations

import json
from typing import Any

from rutasegura.domain.geometry import Point, Polygon, Segment

JsonDict = dict[str, Any]


def point_to_geojson(point: Point) -> JsonDict:
    """``Point`` → GeoJSON Point."""
    return {"type": "Point", "coordinates": [point.x, point.y]}


def segment_to_geojson(segment: Segment) -> JsonDict:
    """``Segment`` → GeoJSON LineString de dos puntos."""
    return {
        "type": "LineString",
        "coordinates": [[segment.start.x, segment.start.y], [segment.end.x, segment.end.y]],
    }


def polygon_to_geojson(polygon: Polygon) -> JsonDict:
    """``Polygon`` → GeoJSON Polygon (anillo exterior cerrado)."""
    ring = [[p.x, p.y] for p in polygon.vertices]
    ring.append(ring[0])
    return {"type": "Polygon", "coordinates": [ring]}


def _expect(geometry: JsonDict, kind: str) -> Any:
    if geometry.get("type") != kind:
        raise ValueError(f"Se esperaba una geometría {kind}, se recibió {geometry.get('type')}.")
    return geometry["coordinates"]


def point_from_geojson(geometry: JsonDict) -> Point:
    """GeoJSON Point → ``Point``."""
    x, y = _expect(geometry, "Point")
    return Point(float(x), float(y))


def segment_from_geojson(geometry: JsonDict) -> Segment:
    """GeoJSON LineString de dos puntos → ``Segment``."""
    coords = _expect(geometry, "LineString")
    if len(coords) != 2:
        raise ValueError("Un segmento debe tener exactamente dos puntos.")
    (x1, y1), (x2, y2) = coords
    return Segment(Point(float(x1), float(y1)), Point(float(x2), float(y2)))


def polygon_from_geojson(geometry: JsonDict) -> Polygon:
    """GeoJSON Polygon → ``Polygon`` (se ignoran agujeros y se quita el punto de cierre)."""
    ring = _expect(geometry, "Polygon")[0]
    if len(ring) > 1 and ring[0] == ring[-1]:
        ring = ring[:-1]
    return Polygon(tuple(Point(float(x), float(y)) for x, y in ring))


def feature_dumps(geometry: JsonDict, properties: JsonDict | None = None) -> str:
    """Serializa un GeoJSON Feature."""
    feature = {"type": "Feature", "geometry": geometry, "properties": properties or {}}
    return json.dumps(feature, ensure_ascii=False, separators=(",", ":"))


def feature_loads(text: str) -> tuple[JsonDict, JsonDict]:
    """Lee un GeoJSON Feature y devuelve (geometría, propiedades)."""
    feature = json.loads(text)
    if feature.get("type") != "Feature":
        raise ValueError("Se esperaba un GeoJSON Feature.")
    return feature["geometry"], feature.get("properties") or {}


def geometry_dumps(geometry: JsonDict) -> str:
    """Serializa una geometría GeoJSON sin envoltorio Feature."""
    return json.dumps(geometry, separators=(",", ":"))


def geometry_loads(text: str) -> JsonDict:
    """Lee una geometría GeoJSON."""
    data: JsonDict = json.loads(text)
    return data
