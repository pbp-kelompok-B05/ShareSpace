from django.contrib import admin, messages
from django.core.exceptions import ValidationError

from review.models import Report


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ["__str__", "reporter", "target_display", "reason", "status", "created_at"]
    list_filter = ["status", "reason"]
    search_fields = [
        "reporter__username", "target_user__username", "target_item__name", "description",
    ]
    list_select_related = ["reporter", "target_user", "target_item"]
    # Isi laporan milik pelapor; status hanya lewat action agar alur moderasi tidak dilompati.
    readonly_fields = [
        "reporter", "target_item", "target_user", "reason", "description",
        "status", "created_at", "updated_at",
    ]
    fields = readonly_fields + ["admin_note"]
    actions = ["mark_reviewing", "mark_resolved", "mark_rejected"]

    @admin.display(description="Target")
    def target_display(self, obj):
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
