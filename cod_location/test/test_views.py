from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from cod_location.models import CODLocation, PickupSchedule
from cod_location.views import overpass_search
from items.models import Item
from loans.models import LoanRequest

User = get_user_model()


class CODViewTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="owner_views", password="Test12345!")
        cls.borrower = User.objects.create_user(username="borrower_views", password="Test12345!")
        cls.other = User.objects.create_user(username="other_views", password="Test12345!")
        cls.staff = User.objects.create_user(username="staff_views", password="Test12345!", is_staff=True)

        cls.item = Item.objects.create(
            owner=cls.owner, name="Kalkulator Casio", description="Barang uji",
            category="electronics", condition="good", is_available=True,
            is_verified=True,
        )
        today = timezone.localdate()
        cls.loan = LoanRequest.objects.create(
            borrower=cls.borrower, item=cls.item,
            start_date=today + timedelta(days=1),
            due_date=today + timedelta(days=7),
            status=LoanRequest.Status.APPROVED,
        )
        cls.location = CODLocation.objects.create(
            name="Perpustakaan UI", address="Depok, Jawa Barat",
            latitude=Decimal("-6.362000"), longitude=Decimal("106.827000"),
            created_by=cls.owner,
        )

    def setUp(self):
        # Test Client standar menggunakan testserver. Pengaturan ini menghindari
        # DisallowedHost tanpa mengubah settings.py proyek.
        self.client = Client(SERVER_NAME="localhost", SERVER_PORT=8000)

    def location_data(self, **changes):
        data = {
            "name": "Taman UI", "address": "Depok",
            "latitude": "-6.360000", "longitude": "106.830000",
            "notes": "Tempat bertemu",
        }
        data.update(changes)
        return data

    def schedule_data(self, **changes):
        data = {
            "cod_location": str(self.location.pk),
            "schedule_type": "pickup",
            "scheduled_time": (timezone.now() + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M"),
            "notes": "Bertemu di depan pintu",
        }
        data.update(changes)
        return data

    def create_schedule(self, **changes):
        data = {
            "loan_request": self.loan,
            "cod_location": self.location,
            "schedule_type": PickupSchedule.ScheduleType.PICKUP,
            "scheduled_time": timezone.now() + timedelta(days=2),
            "created_by": self.borrower,
            "notes": "Catatan awal",
        }
        data.update(changes)
        return PickupSchedule.objects.create(**data)


class LocationViewTests(CODViewTestBase):
    def test_anonymous_cannot_list_locations(self):
        response = self.client.get(reverse("cod_location:location_list"))
        self.assertEqual(response.status_code, 302)

    def test_authenticated_user_can_list_locations(self):
        self.client.force_login(self.borrower)
        response = self.client.get(reverse("cod_location:location_list"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertEqual(len(response.json()["locations"]), 1)

    def test_location_detail(self):
        self.client.force_login(self.borrower)
        response = self.client.get(reverse("cod_location:location_detail", args=[self.location.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["location"]["name"], "Perpustakaan UI")

    def test_location_create(self):
        self.client.force_login(self.borrower)
        response = self.client.post(reverse("cod_location:location_create"), self.location_data())
        self.assertEqual(response.status_code, 201)
        new_location = CODLocation.objects.get(name="Taman UI")
        self.assertEqual(new_location.created_by, self.borrower)

    def test_location_create_invalid_latitude(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("cod_location:location_create"),
            self.location_data(latitude="91"),
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("latitude", response.json()["errors"])

    def test_creator_can_update_location(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("cod_location:location_update", args=[self.location.pk]),
            self.location_data(name="Lokasi Diperbarui"),
        )
        self.assertEqual(response.status_code, 200)
        self.location.refresh_from_db()
        self.assertEqual(self.location.name, "Lokasi Diperbarui")

    def test_other_user_cannot_update_location(self):
        self.client.force_login(self.other)
        response = self.client.post(
            reverse("cod_location:location_update", args=[self.location.pk]),
            self.location_data(name="Lokasi Diretas"),
        )
        self.assertEqual(response.status_code, 403)
        self.location.refresh_from_db()
        self.assertEqual(self.location.name, "Perpustakaan UI")

    def test_staff_can_update_location(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("cod_location:location_update", args=[self.location.pk]),
            self.location_data(name="Lokasi oleh Staff"),
        )
        self.assertEqual(response.status_code, 200)

    def test_other_user_cannot_delete_location(self):
        self.client.force_login(self.other)
        response = self.client.post(reverse("cod_location:location_delete", args=[self.location.pk]))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(CODLocation.objects.filter(pk=self.location.pk).exists())

    def test_creator_can_delete_unused_location(self):
        self.client.force_login(self.owner)
        response = self.client.post(reverse("cod_location:location_delete", args=[self.location.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(CODLocation.objects.filter(pk=self.location.pk).exists())

    def test_cannot_delete_location_in_use(self):
        self.create_schedule()
        self.client.force_login(self.owner)
        response = self.client.post(reverse("cod_location:location_delete", args=[self.location.pk]))
        self.assertEqual(response.status_code, 409)
        self.assertTrue(CODLocation.objects.filter(pk=self.location.pk).exists())

    def test_location_create_rejects_get(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("cod_location:location_create"))
        self.assertEqual(response.status_code, 405)


class ScheduleViewTests(CODViewTestBase):
    def test_owner_can_list_schedules(self):
        self.create_schedule()
        self.client.force_login(self.owner)
        response = self.client.get(reverse("cod_location:schedule_list", args=[self.loan.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["schedules"]), 1)

    def test_borrower_can_view_schedule_detail(self):
        schedule = self.create_schedule()
        self.client.force_login(self.borrower)
        response = self.client.get(reverse("cod_location:schedule_detail", args=[schedule.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["schedule"]["id"], str(schedule.pk))

    def test_other_user_cannot_list_schedules(self):
        self.client.force_login(self.other)
        response = self.client.get(reverse("cod_location:schedule_list", args=[self.loan.pk]))
        self.assertEqual(response.status_code, 404)

    def test_other_user_cannot_view_schedule_detail(self):
        schedule = self.create_schedule()
        self.client.force_login(self.other)
        response = self.client.get(reverse("cod_location:schedule_detail", args=[schedule.pk]))
        self.assertEqual(response.status_code, 403)

    def test_borrower_can_create_schedule(self):
        self.client.force_login(self.borrower)
        response = self.client.post(
            reverse("cod_location:schedule_create", args=[self.loan.pk]),
            self.schedule_data(),
        )
        self.assertEqual(response.status_code, 201)
        schedule = PickupSchedule.objects.get(loan_request=self.loan)
        self.assertEqual(schedule.created_by, self.borrower)

    def test_other_user_cannot_create_schedule(self):
        self.client.force_login(self.other)
        response = self.client.post(
            reverse("cod_location:schedule_create", args=[self.loan.pk]),
            self.schedule_data(),
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(PickupSchedule.objects.count(), 0)

    def test_invalid_schedule_form(self):
        self.client.force_login(self.borrower)
        response = self.client.post(
            reverse("cod_location:schedule_create", args=[self.loan.pk]),
            self.schedule_data(cod_location=""),
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("cod_location", response.json()["errors"])

    def test_duplicate_schedule_type_currently_raises_validation_error(self):
        # Saat ini schedule_create memanggil full_clean() di luar try/except.
        # Duplikasi karenanya memunculkan ValidationError, bukan JSON 409.
        self.create_schedule()
        self.client.force_login(self.borrower)
        with self.assertRaises(ValidationError):
            self.client.post(
                reverse("cod_location:schedule_create", args=[self.loan.pk]),
                self.schedule_data(),
            )
        self.assertEqual(PickupSchedule.objects.filter(loan_request=self.loan).count(), 1)

    def test_borrower_can_update_schedule(self):
        schedule = self.create_schedule()
        self.client.force_login(self.borrower)
        response = self.client.post(
            reverse("cod_location:schedule_update", args=[schedule.pk]),
            self.schedule_data(notes="Catatan baru"),
        )
        self.assertEqual(response.status_code, 200)
        schedule.refresh_from_db()
        self.assertEqual(schedule.notes, "Catatan baru")

    def test_other_user_cannot_update_schedule(self):
        schedule = self.create_schedule()
        self.client.force_login(self.other)
        response = self.client.post(
            reverse("cod_location:schedule_update", args=[schedule.pk]),
            self.schedule_data(notes="Tidak sah"),
        )
        self.assertEqual(response.status_code, 403)
        schedule.refresh_from_db()
        self.assertEqual(schedule.notes, "Catatan awal")

    def test_other_user_cannot_delete_schedule(self):
        schedule = self.create_schedule()
        self.client.force_login(self.other)
        response = self.client.post(reverse("cod_location:schedule_delete", args=[schedule.pk]))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(PickupSchedule.objects.filter(pk=schedule.pk).exists())

    def test_owner_can_delete_schedule_on_approved_loan(self):
        schedule = self.create_schedule()
        self.client.force_login(self.owner)
        response = self.client.post(reverse("cod_location:schedule_delete", args=[schedule.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(PickupSchedule.objects.filter(pk=schedule.pk).exists())

    def test_completed_loan_cannot_create_schedule(self):
        self.loan.status = LoanRequest.Status.COMPLETED
        self.loan.save(update_fields=["status"])
        self.client.force_login(self.borrower)
        response = self.client.post(
            reverse("cod_location:schedule_create", args=[self.loan.pk]),
            self.schedule_data(),
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(PickupSchedule.objects.count(), 0)

    def test_completed_loan_cannot_update_schedule(self):
        schedule = self.create_schedule()
        self.loan.status = LoanRequest.Status.COMPLETED
        self.loan.save(update_fields=["status"])
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("cod_location:schedule_update", args=[schedule.pk]),
            self.schedule_data(notes="Tidak boleh"),
        )
        self.assertEqual(response.status_code, 400)
        schedule.refresh_from_db()
        self.assertEqual(schedule.notes, "Catatan awal")

    def test_completed_loan_cannot_delete_schedule(self):
        schedule = self.create_schedule()
        self.loan.status = LoanRequest.Status.COMPLETED
        self.loan.save(update_fields=["status"])
        self.client.force_login(self.owner)
        response = self.client.post(reverse("cod_location:schedule_delete", args=[schedule.pk]))
        self.assertEqual(response.status_code, 400)
        self.assertTrue(PickupSchedule.objects.filter(pk=schedule.pk).exists())

    def test_borrowed_loan_cannot_delete_schedule(self):
        schedule = self.create_schedule()
        self.loan.status = LoanRequest.Status.BORROWED
        self.loan.save(update_fields=["status"])
        self.client.force_login(self.borrower)
        response = self.client.post(reverse("cod_location:schedule_delete", args=[schedule.pk]))
        self.assertEqual(response.status_code, 400)

    def test_schedule_manage_page_owner(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("cod_location:schedule_manage", args=[self.loan.pk]))
        self.assertEqual(response.status_code, 200)

    def test_schedule_manage_page_other_user(self):
        self.client.force_login(self.other)
        response = self.client.get(reverse("cod_location:schedule_manage", args=[self.loan.pk]))
        self.assertEqual(response.status_code, 404)

    def test_anonymous_cannot_open_map(self):
        response = self.client.get(reverse("cod_location:map"))
        self.assertEqual(response.status_code, 302)

    def test_authenticated_can_open_map(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("cod_location:map"))
        self.assertEqual(response.status_code, 200)


class OverpassViewTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory(SERVER_NAME="localhost")

    def test_invalid_coordinates_rejected(self):
        request = self.factory.get("/cod/overpass/", {"lat": "abc", "lon": "106.8"})
        response = overpass_search(request)
        self.assertEqual(response.status_code, 400)

    def test_invalid_radius_rejected(self):
        request = self.factory.get("/cod/overpass/", {"lat": "-6.3", "lon": "106.8", "radius": "9000"})
        response = overpass_search(request)
        self.assertEqual(response.status_code, 400)

    def test_invalid_category_rejected(self):
        request = self.factory.get("/cod/overpass/", {"lat": "-6.3", "lon": "106.8", "category": "unknown"})
        response = overpass_search(request)
        self.assertEqual(response.status_code, 400)

    @patch("cod_location.views._run_overpass")
    @patch("cod_location.views.cache.get", return_value=None)
    @patch("cod_location.views.cache.set")
    def test_successful_overpass_result(self, mock_set, mock_get, mock_overpass):
        mock_overpass.return_value = {
            "elements": [{
                "type": "node", "id": 123,
                "lat": -6.3, "lon": 106.8,
                "tags": {"name": "Perpustakaan Contoh", "amenity": "library"},
            }]
        }
        request = self.factory.get("/cod/overpass/", {"lat": "-6.3", "lon": "106.8", "category": "library"})
        response = overpass_search(request)
        self.assertEqual(response.status_code, 200)
        import json
        places = json.loads(response.content)["places"]
        self.assertEqual(len(places), 1)
        self.assertEqual(places[0]["name"], "Perpustakaan Contoh")
        mock_overpass.assert_called_once()

    @patch("cod_location.views._run_overpass", side_effect=RuntimeError("Offline"))
    @patch("cod_location.views.cache.get", return_value=None)
    def test_overpass_service_failure(self, mock_get, mock_overpass):
        request = self.factory.get("/cod/overpass/", {"lat": "-6.3", "lon": "106.8"})
        response = overpass_search(request)
        self.assertEqual(response.status_code, 502)
