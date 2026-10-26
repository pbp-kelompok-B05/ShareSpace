import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from items.models import Item
from review.models import Report
from review.tests.test_models import VALID_DESCRIPTION, ReportTestMixin

User = get_user_model()

HTMX = {"HTTP_HX_REQUEST": "true"}


class ModerationTestMixin(ReportTestMixin):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.staff = User.objects.create_user(
            username="reporttest_staff", password="PasswordTest123.", is_staff=True
        )

    def setUp(self):
        self.client.force_login(self.staff)
        self.list_url = reverse("review:report_list")

    def moderate_url(self, report):
        return reverse("review:report_moderate", args=[report.pk])


class ModerationAccessTest(ModerationTestMixin, TestCase):
    def test_anonymous_redirected_to_login(self):
        self.client.logout()
        report = self.make_report()
        login_url = reverse("authentication:login")
        for url in (self.list_url, self.moderate_url(report)):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertRedirects(
                    response, f"{login_url}?next={url}", fetch_redirect_response=False
                )

    def test_regular_user_forbidden(self):
        report = self.make_report()
        self.client.force_login(self.reporter)
        self.assertEqual(self.client.get(self.list_url).status_code, 403)
        response = self.client.post(
            self.moderate_url(report), {"status": Report.Status.REVIEWING}
        )
        self.assertEqual(response.status_code, 403)
        report.refresh_from_db()
        self.assertEqual(report.status, Report.Status.PENDING)

    def test_moderate_rejects_get(self):
        report = self.make_report()
        self.assertEqual(self.client.get(self.moderate_url(report)).status_code, 405)

    def test_navbar_shows_reports_link_for_staff(self):
        response = self.client.get(self.list_url)
        self.assertContains(response, f'href="{self.list_url}"')


