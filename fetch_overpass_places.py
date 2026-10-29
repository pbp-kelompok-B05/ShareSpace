"""Unduh tempat Jabodetabek dari Overpass SEKALI SAJA, simpan ke JSON.

Jalankan ketika server Overpass sedang hidup:
    python fetch_overpass_places.py            -> semua kategori, hasil places_overpass.json
    python fetch_overpass_places.py tambahan   -> hanya mall dan tempat ibadah, hasil places_tambahan.json
Lalu: python manage.py import_places <file hasil>

Tidak butuh Django. Area dibagi menjadi kotak-kotak kecil supaya tiap query ringan.
"""
import json
import sys
import time
import urllib.parse
import urllib.request

# Isi dengan identitas kelompok (email/repo asli)
USER_AGENT = "ShareSpace/1.0 (proyek kuliah PBP; kontak: EMAIL_KELOMPOK@gmail.com)"
REFERER = "https://github.com/ORGANISASI/NAMA-REPO"

ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://z.overpass-api.de/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

# Perkiraan kotak Jabodetabek: (selatan, barat, utara, timur)
BBOX = (-6.85, 106.25, -5.90, 107.25)
ROWS, COLS = 4, 4  # minimarket jumlahnya banyak, jadi kotak dibuat lebih kecil
PAUSE_SECONDS = 5
REQUEST_TIMEOUT = 90


def tiles(bbox, rows, cols):
    south, west, north, east = bbox
    d_lat = (north - south) / rows
    d_lon = (east - west) / cols
    for r in range(rows):
        for c in range(cols):
            yield (
                round(south + r * d_lat, 5),
                round(west + c * d_lon, 5),
                round(south + (r + 1) * d_lat, 5),
                round(west + (c + 1) * d_lon, 5),
            )


# Set query: "semua" = semua kategori, "tambahan" = hanya mall dan tempat ibadah
QUERY_SETS = {
    "semua": [
        '["amenity"~"^(library|cafe|community_centre)$"]["name"]',
        '["leisure"="park"]["name"]',
        '["shop"~"^(convenience|supermarket)$"]["name"]',
        '["shop"="mall"]["name"]',
        '["amenity"="place_of_worship"]["name"]',
    ],
    "tambahan": [
        '["shop"="mall"]["name"]',
        '["amenity"="place_of_worship"]["name"]',
    ],
}


def build_query(tile, filters):
    s, w, n, e = tile
    box = f"({s},{w},{n},{e})"
    body = "".join(f"nwr{f}{box};" for f in filters)
    return f"[out:json][timeout:60];({body});out center tags;"


def run_query(query):
    body = urllib.parse.urlencode({"data": query}).encode()
    errors = []
    for endpoint in ENDPOINTS:
        req = urllib.request.Request(
            endpoint, data=body,
            headers={"User-Agent": USER_AGENT, "Referer": REFERER, "Accept": "*/*"},
        )
        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            if isinstance(data.get("elements"), list):
                return data["elements"]
            errors.append(f"{endpoint}: respons tidak valid")
        except Exception as error:  # noqa: BLE001
            errors.append(f"{endpoint}: {type(error).__name__}: {error}")
    raise RuntimeError("; ".join(errors))


def main():
    set_name = sys.argv[1] if len(sys.argv) > 1 else "semua"
    if set_name not in QUERY_SETS:
        sys.exit(f"Set tidak dikenal: {set_name}. Pilihan: {', '.join(QUERY_SETS)}")
    filters = QUERY_SETS[set_name]
    output = "places_overpass.json" if set_name == "semua" else f"places_{set_name}.json"

    all_tiles = list(tiles(BBOX, ROWS, COLS))
    collected, failed = {}, []

    for index, tile in enumerate(all_tiles, start=1):
        print(f"[{index}/{len(all_tiles)}] kotak {tile} ...", flush=True)
        try:
            elements = run_query(build_query(tile, filters))
        except RuntimeError as error:
            print(f"    GAGAL: {error}")
            failed.append(tile)
        else:
            for el in elements:
                collected[f'{el["type"]}/{el["id"]}'] = el
            print(f"    {len(elements)} elemen (total unik: {len(collected)})")
        time.sleep(PAUSE_SECONDS)

    with open(output, "w", encoding="utf-8") as f:
        json.dump({"elements": list(collected.values())}, f, ensure_ascii=False)

    print(f"\nTersimpan: {output} ({len(collected)} elemen unik).")
    if failed:
        print(f"{len(failed)} kotak gagal; jalankan ulang nanti, atau pakai jalur osmium:")
        for tile in failed:
            print("   ", tile)
        sys.exit(1)


if __name__ == "__main__":
    main()