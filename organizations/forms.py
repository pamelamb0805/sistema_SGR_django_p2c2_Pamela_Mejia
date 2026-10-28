from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db.models import Q

from core.forms import BootstrapFormMixin

from .models import Cargo, Delegacion, Funcionario, ItemMedible, Rol, Usuario

from django.core.exceptions import ValidationError

class DelegacionForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Delegacion
        fields = ["codigo", "nombre", "direccion", "comuna", "ambito", "estado"]

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
        fields = ["codigo", "nombre_item", "descripcion", "tipo", "vigencia"]


class RolForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Rol
        fields = ["nombre_rol", "descripcion", "permisos", "alcance_autorizado"]

    permisos = forms.MultipleChoiceField(choices=[
        ("usuarios.ver", "Ver usuarios"), ("usuarios.editar", "Administrar usuarios"),
        ("catalogos.ver", "Ver catálogos"), ("catalogos.editar", "Administrar catálogos"),
        ("atenciones.ver", "Ver atenciones"), ("atenciones.registrar", "Registrar atenciones"),
        ("reportes.ver", "Ver reportes"), ("delegaciones.editar", "Administrar delegaciones")
    ], required=False, widget=forms.CheckboxSelectMultiple)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.initial["permisos"] = self.instance.permisos or []

    def clean_permisos(self):
        return self.cleaned_data.get("permisos", [])

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.permisos = self.cleaned_data.get("permisos", [])
        if commit:
            obj.save()
            self.save_m2m()
        return obj


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
    email = forms.EmailField(
    label="Correo electrónico",
    max_length=254,
    required=True,
    )

    delegaciones_autorizadas = forms.ModelMultipleChoiceField(
        label="Delegaciones autorizadas",
        queryset=Delegacion.objects.all(),
        required=False,
        widget=forms.SelectMultiple(
            attrs={"class": "form-select"}
        ),
    )

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.usuario = usuario
        if usuario is not None:
            self.fields["username"].initial = usuario.username
            self.fields["username"].disabled = True
        if usuario:
            self.fields["username"].initial = usuario.username
            self.fields["username"].disabled = True
            self.fields["email"].initial = usuario.email
            self.fields["delegaciones_autorizadas"].initial = (
                usuario.delegaciones_autorizadas.all()
            )
            self.fields["password1"].required = False
            self.fields["password2"].required = False

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

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        duplicados = Usuario.objects.filter(email__iexact=email)

        usuario_actual = getattr(self, "usuario", None)
        if usuario_actual and usuario_actual.pk:
            duplicados = duplicados.exclude(pk=usuario_actual.pk)

        if duplicados.exists():
            raise ValidationError(
                "Ese correo ya está asociado a otra cuenta."
            )

        return email

class UsuarioAdminForm(BootstrapFormMixin, forms.ModelForm):
    password1 = forms.CharField(
        label="Contraseña",
        required=False,
        widget=forms.PasswordInput(
            attrs={"autocomplete": "new-password"}
        ),
    )
    password2 = forms.CharField(
        label="Confirmar contraseña",
        required=False,
        widget=forms.PasswordInput(
            attrs={"autocomplete": "new-password"}
        ),
    )

    class Meta:
        model = Usuario
        fields = [
            "username",
            "email",
            "funcionario",
            "delegaciones_autorizadas",
            "activo_acceso",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["email"].required = True
        self.fields["delegaciones_autorizadas"].queryset = (
            Delegacion.objects.all()
        )

        if self.instance and self.instance.pk:
            self.fields["password1"].help_text = (
                "Déjala vacía si no quieres cambiar la contraseña."
            )
            self.fields["password2"].help_text = (
                "Déjala vacía si no quieres cambiar la contraseña."
            )
        else:
            self.fields["password1"].required = True
            self.fields["password2"].required = True

        # --- MODIFICACIÓN INTEGRADA ---
        if self.instance and self.instance.pk and self.instance.funcionario_id:
            funcionarios = Funcionario.objects.filter(
                Q(usuario__isnull=True)
                | Q(pk=self.instance.funcionario_id)
            )
        else:
            funcionarios = Funcionario.objects.filter(
                usuario__isnull=True
            )

        self.fields["funcionario"].queryset = funcionarios 

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        duplicados = Usuario.objects.filter(
            username__iexact=username
        )

        if self.instance and self.instance.pk:
            duplicados = duplicados.exclude(pk=self.instance.pk)

        if duplicados.exists():
            raise ValidationError(
                "Ese nombre de usuario ya está registrado."
            )

        return username

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        duplicados = Usuario.objects.filter(email__iexact=email)

        if self.instance and self.instance.pk:
            duplicados = duplicados.exclude(pk=self.instance.pk)

        if duplicados.exists():
            raise ValidationError(
                "Ese correo ya está asociado a otra cuenta."
            )

        return email

    def clean(self):
        datos = super().clean()
        password1 = datos.get("password1")
        password2 = datos.get("password2")

        es_nuevo = not bool(
            self.instance and self.instance.pk
        )

        if es_nuevo and not password1:
            self.add_error(
                "password1",
                "Debes definir una contraseña para la nueva cuenta.",
            )

        if password1 or password2:
            if password1 != password2:
                self.add_error(
                    "password2",
                    "Las contraseñas no coinciden.",
                )
            elif password1:
                try:
                    validate_password(password1, user=self.instance)
                except ValidationError as exc:
                    self.add_error("password1", exc)

        funcionario = datos.get("funcionario")

        # Una cuenta sin funcionario asociado no puede quedar habilitada.
        if not funcionario:
            datos["activo_acceso"] = False

        return datos

    def save(self, commit=True):
        usuario = super().save(commit=False)
        password = self.cleaned_data.get("password1")

        if password:
            usuario.set_password(password)

        if not usuario.funcionario:
            usuario.activo_acceso = False

        if commit:
            usuario.save()
            self.save_m2m()

        return usuario