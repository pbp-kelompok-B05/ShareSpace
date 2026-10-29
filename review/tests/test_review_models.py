from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase

from items.models import Item
from loans.models import LoanRequest
from review.models import Review

User = get_user_model()


class ReviewTestMixin:
    """Helper pembuatan data; tidak berasumsi DB kosong (ada data seed)."""

    @classmethod
    def setUpTestData(cls):
        cls.lender = User.objects.create_user(
            username="reviewtest_lender", password="PasswordTest123."
        )
        cls.borrower = User.objects.create_user(
            username="reviewtest_borrower", password="PasswordTest123."
        )
        cls.outsider = User.objects.create_user(
            username="reviewtest_outsider", password="PasswordTest123."
        )
        cls.item = Item.objects.create(
            owner=cls.lender,
            name="Raket Badminton",
            description="Raket badminton Yonex, senar masih kencang dan grip baru.",
            category=Item.Category.SPORTS,
            condition=Item.Condition.GOOD,
        )

    def make_loan(self, status=LoanRequest.Status.COMPLETED, **kwargs):
        data = {
            "borrower": self.borrower,
            "item": self.item,
            "start_date": date.today() - timedelta(days=7),
            "due_date": date.today() - timedelta(days=2),
            "status": status,
        }
        data.update(kwargs)
        return LoanRequest.objects.create(**data)

    def make_review(self, loan=None, reviewer=None, **kwargs):
        review = Review.for_loan(loan or self.make_loan(), reviewer or self.borrower)
        review.rating = kwargs.pop("rating", 5)
        review.comment = kwargs.pop("comment", "Pemilik ramah dan barang sesuai foto.")
        for field, value in kwargs.items():
            setattr(review, field, value)
        review.full_clean()
        review.save()
        return review


class ReviewForLoanTest(ReviewTestMixin, TestCase):
    def test_borrower_reviews_lender(self):
        loan = self.make_loan()
        review = Review.for_loan(loan, self.borrower)
        self.assertEqual(review.reviewer, self.borrower)
        self.assertEqual(review.reviewee, self.lender)
        self.assertEqual(review.reviewer_role, Review.Role.BORROWER)
        self.assertEqual(review.loan, loan)

    def test_lender_reviews_borrower(self):
        review = Review.for_loan(self.make_loan(), self.lender)
        self.assertEqual(review.reviewee, self.borrower)
        self.assertEqual(review.reviewer_role, Review.Role.LENDER)

    def test_outsider_cannot_review(self):
        with self.assertRaises(ValidationError):
            Review.for_loan(self.make_loan(), self.outsider)

    def test_reviewee_follows_soft_deleted_item_owner(self):
        loan = self.make_loan()
        self.item.soft_delete()
        loan.refresh_from_db()
        review = Review.for_loan(loan, self.borrower)
        self.assertEqual(review.reviewee, self.lender)


class ReviewValidationTest(ReviewTestMixin, TestCase):
    def build(self, loan=None, reviewer=None, **kwargs):
        review = Review.for_loan(loan or self.make_loan(), reviewer or self.borrower)
        review.rating = kwargs.pop("rating", 4)
        review.comment = kwargs.pop("comment", "")
        for field, value in kwargs.items():
            setattr(review, field, value)
        return review

    def test_valid_review_passes(self):
        self.build().full_clean()

    def test_comment_is_optional(self):
        self.build(comment="").full_clean()

    def test_rating_must_be_between_one_and_five(self):
        for rating in (0, 6, -1):
            with self.subTest(rating=rating):
                with self.assertRaises(ValidationError) as ctx:
                    self.build(rating=rating).full_clean()
                self.assertIn("rating", ctx.exception.message_dict)

    def test_comment_maximum_length(self):
        with self.assertRaises(ValidationError) as ctx:
            self.build(comment="a" * 1001).full_clean()
        self.assertIn("comment", ctx.exception.message_dict)

    def test_only_completed_loans_can_be_reviewed(self):
        for status in (
            LoanRequest.Status.PENDING,
            LoanRequest.Status.APPROVED,
            LoanRequest.Status.BORROWED,
            LoanRequest.Status.REJECTED,
            LoanRequest.Status.CANCELLED,
        ):
            with self.subTest(status=status):
                loan = self.make_loan(status=status)
                with self.assertRaises(ValidationError):
                    self.build(loan=loan).full_clean()
                # loans hanya mengizinkan satu transaksi aktif per barang.
                loan.delete()

    def test_reviewee_must_be_counterpart(self):
        with self.assertRaises(ValidationError):
            self.build(reviewee=self.outsider).full_clean()

    def test_reviewer_swapped_to_outsider_is_invalid(self):
        review = self.build()
        review.reviewer = self.outsider
        with self.assertRaises(ValidationError):
            review.full_clean()

    def test_missing_loan_reports_field_error_only(self):
        review = Review(reviewer=self.borrower, reviewee=self.lender,
                        reviewer_role=Review.Role.BORROWER, rating=5)
        with self.assertRaises(ValidationError) as ctx:
            review.full_clean()
        self.assertIn("loan", ctx.exception.message_dict)

    def test_one_review_per_reviewer_per_loan(self):
        loan = self.make_loan()
        self.make_review(loan=loan)
        with self.assertRaises(ValidationError):
            self.build(loan=loan).full_clean()

    def test_both_parties_can_review_same_loan(self):
        loan = self.make_loan()
        self.make_review(loan=loan, reviewer=self.borrower)
        self.make_review(loan=loan, reviewer=self.lender, rating=4)
        self.assertEqual(loan.reviews.count(), 2)

    def test_existing_review_stays_valid_when_editing(self):
        review = self.make_review()
        review.comment = "Diperbarui: pengembalian juga tepat waktu."
        review.full_clean()