class ModerationListTest(ModerationTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.item_report = self.make_report()
        self.user_report = self.make_report(
            reporter=self.other,
            target_item=None,
            target_user=self.owner,
            reason=Report.Reason.UNRESPONSIVE,
            description="Pemilik barang tidak membalas pesan selama tiga hari.",
        )
        self.closed_report = self.make_report(status=Report.Status.RESOLVED)

    def results(self, **params):
        response = self.client.get(self.list_url, params)
        self.assertEqual(response.status_code, 200)
        return response, list(response.context["page_obj"])

    def test_lists_reports_from_all_reporters(self):
        response, reports = self.results()
        self.assertTemplateUsed(response, "review/report_list.html")
        self.assertCountEqual(reports, [self.item_report, self.user_report, self.closed_report])

    def test_filter_by_status(self):
        _, reports = self.results(status=Report.Status.RESOLVED)
        self.assertEqual(reports, [self.closed_report])

    def test_filter_by_reason(self):
        _, reports = self.results(reason=Report.Reason.UNRESPONSIVE)
        self.assertEqual(reports, [self.user_report])

    def test_unknown_filters_are_ignored(self):
        response, reports = self.results(status="hacked", reason="spam")
        self.assertEqual(len(reports), 3)
        self.assertEqual(response.context["current_status"], "")
        self.assertEqual(response.context["current_reason"], "")

    def test_search_by_reporter_target_item_and_description(self):
        cases = {
            "reporttest_other": [self.user_report],
            "Bor Listrik": [self.item_report, self.closed_report],
            "tiga hari": [self.user_report],
        }
        for query, expected in cases.items():
            with self.subTest(query=query):
                _, reports = self.results(q=query)
                self.assertCountEqual(reports, expected)

    def test_search_by_reported_username(self):
        _, reports = self.results(q="reporttest_owner")
        self.assertIn(self.user_report, reports)

    def test_status_counts_cover_all_reports(self):
        response, _ = self.results(status=Report.Status.PENDING)
        counts = response.context["status_counts"]
        self.assertEqual(counts[Report.Status.PENDING], 2)
        self.assertEqual(counts[Report.Status.RESOLVED], 1)
        self.assertEqual(counts[Report.Status.REVIEWING], 0)

    def test_empty_result_shows_empty_state(self):
        response, _ = self.results(q="tidak-ada-yang-cocok")
        self.assertContains(response, "Tidak ada laporan yang cocok")

    def test_paginates_fifteen_per_page(self):
        for _ in range(15):
            self.make_report(status=Report.Status.REJECTED)
        _, reports = self.results()
        self.assertEqual(len(reports), 15)
        _, reports = self.results(page=2)
        self.assertEqual(len(reports), 3)

    def test_query_count_does_not_grow_with_reports(self):
        extra_item = Item.objects.create(
            owner=self.other,
            name="Tenda Kemah",
            description="Tenda kemah kapasitas empat orang, lengkap dengan pasak.",
            category=Item.Category.OUTDOOR,
            condition=Item.Condition.GOOD,
        )
        for _ in range(3):
            self.make_report(target_item=extra_item, status=Report.Status.REJECTED)
        with self.assertNumQueries(5):
            self.client.get(self.list_url)

    def test_htmx_request_returns_list_partial_only(self):
        response = self.client.get(self.list_url, {"status": Report.Status.PENDING}, **HTMX)
        self.assertTemplateUsed(response, "review/partials/moderation_list.html")
        self.assertTemplateNotUsed(response, "base.html")

    def test_only_valid_transition_buttons_rendered(self):
        button = 'type="submit" name="status" value="{}"'
        response, _ = self.results(status=Report.Status.RESOLVED)
        self.assertNotContains(response, button.format("reviewing"))
        response, _ = self.results(status=Report.Status.PENDING)
        self.assertContains(response, button.format("reviewing"))
        self.assertNotContains(response, button.format("resolved"))

    def test_user_content_is_escaped(self):
        self.make_report(
            reporter=self.owner,
            target_item=None,
            target_user=self.other,
            description="<img src=x onerror=alert(1)> pengguna kasar saat COD",
        )
        response, _ = self.results()
        self.assertNotContains(response, "<img src=x")


class ModerateActionTest(ModerationTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.report = self.make_report()
        self.url = self.moderate_url(self.report)

    def toast(self, response):
        return json.loads(response["HX-Trigger"])["showToast"]

    def test_htmx_transition_updates_status_and_note(self):
        response = self.client.post(
            self.url,
            {"status": Report.Status.REVIEWING, "admin_note": "Sedang menghubungi pemilik."},
            **HTMX,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "review/partials/moderation_row.html")
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, Report.Status.REVIEWING)
        self.assertEqual(self.report.admin_note, "Sedang menghubungi pemilik.")
        self.assertEqual(self.toast(response)["level"], "success")
        self.assertContains(response, "Ditinjau")

    def test_note_only_update_keeps_status(self):
        response = self.client.post(self.url, {"admin_note": "Butuh bukti foto."}, **HTMX)
        self.assertEqual(response.status_code, 200)
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, Report.Status.PENDING)
        self.assertEqual(self.report.admin_note, "Butuh bukti foto.")

    def test_invalid_transition_returns_400_with_toast(self):
        response = self.client.post(self.url, {"status": Report.Status.RESOLVED}, **HTMX)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.toast(response)["level"], "error")
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, Report.Status.PENDING)

    def test_unknown_status_returns_400(self):
        response = self.client.post(self.url, {"status": "deleted"}, **HTMX)
        self.assertEqual(response.status_code, 400)

    def test_note_too_long_returns_400(self):
        response = self.client.post(self.url, {"admin_note": "a" * 1001}, **HTMX)
        self.assertEqual(response.status_code, 400)
        self.report.refresh_from_db()
        self.assertEqual(self.report.admin_note, "")

    def test_without_htmx_redirects_with_message(self):
        response = self.client.post(
            self.url, {"status": Report.Status.REJECTED}, follow=True
        )
        self.assertRedirects(response, self.list_url)
        self.assertContains(response, "Status laporan diubah ke Ditolak")
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, Report.Status.REJECTED)

    def test_without_htmx_invalid_transition_redirects_with_error(self):
        response = self.client.post(self.url, {"status": Report.Status.RESOLVED}, follow=True)
        self.assertRedirects(response, self.list_url)
        self.assertContains(response, "tidak dapat diubah")

    def test_without_htmx_returns_to_safe_next_url(self):
        next_url = f"{self.list_url}?status=pending"
        response = self.client.post(
            self.url, {"status": Report.Status.REVIEWING, "next": next_url}
        )
        self.assertRedirects(response, next_url, fetch_redirect_response=False)

    def test_external_next_url_is_ignored(self):
        response = self.client.post(
            self.url, {"status": Report.Status.REVIEWING, "next": "https://evil.example/"}
        )
        self.assertRedirects(response, self.list_url, fetch_redirect_response=False)

    def test_unknown_report_returns_404(self):
        self.report.delete()
        self.assertEqual(self.client.post(self.url, {"admin_note": "x"}).status_code, 404)


class StaffReportDetailTest(ModerationTestMixin, TestCase):
    def test_staff_back_link_points_to_dashboard(self):
        report = self.make_report(description=VALID_DESCRIPTION)
        response = self.client.get(reverse("review:report_detail", args=[report.pk]))
        self.assertContains(response, "Dashboard laporan")
        self.assertContains(response, self.reporter.username)
