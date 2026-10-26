from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from review.models import Report
from review.tests.test_models import ReportTestMixin

User = get_user_model()


class ReportAdminTest(ReportTestMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.admin_user = User.objects.create_superuser(
            username="reporttest_admin", password="PasswordTest123."
        )

    def setUp(self):
        self.client.force_login(self.admin_user)
        self.changelist_url = reverse("admin:review_report_changelist")

    def run_action(self, action, reports):
        return self.client.post(
            self.changelist_url,
            {"action": action, "_selected_action": [report.pk for report in reports]},
            follow=True,
        )

    def test_changelist_loads(self):
        self.make_report()
        response = self.client.get(self.changelist_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Barang tidak sesuai deskripsi")

    def test_search_by_reporter_username(self):
        self.make_report()
        response = self.client.get(self.changelist_url, {"q": "reporttest_reporter"})
        self.assertEqual(response.context["cl"].result_count, 1)

    def test_change_page_loads(self):
        report = self.make_report()
        response = self.client.get(reverse("admin:review_report_change", args=[report.pk]))
        self.assertEqual(response.status_code, 200)

    def test_mark_reviewing_action(self):
        report = self.make_report()
        self.run_action("mark_reviewing", [report])
        report.refresh_from_db()
        self.assertEqual(report.status, Report.Status.REVIEWING)

    def test_mark_resolved_action(self):
        report = self.make_report()
        report.transition_to(Report.Status.REVIEWING)
        self.run_action("mark_resolved", [report])
        report.refresh_from_db()
        self.assertEqual(report.status, Report.Status.RESOLVED)

    def test_mark_rejected_action(self):
        report = self.make_report()
        self.run_action("mark_rejected", [report])
        report.refresh_from_db()
        self.assertEqual(report.status, Report.Status.REJECTED)

    def test_invalid_transition_is_skipped_with_warning(self):
        report = self.make_report()
        response = self.run_action("mark_resolved", [report])
        report.refresh_from_db()
        self.assertEqual(report.status, Report.Status.PENDING)
        self.assertContains(response, "1 laporan dilewati")

    def test_status_and_user_content_are_read_only(self):
        report = self.make_report()
        response = self.client.get(reverse("admin:review_report_change", args=[report.pk]))
        form_fields = response.context["adminform"].form.fields
        for field in ("status", "reporter", "description", "reason"):
            with self.subTest(field=field):
                self.assertNotIn(field, form_fields)
        self.assertIn("admin_note", form_fields)

    def test_admin_cannot_add_or_delete_reports(self):
        report = self.make_report()
        self.assertEqual(self.client.get(reverse("admin:review_report_add")).status_code, 403)
        self.assertEqual(
            self.client.get(reverse("admin:review_report_delete", args=[report.pk])).status_code,
            403,
        )

    def test_regular_user_cannot_access_admin(self):
        self.client.force_login(self.reporter)
        response = self.client.get(self.changelist_url)
        self.assertEqual(response.status_code, 302)
