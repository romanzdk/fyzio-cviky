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
        labels = {
            "title": "Název",
            "area": "Oblast",
            "position": "Poloha",
            "tags": "Štítky",
            "steps": "Postup",
            "cautions": "Na co dát pozor",
            "reps": "Opakování",
        }
        help_texts = {"tags": "Oddělené čárkou.", "steps": "Jeden krok na řádek."}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("area", "position"):
            self.fields[name].choices = [("", "— nevybráno —"), *self.fields[name].choices[1:]]


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

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("remind_at") and not cleaned.get("weekdays"):
            raise forms.ValidationError(
                "Vyber aspoň jeden den, jinak připomínka nepřijde."
            )
        return cleaned


class ProfileForm(forms.Form):
    neglect_days = forms.IntegerField(
        min_value=1, max_value=60, label="Dlouho jsi nedělal (dny)"
    )
