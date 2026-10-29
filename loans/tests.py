import uuid
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from authentication.models import UserProfile
from items.models import Item
from loans.forms import LoanRequestForm
from loans.models import LoanRequest

User = get_user_model()

# Data awal untuk seluruh pengujian
class LoanTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="leon_s_kennedy", password="TestPass123!", email="leon@example.com")
        cls.borrower = User.objects.create_user(username="ada_wong", password="TestPass123!", email="ada@example.com")
        cls.other = User.objects.create_user(username="chris_redfield", password="TestPass123!")
        cls.second_borrower = User.objects.create_user(username="jill_valentine", password="TestPass123!")
        cls.item = Item.objects.create(
            owner=cls.owner, name="SG-09 R", description="SG-09 R milik Leon S. Kennedy.",
            category=Item.Category.ELECTRONICS, condition=Item.Condition.GOOD,
            image_url="https://example.com/sg09r.jpg", is_verified=True, is_available=True
        )
        cls.start = timezone.localdate() + timedelta(days=2)
        cls.due = cls.start + timedelta(days=5)

    def loan_data(self, **changes):
        data = {"start_date": self.start.isoformat(), "due_date": self.due.isoformat(), "notes": "Meminjam SG-09 R untuk misi."}
        data.update(changes)
        return data

    def make_loan(self, **changes):
        data = {"borrower": self.borrower, "item": self.item, "start_date": self.start, "due_date": self.due, "notes": "Meminjam SG-09 R untuk misi"}
        data.update(changes)
        return LoanRequest.objects.create(**data)

    def login_as(self, user):
        self.client.force_login(user)

    def url(self, name, loan=None):
        return reverse(f"loans:{name}", args=[loan.pk] if loan else None)


