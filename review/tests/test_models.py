from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase

from items.models import Item
from review.models import Report

User = get_user_model()

VALID_DESCRIPTION = "Barang yang diterima berbeda dengan foto di katalog."


class ReportTestMixin:
    """Helper pembuatan data; tidak berasumsi DB kosong (ada data seed)."""

    @classmethod
    def setUpTestData(cls):
        cls.reporter = User.objects.create_user(
            username="reporttest_reporter", password="PasswordTest123."
        )
        cls.owner = User.objects.create_user(
            username="reporttest_owner", password="PasswordTest123."
        )
        cls.other = User.objects.create_user(
            username="reporttest_other", password="PasswordTest123."
        )
        cls.item = Item.objects.create(
            owner=cls.owner,
            name="Bor Listrik",
            description="Bor listrik 500 watt lengkap dengan mata bor kayu.",
            category=Item.Category.HOUSEHOLD,
            condition=Item.Condition.GOOD,
        )

    def report_data(self, **kwargs):
        data = {
            "reporter": self.reporter,
            "target_item": self.item,
            "reason": Report.Reason.ITEM_MISMATCH,
            "description": VALID_DESCRIPTION,
        }
        data.update(kwargs)
        return data

    def make_report(self, **kwargs):
        return Report.objects.create(**self.report_data(**kwargs))

    def build_report(self, **kwargs):
        """Instance belum disimpan, untuk menguji full_clean()."""
        return Report(**self.report_data(**kwargs))

    def assertInvalid(self, field, **kwargs):
        with self.assertRaises(ValidationError) as ctx:
            self.build_report(**kwargs).full_clean()
        self.assertIn(field, ctx.exception.message_dict)


class ReportDefaultsTest(ReportTestMixin, TestCase):
    def test_default_values(self):
        report = self.make_report()
        self.assertEqual(report.status, Report.Status.PENDING)
        self.assertEqual(report.admin_note, "")
        self.assertIsNotNone(report.created_at)
        self.assertIsNotNone(report.updated_at)

    def test_primary_key_is_uuid(self):
        report = self.make_report()
        self.assertEqual(len(str(report.pk)), 36)

    def test_str_contains_reason_label(self):
        report = self.make_report()
        self.assertIn("Barang tidak sesuai deskripsi", str(report))

    def test_ordering_newest_first(self):
        first = self.make_report()
        second = self.make_report(
            target_item=None, target_user=self.other, reason=Report.Reason.UNRESPONSIVE
        )
        reports = list(Report.objects.filter(reporter=self.reporter))
        self.assertEqual(reports, [second, first])

    def test_status_labels_follow_spec(self):
        self.assertEqual(
            [label for _, label in Report.Status.choices],
            ["Menunggu", "Ditinjau", "Selesai", "Ditolak"],
        )


