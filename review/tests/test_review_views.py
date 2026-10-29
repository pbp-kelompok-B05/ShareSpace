import uuid

from django.contrib.auth import get_user_model
from django.template import Context, Template
from django.test import RequestFactory, TestCase
from django.urls import reverse

from loans.models import LoanRequest
from review.models import Review
from review.tests.test_review_models import ReviewTestMixin

User = get_user_model()

HTMX = {"HTTP_HX_REQUEST": "true"}


class ReviewViewTestMixin(ReviewTestMixin):
    def setUp(self):
        self.client.force_login(self.borrower)
        self.loan = self.make_loan()

    def create_url(self, loan=None):
        return reverse("review:review_create", args=[(loan or self.loan).pk])

    def form_data(self, **kwargs):
        data = {"rating": 5, "comment": "Pemilik ramah, barang bersih dan sesuai foto."}
        data.update(kwargs)
        return data


class ReviewLoginRequiredTest(ReviewViewTestMixin, TestCase):
    def test_all_pages_redirect_anonymous_to_login(self):
        review = self.make_review(loan=self.loan)
        self.client.logout()
        login_url = reverse("authentication:login")
        for url in (
            self.create_url(),
            reverse("review:my_reviews"),
            reverse("review:review_update", args=[review.pk]),
            reverse("review:review_delete", args=[review.pk]),
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertRedirects(
                    response, f"{login_url}?next={url}", fetch_redirect_response=False
                )


class ReviewCreateTest(ReviewViewTestMixin, TestCase):
    def test_form_shows_loan_and_counterpart(self):
        response = self.client.get(self.create_url())
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "review/review_form.html")
        self.assertContains(response, self.item.name)
        self.assertContains(response, self.lender.username)
        self.assertContains(response, "pemilik barang")

    def test_star_rating_offers_one_to_five(self):
        response = self.client.get(self.create_url())
        for value in range(1, 6):
            with self.subTest(value=value):
                self.assertContains(response, f'type="radio" name="rating" value="{value}"')

    def test_borrower_creates_review_for_lender(self):
        response = self.client.post(self.create_url(), self.form_data(rating=4))
        review = Review.objects.get(loan=self.loan, reviewer=self.borrower)
        self.assertRedirects(
            response, reverse("loans:detail", args=[self.loan.pk]), fetch_redirect_response=False
        )
        self.assertEqual(review.reviewee, self.lender)
        self.assertEqual(review.rating, 4)
        self.assertEqual(review.reviewer_role, Review.Role.BORROWER)

    def test_lender_creates_review_for_borrower(self):
        self.client.force_login(self.lender)
        self.client.post(self.create_url(), self.form_data(rating=3))
        review = Review.objects.get(loan=self.loan, reviewer=self.lender)
        self.assertEqual(review.reviewee, self.borrower)
        self.assertEqual(review.reviewer_role, Review.Role.LENDER)

    def test_success_message(self):
        response = self.client.post(self.create_url(), self.form_data(), follow=True)
        self.assertContains(response, "Ulasan berhasil dikirim")

    def test_comment_is_optional(self):
        self.client.post(self.create_url(), self.form_data(comment=""))
        self.assertTrue(Review.objects.filter(loan=self.loan, reviewer=self.borrower).exists())

    def test_invalid_rating_rejected(self):
        for rating in ("0", "6", "x", ""):
            with self.subTest(rating=rating):
                response = self.client.post(self.create_url(), self.form_data(rating=rating))
                self.assertEqual(response.status_code, 200)
                self.assertIn("rating", response.context["form"].errors)
        self.assertFalse(Review.objects.filter(loan=self.loan).exists())

    def test_comment_too_long_rejected(self):
        response = self.client.post(self.create_url(), self.form_data(comment="a" * 1001))
        self.assertIn("comment", response.context["form"].errors)

    def test_posted_target_and_moderation_fields_ignored(self):
        self.client.post(
            self.create_url(),
            self.form_data(reviewee=self.outsider.pk, is_hidden="on", reviewer_role="lender"),
        )
        review = Review.objects.get(loan=self.loan, reviewer=self.borrower)
        self.assertEqual(review.reviewee, self.lender)
        self.assertFalse(review.is_hidden)
        self.assertEqual(review.reviewer_role, Review.Role.BORROWER)

    def test_outsider_forbidden(self):
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(self.create_url()).status_code, 403)
        self.assertEqual(self.client.post(self.create_url(), self.form_data()).status_code, 403)
        self.assertFalse(Review.objects.exists())

    def test_unfinished_loan_forbidden(self):
        loan = self.make_loan(status=LoanRequest.Status.BORROWED)
        self.assertEqual(self.client.get(self.create_url(loan)).status_code, 403)

    def test_unknown_loan_404(self):
        response = self.client.get(reverse("review:review_create", args=[uuid.uuid4()]))
        self.assertEqual(response.status_code, 404)

    def test_existing_review_redirects_to_edit(self):
        review = self.make_review(loan=self.loan)
        response = self.client.post(self.create_url(), self.form_data(rating=1), follow=True)
        self.assertRedirects(response, reverse("review:review_update", args=[review.pk]))
        self.assertContains(response, "sudah memberi ulasan")
        review.refresh_from_db()
        self.assertEqual(review.rating, 5)


