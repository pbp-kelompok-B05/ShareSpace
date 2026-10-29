from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from review.models import Review
from review.tests.test_review_models import ReviewTestMixin

User = get_user_model()


class ReviewAdminTest(ReviewTestMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.admin_user = User.objects.create_superuser(
            username="reviewtest_admin", password="PasswordTest123."
        )

    def setUp(self):
        self.client.force_login(self.admin_user)
        self.changelist_url = reverse("admin:review_review_changelist")

    def run_action(self, action, reviews):
        return self.client.post(
            self.changelist_url,
            {"action": action, "_selected_action": [review.pk for review in reviews]},
            follow=True,
        )

    def test_changelist_and_search(self):
        self.make_review()
        response = self.client.get(self.changelist_url, {"q": "reviewtest_lender"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["cl"].result_count, 1)

    def test_hide_and_unhide_actions(self):
        review = self.make_review()
        self.run_action("hide_reviews", [review])
        review.refresh_from_db()
        self.assertTrue(review.is_hidden)
        self.run_action("unhide_reviews", [review])
        review.refresh_from_db()
        self.assertFalse(review.is_hidden)

    def test_review_content_is_read_only(self):
        review = self.make_review()
        response = self.client.get(reverse("admin:review_review_change", args=[review.pk]))
        form_fields = response.context["adminform"].form.fields
        for field in ("rating", "comment", "reviewer", "reviewee", "loan"):
            with self.subTest(field=field):
                self.assertNotIn(field, form_fields)
        self.assertIn("is_hidden", form_fields)

    def test_admin_cannot_add_or_delete_reviews(self):
        review = self.make_review()
        self.assertEqual(self.client.get(reverse("admin:review_review_add")).status_code, 403)
        self.assertEqual(
            self.client.get(reverse("admin:review_review_delete", args=[review.pk])).status_code,
            403,
        )
