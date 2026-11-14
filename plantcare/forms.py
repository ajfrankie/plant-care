from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.core.validators import MaxLengthValidator

from django.utils import timezone

from . import health_library
from .models import CareLog, CareTask, HealthCase, HealthCheck, Plant, PlantSpecies, User, WaterReminder
from .models.choices import SpecialFeature


class MultipleTextInput(forms.TextInput):
    """Several text inputs sharing one name; submits every value."""

    def value_from_datadict(self, data, files, name):
        if hasattr(data, "getlist"):
            return data.getlist(name)
        return data.get(name, [])

    def value_omitted_from_data(self, data, files, name):
        # No inputs submitted means an empty list, not "keep the old value".
        return False


class TextListField(forms.Field):
    """A list of short strings, entered as several text inputs."""

    widget = MultipleTextInput

    def __init__(self, *, item_label, max_length=60, max_items=10, **kwargs):
        self.item_label = item_label
        self.max_length = max_length
        self.max_items = max_items
        super().__init__(**kwargs)

    def to_python(self, value):
        if not value:
            return []
        if isinstance(value, str):
            value = [value]
        items, seen = [], set()
        for item in value:
            item = str(item).strip()
            if item and item.lower() not in seen:  # drop blanks and duplicates
                seen.add(item.lower())
                items.append(item)
        return items

    def validate(self, value):
        super().validate(value)
        if len(value) > self.max_items:
            raise ValidationError(f"Add at most {self.max_items} {self.item_label}s.")
        for item in value:
            if len(item) > self.max_length:
                raise ValidationError(
                    f"Each {self.item_label} must be {self.max_length} characters or fewer."
                )

    def has_changed(self, initial, data):
        return self.to_python(initial) != self.to_python(data)


class PlantForm(forms.ModelForm):
    flower_colors = TextListField(item_label="flower color", max_length=60, required=False)

    class Meta:
        model = Plant
        fields = [
            "name", "nickname", "plant_species", "planting_date",
            "check_interval_days", "status", "image", "has_flowers", "flower_colors",
        ]

    MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB

    def clean_image(self):
        image = self.cleaned_data.get("image")
        if image and image.size > self.MAX_IMAGE_SIZE:
            raise ValidationError("Image must be 5 MB or smaller.")
        return image

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["plant_species"].queryset = PlantSpecies.objects.order_by("common_name")
        self.fields["plant_species"].empty_label = "Select a species..."
        if self.instance.pk and self.instance.planting_date:
            # Date inputs need YYYY-MM-DD, not the localized display format.
            self.initial["planting_date"] = self.instance.planting_date.isoformat()

    def clean_name(self):
        return self.cleaned_data["name"].strip()

    def clean_nickname(self):
        return self.cleaned_data["nickname"].strip()

    def clean_planting_date(self):
        planting_date = self.cleaned_data["planting_date"]
        if planting_date > timezone.localdate():
            raise ValidationError("Planting date cannot be in the future.")
        return planting_date

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get("has_flowers"):
            # Colors only make sense for a flowering plant.
            cleaned_data["flower_colors"] = []
        elif "flower_colors" in cleaned_data and not cleaned_data["flower_colors"]:
            self.add_error("flower_colors", "Add at least one flower color.")
        return cleaned_data


class CareTaskForm(forms.ModelForm):
    class Meta:
        model = CareTask
        fields = ["plant", "kind", "due_date", "repeat_every_days", "notes"]

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        # Tasks can only be scheduled for the user's own plants.
        self.fields["plant"].queryset = Plant.objects.filter(created_user=user).order_by("name")
        self.fields["plant"].empty_label = "Select a plant..."
        self.fields["repeat_every_days"].label = "Repeat every (days)"

    def clean_due_date(self):
        due_date = self.cleaned_data["due_date"]
        if due_date < timezone.localdate():
            raise ValidationError("Due date cannot be in the past.")
        return due_date

    def clean_notes(self):
        return self.cleaned_data["notes"].strip()


