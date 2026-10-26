from django.urls import path
from authentication.views import (
    deactivate_account,
    edit_profile,
    login_user,
    logout_user,
    public_profile,
    register,
    show_profile,
)

app_name = 'authentication'

urlpatterns = [
    path('', login_user, name='auth'),
    path('register/', register, name='register'),
    path('login/', login_user, name='login'),
    path('logout/', logout_user, name='logout'),
    path('profile/', show_profile, name='profile'),
    path('profile/edit/', edit_profile, name='edit_profile'),
    path('deactivate/', deactivate_account, name='deactivate_account'),
    path('user/<str:username>/', public_profile, name='public_profile'),
]

