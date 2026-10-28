"""Formularios de acceso, registro y recuperación para SGR."""

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError


class SGRAuthenticationForm(AuthenticationForm):
    username = forms.CharField(
        label="Usuario o correo electrónico",
        max_length=254,
    )

    def clean_username(self):
        value = self.cleaned_data["username"].strip()
        User = get_user_model()

        if "@" in value:
            user = User.objects.filter(email__iexact=value).first()
            if user:
                return user.get_username()

        return value


class RegistroUsuarioForm(forms.Form):
    username = forms.CharField(
        label="Nombre de usuario",
        max_length=150,
    )
    email = forms.EmailField(
        label="Correo electrónico",
        max_length=254,
    )
    password1 = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(
            attrs={"autocomplete": "new-password"}
        ),
    )
    password2 = forms.CharField(
        label="Confirmar contraseña",
        widget=forms.PasswordInput(
            attrs={"autocomplete": "new-password"}
        ),
    )

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        User = get_user_model()

        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError(
                "Ese nombre de usuario ya está registrado."
            )

        return username

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        User = get_user_model()

        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError(
                "Ya existe una cuenta asociada a ese correo."
            )

        return email

    def clean(self):
        data = super().clean()
        password1 = data.get("password1")
        password2 = data.get("password2")

        if password1 and password2 and password1 != password2:
            self.add_error(
                "password2",
                "Las contraseñas no coinciden.",
            )

        if password1:
            try:
                validate_password(password1)
            except ValidationError as exc:
                self.add_error("password1", exc)

        return data


class SolicitarCodigoForm(forms.Form):
    email = forms.EmailField(
        label="Correo electrónico",
        max_length=254,
    )


class VerificarCodigoForm(forms.Form):
    codigo = forms.CharField(
        label="Código de verificación",
        min_length=6,
        max_length=6,
        widget=forms.TextInput(
            attrs={
                "inputmode": "numeric",
                "autocomplete": "one-time-code",
            }
        ),
    )

    def clean_codigo(self):
        codigo = self.cleaned_data["codigo"].strip()

        if not codigo.isdigit():
            raise ValidationError(
                "El código debe contener seis números."
            )

        return codigo


class NuevaClaveForm(forms.Form):
    password1 = forms.CharField(
        label="Nueva contraseña",
        widget=forms.PasswordInput(
            attrs={"autocomplete": "new-password"}
        ),
    )
    password2 = forms.CharField(
        label="Confirmar contraseña",
        widget=forms.PasswordInput(
            attrs={"autocomplete": "new-password"}
        ),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean(self):
        data = super().clean()
        password1 = data.get("password1")
        password2 = data.get("password2")

        if password1 and password2 and password1 != password2:
            self.add_error(
                "password2",
                "Las contraseñas no coinciden.",
            )
        elif password1:
            try:
                validate_password(password1, user=self.user)
            except ValidationError as exc:
                self.add_error("password1", exc)

        return data