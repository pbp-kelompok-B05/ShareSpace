"""Data migration 0005: impor data tempat Overpass otomatis saat migrate di production."""
import importlib
import json
import tempfile
from pathlib import Path

from django.apps import apps as django_apps
from django.test import TestCase, override_settings

from cod_location.models import Place

migration = importlib.import_module("cod_location.migrations.0005_import_places_production")


def overpass_node(node_id, name, amenity="library", lat=-6.36, lon=106.83):
    return {"type": "node", "id": node_id, "lat": lat, "lon": lon,
            "tags": {"amenity": amenity, "name": name}}


class ImportPlacesMigrationTest(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base_dir = Path(self.tmp.name)
        first, second = migration.PLACE_FILES
        self.write(first, {"elements": [
            overpass_node(1, "Perpustakaan UI"),
            overpass_node(2, "Kafe Kampus", amenity="cafe"),
            {"type": "node", "id": 3, "lat": -6.3, "lon": 106.8, "tags": {"amenity": "library"}},  # tanpa nama
        ]})
        self.write(second, {"elements": [
            overpass_node(2, "Kafe Kampus", amenity="cafe"),  # duplikat antarfile
            overpass_node(4, "Taman Lembah UI", amenity="park"),
        ]})

    def write(self, name, data):
        (self.base_dir / name).write_text(json.dumps(data), encoding="utf-8")

    def run_migration(self):
        migration.import_places(django_apps, None, base_dir=self.base_dir)

    def names(self):
        return sorted(Place.objects.values_list("name", flat=True))

    @override_settings(PRODUCTION=True)
    def test_production_imports_places_from_both_files(self):
        self.run_migration()
        expected = sorted(
            {p["name"] for name in migration.PLACE_FILES
             for p in migration.parse_places(json.loads((self.base_dir / name).read_text(encoding="utf-8")))}
        )
        self.assertEqual(self.names(), expected)
        self.assertIn("Perpustakaan UI", self.names())
        self.assertEqual(Place.objects.filter(osm_id="node/2").count(), 1)

    @override_settings(PRODUCTION=True)
    def test_running_twice_does_not_duplicate_or_overwrite(self):
        self.run_migration()
        Place.objects.filter(osm_id="node/1").update(name="Diubah admin")
        count = Place.objects.count()
        self.run_migration()
        self.assertEqual(Place.objects.count(), count)
        self.assertEqual(Place.objects.get(osm_id="node/1").name, "Diubah admin")

    @override_settings(PRODUCTION=False)
    def test_local_and_test_runs_do_not_import(self):
        self.run_migration()
        self.assertFalse(Place.objects.exists())

    @override_settings(PRODUCTION=True)
    def test_missing_file_is_skipped(self):
        (self.base_dir / migration.PLACE_FILES[1]).unlink()
        self.run_migration()
        self.assertIn("Perpustakaan UI", self.names())

    def test_migrated_test_database_starts_without_places(self):
        # Test DB dibuat lewat migrate dengan PRODUCTION=False, jadi tabel Place kosong.
        self.assertFalse(Place.objects.exists())

    def test_reverse_keeps_imported_data(self):
        self.assertIs(migration.Migration.operations[0].reverse_code, migration.migrations.RunPython.noop)
