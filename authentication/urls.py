from django.urls import path
from authentication.views import edit_profile, login_user, logout_user, register, show_profile

app_name = 'authentication'

urlpatterns = [
    path('', login_user, name='auth'),
    path('register/', register, name='register'),
    path('login/', login_user, name='login'),
    path('logout/', logout_user, name='logout'),
    path('profile/', show_profile, name='profile'),
    path('profile/edit/', edit_profile, name='edit_profile'),
]