class ReviewDatabaseConstraintTest(ReviewTestMixin, TestCase):
    def raw_create(self, **kwargs):
        data = {
            "loan": self.make_loan(),
            "reviewer": self.borrower,
            "reviewee": self.lender,
            "reviewer_role": Review.Role.BORROWER,
            "rating": 5,
        }
        data.update(kwargs)
        return Review.objects.create(**data)

    def test_database_rejects_rating_out_of_range(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.raw_create(rating=9)

    def test_database_rejects_duplicate_review(self):
        loan = self.make_loan()
        self.raw_create(loan=loan)
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.raw_create(loan=loan)

    def test_database_rejects_self_review(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.raw_create(reviewee=self.borrower)


class ReviewBehaviourTest(ReviewTestMixin, TestCase):
    def test_defaults(self):
        review = self.make_review()
        self.assertFalse(review.is_hidden)
        self.assertEqual(len(str(review.pk)), 36)
        self.assertIsNotNone(review.created_at)

    def test_str_shows_rating_and_reviewee(self):
        review = self.make_review(rating=4)
        self.assertIn("4", str(review))
        self.assertIn(self.lender.username, str(review))

    def test_editable_only_by_reviewer(self):
        review = self.make_review()
        self.assertTrue(review.is_editable_by(self.borrower))
        self.assertFalse(review.is_editable_by(self.lender))
        self.assertFalse(review.is_editable_by(self.outsider))

    def test_hidden_review_not_editable(self):
        review = self.make_review(is_hidden=True)
        self.assertFalse(review.is_editable_by(self.borrower))

    def test_visible_queryset_excludes_hidden(self):
        shown = self.make_review()
        hidden = self.make_review(loan=shown.loan, reviewer=self.lender, is_hidden=True)
        visible = Review.objects.visible().filter(loan=shown.loan)
        self.assertIn(shown, visible)
        self.assertNotIn(hidden, visible)

    def test_ordering_newest_first(self):
        first = self.make_review()
        second = self.make_review(loan=self.make_loan())
        reviews = list(Review.objects.filter(reviewer=self.borrower))
        self.assertEqual(reviews, [second, first])

    def test_reviewer_with_review_cannot_be_hard_deleted(self):
        self.make_review()
        with self.assertRaises(ProtectedError):
            self.borrower.delete()


class CanReviewTest(ReviewTestMixin, TestCase):
    def test_participants_of_completed_loan_can_review(self):
        loan = self.make_loan()
        self.assertTrue(Review.can_be_written(loan, self.borrower))
        self.assertTrue(Review.can_be_written(loan, self.lender))

    def test_outsider_cannot(self):
        self.assertFalse(Review.can_be_written(self.make_loan(), self.outsider))

    def test_not_completed_cannot(self):
        loan = self.make_loan(status=LoanRequest.Status.BORROWED)
        self.assertFalse(Review.can_be_written(loan, self.borrower))

    def test_already_reviewed_cannot(self):
        loan = self.make_loan()
        self.make_review(loan=loan)
        self.assertFalse(Review.can_be_written(loan, self.borrower))
        self.assertTrue(Review.can_be_written(loan, self.lender))

    def test_anonymous_cannot(self):
        from django.contrib.auth.models import AnonymousUser

        self.assertFalse(Review.can_be_written(self.make_loan(), AnonymousUser()))
