from django.test import TestCase

from review.models import Report
from review.tests.test_models import ReportTestMixin


class MyReportsAPITest(ReportTestMixin, TestCase):
    url = "/api/review/reports/"

    def setUp(self):
        self.client.force_login(self.reporter)

    def test_lists_only_reports_sent_by_authenticated_user(self):
        mine = self.make_report(admin_note="Laporan diterima.")
        self.make_report(reporter=self.other)
        self.make_report(reporter=self.other, target_item=None, target_user=self.reporter)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["results"][0]["id"], str(mine.pk))
        self.assertEqual(data["results"][0]["target_type"], "item")
        self.assertEqual(data["results"][0]["admin_note"], "Laporan diterima.")

    def test_filters_by_status(self):
        self.make_report()
        resolved = self.make_report(status=Report.Status.RESOLVED)

        response = self.client.get(self.url, {"status": Report.Status.RESOLVED})

        self.assertEqual(response.status_code, 200)
        self.assertEqual([row["id"] for row in response.json()["results"]], [str(resolved.pk)])

    def test_invalid_status_returns_400(self):
        response = self.client.get(self.url, {"status": "invalid"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("status", response.json())

    def test_returns_ten_reports_per_page_newest_first(self):
        oldest = self.make_report(status=Report.Status.RESOLVED)
        for _ in range(10):
            self.make_report(status=Report.Status.RESOLVED)

        response = self.client.get(self.url, {"page": 2})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 11)
        self.assertEqual([row["id"] for row in response.json()["results"]], [str(oldest.pk)])

    def test_requires_login(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_does_not_accept_post(self):
        self.assertEqual(self.client.post(self.url).status_code, 405)
