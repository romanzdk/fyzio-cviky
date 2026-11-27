from django import forms

from cviky.models import Exercise


class ExerciseForm(forms.ModelForm):
    class Meta:
        model = Exercise
        fields = ["title", "area", "position", "tags", "steps", "cautions", "reps", "original_text"]
        widgets = {
            "original_text": forms.HiddenInput(),
            "steps": forms.Textarea(attrs={"rows": 5}),
            "cautions": forms.Textarea(attrs={"rows": 3}),
        }
