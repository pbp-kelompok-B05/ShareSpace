
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from cod_location.models import CODLocation, PickupSchedule
from items.models import Item
from loans.models import LoanRequest


User = get_user_model()


class CODModelTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(
            username="owner_test",
            password="Test12345!"
        )
        cls.borrower = User.objects.create_user(
            username="borrower_test",
            password="Test12345!"
        )
        cls.other_user = User.objects.create_user(
            username="other_test",
            password="Test12345!"
        )

        cls.item = Item.objects.create(
            owner=cls.owner,
            name="Kalkulator Casio",
            description="Kalkulator untuk pengujian COD",
            category="electronics",
            condition="good",
            is_available=True,
            is_verified=True,
        )

        today = timezone.localdate()

        cls.loan = LoanRequest.objects.create(
            borrower=cls.borrower,
            item=cls.item,
            start_date=today + timedelta(days=1),
            due_date=today + timedelta(days=7),
            status=LoanRequest.Status.APPROVED,
        )

        cls.location = CODLocation.objects.create(
            name="Perpustakaan UI",
            address="Universitas Indonesia, Depok",
            latitude=Decimal("-6.362000"),
            longitude=Decimal("106.827000"),
            created_by=cls.owner,
        )

    def make_schedule(self, **overrides):
        data = {
            "loan_request": self.loan,
            "cod_location": self.location,
            "schedule_type": PickupSchedule.ScheduleType.PICKUP,
            "scheduled_time": timezone.now() + timedelta(days=2),
            "created_by": self.borrower,
        }
        data.update(overrides)
        return PickupSchedule(**data)


class CODLocationModelTests(CODModelTestBase):

    def test_location_created_successfully(self):
        self.assertEqual(self.location.name, "Perpustakaan UI")
        self.assertEqual(self.location.created_by, self.owner)
        self.assertIsNotNone(self.location.pk)

    def test_location_string_representation(self):
        self.assertEqual(
            str(self.location),
            "Perpustakaan UI"
        )

    def test_valid_coordinates(self):
        self.location.full_clean()

    def test_latitude_above_maximum(self):
        self.location.latitude = Decimal("90.000001")

        with self.assertRaises(ValidationError) as context:
            self.location.full_clean()

        self.assertIn("latitude", context.exception.message_dict)

    def test_latitude_below_minimum(self):
        self.location.latitude = Decimal("-90.000001")

        with self.assertRaises(ValidationError) as context:
            self.location.full_clean()

        self.assertIn("latitude", context.exception.message_dict)

    def test_longitude_above_maximum(self):
        self.location.longitude = Decimal("180.000001")

        with self.assertRaises(ValidationError) as context:
            self.location.full_clean()

        self.assertIn("longitude", context.exception.message_dict)

    def test_longitude_below_minimum(self):
        self.location.longitude = Decimal("-180.000001")

        with self.assertRaises(ValidationError) as context:
            self.location.full_clean()

        self.assertIn("longitude", context.exception.message_dict)

    def test_boundary_coordinates_are_valid(self):
        self.location.latitude = Decimal("90.000000")
        self.location.longitude = Decimal("-180.000000")

        self.location.full_clean()

    def test_location_has_timestamps(self):
        self.assertIsNotNone(self.location.created_at)
        self.assertIsNotNone(self.location.updated_at)


class PickupScheduleModelTests(CODModelTestBase):

    def test_pickup_schedule_is_valid(self):
        schedule = self.make_schedule()

        schedule.full_clean()
        schedule.save()

        self.assertIsNotNone(schedule.pk)
        self.assertEqual(schedule.loan_request, self.loan)
        self.assertEqual(schedule.cod_location, self.location)

    def test_return_schedule_is_valid(self):
        schedule = self.make_schedule(
            schedule_type=PickupSchedule.ScheduleType.RETURN,
        )

        schedule.full_clean()

    def test_schedule_in_the_past_is_rejected(self):
        schedule = self.make_schedule(
            scheduled_time=timezone.now() - timedelta(days=1)
        )

        with self.assertRaises(ValidationError) as context:
            schedule.full_clean()

        self.assertIn(
            "scheduled_time",
            context.exception.message_dict
        )

    def test_borrower_can_create_schedule(self):
        schedule = self.make_schedule(
            created_by=self.borrower
        )

        schedule.full_clean()

    def test_owner_can_create_schedule(self):
        schedule = self.make_schedule(
            created_by=self.owner
        )

        schedule.full_clean()

    def test_other_user_cannot_create_schedule(self):
        schedule = self.make_schedule(
            created_by=self.other_user
        )

        with self.assertRaises(ValidationError):
            schedule.full_clean()

    def test_invalid_schedule_type(self):
        schedule = self.make_schedule(
            schedule_type="invalid"
        )

        with self.assertRaises(ValidationError) as context:
            schedule.full_clean()

        self.assertIn(
            "schedule_type",
            context.exception.message_dict
        )

    def test_duplicate_pickup_schedule_is_rejected(self):
        first_schedule = self.make_schedule()
        first_schedule.full_clean()
        first_schedule.save()

        second_schedule = self.make_schedule()

        with self.assertRaises(ValidationError):
            second_schedule.full_clean()

    def test_pickup_and_return_can_coexist(self):
        pickup = self.make_schedule(
            schedule_type=PickupSchedule.ScheduleType.PICKUP
        )
        pickup.full_clean()
        pickup.save()

        returned = self.make_schedule(
            schedule_type=PickupSchedule.ScheduleType.RETURN,
            scheduled_time=timezone.now() + timedelta(days=3),
        )
        returned.full_clean()
        returned.save()

        self.assertEqual(
            PickupSchedule.objects.filter(
                loan_request=self.loan
            ).count(),
            2
        )

    def test_database_rejects_duplicate_schedule_type(self):
        first_schedule = self.make_schedule()
        first_schedule.save()

        second_schedule = self.make_schedule()

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                second_schedule.save()

    def test_schedule_string_representation(self):
        schedule = self.make_schedule()

        self.assertIn(
            "Pengambilan",
            str(schedule)
        )

    def test_schedule_has_timestamps(self):
        schedule = self.make_schedule()
        schedule.save()

        self.assertIsNotNone(schedule.created_at)
        self.assertIsNotNone(schedule.updated_at)
