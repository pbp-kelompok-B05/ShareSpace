import uuid

from django.test import SimpleTestCase
from django.urls import resolve, reverse

from cod_location import views


class CODLocationURLTests(SimpleTestCase):

    def test_map_url(self):
        url = reverse("cod_location:map")
        self.assertEqual(resolve(url).func, views.cod_map_page)

    def test_location_list_url(self):
        url = reverse("cod_location:location_list")
        self.assertEqual(resolve(url).func, views.location_list)

    def test_location_create_url(self):
        url = reverse("cod_location:location_create")
        self.assertEqual(resolve(url).func, views.location_create)

    def test_location_detail_url(self):
        pk = uuid.uuid4()
        url = reverse("cod_location:location_detail", args=[pk])
        self.assertEqual(resolve(url).func, views.location_detail)

    def test_location_update_url(self):
        pk = uuid.uuid4()
        url = reverse("cod_location:location_update", args=[pk])
        self.assertEqual(resolve(url).func, views.location_update)

    def test_location_delete_url(self):
        pk = uuid.uuid4()
        url = reverse("cod_location:location_delete", args=[pk])
        self.assertEqual(resolve(url).func, views.location_delete)

    def test_schedule_list_url(self):
        loan_id = uuid.uuid4()
        url = reverse("cod_location:schedule_list", args=[loan_id])
        self.assertEqual(resolve(url).func, views.schedule_list)

    def test_schedule_create_url(self):
        loan_id = uuid.uuid4()
        url = reverse("cod_location:schedule_create", args=[loan_id])
        self.assertEqual(resolve(url).func, views.schedule_create)

    def test_schedule_detail_url(self):
        pk = uuid.uuid4()
        url = reverse("cod_location:schedule_detail", args=[pk])
        self.assertEqual(resolve(url).func, views.schedule_detail)

    def test_schedule_update_url(self):
        pk = uuid.uuid4()
        url = reverse("cod_location:schedule_update", args=[pk])
        self.assertEqual(resolve(url).func, views.schedule_update)

    def test_schedule_delete_url(self):
        pk = uuid.uuid4()
        url = reverse("cod_location:schedule_delete", args=[pk])
        self.assertEqual(resolve(url).func, views.schedule_delete)

    def test_overpass_search_url(self):
        url = reverse("cod_location:overpass_search")
        self.assertEqual(resolve(url).func, views.overpass_search)

    def test_schedule_manage_url(self):
        loan_id = uuid.uuid4()
        url = reverse("cod_location:schedule_manage", args=[loan_id])
        self.assertEqual(resolve(url).func, views.schedule_manage_page)