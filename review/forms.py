from django import forms

from review.models import Report


class ReportForm(forms.ModelForm):
    """Hanya isi laporan; pelapor, target, dan status diisi oleh view."""

    class Meta:
        model = Report
        fields = ["reason", "description"]
        labels = {
            "reason": "Alasan laporan",
            "description": "Ceritakan masalahnya",
        }
        help_texts = {
            "description": "Minimal 20 karakter. Sertakan kronologi singkat agar admin mudah meninjau.",
        }
        widgets = {
            "description": forms.Textarea(attrs={"rows": 6, "maxlength": 1000}),
        }
