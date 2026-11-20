from django.utils import timezone
from rest_framework import serializers
from items.models import Item
from loans.models import LoanRequest

def display_name(user):
    profile = getattr(user, "userprofile", None)

    return (profile.full_name.strip() if profile else "") or user.username

# Loan request serializer
class LoanRequestSerializer(serializers.ModelSerializer):
    item = serializers.PrimaryKeyRelatedField(queryset=Item.objects.visible())
    item_name = serializers.CharField(source="item.name", read_only=True)
    image_url = serializers.CharField(source="item.image_url", read_only=True)
    owner = serializers.IntegerField(source="item.owner_id", read_only=True)
    owner_name = serializers.SerializerMethodField()
    borrower_name = serializers.SerializerMethodField()
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    return_requested = serializers.SerializerMethodField()
    contact_url = serializers.SerializerMethodField()
    available_actions = serializers.SerializerMethodField()
    initial = serializers.CharField(max_length=100, required=False, allow_blank=True)

    class Meta:
        model = LoanRequest
        fields = [
            "id", 
            "item", 
            "item_name", 
            "image_url", 
            "owner", 
            "owner_name", 
            "borrower", 
            "borrower_name",
            "start_date", 
            "due_date", 
            "notes", 
            "initial", 
            "status", 
            "status_label", 
            "return_requested_at",
            "return_requested", 
            "contact_url", 
            "available_actions", 
            "created_at", 
            "updated_at",
        ]
        read_only_fields = ["id", "borrower", "status", "return_requested_at", "created_at", "updated_at"]
        validators = []

    def get_fields(self):
        fields = super().get_fields()

        if self.instance is not None:
            fields["item"].read_only = True

        return fields

    def validate(self, attrs):
        start_date = attrs.get("start_date", getattr(self.instance, "start_date", None))
        due_date = attrs.get("due_date", getattr(self.instance, "due_date", None))
        start_changed = self.instance is None or start_date != self.instance.start_date

        if start_date and start_changed and start_date < timezone.localdate():
            raise serializers.ValidationError({
                "start_date": "Tanggal mulai tidak boleh di masa lalu.",
            })

        if start_date and due_date and due_date < start_date:
            raise serializers.ValidationError({
                "due_date": "Tanggal selesai harus setelah atau sama dengan tanggal mulai.",
            })

        return attrs

    def get_owner_name(self, obj):
        return display_name(obj.item.owner)

    def get_borrower_name(self, obj):
        return display_name(obj.borrower)

    def get_return_requested(self, obj):
        return obj.return_requested_at is not None

    def get_contact_url(self, obj):
        request = self.context.get("request")

        if request is None or not request.user.is_authenticated:
            return None

        if obj.status not in (LoanRequest.Status.APPROVED, LoanRequest.Status.BORROWED):
            return None

        person = obj.item.owner if obj.borrower_id == request.user.pk else obj.borrower
        profile = getattr(person, "userprofile", None)
        phone = profile.phone_number.strip() if profile else ""

        if phone:
            return "tel:" + phone

        if person.email:
            return "mailto:" + person.email

        return None

    def get_available_actions(self, obj):
        request = self.context.get("request")

        if request is None or not request.user.is_authenticated:
            return []

        if obj.borrower_id == request.user.pk:
            if obj.status == LoanRequest.Status.PENDING:
                return ["edit", "cancel"]

            if obj.status == LoanRequest.Status.BORROWED and not obj.return_requested_at:
                return ["request_return"]

        if obj.item.owner_id == request.user.pk:
            if obj.status == LoanRequest.Status.PENDING:
                return ["approve", "reject"]

            if obj.status == LoanRequest.Status.APPROVED:
                return ["mark_borrowed"]

            if obj.status == LoanRequest.Status.BORROWED and obj.return_requested_at:
                return ["complete"]

        return []
    