class ReviewUpdateDeleteTest(ReviewViewTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.review = self.make_review(loan=self.loan, rating=5)
        self.update_url = reverse("review:review_update", args=[self.review.pk])
        self.delete_url = reverse("review:review_delete", args=[self.review.pk])

    def test_update_form_prefilled(self):
        response = self.client.get(self.update_url)
        self.assertEqual(response.context["form"].instance, self.review)
        self.assertContains(response, 'value="5" checked')

    def test_update_changes_rating_and_comment(self):
        response = self.client.post(self.update_url, self.form_data(rating=2, comment="Telat dibalas."))
        self.assertRedirects(response, reverse("review:my_reviews"), fetch_redirect_response=False)
        self.review.refresh_from_db()
        self.assertEqual(self.review.rating, 2)
        self.assertEqual(self.review.comment, "Telat dibalas.")

    def test_other_user_cannot_update_or_delete(self):
        self.client.force_login(self.lender)
        self.assertEqual(self.client.post(self.update_url, self.form_data()).status_code, 403)
        self.assertEqual(self.client.post(self.delete_url).status_code, 403)
        self.assertTrue(Review.objects.filter(pk=self.review.pk).exists())

    def test_hidden_review_locked(self):
        self.review.is_hidden = True
        self.review.save()
        self.assertEqual(self.client.get(self.update_url).status_code, 403)
        self.assertEqual(self.client.post(self.delete_url).status_code, 403)

    def test_delete_get_confirms_post_deletes(self):
        response = self.client.get(self.delete_url)
        self.assertTemplateUsed(response, "review/review_confirm_delete.html")
        self.assertTrue(Review.objects.filter(pk=self.review.pk).exists())
        response = self.client.post(self.delete_url, follow=True)
        self.assertRedirects(response, reverse("review:my_reviews"))
        self.assertContains(response, "Ulasan dihapus")
        self.assertFalse(Review.objects.filter(pk=self.review.pk).exists())

    def test_deleted_review_can_be_written_again(self):
        self.client.post(self.delete_url)
        self.assertTrue(Review.can_be_written(self.loan, self.borrower))

    def test_unknown_review_404(self):
        response = self.client.get(reverse("review:review_update", args=[uuid.uuid4()]))
        self.assertEqual(response.status_code, 404)


class MyReviewsTest(ReviewViewTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.url = reverse("review:my_reviews")
        self.written = self.make_review(loan=self.loan, reviewer=self.borrower, rating=5)
        self.received = self.make_review(loan=self.loan, reviewer=self.lender, rating=3,
                                         comment="Peminjam mengembalikan tepat waktu.")

    def test_written_tab_is_default(self):
        response = self.client.get(self.url)
        self.assertEqual(response.context["tab"], "written")
        self.assertEqual(list(response.context["page_obj"]), [self.written])

    def test_received_tab_lists_visible_reviews_about_me(self):
        response = self.client.get(self.url, {"tab": "received"})
        self.assertEqual(list(response.context["page_obj"]), [self.received])
        self.assertContains(response, "Peminjam mengembalikan tepat waktu.")

    def test_hidden_received_review_not_shown(self):
        self.received.is_hidden = True
        self.received.save()
        response = self.client.get(self.url, {"tab": "received"})
        self.assertEqual(list(response.context["page_obj"]), [])
        self.assertContains(response, "Belum ada ulasan")

    def test_hidden_written_review_shown_with_badge(self):
        self.written.is_hidden = True
        self.written.save()
        response = self.client.get(self.url)
        self.assertContains(response, "Disembunyikan admin")
        self.assertNotContains(response, reverse("review:review_update", args=[self.written.pk]))

    def test_unknown_tab_falls_back_to_written(self):
        response = self.client.get(self.url, {"tab": "hacked"})
        self.assertEqual(response.context["tab"], "written")

    def test_pending_reviews_list_completed_loans_without_my_review(self):
        pending_loan = self.make_loan()
        self.make_loan(status=LoanRequest.Status.REJECTED)
        response = self.client.get(self.url)
        self.assertEqual(list(response.context["pending_loans"]), [pending_loan])
        self.assertContains(response, self.create_url(pending_loan))

    def test_htmx_tab_switch_returns_partial(self):
        response = self.client.get(self.url, {"tab": "received"}, **HTMX)
        self.assertTemplateUsed(response, "review/partials/my_review_list.html")
        self.assertTemplateNotUsed(response, "base.html")
        self.assertIn("HX-Request", response["Vary"])

    def test_query_count_does_not_grow_with_reviews(self):
        for _ in range(3):
            loan = self.make_loan()
            self.make_review(loan=loan)
        with self.assertNumQueries(5):
            self.client.get(self.url)

    def test_comment_is_escaped(self):
        self.written.comment = "<script>alert(1)</script> barang oke"
        self.written.save()
        response = self.client.get(self.url)
        self.assertNotContains(response, "<script>alert(1)")


class ReviewActionTagTest(ReviewViewTestMixin, TestCase):
    """Template tag untuk tombol ulasan di halaman detail transaksi (modul loans)."""

    def render(self, user, loan):
        request = RequestFactory().get("/")
        request.user = user
        template = Template("{% load review_tags %}{% review_action loan %}")
        return template.render(Context({"loan": loan, "request": request, "user": user}))

    def test_shows_write_button_when_allowed(self):
        html = self.render(self.borrower, self.loan)
        self.assertIn(self.create_url(), html)
        self.assertIn("Beri ulasan", html)

    def test_shows_edit_link_after_reviewing(self):
        review = self.make_review(loan=self.loan)
        html = self.render(self.borrower, self.loan)
        self.assertIn(reverse("review:review_update", args=[review.pk]), html)
        self.assertNotIn("Beri ulasan", html)

    def test_renders_nothing_for_outsider_or_unfinished_loan(self):
        self.assertEqual(self.render(self.outsider, self.loan).strip(), "")
        loan = self.make_loan(status=LoanRequest.Status.BORROWED)
        self.assertEqual(self.render(self.borrower, loan).strip(), "")
