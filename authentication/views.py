import datetime

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.shortcuts import redirect, render

from authentication.models import UserProfile

# Create your views here.
def register(request):
    form = UserCreationForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        user = form.save()
        UserProfile.objects.create(user=user)
        messages.success(request, "Akun berhasil dibuat. Silakan login.")
        return redirect("authentication:login")

    context = {
        "form": form,
    }
    return render(request, "register.html", context)


def login_user(request):
    form = AuthenticationForm(request, data=request.POST or None)

    if request.method == "POST" and form.is_valid():
        user = form.get_user()
        login(request, user)
        response = redirect("landing_page")
        response.set_cookie("last_login", str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        return response

    context = {
        "form": form,
    }
    return render(request, "login.html", context)


def logout_user(request):
    logout(request)
    response = redirect("landing_page")
    response.delete_cookie("last_login")
    return response
