import uuid

from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase
from django.urls import reverse

from review.models import Report
from review.tests.test_models import VALID_DESCRIPTION, ReportTestMixin

User = get_user_model()


class ReportViewTestMixin(ReportTestMixin):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.staff = User.objects.create_user(
            username="reporttest_staff", password="PasswordTest123.", is_staff=True
        )

    def setUp(self):
        self.client.force_login(self.reporter)

    def item_create_url(self, item=None):
        return reverse("review:report_item_create", args=[(item or self.item).pk])

    def user_create_url(self, user=None):
        return reverse("review:report_user_create", args=[(user or self.other).username])

    def form_data(self, **kwargs):
        data = {"reason": Report.Reason.ITEM_MISMATCH, "description": VALID_DESCRIPTION}
        data.update(kwargs)
        return data


class LoginRequiredTest(ReportViewTestMixin, TestCase):
    def test_all_pages_redirect_anonymous_to_login(self):
        self.client.logout()
        report = self.make_report()
        urls = [
            reverse("review:my_reports"),
            self.item_create_url(),
            self.user_create_url(),
            reverse("review:report_detail", args=[report.pk]),
            reverse("review:report_update", args=[report.pk]),
            reverse("review:report_delete", args=[report.pk]),
        ]
        login_url = reverse("authentication:login")
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertRedirects(
                    response, f"{login_url}?next={url}", fetch_redirect_response=False
                )


