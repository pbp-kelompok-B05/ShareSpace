from django.test import TestCase
from django.urls import reverse

from review.models import Report
from review.tests.test_views import ReportViewTestMixin

HTMX = {"HTTP_HX_REQUEST": "true"}


class MyReportsHtmxTest(ReportViewTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.url = reverse("review:my_reports")

    def test_filter_form_updates_list_without_reload(self):
        response = self.client.get(self.url)
        self.assertContains(response, f'hx-get="{self.url}"')
        self.assertContains(response, 'hx-target="#report-list"')
        self.assertContains(response, 'hx-push-url="true"')

    def test_htmx_request_returns_list_partial_only(self):
        self.make_report()
        response = self.client.get(self.url, {"status": Report.Status.PENDING}, **HTMX)
        self.assertTemplateUsed(response, "review/partials/my_report_list.html")
        self.assertTemplateNotUsed(response, "base.html")
        self.assertContains(response, "Barang tidak sesuai deskripsi")

    def test_htmx_empty_filter_returns_empty_state(self):
        response = self.client.get(self.url, {"status": Report.Status.RESOLVED}, **HTMX)
        self.assertContains(response, "Tidak ada laporan dengan status ini")

    def test_pagination_links_target_list(self):
        for _ in range(11):
            self.make_report(status=Report.Status.REJECTED)
        response = self.client.get(self.url, **HTMX)
        self.assertContains(response, 'hx-target="#report-list"', count=2)  # halaman 2 + "Selanjutnya"


class ReportFormEnhancementTest(ReportViewTestMixin, TestCase):
    def test_description_has_live_character_counter(self):
        response = self.client.get(self.item_create_url())
        self.assertContains(response, "data-char-counter")
        self.assertContains(response, 'data-min-length="20"')
        self.assertContains(response, 'maxlength="1000"')
        self.assertContains(response, "review/js/char-counter.js")

    def test_counter_script_not_inline(self):
        response = self.client.get(self.item_create_url())
        self.assertNotContains(response, "<script>")


class CancelDialogTest(ReportViewTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.report = self.make_report()
        self.detail_url = reverse("review:report_detail", args=[self.report.pk])
        self.delete_url = reverse("review:report_delete", args=[self.report.pk])

    def test_detail_has_confirmation_dialog_posting_to_delete(self):
        response = self.client.get(self.detail_url)
        self.assertContains(response, "<dialog")
        self.assertContains(response, f'action="{self.delete_url}"')
        self.assertContains(response, "csrfmiddlewaretoken")
        self.assertContains(response, "review/js/confirm-dialog.js")

    def test_cancel_link_falls_back_to_confirmation_page(self):
        response = self.client.get(self.detail_url)
        self.assertContains(response, f'href="{self.delete_url}"')
        self.assertContains(response, 'data-confirm-dialog="cancel-report-dialog"')

    def test_dialog_hidden_when_report_not_editable(self):
        self.report.transition_to(Report.Status.REVIEWING)
        response = self.client.get(self.detail_url)
        self.assertNotContains(response, "<dialog")
        self.assertNotContains(response, "review/js/confirm-dialog.js")

    def test_dialog_post_still_deletes(self):
        response = self.client.post(self.delete_url, follow=True)
        self.assertRedirects(response, reverse("review:my_reports"))
        self.assertFalse(Report.objects.filter(pk=self.report.pk).exists())


class ReviewStaticAssetsTest(TestCase):
    def test_static_files_are_discoverable(self):
        from django.contrib.staticfiles import finders

        for path in (
            "review/js/char-counter.js",
            "review/js/confirm-dialog.js",
            "review/css/review.css",
        ):
            with self.subTest(path=path):
                self.assertIsNotNone(finders.find(path))
