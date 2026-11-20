from django.urls import path

from review.api_views import MyReportList, ReceivedReviewList, UserReputationDetail

app_name = "review_api"

urlpatterns = [
    path("reports/", MyReportList.as_view(), name="my_reports"),
    path("users/<str:username>/reviews/", ReceivedReviewList.as_view(), name="user_reviews"),
    path("users/<str:username>/reputation/", UserReputationDetail.as_view(), name="user_reputation"),
]
