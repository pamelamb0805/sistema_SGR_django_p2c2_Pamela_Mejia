"""Formularios de acceso y recuperación para SGR."""
from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import get_user_model


class SGRAuthenticationForm(AuthenticationForm):
    username = forms.CharField(label="Usuario o correo electrónico", max_length=254)

    def clean_username(self):
        value = self.cleaned_data["username"].strip()
        User = get_user_model()
        if "@" in value:
            match = User.objects.filter(funcionario__email__iexact=value).values_list("username", flat=True).first()
            if match:
                return match
        return value


class SolicitarCodigoForm(forms.Form):
    email = forms.EmailField(label="Correo electrónico", max_length=254)


class VerificarCodigoForm(forms.Form):
    codigo = forms.CharField(label="Código de verificación", min_length=6, max_length=6,
                             widget=forms.TextInput(attrs={"inputmode": "numeric", "autocomplete": "one-time-code"}))


class NuevaClaveForm(forms.Form):
    password1 = forms.CharField(label="Nueva contraseña", widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))
    password2 = forms.CharField(label="Confirmar contraseña", widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean(self):
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError
        data = super().clean()
        p1, p2 = data.get("password1"), data.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Las contraseñas no coinciden.")
        elif p1:
            try:
                validate_password(p1, user=self.user)
            except ValidationError as exc:
                self.add_error("password1", exc)
        return data
