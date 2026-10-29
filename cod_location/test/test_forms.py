from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from cod_location.forms import CODLocationForm, PickupScheduleForm
from cod_location.models import CODLocation, PickupSchedule


class CODLocationFormTests(TestCase):
    def setUp(self):
        self.valid_data = {
            "name": "Perpustakaan UI",
            "address": "Kampus UI, Depok",
            "latitude": "-6.362000",
            "longitude": "106.827000",
            "notes": "Dekat pintu masuk",
        }

    def test_valid_location_form(self):
        form = CODLocationForm(data=self.valid_data)
        self.assertTrue(form.is_valid(), form.errors)

    def test_optional_notes(self):
        data = {**self.valid_data, "notes": ""}
        self.assertTrue(CODLocationForm(data=data).is_valid())

    def test_required_fields(self):
        for field in ("name", "address", "latitude", "longitude"):
            with self.subTest(field=field):
                data = {**self.valid_data, field: ""}
                form = CODLocationForm(data=data)
                self.assertFalse(form.is_valid())
                self.assertIn(field, form.errors)

    def test_latitude_outside_range(self):
        for value in ("90.000001", "-90.000001"):
            with self.subTest(value=value):
                form = CODLocationForm(data={**self.valid_data, "latitude": value})
                self.assertFalse(form.is_valid())
                self.assertIn("latitude", form.errors)

    def test_longitude_outside_range(self):
        for value in ("180.000001", "-180.000001"):
            with self.subTest(value=value):
                form = CODLocationForm(data={**self.valid_data, "longitude": value})
                self.assertFalse(form.is_valid())
                self.assertIn("longitude", form.errors)

    def test_coordinate_boundaries(self):
        for lat, lon in (("90", "180"), ("-90", "-180")):
            with self.subTest(lat=lat, lon=lon):
                form = CODLocationForm(data={**self.valid_data, "latitude": lat, "longitude": lon})
                self.assertTrue(form.is_valid(), form.errors)

    def test_non_numeric_coordinates(self):
        form = CODLocationForm(data={**self.valid_data, "latitude": "abc"})
        self.assertFalse(form.is_valid())
        self.assertIn("latitude", form.errors)

    def test_name_max_length(self):
        form = CODLocationForm(data={**self.valid_data, "name": "X" * 151})
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)

    def test_form_does_not_expose_created_by(self):
        self.assertNotIn("created_by", CODLocationForm().fields)

    def test_coordinate_widgets_are_readonly(self):
        form = CODLocationForm()
        for field in ("latitude", "longitude"):
            with self.subTest(field=field):
                self.assertTrue(form.fields[field].widget.attrs.get("readonly"))

    def test_cleaned_coordinates_are_decimal(self):
        form = CODLocationForm(data=self.valid_data)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsInstance(form.cleaned_data["latitude"], Decimal)
        self.assertIsInstance(form.cleaned_data["longitude"], Decimal)


class PickupScheduleFormTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user = get_user_model().objects.create_user(
            username="forms_test_user", password="Test12345!"
        )
        cls.location = CODLocation.objects.create(
            name="Gerbang UI",
            address="Depok",
            latitude=Decimal("-6.362000"),
            longitude=Decimal("106.827000"),
            created_by=user,
        )

    def valid_data(self, **overrides):
        data = {
            "cod_location": str(self.location.pk),
            "schedule_type": PickupSchedule.ScheduleType.PICKUP,
            "scheduled_time": (timezone.localtime(timezone.now()) + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M"),
            "notes": "Bertemu di gerbang",
        }
        data.update(overrides)
        return data

    def test_valid_pickup_form(self):
        form = PickupScheduleForm(data=self.valid_data())
        self.assertTrue(form.is_valid(), form.errors)

    def test_valid_return_form(self):
        form = PickupScheduleForm(data=self.valid_data(schedule_type="return"))
        self.assertTrue(form.is_valid(), form.errors)

    def test_notes_are_optional(self):
        form = PickupScheduleForm(data=self.valid_data(notes=""))
        self.assertTrue(form.is_valid(), form.errors)

    def test_required_fields(self):
        for field in ("cod_location", "schedule_type", "scheduled_time"):
            with self.subTest(field=field):
                form = PickupScheduleForm(data=self.valid_data(**{field: ""}))
                self.assertFalse(form.is_valid())
                self.assertIn(field, form.errors)

    def test_past_schedule_is_rejected(self):
        past = (timezone.localtime(timezone.now()) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")
        form = PickupScheduleForm(data=self.valid_data(scheduled_time=past))
        self.assertFalse(form.is_valid())
        self.assertIn("scheduled_time", form.errors)

    def test_invalid_schedule_type(self):
        form = PickupScheduleForm(data=self.valid_data(schedule_type="delivery"))
        self.assertFalse(form.is_valid())
        self.assertIn("schedule_type", form.errors)

    def test_invalid_location(self):
        import uuid
        form = PickupScheduleForm(data=self.valid_data(cod_location=str(uuid.uuid4())))
        self.assertFalse(form.is_valid())
        self.assertIn("cod_location", form.errors)

    def test_location_queryset_contains_saved_locations(self):
        form = PickupScheduleForm()
        self.assertIn(self.location, form.fields["cod_location"].queryset)

    def test_accepts_seconds_in_datetime(self):
        date_with_seconds = (timezone.localtime(timezone.now()) + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%S")
        form = PickupScheduleForm(data=self.valid_data(scheduled_time=date_with_seconds))
        self.assertTrue(form.is_valid(), form.errors)

        
    def test_datetime_widget_type(self):
        form = PickupScheduleForm()

        html = str(form["scheduled_time"])

        self.assertIn('type="datetime-local"', html)
        
    def test_form_does_not_expose_loan_or_creator(self):
        form = PickupScheduleForm()
        self.assertNotIn("loan_request", form.fields)
        self.assertNotIn("created_by", form.fields)