class ReportCreateTest(ReportViewTestMixin, TestCase):
    def test_item_form_shows_target(self):
        response = self.client.get(self.item_create_url())
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "review/report_form.html")
        self.assertContains(response, self.item.name)

    def test_user_form_shows_target(self):
        response = self.client.get(self.user_create_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.other.username)

    def test_create_item_report(self):
        response = self.client.post(self.item_create_url(), self.form_data())
        report = Report.objects.get(reporter=self.reporter, target_item=self.item)
        self.assertRedirects(response, reverse("review:report_detail", args=[report.pk]))
        self.assertEqual(report.status, Report.Status.PENDING)
        self.assertIsNone(report.target_user)

    def test_create_user_report(self):
        self.client.post(
            self.user_create_url(), self.form_data(reason=Report.Reason.UNRESPONSIVE)
        )
        report = Report.objects.get(reporter=self.reporter, target_user=self.other)
        self.assertIsNone(report.target_item)
        self.assertEqual(report.reason, Report.Reason.UNRESPONSIVE)

    def test_success_message_shown(self):
        response = self.client.post(self.item_create_url(), self.form_data(), follow=True)
        self.assertContains(response, "Laporan berhasil dikirim")

    def test_invalid_form_shows_errors_and_creates_nothing(self):
        response = self.client.post(self.item_create_url(), self.form_data(description="pendek"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertFalse(Report.objects.filter(reporter=self.reporter).exists())

    def test_posted_status_and_target_are_ignored(self):
        self.client.post(
            self.item_create_url(),
            self.form_data(status=Report.Status.RESOLVED, target_user=self.other.pk),
        )
        report = Report.objects.get(reporter=self.reporter)
        self.assertEqual(report.status, Report.Status.PENDING)
        self.assertIsNone(report.target_user)

    def test_cannot_report_own_item(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(self.item_create_url()).status_code, 403)
        self.assertEqual(self.client.post(self.item_create_url(), self.form_data()).status_code, 403)
        self.assertFalse(Report.objects.exists())

    def test_cannot_report_self(self):
        response = self.client.get(self.user_create_url(self.reporter))
        self.assertEqual(response.status_code, 403)

    def test_deleted_item_returns_404(self):
        self.item.soft_delete()
        self.assertEqual(self.client.get(self.item_create_url()).status_code, 404)

    def test_unknown_or_inactive_user_returns_404(self):
        self.assertEqual(
            self.client.get(reverse("review:report_user_create", args=["tidak-ada"])).status_code,
            404,
        )
        self.other.is_active = False
        self.other.save()
        self.assertEqual(self.client.get(self.user_create_url()).status_code, 404)

    def test_active_duplicate_redirects_to_existing_report(self):
        existing = self.make_report()
        response = self.client.post(self.item_create_url(), self.form_data(), follow=True)
        self.assertRedirects(response, reverse("review:report_detail", args=[existing.pk]))
        self.assertContains(response, "masih punya laporan aktif")
        self.assertEqual(Report.objects.filter(reporter=self.reporter).count(), 1)


class MyReportsTest(ReportViewTestMixin, TestCase):
    url = None

    def setUp(self):
        super().setUp()
        self.url = reverse("review:my_reports")

    def test_lists_only_own_reports(self):
        mine = self.make_report()
        others = self.make_report(reporter=self.other)
        response = self.client.get(self.url)
        reports = list(response.context["page_obj"])
        self.assertIn(mine, reports)
        self.assertNotIn(others, reports)

    def test_empty_state(self):
        response = self.client.get(self.url)
        self.assertContains(response, "Belum ada laporan")

    def test_filter_by_status(self):
        pending = self.make_report()
        rejected = self.make_report(
            target_item=None, target_user=self.other, status=Report.Status.REJECTED
        )
        response = self.client.get(self.url, {"status": Report.Status.REJECTED})
        reports = list(response.context["page_obj"])
        self.assertEqual(reports, [rejected])
        self.assertNotIn(pending, reports)
        self.assertEqual(response.context["current_status"], Report.Status.REJECTED)

    def test_unknown_status_filter_is_ignored(self):
        self.make_report()
        response = self.client.get(self.url, {"status": "hacked"})
        self.assertEqual(response.context["current_status"], "")
        self.assertEqual(len(response.context["page_obj"]), 1)

    def test_paginates_ten_per_page(self):
        for _ in range(11):
            self.make_report(status=Report.Status.REJECTED)
        response = self.client.get(self.url)
        self.assertEqual(len(response.context["page_obj"]), 10)
        response = self.client.get(self.url, {"page": 2})
        self.assertEqual(len(response.context["page_obj"]), 1)

    def test_query_count_does_not_grow_with_reports(self):
        for _ in range(3):
            self.make_report(status=Report.Status.REJECTED)
        self.make_report(target_item=None, target_user=self.other)
        with self.assertNumQueries(4):
            self.client.get(self.url)


class ReportDetailTest(ReportViewTestMixin, TestCase):
    def test_reporter_sees_report_and_admin_note(self):
        report = self.make_report(admin_note="Pemilik barang sudah dihubungi.")
        response = self.client.get(reverse("review:report_detail", args=[report.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, VALID_DESCRIPTION)
        self.assertContains(response, "Pemilik barang sudah dihubungi.")

    def test_staff_can_view(self):
        report = self.make_report()
        self.client.force_login(self.staff)
        response = self.client.get(reverse("review:report_detail", args=[report.pk]))
        self.assertEqual(response.status_code, 200)

    def test_other_user_forbidden(self):
        report = self.make_report()
        self.client.force_login(self.other)
        response = self.client.get(reverse("review:report_detail", args=[report.pk]))
        self.assertEqual(response.status_code, 403)

    def test_unknown_report_404(self):
        response = self.client.get(reverse("review:report_detail", args=[uuid.uuid4()]))
        self.assertEqual(response.status_code, 404)

    def test_edit_actions_only_while_pending(self):
        report = self.make_report()
        url = reverse("review:report_detail", args=[report.pk])
        self.assertContains(self.client.get(url), reverse("review:report_update", args=[report.pk]))
        report.transition_to(Report.Status.REVIEWING)
        self.assertNotContains(
            self.client.get(url), reverse("review:report_update", args=[report.pk])
        )

    def test_description_is_escaped(self):
        report = self.make_report(description="<script>alert('xss')</script> barang palsu sekali")
        response = self.client.get(reverse("review:report_detail", args=[report.pk]))
        self.assertNotContains(response, "<script>alert")
        self.assertContains(response, "&lt;script&gt;")


class ReportUpdateTest(ReportViewTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.report = self.make_report()
        self.url = reverse("review:report_update", args=[self.report.pk])

    def test_form_prefilled(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["form"].instance, self.report)

    def test_update_changes_reason_and_description(self):
        new_description = "Barang ternyata tidak lengkap, charger tidak disertakan."
        response = self.client.post(
            self.url, self.form_data(reason=Report.Reason.ITEM_DAMAGED, description=new_description)
        )
        self.assertRedirects(response, reverse("review:report_detail", args=[self.report.pk]))
        self.report.refresh_from_db()
        self.assertEqual(self.report.reason, Report.Reason.ITEM_DAMAGED)
        self.assertEqual(self.report.description, new_description)

    def test_other_user_forbidden(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.post(self.url, self.form_data()).status_code, 403)

    def test_cannot_edit_after_review_started(self):
        self.report.transition_to(Report.Status.REVIEWING)
        self.assertEqual(self.client.post(self.url, self.form_data()).status_code, 403)

    def test_can_edit_after_item_soft_deleted(self):
        self.item.soft_delete()
        response = self.client.post(self.url, self.form_data())
        self.assertEqual(response.status_code, 302)


class ReportDeleteTest(ReportViewTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.report = self.make_report()
        self.url = reverse("review:report_delete", args=[self.report.pk])

    def test_get_shows_confirmation_without_deleting(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "review/report_confirm_delete.html")
        self.assertTrue(Report.objects.filter(pk=self.report.pk).exists())

    def test_post_deletes_and_redirects(self):
        response = self.client.post(self.url, follow=True)
        self.assertRedirects(response, reverse("review:my_reports"))
        self.assertContains(response, "Laporan dibatalkan")
        self.assertFalse(Report.objects.filter(pk=self.report.pk).exists())

    def test_other_user_forbidden(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(self.url).status_code, 403)
        self.assertTrue(Report.objects.filter(pk=self.report.pk).exists())

    def test_cannot_delete_after_review_started(self):
        self.report.transition_to(Report.Status.REVIEWING)
        self.assertEqual(self.client.post(self.url).status_code, 403)
        self.assertTrue(Report.objects.filter(pk=self.report.pk).exists())


class ReportLinkPartialTest(ReportViewTestMixin, TestCase):
    """Partial yang dipakai modul lain untuk menampilkan tombol "Laporkan"."""

    def render(self, user, **context):
        request = RequestFactory().get("/")
        request.user = user
        return render_to_string(
            "review/partials/report_link.html", {"user": user, **context}, request=request
        )

    def test_item_link_for_other_user(self):
        html = self.render(self.reporter, item=self.item)
        self.assertIn(self.item_create_url(), html)

    def test_hidden_for_item_owner(self):
        self.assertNotIn("Laporkan", self.render(self.owner, item=self.item))

    def test_user_link_and_hidden_for_self(self):
        self.assertIn(self.user_create_url(), self.render(self.reporter, target_user=self.other))
        self.assertNotIn("Laporkan", self.render(self.other, target_user=self.other))