class ReportTargetTest(ReportTestMixin, TestCase):
    def test_item_target(self):
        report = self.make_report()
        self.assertEqual(report.target, self.item)
        self.assertEqual(report.target_type, "item")

    def test_user_target(self):
        report = self.make_report(target_item=None, target_user=self.other)
        self.assertEqual(report.target, self.other)
        self.assertEqual(report.target_type, "user")

    def test_without_target_is_invalid(self):
        with self.assertRaises(ValidationError):
            self.build_report(target_item=None).full_clean()

    def test_with_two_targets_is_invalid(self):
        with self.assertRaises(ValidationError):
            self.build_report(target_user=self.other).full_clean()

    def test_database_rejects_missing_target(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_report(target_item=None)

    def test_database_rejects_two_targets(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_report(target_user=self.other)

    def test_cannot_report_self(self):
        self.assertInvalid("target_user", target_item=None, target_user=self.reporter)

    def test_cannot_report_own_item(self):
        self.assertInvalid("target_item", reporter=self.owner)

    def test_cannot_report_soft_deleted_item(self):
        self.item.soft_delete()
        self.assertInvalid("target_item")

    def test_existing_report_stays_valid_after_item_soft_deleted(self):
        report = self.make_report()
        self.item.soft_delete()
        report.description = "Deskripsi diperbarui setelah barang dihapus pemilik."
        report.full_clean()


class ReportFieldValidationTest(ReportTestMixin, TestCase):
    def test_valid_report_passes_full_clean(self):
        self.build_report().full_clean()

    def test_description_minimum_length_ignores_whitespace(self):
        self.assertInvalid("description", description="   terlalu pendek   ")

    def test_description_maximum_length(self):
        self.assertInvalid("description", description="a" * 1001)

    def test_invalid_reason_rejected(self):
        self.assertInvalid("reason", reason="spam")


class ReportDuplicateTest(ReportTestMixin, TestCase):
    def test_duplicate_active_item_report_invalid(self):
        self.make_report()
        with self.assertRaises(ValidationError):
            self.build_report().full_clean()

    def test_duplicate_active_item_report_rejected_by_database(self):
        self.make_report()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_report()

    def test_duplicate_active_user_report_rejected_by_database(self):
        self.make_report(target_item=None, target_user=self.other)
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_report(target_item=None, target_user=self.other)

    def test_new_report_allowed_after_previous_closed(self):
        old = self.make_report()
        old.transition_to(Report.Status.REJECTED)
        self.build_report().full_clean()
        self.make_report()

    def test_different_reporters_can_report_same_item(self):
        self.make_report()
        self.make_report(reporter=self.other)
        self.assertEqual(Report.objects.filter(target_item=self.item).count(), 2)


class ReportStatusTransitionTest(ReportTestMixin, TestCase):
    def test_allowed_transitions(self):
        allowed = [
            (Report.Status.PENDING, Report.Status.REVIEWING),
            (Report.Status.PENDING, Report.Status.REJECTED),
            (Report.Status.REVIEWING, Report.Status.RESOLVED),
            (Report.Status.REVIEWING, Report.Status.REJECTED),
        ]
        for current, target in allowed:
            with self.subTest(current=current, target=target):
                report = Report(status=current)
                self.assertTrue(report.can_transition_to(target))

    def test_disallowed_transitions(self):
        disallowed = [
            (Report.Status.PENDING, Report.Status.RESOLVED),
            (Report.Status.PENDING, Report.Status.PENDING),
            (Report.Status.REVIEWING, Report.Status.PENDING),
            (Report.Status.RESOLVED, Report.Status.REJECTED),
            (Report.Status.REJECTED, Report.Status.REVIEWING),
        ]
        for current, target in disallowed:
            with self.subTest(current=current, target=target):
                report = Report(status=current)
                self.assertFalse(report.can_transition_to(target))

    def test_transition_to_saves_status_and_note(self):
        report = self.make_report()
        report.transition_to(Report.Status.REVIEWING, note="Sedang dicek admin.")
        report.refresh_from_db()
        self.assertEqual(report.status, Report.Status.REVIEWING)
        self.assertEqual(report.admin_note, "Sedang dicek admin.")

    def test_transition_without_note_keeps_existing_note(self):
        report = self.make_report(admin_note="Catatan awal.")
        report.transition_to(Report.Status.REVIEWING)
        report.refresh_from_db()
        self.assertEqual(report.admin_note, "Catatan awal.")

    def test_invalid_transition_raises_and_does_not_save(self):
        report = self.make_report()
        with self.assertRaises(ValidationError):
            report.transition_to(Report.Status.RESOLVED)
        report.refresh_from_db()
        self.assertEqual(report.status, Report.Status.PENDING)

    def test_is_active(self):
        report = self.make_report()
        self.assertTrue(report.is_active)
        report.transition_to(Report.Status.REJECTED)
        self.assertFalse(report.is_active)


class ReportPermissionTest(ReportTestMixin, TestCase):
    def test_reporter_can_edit_pending_report(self):
        report = self.make_report()
        self.assertTrue(report.is_editable_by(self.reporter))

    def test_other_user_cannot_edit(self):
        report = self.make_report()
        self.assertFalse(report.is_editable_by(self.other))

    def test_reporter_cannot_edit_after_review_started(self):
        report = self.make_report()
        report.transition_to(Report.Status.REVIEWING)
        self.assertFalse(report.is_editable_by(self.reporter))


class ReportDeletionProtectionTest(ReportTestMixin, TestCase):
    def test_reporter_with_report_cannot_be_hard_deleted(self):
        self.make_report(target_item=None, target_user=self.other)
        with self.assertRaises(ProtectedError):
            self.reporter.delete()

    def test_reported_user_cannot_be_hard_deleted(self):
        self.make_report(target_item=None, target_user=self.other)
        with self.assertRaises(ProtectedError):
            self.other.delete()
