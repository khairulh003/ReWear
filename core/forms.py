from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
    UserCreationForm,
)
from django.contrib.auth.models import User

from .models import ClothingRequest, Event


class PlaceholderFormMixin:
    """
    Applies Bootstrap's form-control/form-select classes to every widget
    plus the placeholder text.
    """

    placeholders = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault("class", "form-select")
            else:
                widget.attrs.setdefault("class", "form-control")
            if name in self.placeholders:
                widget.attrs.setdefault("placeholder", self.placeholders[name])


class LoginForm(PlaceholderFormMixin, AuthenticationForm):
    placeholders = {"username": "Your username"}


class RegisterForm(PlaceholderFormMixin, UserCreationForm):
    """
    Registration form. Django provides no built-in registration view,
    so this is built manually. Usernames capped at 15 characters.
    """

    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=60, required=True, label="First name")
    last_name = forms.CharField(max_length=60, required=True, label="Last name")
    username = forms.CharField(
        max_length=15,
        label="Username",
        help_text="15 characters or fewer. Letters, digits and @/./+/-/_ only.",
    )

    placeholders = {
        "first_name": "First name",
        "last_name": "Last name",
        "username": "Pick a username",
        "email": "you@example.com",
        "password1": "Create a password",
        "password2": "Repeat your password",
    }

    class Meta:
        model = User
        fields = ["first_name", "last_name", "username", "email", "password1", "password2"]

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user


class ClothingRequestForm(PlaceholderFormMixin, forms.ModelForm):
    placeholders = {
        "organisation_name": "Your organisation's name",
        "contact_name": "Your name",
        "email": "you@organisation.org",
        "clothing_type": "e.g. Warm jackets, children's clothing",
        "quantity": "e.g. 100 pieces",
        "message": "Who this is for, and by when you'd need it",
    }

    class Meta:
        model = ClothingRequest
        fields = [
            "organisation_name",
            "contact_name",
            "email",
            "clothing_type",
            "quantity",
            "message",
        ]
        labels = {
            "organisation_name": "Organisation name",
            "contact_name": "Contact person",
            "email": "Contact email",
            "clothing_type": "Type of clothing needed",
            "quantity": "Approximate amount needed",
            "message": "Tell us more",
        }
        help_texts = {"clothing_type": "", "quantity": ""}
        widgets = {"message": forms.Textarea(attrs={"rows": 4})}


class EventForm(PlaceholderFormMixin, forms.ModelForm):
    class Meta:
        model = Event
        fields = [
            "title",
            "description",
            "event_type",
            "date",
            "location",
            "allow_participants",
            "allow_volunteers",
        ]
        widgets = {
            "date": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
            ),
            "description": forms.Textarea(attrs={"rows": 5}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["date"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["location"].initial = "ReWear Facility, Tampines"

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("allow_participants") and not cleaned.get("allow_volunteers"):
            raise forms.ValidationError(
                "An event must allow participants, request volunteers, or both."
            )
        return cleaned


class ProfileForm(PlaceholderFormMixin, forms.ModelForm):
    first_name = forms.CharField(max_length=60, required=True, label="First name")
    last_name = forms.CharField(max_length=60, required=True, label="Last name")
    username = forms.CharField(max_length=15, label="Username")

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email"]
        labels = {"email": "Email", "username": "Username"}
        help_texts = {"username": ""}


class PasswordChangeStyledForm(PlaceholderFormMixin, PasswordChangeForm):
    """Django's built-in password change form with the site's field styling."""
