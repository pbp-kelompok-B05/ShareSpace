"""Endpoint baca untuk ulasan, reputasi, dan laporan pengguna."""
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from rest_framework import generics, serializers
from rest_framework.authentication import SessionAuthentication
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response

from review.models import Report, Review
from review.reputation import get_reputation
from review.review_views import USER_REVIEWS_PER_PAGE
from review.serializers import MyReportSerializer, ReceivedReviewSerializer, ReputationSerializer
from review.views import REPORTS_PER_PAGE


class AuthenticatedReviewAPI:
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]
    renderer_classes = [JSONRenderer]


class ReportPagination(PageNumberPagination):
    page_size = REPORTS_PER_PAGE


class MyReportList(AuthenticatedReviewAPI, generics.ListAPIView):
    serializer_class = MyReportSerializer
    pagination_class = ReportPagination

    def get_queryset(self):
        queryset = Report.objects.filter(reporter=self.request.user).order_by("-created_at", "-pk")
        status_filter = self.request.query_params.get("status")
        if status_filter:
            if status_filter not in Report.Status.values:
                raise serializers.ValidationError({"status": "Status laporan tidak valid."})
            queryset = queryset.filter(status=status_filter)
        return queryset


class UserReviewAPI(AuthenticatedReviewAPI):
    def get_target_user(self):
        return get_object_or_404(
            get_user_model(), username=self.kwargs["username"], is_active=True
        )


class ReceivedReviewPagination(PageNumberPagination):
    page_size = USER_REVIEWS_PER_PAGE


class ReceivedReviewList(UserReviewAPI, generics.ListAPIView):
    serializer_class = ReceivedReviewSerializer
    pagination_class = ReceivedReviewPagination

    def get_queryset(self):
        return (
            Review.objects.visible()
            .filter(reviewee=self.get_target_user())
            .select_related("reviewer")
            .order_by("-created_at", "-pk")
        )


class UserReputationDetail(UserReviewAPI, generics.GenericAPIView):
    serializer_class = ReputationSerializer

    def get(self, request, *args, **kwargs):
        user = self.get_target_user()
        reputation = get_reputation(user)
        serializer = self.get_serializer({
            "username": user.username,
            "average_rating": reputation.average_rating,
            "review_count": reputation.review_count,
            "completed_count": reputation.completed_count,
            "score": reputation.score,
            "level": reputation.level,
            "distribution": reputation.distribution,
        })
        return Response(serializer.data)
