from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .models import User


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
