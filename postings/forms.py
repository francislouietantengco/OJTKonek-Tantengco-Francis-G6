from django import forms
from django.utils import timezone

from accounts.forms import StyledFormMixin

from .models import Field, OjtPosting


class PostingForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = OjtPosting
        fields = (
            "title", "field", "location", "duration_weeks", "slots",
            "application_deadline", "description", "requirements",
        )
        labels = {
            "duration_weeks": "Duration (weeks)",
            "application_deadline": "Application deadline",
            "requirements": "Skills / requirements",
        }
        help_texts = {
            "duration_weeks": "Between 4 and 24 weeks.",
            "slots": "How many students you will accept.",
        }
        widgets = {
            "application_deadline": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "description": forms.Textarea(attrs={"rows": 5}),
            "requirements": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.company = company or getattr(self.instance, "company", None)
        self.fields["field"].empty_label = "Select a field"
        self.fields["duration_weeks"].widget.attrs.update(min=OjtPosting.MIN_WEEKS, max=OjtPosting.MAX_WEEKS)
        self.fields["slots"].widget.attrs.update(min=1)

    def clean_title(self):
        return self.cleaned_data["title"].strip()

    def clean_location(self):
        return self.cleaned_data["location"].strip()

    def clean_application_deadline(self):
        deadline = self.cleaned_data["application_deadline"]
        # BR-14 for new postings; for edits, compare with the original posting date.
        start = timezone.localdate(self.instance.created_at) if self.instance.pk else timezone.localdate()
        if deadline < start:
            raise forms.ValidationError("The deadline cannot be earlier than the posting date.")
        if not self.instance.pk and deadline < timezone.localdate():
            raise forms.ValidationError("The deadline cannot be in the past.")
        return deadline

    def save(self, commit=True):
        posting = super().save(commit=False)
        if self.company is not None:
            posting.company = self.company
        if commit:
            posting.save()
        return posting


class PostingSearchForm(forms.Form):
    """F-06: search and filter by keyword, field, location and duration."""

    DURATION_CHOICES = [
        ("", "Any duration"),
        ("4-8", "4–8 weeks"),
        ("9-12", "9–12 weeks"),
        ("13-24", "13–24 weeks"),
    ]

    q = forms.CharField(required=False, widget=forms.TextInput(attrs={"placeholder": "Keyword, title or company"}))
    field = forms.ModelChoiceField(queryset=Field.objects.all(), required=False, empty_label="All fields")
    location = forms.CharField(required=False, widget=forms.TextInput(attrs={"placeholder": "City or area"}))
    duration = forms.ChoiceField(choices=DURATION_CHOICES, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            f.widget.attrs.setdefault("class", "input")
