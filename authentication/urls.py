from django.urls import path
from authentication.views import (
    deactivate_account,
    edit_profile,
    google_login,
    login_user,
    logout_user,
    profile_reputation_api,
    public_profile,
    register,
    show_profile,
    sso_ui_callback,
    sso_ui_login,
)

app_name = 'authentication'

urlpatterns = [
    path('', login_user, name='auth'),
    path('register/', register, name='register'),
    path('login/', login_user, name='login'),
    path('logout/', logout_user, name='logout'),
    path('google/', google_login, name='google_login'),
    path('sso-ui/', sso_ui_login, name='sso_ui_login'),
    path('sso-ui/callback/', sso_ui_callback, name='sso_ui_callback'),
    path('profile/', show_profile, name='profile'),
    path('profile/edit/', edit_profile, name='edit_profile'),
    path('deactivate/', deactivate_account, name='deactivate_account'),
    path('user/<str:username>/', public_profile, name='public_profile'),
    path('api/profile/reputation/', profile_reputation_api, name='profile_reputation_api'),
    path('api/profile/<str:username>/reputation/', profile_reputation_api, name='public_profile_reputation_api'),
]
