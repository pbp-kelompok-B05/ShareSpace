"""Data seed: user dummy demo_* dan barang sintetis dari items/seed_data.json.

Memakai model historis (apps.get_model) agar migration tetap jalan walaupun
model berubah di kemudian hari. Idempoten lewat get_or_create; reverse hanya
menghapus data yang tercantum di JSON.
"""
import json
import operator
from datetime import timedelta
from functools import reduce
from pathlib import Path

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.db import migrations
from django.db.models import Q
from django.utils import timezone

SEED_FILE = Path(__file__).resolve().parent.parent / "seed_data.json"


def load_seed():
    with SEED_FILE.open(encoding="utf-8") as f:
        return json.load(f)


def get_models(apps):
    return (
        apps.get_model(settings.AUTH_USER_MODEL),
        apps.get_model("authentication", "UserProfile"),
        apps.get_model("items", "Item"),
    )


def seed_forward(apps, schema_editor):
    User, UserProfile, Item = get_models(apps)
    data = load_seed()
    now = timezone.now()

    users = {}
    for entry in data["users"]:
        user, _ = User.objects.get_or_create(
            username=entry["username"],
            defaults={
                "first_name": entry["first_name"],
                "last_name": entry["last_name"],
                "is_active": entry["is_active"],
                # Unusable password: akun demo tidak bisa dipakai login.
                "password": make_password(None),
            },
        )
        UserProfile.objects.get_or_create(
            user=user,
            defaults={"full_name": entry["full_name"], "address": entry["address"]},
        )
        users[entry["username"]] = user

    for entry in data["items"]:
        # _base_manager ikut melihat barang soft delete, jadi barang seed yang
        # sudah dihapus tidak dibuat ulang.
        item, created = Item._base_manager.get_or_create(
            owner=users[entry["owner"]],
            name=entry["name"],
            defaults={
                "description": entry["description"],
                "category": entry["category"],
                "condition": entry["condition"],
                "is_verified": entry["is_verified"],
            },
        )
        if created:
            # auto_now_add menimpa created_at saat save, jadi diatur lewat update().
            created_at = now - timedelta(days=entry["days_ago"])
            Item._base_manager.filter(pk=item.pk).update(created_at=created_at, updated_at=created_at)


def seed_reverse(apps, schema_editor):
    User, UserProfile, Item = get_models(apps)
    data = load_seed()
    usernames = [entry["username"] for entry in data["users"]]

    seed_items = reduce(
        operator.or_,
        (Q(owner__username=entry["owner"], name=entry["name"]) for entry in data["items"]),
    )
    Item._base_manager.filter(seed_items).delete()
    UserProfile.objects.filter(user__username__in=usernames).delete()
    # Sengaja gagal (ProtectedError) jika user demo masih direferensikan data lain.
    User.objects.filter(username__in=usernames).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("items", "0001_initial"),
        ("authentication", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(seed_forward, seed_reverse),
    ]
