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


class ModerationForm(forms.Form):
    """Aksi admin pada satu laporan. Status kosong berarti hanya menyimpan catatan."""

    status = forms.ChoiceField(choices=[("", "")] + Report.Status.choices, required=False)
    admin_note = forms.CharField(max_length=1000, required=False)