# Pengujian model peminjaman
class LoanModelTests(LoanTestBase):
    # Memastikan transaksi memiliki UUID, status pending, dan waktu pembuatan.
    def test_default_status_and_uuid(self):
        loan = self.make_loan()
        self.assertIsInstance(loan.pk, uuid.UUID)
        self.assertEqual(loan.status, LoanRequest.Status.PENDING)
        self.assertIsNone(loan.return_requested_at)
        self.assertIsNotNone(loan.created_at)

    # Memastikan nama barang dan status muncul pada representasi transaksi.
    def test_str_contains_item_and_status(self):
        loan = self.make_loan()
        self.assertIn(self.item.name, str(loan))
        self.assertIn(loan.get_status_display(), str(loan))

    # Memastikan database menolak tanggal pengembalian sebelum tanggal peminjaman.
    def test_database_rejects_due_date_before_start_date(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.make_loan(due_date=self.start - timedelta(days=1))

    # Memastikan satu barang tidak memiliki dua transaksi aktif sekaligus.
    def test_database_prevents_two_active_loans_for_one_item(self):
        self.make_loan(status=LoanRequest.Status.APPROVED)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.make_loan(borrower=self.second_borrower, status=LoanRequest.Status.BORROWED)

    # Memastikan beberapa pengguna boleh mengajukan peminjaman pending untuk barang yang sama.
    def test_multiple_pending_requests_are_allowed(self):
        self.make_loan()
        self.make_loan(borrower=self.second_borrower)
        self.assertEqual(LoanRequest.objects.filter(item=self.item).count(), 2)

    # Memastikan pengguna dan barang tidak bisa dihapus langsung jika masih direferensikan transaksi.
    def test_borrower_and_item_cannot_be_deleted_while_referenced(self):
        self.make_loan()
        with self.assertRaises(ProtectedError):
            self.borrower.delete()
        with self.assertRaises(ProtectedError):
            self.item.delete()


# Pengujian form peminjaman
class LoanFormTests(LoanTestBase):
    # Memastikan form menerima tanggal peminjaman yang valid.
    def test_valid_dates(self):
        self.assertTrue(LoanRequestForm(data=self.loan_data()).is_valid())

    # Memastikan tanggal mulai dan selesai boleh sama.
    def test_same_start_and_due_date_is_valid(self):
        form = LoanRequestForm(data=self.loan_data(due_date=self.start.isoformat()))
        self.assertTrue(form.is_valid())

    # Memastikan tanggal mulai tidak boleh berada di masa lalu.
    def test_start_date_cannot_be_in_the_past(self):
        form = LoanRequestForm(data=self.loan_data(start_date=(timezone.localdate() - timedelta(days=1)).isoformat()))
        self.assertFalse(form.is_valid())
        self.assertIn("start_date", form.errors)

    # Memastikan tanggal pengembalian tidak boleh sebelum tanggal mulai.
    def test_due_date_cannot_precede_start_date(self):
        form = LoanRequestForm(data=self.loan_data(due_date=(self.start - timedelta(days=1)).isoformat()))
        self.assertFalse(form.is_valid())
        self.assertIn("due_date", form.errors)

    # Memastikan tanggal mulai wajib diisi.
    def test_missing_start_date_is_invalid(self):
        form = LoanRequestForm(data=self.loan_data(start_date=""))
        self.assertFalse(form.is_valid())
        self.assertIn("start_date", form.errors)

    # Memastikan catatan transaksi lama dapat diedit tanpa mengganti tanggal mulai.
    def test_unchanged_past_start_date_can_be_edited(self):
        yesterday = timezone.localdate() - timedelta(days=1)
        loan = self.make_loan(start_date=yesterday, due_date=self.due)
        form = LoanRequestForm(data=self.loan_data(start_date=yesterday.isoformat(), notes="Catatan diperbarui"), instance=loan)
        self.assertTrue(form.is_valid())


# Pengujian halaman transaksi
class LoanPageTests(LoanTestBase):
    # Memastikan halaman borrower dan lender memiliki context yang sesuai.
    def test_borrower_and_lender_pages_have_correct_context(self):
        self.make_loan()
        for user, name, role in ((self.borrower, "list", "borrower"), (self.owner, "lender_list", "lender")):
            with self.subTest(role=role):
                self.login_as(user)
                response = self.client.get(self.url(name))
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, "loan_list.html")
                self.assertEqual(response.context["role"], role)
                self.assertEqual(response.context[f"{role}_count"], 1)

    # Memastikan detail transaksi hanya dapat diakses oleh peminjam dan pemilik barang.
    def test_only_borrower_and_owner_can_view_detail(self):
        loan = self.make_loan()
        for user in (self.borrower, self.owner):
            with self.subTest(username=user.username):
                self.login_as(user)
                response = self.client.get(self.url("detail", loan))
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, "loan_detail.html")
        self.login_as(self.other)
        self.assertEqual(self.client.get(self.url("detail", loan)).status_code, 404)

    # Memastikan form dan hak akses tindakan sesuai peran dan status transaksi.
    def test_detail_context_exposes_actions_by_status(self):
        loan = self.make_loan()
        self.login_as(self.borrower)
        response = self.client.get(self.url("detail", loan))
        self.assertIsNotNone(response.context["form"])
        self.assertFalse(response.context["can_manage"])
        self.login_as(self.owner)
        response = self.client.get(self.url("detail", loan))
        self.assertTrue(response.context["can_manage"])
        self.assertIsNone(response.context["form"])
        loan.status = LoanRequest.Status.BORROWED
        loan.save()
        self.login_as(self.borrower)
        response = self.client.get(self.url("detail", loan))
        self.assertTrue(response.context["can_request_return"])


