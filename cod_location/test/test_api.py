
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.urls import reverse

from rest_framework.test import APIClient

from cod_location.models import CODLocation, Place


User = get_user_model()


class CODLocationAPITest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="codtester",
            password="testpassword123",
        )

        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.location = CODLocation.objects.create(
            name="Titik COD UI",
            address="Depok, Jawa Barat",
            latitude=-6.3600,
            longitude=106.8270,
            created_by=self.user,
        )

        self.delete_url = reverse(
            "cod_location_api:location-detail",
            kwargs={"pk": self.location.pk},
        )

    @patch(
        "cod_location.api_views.CODLocation.delete",
        side_effect=ProtectedError(
            "Cannot delete protected object.",
            [],
        ),
    )
    def test_delete_location_still_used_returns_409(self, mocked_delete):
        response = self.client.delete(self.delete_url)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["success"], False)
        self.assertEqual(
            response.data["message"],
            "Lokasi masih digunakan dalam jadwal COD.",
        )

        self.assertTrue(
            CODLocation.objects.filter(
                pk=self.location.pk
            ).exists()
        )


class CODPlacesAPITest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="placetester",
            password="testpassword123",
        )

        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        for i in range(51):
            Place.objects.create(
                osm_id=f"test-{i}",
                name=f"Tempat {i:02d}",
                address="Depok, Jawa Barat",
                kind="cafe",
                latitude=-6.3600,
                longitude=106.8270,
            )

        self.url = reverse("cod_location_api:place-list")

    def test_places_are_paginated(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 51)
        self.assertEqual(len(response.data["results"]), 20)
        self.assertIsNotNone(response.data["next"])

    def test_places_third_page_contains_remaining_results(self):
        response = self.client.get(
            self.url,
            {"page": 3},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 51)
        self.assertEqual(len(response.data["results"]), 11)
        self.assertIsNone(response.data["next"])
