from django.contrib import admin, messages
from django.core.exceptions import ValidationError

from review.models import Report, Review


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ["__str__", "reporter", "target_display", "reason", "status", "created_at"]
    list_filter = ["status", "reason"]
    search_fields = [
        "reporter__username", "target_user__username", "target_item__name",
        "target_loan__item__name", "description",
    ]
    list_select_related = ["reporter", "target_user", "target_item", "target_loan__item"]
    # Isi laporan milik pelapor; status hanya lewat action agar alur moderasi tidak dilompati.
    readonly_fields = [
        "reporter", "target_item", "target_user", "target_loan", "reason", "description",
        "status", "created_at", "updated_at",
    ]
    fields = readonly_fields + ["admin_note"]
    actions = ["mark_reviewing", "mark_resolved", "mark_rejected"]

    @admin.display(description="Target")
    def target_display(self, obj):
        if obj.target_loan_id:
            return f"Transaksi {obj.target_loan.item.name}"
        return obj.target

    def has_add_permission(self, request):
        # Laporan dibuat pengguna lewat halaman ShareSpace, bukan oleh admin.
        return False

    def has_delete_permission(self, request, obj=None):
        # Riwayat laporan disimpan sebagai jejak moderasi; tolak lewat status "Ditolak".
        return False

    def _transition(self, request, queryset, status):
        changed, skipped = 0, 0
        for report in queryset:
            try:
                report.transition_to(status)
                changed += 1
            except ValidationError:
                skipped += 1
        label = Report.Status(status).label
        if changed:
            self.message_user(request, f"{changed} laporan diubah ke {label}.", messages.SUCCESS)
        if skipped:
            self.message_user(
                request,
                f"{skipped} laporan dilewati karena tidak bisa diubah ke {label}.",
                messages.WARNING,
            )

    @admin.action(description="Tandai sedang ditinjau")
    def mark_reviewing(self, request, queryset):
        self._transition(request, queryset, Report.Status.REVIEWING)

    @admin.action(description="Tandai selesai")
    def mark_resolved(self, request, queryset):
        self._transition(request, queryset, Report.Status.RESOLVED)

    @admin.action(description="Tolak laporan")
    def mark_rejected(self, request, queryset):
        self._transition(request, queryset, Report.Status.REJECTED)


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ["__str__", "reviewer", "reviewee", "reviewer_role", "rating", "is_hidden", "created_at"]
    list_filter = ["rating", "reviewer_role", "is_hidden"]
    search_fields = ["reviewer__username", "reviewee__username", "comment"]
    list_select_related = ["reviewer", "reviewee"]
    # Isi ulasan milik penulisnya; admin hanya bisa menyembunyikan atau menampilkan kembali.
    readonly_fields = [
        "loan", "reviewer", "reviewee", "reviewer_role", "rating", "comment",
        "created_at", "updated_at",
    ]
    fields = readonly_fields + ["is_hidden"]
    actions = ["hide_reviews", "unhide_reviews"]

    def has_add_permission(self, request):
        # Ulasan hanya lahir dari transaksi selesai lewat halaman ShareSpace.
        return False

    def has_delete_permission(self, request, obj=None):
        # Riwayat ulasan dipakai untuk reputasi; moderasi lewat "Sembunyikan".
        return False

    @admin.action(description="Sembunyikan ulasan terpilih")
    def hide_reviews(self, request, queryset):
        count = queryset.update(is_hidden=True)
        self.message_user(request, f"{count} ulasan disembunyikan.", messages.SUCCESS)

    @admin.action(description="Tampilkan kembali ulasan terpilih")
    def unhide_reviews(self, request, queryset):
        count = queryset.update(is_hidden=False)
        self.message_user(request, f"{count} ulasan ditampilkan kembali.", messages.SUCCESS)
