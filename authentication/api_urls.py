from django.urls import path

from authentication import api_views

app_name = "authentication_api"

urlpatterns = [
    path("profiles/", api_views.profile_list, name="profile-list"),
    path("profiles/me/", api_views.profile_me, name="profile-me"),
    path("profiles/<str:username>/", api_views.profile_detail, name="profile-detail"),
    path("help-requests/", api_views.login_help_list_create, name="help-request-create"),
]
