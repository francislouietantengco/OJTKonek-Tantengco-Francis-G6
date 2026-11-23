from django import forms

from accounts.forms import StyledFormMixin

from .models import Application


class ApplicationForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Application
        fields = ("cover_letter",)
        labels = {"cover_letter": "Cover letter (optional)"}
        widgets = {
            "cover_letter": forms.Textarea(
                attrs={"rows": 6, "placeholder": "Tell the company why you are a good fit for this OJT."}
            )
        }

    def clean_cover_letter(self):
        text = (self.cleaned_data.get("cover_letter") or "").strip()
        if len(text) > 3000:
            raise forms.ValidationError("Keep your cover letter under 3,000 characters.")
        return text or None


class DecisionForm(StyledFormMixin, forms.Form):
    ACTIONS = [("review", "Mark as under review"), ("accept", "Accept"), ("reject", "Reject")]

    action = forms.ChoiceField(choices=ACTIONS, widget=forms.HiddenInput)
    remarks = forms.CharField(
        max_length=255,
        required=False,
        label="Remarks",
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Required when rejecting. The student will see these remarks.",
    )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("action") == "reject" and not (cleaned.get("remarks") or "").strip():
            self.add_error("remarks", "Remarks are required when rejecting an application.")  # BR-25
        return cleaned
