from django.contrib import admin
from authentication.models import LoginHelpRequest, UserProfile

# Register your models here.
@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "full_name",
        "auth_provider",
        "is_verified",
        "npm",
        "phone_number",
    )
    list_filter = ("auth_provider", "is_verified")
    search_fields = ("user__username", "user__email", "full_name", "npm")

@admin.register(LoginHelpRequest)
class LoginHelpRequestAdmin(admin.ModelAdmin):
    list_display = (
        "email_or_username",
        "contact_email",
        "issue_type",
        "status",
        "created_at",
    )
    list_filter = ("status", "issue_type")
    search_fields = ("email_or_username", "contact_email", "message")
    readonly_fields = ("created_at", "updated_at")

    @admin.action(description="Tandai selesai")
    def mark_as_resolved(self, request, queryset):
        updated = queryset.update(status=LoginHelpRequest.Status.RESOLVED)
        self.message_user(request, f"{updated} permohonan bantuan berhasil ditandai selesai.")

    actions = [mark_as_resolved]

