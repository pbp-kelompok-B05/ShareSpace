import datetime

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.shortcuts import redirect, render

from authentication.forms import UserProfileForm
from authentication.models import UserProfile


# Create your views here.
def register(request):
    if request.user.is_authenticated:
        return redirect("landing_page")

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
    if request.user.is_authenticated:
        return redirect("landing_page")

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


@login_required(login_url="/auth/login/")
def show_profile(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    last_login = request.COOKIES.get("last_login", "Belum ada sesi login / Cookie tidak ditemukan")

    context = {
        "profile": profile,
        "last_login": last_login,
        # Placeholder integrasi Modul 5
        "trust_score": None,
        "average_rating": None,
        "review_count": 0,
        "completed_transactions_count": 0,
    }

    if request.headers.get("HX-Request"):
        return render(request, "profile_content.html", context)

    return render(request, "profile.html", context)


@login_required(login_url="/auth/login/")
def edit_profile(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    form = UserProfileForm(request.POST or None, instance=profile)

    if request.method == "POST":
        if form.is_valid():
            form.save()
            messages.success(request, "Profil berhasil diperbarui!")

            if request.headers.get("HX-Request"):
                context = {
                    "profile": profile,
                    "last_login": request.COOKIES.get("last_login", "Belum ada sesi login / Cookie tidak ditemukan"),
                    "trust_score": None,
                    "average_rating": None,
                    "review_count": 0,
                    "completed_transactions_count": 0,
                }
                return render(request, "profile_content.html", context)

            return redirect("authentication:profile")
        else:
            messages.error(request, "Terdapat kesalahan pengisian form. Silakan periksa kembali.")

    context = {
        "profile": profile,
        "form": form,
    }

    template = "edit_profile_content.html" if request.headers.get("HX-Request") else "edit_profile.html"
    return render(request, template, context)

