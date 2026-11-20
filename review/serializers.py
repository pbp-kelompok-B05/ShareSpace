"""Representasi JSON untuk ulasan, reputasi, dan laporan di ShareSpace Mobile."""
from datetime import UTC

from rest_framework import serializers

from review.models import Report, Review


class MyReportSerializer(serializers.ModelSerializer):
    target_type = serializers.CharField(read_only=True)
    target_id = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField(default_timezone=UTC, read_only=True)
    updated_at = serializers.DateTimeField(default_timezone=UTC, read_only=True)

    class Meta:
        model = Report
        fields = (
            "id", "target_type", "target_id", "reason", "description", "status",
            "admin_note", "created_at", "updated_at",
        )
        read_only_fields = fields

    def get_target_id(self, report):
        return str(getattr(report, f"target_{report.target_type}_id"))


class ReceivedReviewSerializer(serializers.ModelSerializer):
    reviewer = serializers.CharField(source="reviewer.username", read_only=True)
    created_at = serializers.DateTimeField(default_timezone=UTC, read_only=True)

    class Meta:
        model = Review
        fields = ("id", "reviewer", "rating", "comment", "created_at")
        read_only_fields = fields


class StarCountSerializer(serializers.Serializer):
    stars = serializers.IntegerField()
    count = serializers.IntegerField()
    percent = serializers.IntegerField()


class TrustLevelSerializer(serializers.Serializer):
    key = serializers.CharField()
    label = serializers.CharField()


class ReputationSerializer(serializers.Serializer):
    username = serializers.CharField()
    average_rating = serializers.FloatField(allow_null=True)
    review_count = serializers.IntegerField()
    completed_count = serializers.IntegerField()
    score = serializers.IntegerField(allow_null=True)
    level = TrustLevelSerializer()
    distribution = StarCountSerializer(many=True)
