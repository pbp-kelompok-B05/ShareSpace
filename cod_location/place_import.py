"""Pengolah data tempat OSM -> daftar dict siap simpan.

Tidak mengimpor Django, jadi bisa diuji terpisah.
Mendukung dua format masukan:
  1. JSON Overpass  : {"elements": [...]}
  2. GeoJSON osmium : {"features": [...]}
"""

# pasangan tag OSM -> nilai "kind" yang disimpan di database
KIND_RULES = [
    ("amenity", "library", "library"),
    ("amenity", "cafe", "cafe"),
    ("amenity", "community_centre", "community_centre"),
    ("leisure", "park", "park"),
    ("shop", "convenience", "convenience"),   # Indomaret, Alfamart, dll.
    ("shop", "supermarket", "supermarket"),   # Superindo, Hypermart, dll.
    ("shop", "mall", "mall"),                 # pusat perbelanjaan
    ("amenity", "place_of_worship", "place_of_worship"),  # masjid, gereja, pura, vihara, dll.
]


def detect_kind(tags):
    for key, value, kind in KIND_RULES:
        if tags.get(key) == value:
            return kind
    return None


def build_address(tags):
    parts = (
        tags.get("addr:street"),
        tags.get("addr:housenumber"),
        tags.get("addr:city"),
    )
    return ", ".join(p for p in parts if p)


def geometry_center(geometry):
    """Titik tengah kasar (lat, lon) dari geometri GeoJSON."""
    if not geometry:
        return None
    kind, coords = geometry.get("type"), geometry.get("coordinates")
    if not coords:
        return None

    if kind == "Point":
        pts = [coords]
    elif kind == "LineString":
        pts = coords
    elif kind == "Polygon":
        pts = coords[0]
    elif kind == "MultiPolygon":
        pts = coords[0][0]
    else:
        return None

    if not pts:
        return None
    lat = sum(p[1] for p in pts) / len(pts)
    lon = sum(p[0] for p in pts) / len(pts)
    return lat, lon


def _make(osm_id, tags, lat, lon):
    name = (tags.get("name") or "").strip()
    kind = detect_kind(tags)
    if not name or not kind or lat is None or lon is None:
        return None
    return {
        "osm_id": str(osm_id)[:30],
        "name": name[:200],
        "address": build_address(tags)[:300],
        "kind": kind,
        "latitude": float(lat),
        "longitude": float(lon),
    }


def parse_overpass(data):
    places = []
    for el in data.get("elements", []):
        center = el.get("center", {})
        lat = el.get("lat", center.get("lat"))
        lon = el.get("lon", center.get("lon"))
        item = _make(f'{el.get("type", "x")}/{el.get("id", "")}',
                     el.get("tags", {}), lat, lon)
        if item:
            places.append(item)
    return places


def parse_geojson(data):
    places = []
    for feat in data.get("features", []):
        props = feat.get("properties", {}) or {}
        point = geometry_center(feat.get("geometry"))
        if not point:
            continue
        # id bawaan osmium (mis. "n123") jika ada; jika tidak, buat dari nama+koordinat
        osm_id = feat.get("id") or f'{props.get("name", "")}@{point[0]:.5f},{point[1]:.5f}'
        item = _make(osm_id, props, point[0], point[1])
        if item:
            places.append(item)
    return places


def parse_places(data):
    """Deteksi format otomatis."""
    if isinstance(data, dict) and "elements" in data:
        return parse_overpass(data)
    if isinstance(data, dict) and "features" in data:
        return parse_geojson(data)
    raise ValueError("Format tidak dikenali: butuh JSON Overpass atau GeoJSON.")