from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from django.utils import timezone

from .models import Plant, PlantSpecies, User


class PlantForm(forms.ModelForm):
    class Meta:
        model = Plant
        fields = [
            "name", "nickname", "plant_species", "planting_date",
            "check_interval_days", "status", "image",
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
