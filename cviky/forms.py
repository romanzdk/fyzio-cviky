from django import forms

from cviky.choices import WEEKDAYS
from cviky.models import Exercise, Series


class ExerciseForm(forms.ModelForm):
    class Meta:
        model = Exercise
        fields = ["title", "area", "position", "tags", "steps", "cautions", "reps", "original_text"]
        widgets = {
            "original_text": forms.HiddenInput(),
            "steps": forms.Textarea(attrs={"rows": 5}),
            "cautions": forms.Textarea(attrs={"rows": 3}),
        }


class SeriesForm(forms.ModelForm):
    weekdays = forms.TypedMultipleChoiceField(
        choices=WEEKDAYS,
        coerce=int,
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = Series
        fields = ["name", "weekdays", "remind_at"]
        widgets = {"remind_at": forms.TimeInput(attrs={"type": "time"})}