# Pengujian daftar transaksi melalui AJAX
class LoanListDataTests(LoanTestBase):
    # Memastikan Ada hanya melihat transaksi peminjamannya sendiri.
    def test_borrower_data_only_contains_own_transactions(self):
        mine = self.make_loan()
        self.make_loan(borrower=self.second_borrower)
        self.login_as(self.borrower)
        response = self.client.get(self.url("data"))
        self.assertEqual(response.status_code, 200)
        loans = response.json()["loans"]
        self.assertEqual(len(loans), 1)
        self.assertEqual(loans[0]["id"], str(mine.pk))
        self.assertEqual(loans[0]["person_label"], "Pemilik")
        self.assertEqual(loans[0]["item_name"], self.item.name)
        self.assertIsNotNone(loans[0]["cancel_url"])
        self.assertIsNone(loans[0]["return_url"])

    # Memastikan Leon hanya melihat peminjaman barang miliknya.
    def test_lender_data_only_contains_items_owned_by_user(self):
        mine = self.make_loan()
        second_item = Item.objects.create(
            owner=self.other, name="Green Herb", description="Tanaman herbal dari Raccoon City.",
            category=Item.Category.HOUSEHOLD, condition=Item.Condition.GOOD, is_verified=True
        )
        self.make_loan(item=second_item)
        self.login_as(self.owner)
        response = self.client.get(self.url("lender_data"))
        loans = response.json()["loans"]
        self.assertEqual(len(loans), 1)
        self.assertEqual(loans[0]["id"], str(mine.pk))
        self.assertEqual(loans[0]["person_label"], "Peminjam")
        self.assertIsNotNone(loans[0]["approve_url"])
        self.assertIsNotNone(loans[0]["reject_url"])

    # Memastikan filter status berfungsi dan status yang tidak dikenal ditolak.
    def test_status_filter_and_invalid_status(self):
        self.make_loan()
        self.make_loan(status=LoanRequest.Status.REJECTED)
        self.login_as(self.borrower)
        response = self.client.get(self.url("data"), {"status": "rejected"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["loans"]), 1)
        self.assertEqual(response.json()["loans"][0]["status"], "rejected")
        self.login_as(self.owner)
        response = self.client.get(self.url("lender_data"), {"status": "pending"})
        self.assertEqual(len(response.json()["loans"]), 1)
        for name in ("data", "lender_data"):
            response = self.client.get(self.url(name), {"status": "unknown"})
            self.assertEqual(response.status_code, 400)
            self.assertIn("error", response.json())

    # Memastikan nama dan nomor telepon pemilik atau peminjam muncul pada respons AJAX.
    def test_profile_name_and_phone_are_in_response(self):
        self.make_loan()
        UserProfile.objects.create(user=self.owner, full_name="Leon S. Kennedy", phone_number="0812345678")
        UserProfile.objects.create(user=self.borrower, full_name="Ada Wong", phone_number="0898765432")
        self.login_as(self.borrower)
        borrower_data = self.client.get(self.url("data")).json()["loans"][0]
        self.assertEqual(borrower_data["person_name"], "Leon S. Kennedy")
        self.assertEqual(borrower_data["contact_url"], "tel:0812345678")
        self.login_as(self.owner)
        lender_data = self.client.get(self.url("lender_data")).json()["loans"][0]
        self.assertEqual(lender_data["person_name"], "Ada Wong")
        self.assertEqual(lender_data["contact_url"], "tel:0898765432")

    # Memastikan email digunakan sebagai kontak jika profil belum tersedia.
    def test_contact_falls_back_to_email_when_no_profile(self):
        self.make_loan()
        self.login_as(self.borrower)
        data = self.client.get(self.url("data")).json()["loans"][0]
        self.assertEqual(data["person_name"], self.owner.username)
        self.assertEqual(data["contact_url"], "mailto:leon@example.com")


