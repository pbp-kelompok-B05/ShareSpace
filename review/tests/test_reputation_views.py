from django.contrib.auth import get_user_model
from django.template import Context, Template
from django.test import TestCase
from django.urls import reverse

from review.tests.test_review_models import ReviewTestMixin

User = get_user_model()

HTMX = {"HTTP_HX_REQUEST": "true"}


class ReputationDataMixin(ReviewTestMixin):
    def give_reviews(self, ratings, **kwargs):
        """Borrower menulis satu ulasan per transaksi selesai untuk lender."""
        return [
            self.make_review(loan=self.make_loan(), reviewer=self.borrower, rating=rating,
                             comment=f"Ulasan bintang {rating} nomor {index}.", **kwargs)
            for index, rating in enumerate(ratings)
        ]


class UserReviewsPageTest(ReputationDataMixin, TestCase):
    def setUp(self):
        self.client.force_login(self.outsider)
        self.url = reverse("review:user_reviews", args=[self.lender.username])

    def test_login_required(self):
        self.client.logout()
        response = self.client.get(self.url)
        login_url = reverse("authentication:login")
        self.assertRedirects(response, f"{login_url}?next={self.url}", fetch_redirect_response=False)

    def test_lists_visible_reviews_received(self):
        shown, hidden = self.give_reviews([5, 1])
        hidden.is_hidden = True
        hidden.save()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["page_obj"]), [shown])
        self.assertContains(response, shown.comment)
        self.assertNotContains(response, hidden.comment)

    def test_shows_reputation_summary(self):
        self.give_reviews([5, 4])
        response = self.client.get(self.url)
        reputation = response.context["reputation"]
        self.assertEqual(reputation.review_count, 2)
        self.assertContains(response, str(reputation.score))
        self.assertContains(response, reputation.level.label)

    def test_unknown_or_inactive_user_404(self):
        self.assertEqual(
            self.client.get(reverse("review:user_reviews", args=["tidak-ada"])).status_code, 404
        )
        self.lender.is_active = False
        self.lender.save()
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_empty_state(self):
        response = self.client.get(self.url)
        self.assertContains(response, "Belum ada ulasan")

    def test_load_more_link_and_partial_next_page(self):
        self.give_reviews([5, 4, 3, 5, 4, 2, 1])
        response = self.client.get(self.url)
        self.assertEqual(len(response.context["page_obj"]), 5)
        self.assertContains(response, "Muat lebih banyak")
        self.assertContains(response, 'hx-swap="outerHTML"')

        response = self.client.get(self.url, {"page": 2}, **HTMX)
        self.assertTemplateUsed(response, "review/partials/user_review_items.html")
        self.assertTemplateNotUsed(response, "base.html")
        self.assertEqual(len(response.context["page_obj"]), 2)
        self.assertNotContains(response, "Muat lebih banyak")

    def test_load_more_without_js_is_a_normal_link(self):
        self.give_reviews([5] * 6)
        response = self.client.get(self.url)
        self.assertContains(response, 'href="?page=2"')

    def test_query_count_does_not_grow_with_reviews(self):
        # sesi + user + target + 3 agregat reputasi + count halaman + isi halaman
        self.give_reviews([5, 4, 3])
        with self.assertNumQueries(8):
            self.client.get(self.url)
        self.give_reviews([2, 1, 5])
        with self.assertNumQueries(8):
            self.client.get(self.url)


class ReputationCardTagTest(ReputationDataMixin, TestCase):
    def render(self, target):
        template = Template("{% load review_tags %}{% reputation_card target %}")
        return template.render(Context({"target": target}))

    def test_new_user_card(self):
        html = self.render(self.outsider)
        self.assertIn("Pengguna baru", html)
        self.assertIn("Belum ada ulasan", html)

    def test_card_shows_score_average_and_count(self):
        self.give_reviews([5, 4])
        html = self.render(self.lender)
        self.assertIn("4,5", html)  # rata-rata dengan format Indonesia
        self.assertIn("2 ulasan", html)
        self.assertIn("Trust Score", html)

    def test_card_shows_latest_three_visible_reviews(self):
        reviews = self.give_reviews([5, 4, 3, 2])
        reviews[-1].is_hidden = True
        reviews[-1].save()
        html = self.render(self.lender)
        for review in reviews[:3]:
            self.assertIn(review.comment, html)
        self.assertNotIn(reviews[-1].comment, html)

    def test_card_links_to_all_reviews(self):
        self.give_reviews([5])
        self.assertIn(reverse("review:user_reviews", args=[self.lender.username]), self.render(self.lender))

    def test_comment_escaped(self):
        self.make_review(loan=self.make_loan(), reviewer=self.borrower, rating=5,
                         comment="<b onmouseover=alert(1)>hai</b>")
        html = self.render(self.lender)
        self.assertNotIn("<b onmouseover", html)

    def test_card_uses_four_queries(self):
        self.give_reviews([5, 4, 3, 2, 1])
        with self.assertNumQueries(4):
            self.render(self.lender)
