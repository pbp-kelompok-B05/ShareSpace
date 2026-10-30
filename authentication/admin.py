from django.contrib import admin
from authentication.models import UserProfile

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

