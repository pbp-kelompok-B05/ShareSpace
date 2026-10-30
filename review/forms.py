from django import forms

from review.models import Report, Review


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
            "description": forms.Textarea(attrs={
                "rows": 6,
                "maxlength": 1000,
                # Dipakai static/review/js/char-counter.js; samakan dengan validator model.
                "data-char-counter": "",
                "data-min-length": 20,
            }),
        }


class ModerationForm(forms.Form):
    """Aksi admin pada satu laporan. Status kosong berarti hanya menyimpan catatan."""

    status = forms.ChoiceField(choices=[("", "")] + Report.Status.choices, required=False)
    admin_note = forms.CharField(max_length=1000, required=False)


class ReviewForm(forms.ModelForm):
    """Isi ulasan saja; transaksi, penulis, dan pihak yang dinilai diisi oleh view."""

    RATING_CHOICES = [(value, f"{value} bintang") for value in range(Review.MIN_RATING, Review.MAX_RATING + 1)]

    # Pilihan tetap 1–5 agar nilai lain ditolak sebagai "pilihan tidak valid".
    rating = forms.TypedChoiceField(
        label="Rating",
        choices=RATING_CHOICES,
        coerce=int,
        widget=forms.RadioSelect,
        error_messages={"required": "Pilih rating 1 sampai 5 bintang."},
    )

    class Meta:
        model = Review
        fields = ["rating", "comment"]
        labels = {"comment": "Ceritakan pengalamanmu (opsional)"}
        help_texts = {"comment": "Ulasan tampil di profil pihak yang kamu nilai."}
        widgets = {
            "comment": forms.Textarea(attrs={
                "rows": 5,
                "maxlength": 1000,
                "data-char-counter": "",
            }),
        }