class CareLogForm(forms.ModelForm):
    """Record something already done to a plant (Care History page)."""

    performed_at = forms.DateTimeField(
        label="When", input_formats=["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%d"]
    )

    class Meta:
        model = CareLog
        fields = ["plant", "activity", "performed_at", "notes"]

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        # Activities can only be logged for the user's own plants.
        self.fields["plant"].queryset = Plant.objects.filter(created_user=user).order_by("name")
        self.fields["plant"].empty_label = "Select a plant..."
        self.fields["notes"].max_length = 1000
        self.fields["notes"].validators.append(MaxLengthValidator(1000))

    def clean_performed_at(self):
        performed_at = self.cleaned_data["performed_at"]
        if performed_at > timezone.now() + timedelta(minutes=1):
            raise ValidationError("This can't be in the future.")
        return performed_at

    def clean_notes(self):
        return self.cleaned_data["notes"].strip()


class WaterReminderForm(forms.ModelForm):
    class Meta:
        model = WaterReminder
        fields = [
            "plant", "frequency_days", "next_due_date", "reminder_time",
            "method", "amount_ml", "notes", "is_active",
        ]
        labels = {
            "frequency_days": "Water every (days)",
            "next_due_date": "Next watering",
            "amount_ml": "Amount (ml)",
            "is_active": "Reminder is on",
        }

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        # Reminders can only be set for the user's own plants.
        self.fields["plant"].queryset = Plant.objects.filter(created_user=user).order_by("name")
        self.fields["plant"].empty_label = "Select a plant..."
        if self.instance.pk:
            # Date/time inputs need ISO values, not the localized display format.
            self.initial["next_due_date"] = self.instance.next_due_date.isoformat()
            self.initial["reminder_time"] = self.instance.reminder_time.strftime("%H:%M")

    def clean_next_due_date(self):
        due = self.cleaned_data["next_due_date"]
        unchanged = self.instance.pk and due == self.instance.next_due_date
        if due < timezone.localdate() and not unchanged:
            raise ValidationError("Next watering cannot be in the past.")
        return due

    def clean_notes(self):
        return self.cleaned_data["notes"].strip()


MAX_HEALTH_IMAGE_SIZE = 8 * 1024 * 1024  # 8 MB


def _check_photo(image):
    if image and image.size > MAX_HEALTH_IMAGE_SIZE:
        raise ValidationError("Photo must be 8 MB or smaller.")
    return image


class HealthCheckForm(forms.Form):
    """New health check: a photo plus either a known issue or a request to find it."""

    FIND, KNOWN = "find", "known"

    plant = forms.ModelChoiceField(queryset=Plant.objects.none(), empty_label="Select a plant...")
    image = forms.ImageField(label="Photo of the plant or a leaf")
    notes = forms.CharField(
        label="What have you noticed?", required=False, max_length=500, widget=forms.Textarea
    )
    issue_key = forms.ChoiceField(label="Known issue", required=False)
    other_issue = forms.CharField(label="Other issue", required=False, max_length=120)
    severity = forms.ChoiceField(choices=HealthCase.Severity.choices, initial=HealthCase.Severity.MODERATE)
    check_every_days = forms.IntegerField(
        label="Photo update every (days)", min_value=1, max_value=60, initial=7
    )
    action = forms.ChoiceField(choices=[(FIND, "Find the issue"), (KNOWN, "I know the issue")])

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["plant"].queryset = Plant.objects.filter(created_user=user).order_by("name")
        self.fields["issue_key"].choices = [("", "Select an issue...")] + health_library.CHOICES

    def clean_image(self):
        return _check_photo(self.cleaned_data["image"])

    def clean_other_issue(self):
        return self.cleaned_data["other_issue"].strip()

    def clean_notes(self):
        return self.cleaned_data["notes"].strip()

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("action") == self.KNOWN and not (
            cleaned_data.get("issue_key") or cleaned_data.get("other_issue")
        ):
            self.add_error("issue_key", "Choose the issue, or type it under \"Other issue\".")
        return cleaned_data