# Pengujian pengajuan peminjaman
class LoanCreateTests(LoanTestBase):
    # Memastikan Ada dapat mengajukan peminjaman SG-09 R kepada Leon.
    def test_borrower_can_create_pending_loan(self):
        self.login_as(self.borrower)
        response = self.client.post(reverse("loans:create", args=[self.item.pk]), self.loan_data())
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json()["success"])
        loan = LoanRequest.objects.get()
        self.assertEqual(loan.borrower, self.borrower)
        self.assertEqual(loan.item, self.item)
        self.assertEqual(loan.status, LoanRequest.Status.PENDING)
        self.assertEqual(response.json()["detail_url"], self.url("detail", loan))

    # Memastikan Leon tidak dapat meminjam SG-09 R miliknya sendiri.
    def test_owner_cannot_borrow_own_item(self):
        self.login_as(self.owner)
        response = self.client.post(reverse("loans:create", args=[self.item.pk]), self.loan_data())
        self.assertEqual(response.status_code, 403)
        self.assertFalse(LoanRequest.objects.exists())

    # Memastikan barang yang belum diverifikasi atau tidak tersedia tidak dapat dipinjam.
    def test_unverified_or_unavailable_item_rejected(self):
        self.login_as(self.borrower)
        url = reverse("loans:create", args=[self.item.pk])
        for update in ({"is_verified": False}, {"is_verified": True, "is_available": False}):
            with self.subTest(update=update):
                Item.objects.filter(pk=self.item.pk).update(is_verified=True, is_available=True)
                Item.objects.filter(pk=self.item.pk).update(**update)
                response = self.client.post(url, self.loan_data())
                self.assertEqual(response.status_code, 409)
        self.assertFalse(LoanRequest.objects.exists())

    # Memastikan Ada tidak dapat mengajukan peminjaman pending yang sama dua kali.
    def test_duplicate_pending_request_rejected(self):
        self.make_loan()
        self.login_as(self.borrower)
        response = self.client.post(reverse("loans:create", args=[self.item.pk]), self.loan_data())
        self.assertEqual(response.status_code, 409)
        self.assertEqual(LoanRequest.objects.count(), 1)

    # Memastikan endpoint create menolak tanggal peminjaman yang tidak valid.
    def test_invalid_date_rejected(self):
        self.login_as(self.borrower)
        response = self.client.post(reverse("loans:create", args=[self.item.pk]), self.loan_data(due_date=(self.start - timedelta(days=1)).isoformat()))
        self.assertEqual(response.status_code, 400)
        self.assertIn("due_date", response.json()["errors"])

    # Memastikan pengajuan untuk barang yang tidak ada atau sudah dihapus menghasilkan 404.
    def test_missing_or_deleted_item_returns_404(self):
        self.login_as(self.borrower)
        missing = self.client.post(reverse("loans:create", args=[999999]), self.loan_data())
        self.assertEqual(missing.status_code, 404)
        self.item.soft_delete()
        deleted = self.client.post(reverse("loans:create", args=[self.item.pk]), self.loan_data())
        self.assertEqual(deleted.status_code, 404)

    # Memastikan Ada dapat mengajukan ulang setelah permintaan sebelumnya ditolak.
    def test_create_again_after_rejection_is_allowed(self):
        self.make_loan(status=LoanRequest.Status.REJECTED)
        self.login_as(self.borrower)
        response = self.client.post(reverse("loans:create", args=[self.item.pk]), self.loan_data())
        self.assertEqual(response.status_code, 201)
        self.assertEqual(LoanRequest.objects.count(), 2)


# Pengujian pengubahan dan pembatalan
class LoanEditCancelTests(LoanTestBase):
    # Memastikan Ada dapat mengubah catatan transaksi yang masih pending.
    def test_borrower_can_update_pending_loan(self):
        loan = self.make_loan()
        self.login_as(self.borrower)
        response = self.client.post(self.url("update", loan), self.loan_data(notes="Catatan baru"))
        self.assertEqual(response.status_code, 200)
        loan.refresh_from_db()
        self.assertEqual(loan.notes, "Catatan baru")

    # Memastikan Leon tidak dapat mengubah atau membatalkan pengajuan Ada.
    def test_only_borrower_can_update_or_cancel(self):
        loan = self.make_loan()
        self.login_as(self.owner)
        self.assertEqual(self.client.post(self.url("update", loan), self.loan_data()).status_code, 403)
        self.assertEqual(self.client.post(self.url("cancel", loan)).status_code, 403)

    # Memastikan proses pengubahan menolak data tanggal yang tidak valid.
    def test_update_invalid_data_rejected(self):
        loan = self.make_loan()
        self.login_as(self.borrower)
        response = self.client.post(self.url("update", loan), self.loan_data(start_date=""))
        self.assertEqual(response.status_code, 400)
        self.assertIn("start_date", response.json()["errors"])

    # Memastikan Ada dapat membatalkan pengajuan yang masih pending.
    def test_borrower_can_cancel_pending_loan(self):
        loan = self.make_loan()
        self.login_as(self.borrower)
        self.assertEqual(self.client.post(self.url("cancel", loan)).status_code, 200)
        loan.refresh_from_db()
        self.assertEqual(loan.status, LoanRequest.Status.CANCELLED)

    # Memastikan transaksi approved tidak dapat diedit atau dibatalkan.
    def test_nonpending_loan_cannot_be_edited_or_cancelled(self):
        loan = self.make_loan(status=LoanRequest.Status.APPROVED)
        self.login_as(self.borrower)
        self.assertEqual(self.client.post(self.url("update", loan), self.loan_data()).status_code, 409)
        self.assertEqual(self.client.post(self.url("cancel", loan)).status_code, 409)


