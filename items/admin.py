from django.contrib import admin, messages

from items.models import Item


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = [
        "name", "owner", "category", "condition",
        "is_available", "is_verified", "is_deleted", "created_at",
    ]
    list_filter = ["category", "condition", "is_available", "is_verified", "is_deleted"]
    search_fields = ["name", "owner__username"]
    list_select_related = ["owner"]
    # is_available milik modul transaksi; is_deleted hanya lewat action agar deleted_at konsisten.
    readonly_fields = ["is_available", "is_deleted", "deleted_at", "created_at", "updated_at"]
    actions = ["hide_items", "restore_items", "verify_items", "unverify_items"]

    def get_queryset(self, request):
        # Admin perlu melihat barang tersembunyi agar bisa dipulihkan.
        return Item.all_objects.all()

    def has_delete_permission(self, request, obj=None):
        # Hard delete dimatikan; pakai action "Sembunyikan" (soft delete).
        return False

    @admin.action(description="Sembunyikan barang terpilih (moderasi)")
    def hide_items(self, request, queryset):
        items = list(queryset.filter(is_deleted=False))
        for item in items:
            item.soft_delete(force=True)
        self.message_user(request, f"{len(items)} barang disembunyikan.", messages.SUCCESS)

    @admin.action(description="Pulihkan barang terpilih")
    def restore_items(self, request, queryset):
        items = list(queryset.filter(is_deleted=True))
        for item in items:
            item.restore()
        self.message_user(request, f"{len(items)} barang dipulihkan.", messages.SUCCESS)

    @admin.action(description="Beri badge terverifikasi")
    def verify_items(self, request, queryset):
        count = queryset.update(is_verified=True)
        self.message_user(request, f"{count} barang diverifikasi.", messages.SUCCESS)

    @admin.action(description="Cabut badge terverifikasi")
    def unverify_items(self, request, queryset):
        count = queryset.update(is_verified=False)
        self.message_user(request, f"{count} barang dicabut verifikasinya.", messages.SUCCESS)