class HealthUpdateForm(forms.Form):
    """A follow-up photo for a health case being tracked."""

    image = forms.ImageField(label="New photo")
    progress = forms.ChoiceField(
        label="How does it look?", required=False,
        choices=[("", "Let the photo analysis decide")] + [
            c for c in HealthCheck.Progress.choices if c[0] != HealthCheck.Progress.FIRST
        ],
    )
    notes = forms.CharField(label="Notes", required=False, max_length=500, widget=forms.Textarea)
    analyse = forms.BooleanField(label="Analyse this photo", required=False, initial=True)

    def clean_image(self):
        return _check_photo(self.cleaned_data["image"])

    def clean_notes(self):
        return self.cleaned_data["notes"].strip()


class SpeciesForm(forms.ModelForm):
    # Stored as a comma-separated list in PlantSpecies.special_features.
    special_features = forms.MultipleChoiceField(choices=SpecialFeature.choices, required=False)
    soil_type = TextListField(item_label="soil type", max_length=120, required=False)
    flower_color = TextListField(item_label="flower color", max_length=60, required=False)

    class Meta:
        model = PlantSpecies
        fields = [
            "common_name", "scientific_name", "family", "category", "origin",
            "description", "difficulty", "light", "watering", "fertilizing",
            "temperature_range", "humidity", "soil_type", "growth_rate",
            "mature_height", "mature_width", "foliage_color", "flower_color",
            "special_features",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["fertilizing"].required = True
        if self.instance.pk:
            self.initial["special_features"] = [
                f for f in self.instance.special_features.split(",") if f
            ]

    def clean_common_name(self):
        return self.cleaned_data["common_name"].strip()

    def clean_scientific_name(self):
        name = self.cleaned_data["scientific_name"].strip()
        taken = PlantSpecies.objects.filter(scientific_name__iexact=name)
        if self.instance.pk:
            taken = taken.exclude(pk=self.instance.pk)
        if taken.exists():
            raise ValidationError("A species with this scientific name already exists.")
        return name

    def clean_special_features(self):
        return ",".join(self.cleaned_data["special_features"])


class LoginForm(forms.Form):
    INVALID_CREDENTIALS = "Incorrect email or password."
    NOT_ACTIVE = "Your account is not active. Please activate your account to sign in."

    email = forms.EmailField()
    password = forms.CharField(strip=False, widget=forms.PasswordInput)
    remember = forms.BooleanField(required=False)

    user = None

    def clean_email(self):
        return self.cleaned_data["email"].lower()

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get("email")
        password = cleaned_data.get("password")

        if email and password:
            inactive_user = User.objects.filter(email=email, is_active=False).first()
            if inactive_user is not None:
                # Only someone who knows the password learns the account's status.
                if inactive_user.check_password(password):
                    raise ValidationError(self.NOT_ACTIVE)
                raise ValidationError(self.INVALID_CREDENTIALS)

            self.user = authenticate(email=email, password=password)
            if self.user is None:
                raise ValidationError(self.INVALID_CREDENTIALS)

        return cleaned_data


class RegisterForm(forms.ModelForm):
    password = forms.CharField(strip=False, widget=forms.PasswordInput)
    confirm_password = forms.CharField(strip=False, widget=forms.PasswordInput)
    terms = forms.BooleanField(
        error_messages={"required": "Please accept the terms to continue."}
    )

    class Meta:
        model = User
        fields = ["full_name", "email"]

    def clean_email(self):
        return self.cleaned_data["email"].lower()

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password and confirm_password and password != confirm_password:
            self.add_error("confirm_password", "Passwords do not match.")
        elif password:
            candidate = User(
                full_name=cleaned_data.get("full_name", ""),
                email=cleaned_data.get("email", ""),
            )
            try:
                validate_password(password, user=candidate)
            except ValidationError as error:
                self.add_error("password", error)

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user
