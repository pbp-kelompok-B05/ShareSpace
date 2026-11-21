
import copy

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import CODLocation, PickupSchedule, Place


class CODLocationSerializer(serializers.ModelSerializer):
    latitude = serializers.DecimalField(
        max_digits=9,
        decimal_places=6,
        min_value=-90,
        max_value=90,
    )
    longitude = serializers.DecimalField(
        max_digits=9,
        decimal_places=6,
        min_value=-180,
        max_value=180,
    )

    class Meta:
        model = CODLocation
        fields = [
            "id",
            "name",
            "address",
            "latitude",
            "longitude",
            "notes",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_by",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        instance = copy.copy(self.instance) if self.instance else CODLocation()

        for field, value in attrs.items():
            setattr(instance, field, value)

        if self.instance is None:
            instance.created_by = self.context["request"].user

        try:
            instance.full_clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                getattr(exc, "message_dict", exc.messages)
            )

        return attrs


class PickupScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = PickupSchedule
        fields = [
            "id",
            "loan_request",
            "cod_location",
            "schedule_type",
            "scheduled_time",
            "notes",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "loan_request",
            "created_by",
            "created_at",
            "updated_at",
        ]
        validators = []

    def validate(self, attrs):
        instance = copy.copy(self.instance) if self.instance else PickupSchedule()

        for field, value in attrs.items():
            setattr(instance, field, value)

        loan = (
            self.context.get("loan_request")
            or getattr(self.instance, "loan_request", None)
        )

        if loan:
            instance.loan_request = loan

        if self.instance is None:
            instance.created_by = self.context["request"].user

        try:
            instance.full_clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                getattr(exc, "message_dict", exc.messages)
            )

        return attrs


class PlaceSerializer(serializers.ModelSerializer):
    distance_meters = serializers.SerializerMethodField()

    class Meta:
        model = Place
        fields = [
            "osm_id",
            "name",
            "address",
            "kind",
            "latitude",
            "longitude",
            "distance_meters",
        ]
        read_only_fields = fields

    def get_distance_meters(self, obj):
        return getattr(obj, "distance_meters", None)