# Pengujian alur dan perubahan status transaksi
class LoanStatusFlowTests(LoanTestBase):
    # Memastikan hanya Leon yang dapat menyetujui, menolak, atau menyerahkan barang.
    def test_only_owner_can_approve_reject_and_mark_borrowed(self):
        loan = self.make_loan()
        self.login_as(self.borrower)
        for name in ("approve", "reject", "mark_borrowed", "complete"):
            with self.subTest(action=name):
                self.assertEqual(self.client.post(self.url(name, loan)).status_code, 403)

    # Memastikan persetujuan mengubah status transaksi dan membuat barang tidak tersedia.
    def test_approve_sets_item_unavailable(self):
        loan = self.make_loan()
        self.login_as(self.owner)
        response = self.client.post(self.url("approve", loan))
        self.assertEqual(response.status_code, 200)
        loan.refresh_from_db()
        self.item.refresh_from_db()
        self.assertEqual(loan.status, LoanRequest.Status.APPROVED)
        self.assertFalse(self.item.is_available)

    # Memastikan barang yang sudah tidak tersedia tidak dapat disetujui lagi.
    def test_approve_rejects_item_already_unavailable(self):
        loan = self.make_loan()
        Item.objects.filter(pk=self.item.pk).update(is_available=False)
        self.login_as(self.owner)
        response = self.client.post(self.url("approve", loan))
        self.assertEqual(response.status_code, 409)
        loan.refresh_from_db()
        self.assertEqual(loan.status, LoanRequest.Status.PENDING)

    # Memastikan Leon tidak dapat menyetujui dua pengajuan aktif untuk SG-09 R.
    def test_second_pending_loan_cannot_be_approved_after_first(self):
        first = self.make_loan()
        second = self.make_loan(borrower=self.second_borrower)
        self.login_as(self.owner)
        self.assertEqual(self.client.post(self.url("approve", first)).status_code, 200)
        self.assertEqual(self.client.post(self.url("approve", second)).status_code, 409)
        second.refresh_from_db()
        self.assertEqual(second.status, LoanRequest.Status.PENDING)

    # Memastikan Leon dapat menolak pengajuan dan barang tetap tersedia.
    def test_owner_can_reject_pending_loan(self):
        loan = self.make_loan()
        self.login_as(self.owner)
        self.assertEqual(self.client.post(self.url("reject", loan)).status_code, 200)
        loan.refresh_from_db()
        self.item.refresh_from_db()
        self.assertEqual(loan.status, LoanRequest.Status.REJECTED)
        self.assertTrue(self.item.is_available)

    # Memastikan transaksi approved dapat diubah menjadi borrowed.
    def test_owner_can_mark_approved_loan_borrowed(self):
        loan = self.make_loan(status=LoanRequest.Status.APPROVED)
        self.login_as(self.owner)
        self.assertEqual(self.client.post(self.url("mark_borrowed", loan)).status_code, 200)
        loan.refresh_from_db()
        self.assertEqual(loan.status, LoanRequest.Status.BORROWED)

    # Memastikan perubahan status yang tidak sesuai alur ditolak.
    def test_invalid_status_transitions_return_409(self):
        loan = self.make_loan()
        self.login_as(self.owner)
        for name in ("mark_borrowed", "complete"):
            with self.subTest(action=name):
                self.assertEqual(self.client.post(self.url(name, loan)).status_code, 409)
        loan.status = LoanRequest.Status.REJECTED
        loan.save()
        for name in ("approve", "reject"):
            with self.subTest(action=name):
                self.assertEqual(self.client.post(self.url(name, loan)).status_code, 409)

    # Memastikan hanya Ada yang dapat mengajukan pengembalian SG-09 R.
    def test_only_borrower_can_request_return(self):
        loan = self.make_loan(status=LoanRequest.Status.BORROWED)
        self.login_as(self.owner)
        self.assertEqual(self.client.post(self.url("request_return", loan)).status_code, 403)
        self.login_as(self.borrower)
        self.assertEqual(self.client.post(self.url("request_return", loan)).status_code, 200)
        loan.refresh_from_db()
        self.assertIsNotNone(loan.return_requested_at)

    # Memastikan pengembalian tidak dapat diajukan dua kali atau sebelum barang dipinjam.
    def test_return_cannot_be_requested_twice_or_before_borrowed(self):
        loan = self.make_loan(status=LoanRequest.Status.BORROWED)
        self.login_as(self.borrower)
        self.assertEqual(self.client.post(self.url("request_return", loan)).status_code, 200)
        self.assertEqual(self.client.post(self.url("request_return", loan)).status_code, 409)
        loan.status = LoanRequest.Status.APPROVED
        loan.return_requested_at = None
        loan.save()
        self.assertEqual(self.client.post(self.url("request_return", loan)).status_code, 409)

    # Memastikan transaksi tidak dapat diselesaikan sebelum pengembalian diajukan.
    def test_complete_requires_return_request(self):
        loan = self.make_loan(status=LoanRequest.Status.BORROWED)
        Item.objects.filter(pk=self.item.pk).update(is_available=False)
        self.login_as(self.owner)
        response = self.client.post(self.url("complete", loan))
        self.assertEqual(response.status_code, 409)
        loan.refresh_from_db()
        self.assertEqual(loan.status, LoanRequest.Status.BORROWED)

    # Memastikan alur lengkap Ada meminjam SG-09 R hingga Leon menerimanya kembali.
    def test_full_workflow_until_item_available_again(self):
        self.login_as(self.borrower)
        response = self.client.post(reverse("loans:create", args=[self.item.pk]), self.loan_data())
        self.assertEqual(response.status_code, 201)
        loan = LoanRequest.objects.get()
        self.login_as(self.owner)
        self.assertEqual(self.client.post(self.url("approve", loan)).status_code, 200)
        self.assertEqual(self.client.post(self.url("mark_borrowed", loan)).status_code, 200)
        self.item.refresh_from_db()
        self.assertFalse(self.item.is_available)
        self.login_as(self.borrower)
        self.assertEqual(self.client.post(self.url("request_return", loan)).status_code, 200)
        self.login_as(self.owner)
        self.assertEqual(self.client.post(self.url("complete", loan)).status_code, 200)
        loan.refresh_from_db()
        self.item.refresh_from_db()
        self.assertEqual(loan.status, LoanRequest.Status.COMPLETED)
        self.assertTrue(self.item.is_available)

    # Memastikan barang yang sudah dihapus tidak otomatis tersedia lagi setelah transaksi selesai.
    def test_complete_deleted_item_does_not_restore_availability(self):
        loan = self.make_loan(status=LoanRequest.Status.BORROWED, return_requested_at=timezone.now())
        self.item.is_available = False
        self.item.save()
        self.item.soft_delete(force=True)
        self.login_as(self.owner)
        self.assertEqual(self.client.post(self.url("complete", loan)).status_code, 200)
        self.item.refresh_from_db()
        self.assertTrue(self.item.is_deleted)
        self.assertFalse(self.item.is_available)


