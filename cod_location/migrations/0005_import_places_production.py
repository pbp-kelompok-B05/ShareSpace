"""Impor data tempat Overpass (model Place) otomatis saat migrate di production.

Pencarian rekomendasi titik COD membaca tabel Place, bukan memanggil Overpass API langsung
(lihat cod_location/README.md). Migration ini mengisi tabel itu dari file JSON di root proyek
ketika PRODUCTION=true, sehingga deploy ke PWS tidak perlu menjalankan import_places manual.

Di lokal dan saat test (PRODUCTION=false) migration ini tidak melakukan apa-apa: test database
tetap kosong, dan developer bisa menjalankan `python manage.py import_places <file>` sendiri.
Aman dijalankan ulang: tempat yang osm_id-nya sudah ada dilewati. Reverse tidak menghapus data.
"""
import json
from pathlib import Path

from django.conf import settings
from django.db import migrations

from cod_location.place_import import parse_places

PLACE_FILES = ("places_overpass.json", "places_tambahan.json")


def import_places(apps, schema_editor, base_dir=None):
    if not getattr(settings, "PRODUCTION", False):
        return

    Place = apps.get_model("cod_location", "Place")
    base_dir = Path(base_dir or settings.BASE_DIR)

    unique = {}
    for name in PLACE_FILES:
        path = base_dir / name
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as f:
            for place in parse_places(json.load(f)):
                unique[place["osm_id"]] = place

    existing = set(Place.objects.values_list("osm_id", flat=True))
    Place.objects.bulk_create(
        [Place(**place) for osm_id, place in unique.items() if osm_id not in existing],
        batch_size=500,
    )


class Migration(migrations.Migration):

    dependencies = [
        ("cod_location", "0004_place"),
    ]

    operations = [
        migrations.RunPython(import_places, migrations.RunPython.noop),
    ]
