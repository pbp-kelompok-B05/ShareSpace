"""Decorator view Modul 2: cek kepemilikan barang dan rate limit berbasis cache Django."""
import json
import math
import time
from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse
from django.shortcuts import render

from items.models import Item

FORBIDDEN_MESSAGE = "Hanya pemilik barang atau admin yang dapat mengubah barang ini."
BORROWED_MESSAGE = "Barang sedang dipinjam sehingga tidak dapat diubah atau dihapus."


def is_htmx(request):
    return request.headers.get("HX-Request") == "true"


def toast_response(message, status, level="error"):
    """Respons HTMX tanpa isi; pesan tampil lewat event showToast (toast.js)."""
    response = HttpResponse(status=status)
    response["HX-Trigger"] = json.dumps({"showToast": {"message": message, "level": level}})
    return response


def _deny(request, message):
    if is_htmx(request):
        return toast_response(message, 403)
    # Dirender oleh handler 403 bawaan memakai templates/403.html.
    raise PermissionDenied(message)


def item_owner_required(view_func):
    """Hanya pemilik atau admin, dan hanya untuk barang yang sedang tidak dipinjam.

    View menerima argumen `item` (sudah beserta owner), bukan `pk`.
    """

    @wraps(view_func)
    def wrapper(request, pk, *args, **kwargs):
        if not request.user.is_authenticated:
            login_redirect = redirect_to_login(request.get_full_path())
            if is_htmx(request):
                # Redirect 302 akan diikuti HTMX diam-diam; minta browser pindah halaman penuh.
                response = HttpResponse(status=204)
                response["HX-Redirect"] = login_redirect.url
                return response
            return login_redirect

        try:
            item = Item.objects.visible().select_related("owner").get(pk=pk)
        except Item.DoesNotExist:
            raise Http404("Barang tidak ditemukan.")

        # Kepemilikan dicek dulu agar user lain tidak tahu status peminjaman barang orang lain.
        if not item.can_be_managed_by(request.user):
            return _deny(request, FORBIDDEN_MESSAGE)
        if not item.is_available:
            return _deny(request, BORROWED_MESSAGE)
        return view_func(request, *args, item=item, **kwargs)

    return wrapper


def _client_key(request):
    if request.user.is_authenticated:
        return f"user:{request.user.pk}"
    # Cadangan untuk tamu; di balik proxy (PWS) REMOTE_ADDR bisa berupa IP proxy.
    return f"ip:{request.META.get('REMOTE_ADDR', 'unknown')}"


def rate_limit(scope, limit, period):
    """Batasi POST: maksimal `limit` kali per `period` detik per user, per `scope`.

    Fixed window di cache default Django. Catatan: LocMemCache bersifat per proses,
    jadi dengan beberapa worker batas efektifnya limit x jumlah worker.
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if request.method != "POST":
                return view_func(request, *args, **kwargs)

            now = time.time()
            window = int(now // period)
            key = f"ratelimit:{scope}:{_client_key(request)}:{window}"
            cache.add(key, 0, timeout=period)
            try:
                count = cache.incr(key)
            except ValueError:
                # Key kedaluwarsa tepat di antara add() dan incr().
                cache.set(key, 1, timeout=period)
                count = 1

            if count > limit:
                retry_after = max(1, math.ceil((window + 1) * period - now))
                return _rate_limited(request, retry_after)
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def _rate_limited(request, retry_after):
    minutes = math.ceil(retry_after / 60)
    message = f"Terlalu banyak permintaan. Coba lagi dalam {minutes} menit."
    if is_htmx(request):
        response = toast_response(message, 429)
    else:
        response = render(request, "items/rate_limited.html", {"message": message}, status=429)
    response["Retry-After"] = str(retry_after)
    return response