# Pengujian login dan metode HTTP
class LoanAccessAndMethodTests(LoanTestBase):
    # Memastikan semua endpoint transaksi membutuhkan login.
    def test_login_required_on_all_loan_endpoints(self):
        loan = self.make_loan()
        routes = (
            ("list", None, "GET"), ("lender_list", None, "GET"),
            ("data", None, "GET"), ("lender_data", None, "GET"),
            ("detail", loan, "GET"), ("create", self.item.pk, "POST"),
            ("update", loan, "POST"), ("cancel", loan, "POST"),
            ("approve", loan, "POST"), ("reject", loan, "POST"),
            ("mark_borrowed", loan, "POST"), ("request_return", loan, "POST"),
            ("complete", loan, "POST"),
        )
        for name, value, method in routes:
            with self.subTest(endpoint=name):
                url = reverse("loans:create", args=[value]) if name == "create" else self.url(name, value)
                response = self.client.get(url) if method == "GET" else self.client.post(url)
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse("authentication:login"), response["Location"])

    # Memastikan endpoint yang mengubah data tidak menerima request GET.
    def test_mutating_endpoints_reject_get(self):
        loan = self.make_loan()
        self.login_as(self.owner)
        for name in ("update", "cancel", "approve", "reject", "mark_borrowed", "request_return", "complete"):
            with self.subTest(endpoint=name):
                self.assertEqual(self.client.get(self.url(name, loan)).status_code, 405)
        self.assertEqual(self.client.get(reverse("loans:create", args=[self.item.pk])).status_code, 405)

    # Memastikan UUID transaksi yang tidak ditemukan menghasilkan respons 404.
    def test_invalid_loan_uuid_returns_404(self):
        self.login_as(self.borrower)
        response = self.client.get(reverse("loans:detail", args=[uuid.uuid4()]))
        self.assertEqual(response.status_code, 404)
