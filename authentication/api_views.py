from django.contrib.auth.models import User
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from authentication.models import UserProfile
from authentication.permissions import IsProfileOwnerOrReadOnly, IsUnauthenticatedOnly
from authentication.serializers import (
    LoginHelpRequestSerializer,
    PublicUserProfileSerializer,
    UserProfileSerializer,
)
from authentication.views import reputation_service


def _build_reputation_summary(user):
    """Menyusun ringkasan reputasi dari reputation_service untuk respons API."""
    reputation_ctx = reputation_service.get_reputation_context(user)
    average_rating = reputation_ctx["average_rating"]
    return {
        "trust_score": reputation_ctx["trust_score"],
        "trust_level": reputation_ctx["trust_level"],
        "trust_description": reputation_ctx["trust_description"],
        "average_rating": round(average_rating, 1) if average_rating is not None else None,
        "reviews_count": reputation_ctx["reviews_count"],
        "completed_loans_count": reputation_ctx["completed_loans_count"],
        "borrowed_loans_count": reputation_ctx["borrowed_loans_count"],
        "owned_items_count": reputation_ctx["owned_items_count"],
    }


@api_view(["GET", "HEAD"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsProfileOwnerOrReadOnly])
def profile_list(request):
    profiles = (
        UserProfile.objects.filter(user__is_active=True)
        .select_related("user")
        .order_by("user__username", "id")
    )
    keyword = request.query_params.get("q", "").strip()
    if keyword:
        profiles = profiles.filter(
            Q(user__username__icontains=keyword) | Q(full_name__icontains=keyword)
        )
    serializer = PublicUserProfileSerializer(
        profiles, many=True, context={"request": request}
    )
    return Response(serializer.data)


@api_view(["GET", "HEAD", "PUT", "PATCH"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def profile_me(request):
    profile, _ = UserProfile.objects.select_related("user").get_or_create(
        user=request.user
    )

    if request.method in ("GET", "HEAD"):
        serializer = UserProfileSerializer(profile, context={"request": request})
        data = dict(serializer.data)
        data["reputation"] = _build_reputation_summary(request.user)
        return Response(data)

    serializer = UserProfileSerializer(
        profile,
        data=request.data,
        partial=request.method == "PATCH",
        context={"request": request},
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()
    data = dict(serializer.data)
    data["reputation"] = _build_reputation_summary(request.user)
    return Response(data)


@api_view(["GET", "HEAD"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsProfileOwnerOrReadOnly])
def profile_detail(request, username):
    target_user = get_object_or_404(User, username=username, is_active=True)
    profile = UserProfile.objects.select_related("user").filter(user=target_user).first()
    if profile is None:
        profile = UserProfile(user=target_user)
    serializer = PublicUserProfileSerializer(profile, context={"request": request})
    data = dict(serializer.data)
    data["reputation"] = _build_reputation_summary(target_user)
    return Response(data)


@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsUnauthenticatedOnly])
def login_help_list_create(request):
    serializer = LoginHelpRequestSerializer(
        data=request.data, context={"request": request}
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(
        {
            "detail": (
                "Permohonan bantuan Anda telah diterima. "
                "Jika akun terdaftar, admin akan menghubungi email kontakmu."
            ),
            "data": serializer.data,
        },
        status=status.HTTP_201_CREATED,
    )
