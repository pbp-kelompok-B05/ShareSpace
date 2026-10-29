import json

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from cod_location.models import Place
from cod_location.place_import import parse_places


class Command(BaseCommand):
    help = "Impor tempat (perpustakaan, kafe, taman, pusat komunitas) dari JSON Overpass atau GeoJSON."

    def add_arguments(self, parser):
        parser.add_argument("path", help="Path file .json / .geojson")
        parser.add_argument(
            "--replace",
            action="store_true",
            help="Hapus semua data Place lama sebelum impor.",
        )

    def handle(self, *args, **options):
        try:
            with open(options["path"], encoding="utf-8") as f:
                data = json.load(f)
            places = parse_places(data)
        except (OSError, ValueError) as error:
            raise CommandError(str(error))

        # buang duplikat di dalam file
        unique = {p["osm_id"]: p for p in places}

        with transaction.atomic():
            if options["replace"]:
                Place.objects.all().delete()

            existing = set(Place.objects.values_list("osm_id", flat=True))
            new_items = [
                Place(**p) for oid, p in unique.items() if oid not in existing
            ]
            Place.objects.bulk_create(new_items, batch_size=500)

        self.stdout.write(self.style.SUCCESS(
            f"Selesai: {len(new_items)} tempat baru "
            f"({len(unique) - len(new_items)} sudah ada, dilewati). "
            f"Total di database: {Place.objects.count()}."
        ))