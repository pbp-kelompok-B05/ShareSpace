import datetime
import json

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

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


def build_profile_context(request, profile):
    last_login = request.COOKIES.get("last_login", "Belum ada sesi login / Cookie tidak ditemukan")

    return {
        "profile": profile,
        "last_login": last_login,
    }


@login_required(login_url="/auth/login/")
def show_profile(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    context = build_profile_context(request, profile)

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

            # Respons HTMX tidak me-reload halaman, jadi toast dikirim lewat header HX-Trigger
            if request.headers.get("HX-Request"):
                context = build_profile_context(request, profile)
                response = render(request, "profile_content.html", context)
                response["HX-Trigger"] = json.dumps(
                    {"showToast": {"message": "Profil berhasil diperbarui!", "level": "success"}}
                )
                return response

            messages.success(request, "Profil berhasil diperbarui!")
            return redirect("authentication:profile")
        elif not request.headers.get("HX-Request"):
            messages.error(request, "Terdapat kesalahan pengisian form. Silakan periksa kembali.")

    context = {
        "profile": profile,
        "form": form,
    }

    template = "edit_profile_content.html" if request.headers.get("HX-Request") else "edit_profile.html"
    return render(request, template, context)


@login_required(login_url="/auth/login/")
@require_http_methods(["GET", "POST"])
def deactivate_account(request):
    if request.method == "POST":
        user = request.user
        user.is_active = False
        user.save()
        logout(request)
        messages.success(request, "Akun Anda telah berhasil dinonaktifkan.")
        response = redirect("landing_page")
        response.delete_cookie("last_login")
        return response

    return render(request, "deactivate_account.html")


@login_required(login_url="/auth/login/")
def public_profile(request, username):
    target_user = get_object_or_404(User, username=username, is_active=True)

    if target_user.pk == request.user.pk:
        return redirect("authentication:profile")

    # Profil publik hanya menampilkan identitas, nomor telepon dan alamat tidak ikut dikirim ke template
    profile = UserProfile.objects.filter(user=target_user).first()

    context = {
        "target_user": target_user,
        "profile": profile,
    }
    return render(request, "public_profile.html", context)

