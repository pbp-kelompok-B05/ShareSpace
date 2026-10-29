from unittest import mock

from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase

from review.htmx import is_htmx, render_list, wants_partial


class HtmxHelperTest(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_plain_request(self):
        request = self.factory.get("/")
        self.assertFalse(is_htmx(request))
        self.assertFalse(wants_partial(request))

    def test_htmx_request_wants_partial(self):
        request = self.factory.get("/", HTTP_HX_REQUEST="true")
        self.assertTrue(is_htmx(request))
        self.assertTrue(wants_partial(request))

    def test_history_restore_wants_full_page(self):
        # htmx 2 men-swap respons history-restore ke <body>.
        request = self.factory.get(
            "/", HTTP_HX_REQUEST="true", HTTP_HX_HISTORY_RESTORE_REQUEST="true"
        )
        self.assertTrue(is_htmx(request))
        self.assertFalse(wants_partial(request))

    @mock.patch("review.htmx.render", side_effect=lambda *args, **kwargs: HttpResponse())
    def test_render_list_picks_template_and_sets_vary(self, render):
        cases = [
            ({}, "full.html"),
            ({"HTTP_HX_REQUEST": "true"}, "partial.html"),
            ({"HTTP_HX_REQUEST": "true", "HTTP_HX_HISTORY_RESTORE_REQUEST": "true"}, "full.html"),
        ]
        for headers, expected in cases:
            with self.subTest(headers=headers):
                request = self.factory.get("/", **headers)
                response = render_list(request, "full.html", "partial.html", {"a": 1})
                render.assert_called_with(request, expected, {"a": 1})
                vary = {value.strip() for value in response["Vary"].split(",")}
                self.assertEqual(vary, {"HX-Request", "HX-History-Restore-Request"})
