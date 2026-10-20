from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db.models import Q

from core.forms import BootstrapFormMixin

from .models import Cargo, Delegacion, Funcionario, ItemMedible, Rol


class DelegacionForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Delegacion
        fields = ["nombre", "ambito", "estado"]

    def clean_nombre(self):
        return self.cleaned_data["nombre"].strip()


class CargoForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Cargo
        fields = ["nombre_cargo", "vigencia_desde", "vigencia_hasta"]
        widgets = {
            "vigencia_desde": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "vigencia_hasta": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }


class ItemMedibleForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ItemMedible
        fields = ["nombre_item", "tipo", "vigencia"]


class RolForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Rol
        fields = ["nombre_rol", "descripcion"]


class FuncionarioForm(BootstrapFormMixin, forms.ModelForm):
    roles = forms.ModelMultipleChoiceField(
        queryset=Rol.objects.all(), label="Roles",
        help_text="Seleccione uno o más roles (Ctrl + clic para varios).",
        error_messages={"required": "Debe asignar al menos un rol."},
    )

    class Meta:
        model = Funcionario
        fields = ["identificador_institucional", "nombre", "estado", "cargo", "delegacion"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        cargos = Cargo.objects.vigentes()
        delegaciones = Delegacion.objects.filter(estado=Delegacion.ESTADO_ACTIVA)
        if self.instance.pk:
            # Conservar el cargo/delegación actual aunque ya no estén vigentes/activos
            cargos = Cargo.objects.filter(Q(pk=self.instance.cargo_id) | Q(pk__in=cargos.values("pk")))
            delegaciones = Delegacion.objects.filter(
                Q(pk=self.instance.delegacion_id) | Q(pk__in=delegaciones.values("pk")))
            self.fields["roles"].initial = list(self.instance.roles.values_list("pk", flat=True))
        self.fields["cargo"].queryset = cargos
        self.fields["delegacion"].queryset = delegaciones

    def clean_identificador_institucional(self):
        return self.cleaned_data["identificador_institucional"].strip()


class AccesoForm(BootstrapFormMixin, forms.Form):
    """Crea el acceso (usuario y contraseña) de un funcionario o cambia su contraseña."""
    username = forms.CharField(label="Nombre de usuario", max_length=150)
    password1 = forms.CharField(label="Contraseña", widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))
    password2 = forms.CharField(label="Repetir contraseña", widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.usuario = usuario
        if usuario is not None:
            self.fields["username"].initial = usuario.username
            self.fields["username"].disabled = True

    def clean(self):
        datos = super().clean()
        p1, p2 = datos.get("password1"), datos.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Las contraseñas no coinciden.")
        elif p1:
            try:
                validate_password(p1, user=self.usuario)
            except ValidationError as exc:
                self.add_error("password1", exc)
        return datos
