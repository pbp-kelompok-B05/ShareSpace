from django.test import TestCase

from review.tests.test_reputation_views import ReputationDataMixin


class UserReviewAPITest(ReputationDataMixin, TestCase):
    def setUp(self):
        self.base_url = f"/api/review/users/{self.lender.username}/"
        self.client.force_login(self.outsider)

    def test_reviews_return_only_visible_received_reviews(self):
        shown, hidden = self.give_reviews([5, 1])
        hidden.is_hidden = True
        hidden.save(update_fields=["is_hidden"])

        response = self.client.get(f"{self.base_url}reviews/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"], [{
            "id": str(shown.pk),
            "reviewer": self.borrower.username,
            "rating": 5,
            "comment": shown.comment,
            "created_at": shown.created_at.isoformat().replace("+00:00", "Z"),
        }])

    def test_reviews_are_paginated(self):
        self.give_reviews([5] * 6)
        response = self.client.get(f"{self.base_url}reviews/", {"page": 2})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 6)
        self.assertEqual(len(response.json()["results"]), 1)
        self.assertIsNone(response.json()["next"])

    def test_reputation_reuses_visible_ratings(self):
        hidden, _ = self.give_reviews([1, 5])
        hidden.is_hidden = True
        hidden.save(update_fields=["is_hidden"])

        response = self.client.get(f"{self.base_url}reputation/")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["username"], self.lender.username)
        self.assertEqual(data["review_count"], 1)
        self.assertEqual(data["average_rating"], 5)
        self.assertEqual(data["completed_count"], 2)
        self.assertEqual(data["score"], 53)
        self.assertEqual(data["level"]["key"], "fair")
        self.assertEqual(data["distribution"][0], {"stars": 5, "count": 1, "percent": 100})
        self.assertNotIn("resolved_report_count", data)

    def test_endpoints_require_login(self):
        self.client.logout()
        for endpoint in ("reviews/", "reputation/"):
            with self.subTest(endpoint=endpoint):
                response = self.client.get(self.base_url + endpoint)
                self.assertEqual(response.status_code, 403)
                self.assertIn("detail", response.json())

    def test_endpoints_return_404_for_inactive_user(self):
        self.lender.is_active = False
        self.lender.save(update_fields=["is_active"])
        for endpoint in ("reviews/", "reputation/"):
            with self.subTest(endpoint=endpoint):
                response = self.client.get(self.base_url + endpoint)
                self.assertEqual(response.status_code, 404)
                self.assertIn("detail", response.json())
