from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db.models import Q

from core.forms import BootstrapFormMixin

from .models import Cargo, Delegacion, Funcionario, ItemMedible, Rol, Usuario

from django.core.exceptions import ValidationError
from django.core.exceptions import ValidationError

def _roles_disponibles_para_actor(actor, roles_actuales_ids=None):
    """
    Devuelve únicamente los roles que el actor puede delegar.

    Conserva los roles que ya tenía el funcionario editado,
    pero no permite conceder nuevos privilegios superiores.
    """
    roles_actuales_ids = set(roles_actuales_ids or [])

    if actor is None:
        return Rol.objects.all()

    if not getattr(actor, "is_authenticated", False):
        return Rol.objects.none()

    if getattr(actor, "is_superuser", False):
        return Rol.objects.all()

    from core.mixins import get_permisos, get_alcances

    permisos_actor = get_permisos(actor)
    alcances_actor = get_alcances(actor)

    roles_permitidos = []

    for rol in Rol.objects.all():

        # Permite conservar roles que ya estaban asignados.
        if rol.pk in roles_actuales_ids:
            roles_permitidos.append(rol.pk)
            continue

        # Nadie puede delegar el rol Administrador.
        if rol.nombre_rol.strip().casefold() == "administrador":
            continue

        # El alcance global está reservado al superusuario.
        if rol.alcance_autorizado == "global":
            continue

        permisos_rol = set(rol.permisos or [])

        if not permisos_rol.issubset(permisos_actor):
            continue

        if (
            rol.alcance_autorizado == "multiples"
            and "multiples" not in alcances_actor
        ):
            continue

        roles_permitidos.append(rol.pk)

    return Rol.objects.filter(pk__in=roles_permitidos)

class DelegacionForm(BootstrapFormMixin, forms.ModelForm):

    class Meta:
        model = Delegacion
        fields = [
            "codigo",
            "nombre",
            "direccion",
            "comuna",
            "ambito",
            "estado",
        ]

    def clean_codigo(self):
        codigo = self.cleaned_data["codigo"].strip()

        if not codigo:
            raise ValidationError(
                "El código de la delegación es obligatorio."
            )

        duplicados = Delegacion.objects.filter(
            codigo__iexact=codigo
        )

        if self.instance and self.instance.pk:
            duplicados = duplicados.exclude(pk=self.instance.pk)

        if duplicados.exists():
            raise ValidationError(
                "Ya existe una delegación con ese código."
            )

        return codigo

    def clean_nombre(self):
        nombre = self.cleaned_data["nombre"].strip()

        if not nombre:
            raise ValidationError(
                "El nombre de la delegación es obligatorio."
            )

        duplicados = Delegacion.objects.filter(
            nombre__iexact=nombre
        )

        if self.instance and self.instance.pk:
            duplicados = duplicados.exclude(pk=self.instance.pk)

        if duplicados.exists():
            raise ValidationError(
                "Ya existe una delegación con ese nombre."
            )

        return nombre

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
        fields = [
            "codigo",
            "nombre_item",
            "descripcion",
            "tipo",
            "vigencia",
            "contabiliza_compromisos",
        ]

        labels = {
            "contabiliza_compromisos": (
                "Contabilizar compromisos realizados en el indicador"
            ),
        }

        help_texts = {
            "contabiliza_compromisos": (
                "Activa esta opción si los compromisos asociados "
                "a este ítem deben sumar al avance individual "
                "cuando alcancen el estado Realizado."
            ),
        }

        widgets = {
            "contabiliza_compromisos": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
        }



class RolForm(BootstrapFormMixin, forms.ModelForm):

    PERMISOS = [
        # Administración y seguridad
        ("roles.ver", "Consultar roles"),
        ("roles.editar", "Crear, editar y eliminar roles"),
        ("usuarios.ver", "Consultar usuarios"),
        ("usuarios.editar", "Crear, editar y administrar accesos de usuarios"),
        ("funcionarios.ver", "Consultar funcionarios"),
        ("funcionarios.editar", "Crear, editar y administrar funcionarios"),
        ("delegaciones.ver", "Consultar delegaciones"),
        ("delegaciones.editar", "Crear, editar y administrar delegaciones"),
        ("cargos.ver", "Consultar cargos"),
        ("cargos.editar", "Administrar cargos"),
        ("items.ver", "Consultar ítems medibles"),
        ("items.editar", "Administrar ítems medibles"),

        # Catálogos
        ("catalogos.ver", "Consultar catálogos"),
        ("catalogos.editar", "Administrar catálogos"),

        # Atención social
        ("atenciones.ver", "Consultar casos de atención social"),
        ("atenciones.registrar", "Registrar casos de atención social"),
        ("atenciones.editar", "Editar casos de atención social"),
        ("atenciones.gestionar", "Registrar gestiones y seguimientos"),
        ("atenciones.estado", "Cambiar estado de casos"),
        ("atenciones.exportar", "Exportar información de atención social"),

        # Organizaciones comunitarias
        ("organizaciones.ver", "Consultar organizaciones comunitarias"),
        ("organizaciones.editar", "Administrar organizaciones comunitarias"),

        # Actividades y evidencias
        ("actividades.ver", "Consultar actividades"),
        ("actividades.registrar", "Registrar actividades"),
        ("actividades.editar", "Editar actividades"),
        ("actividades.anular", "Anular actividades"),
        ("evidencias.registrar", "Adjuntar evidencias"),
        ("evidencias.ver", "Consultar evidencias"),
        ("validaciones.ver", "Consultar bandeja de validaciones"),
        ("validaciones.gestionar", "Aprobar o rechazar evidencias"),

        # Agenda
        ("agenda.ver", "Consultar agenda y compromisos"),
        ("agenda.registrar", "Registrar compromisos"),
        ("agenda.editar", "Editar compromisos"),
        ("agenda.estado", "Cambiar estado de compromisos"),
        ("agenda.reasignar", "Reasignar compromisos"),
        ("agenda.exportar", "Exportar agenda"),

        # Medición y planificación
        ("periodos.ver", "Consultar períodos de medición"),
        ("periodos.editar", "Crear y editar períodos"),
        ("periodos.cerrar", "Cerrar períodos"),
        ("periodos.reabrir", "Reabrir períodos"),
        ("metas.ver", "Consultar metas"),
        ("metas.editar", "Crear y editar metas"),
        ("metas.eliminar", "Eliminar metas"),
        ("ajustes.ver", "Consultar ajustes"),
        ("ajustes.editar", "Crear y editar ajustes"),
        ("indicadores.ver", "Consultar indicadores y desempeño"),
        ("reportes.ver", "Consultar reportes"),
        ("reportes.exportar", "Exportar reportes"),

        # Auditoría
        ("auditoria.ver", "Consultar auditoría"),
        ("auditoria.exportar", "Exportar auditoría"),
        ("notificaciones.ver", "Consultar notificaciones"),
        ("comentarios.ver", "Consultar comentarios de registros"),
        ("comentarios.registrar", "Registrar comentarios"),

        # Servicios comunitarios y gestión territorial
        ("servicios.ver", "Consultar servicios comunitarios"),
        ("servicios.gestionar", "Gestionar servicios comunitarios"),
        ("proyectos.ver", "Consultar proyectos y compras"),
        ("proyectos.gestionar", "Gestionar proyectos y compras"),
        ("planificacion.ver", "Consultar información de planificación"),
        ("planificacion.gestionar", "Gestionar planificación"),
    ]

    permisos = forms.MultipleChoiceField(
        choices=PERMISOS,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Permisos autorizados",
    )

    class Meta:
        model = Rol
        fields = [
            "nombre_rol",
            "descripcion",
            "permisos",
            "alcance_autorizado",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance and self.instance.pk:
            self.initial["permisos"] = self.instance.permisos or []

    def clean_nombre_rol(self):
        nombre = self.cleaned_data["nombre_rol"].strip()

        duplicados = Rol.objects.filter(
            nombre_rol__iexact=nombre
        )

        if self.instance and self.instance.pk:
            duplicados = duplicados.exclude(pk=self.instance.pk)

        if duplicados.exists():
            raise ValidationError(
                "Ya existe un rol con ese nombre."
            )

        return nombre

    def clean_permisos(self):
        permisos_seleccionados = self.cleaned_data.get("permisos", [])
        permisos_validos = {codigo for codigo, _ in self.PERMISOS}

        invalidos = set(permisos_seleccionados) - permisos_validos

        if invalidos:
            raise ValidationError(
                "Se enviaron permisos que no están disponibles."
            )

        return list(dict.fromkeys(permisos_seleccionados))

    def save(self, commit=True):
        rol = super().save(commit=False)
        rol.permisos = self.cleaned_data.get("permisos", [])

        if commit:
            rol.save()
            self.save_m2m()

        return rol

class FuncionarioForm(BootstrapFormMixin, forms.ModelForm):

    roles = forms.ModelMultipleChoiceField(
        queryset=Rol.objects.none(),
        label="Roles",
        help_text="Seleccione uno o más roles autorizados.",
        error_messages={
            "required": "Debe asignar al menos un rol."
        },
    )

    class Meta:
        model = Funcionario
        fields = [
            "identificador_institucional",
            "nombre",
            "estado",
            "cargo",
            "delegacion",
        ]

    def __init__(self, *args, actor=None, **kwargs):
        super().__init__(*args, **kwargs)

        cargos = Cargo.objects.vigentes()

        delegaciones = Delegacion.objects.filter(
            estado=Delegacion.ESTADO_ACTIVA
        )

        roles_actuales_ids = set()

        if self.instance and self.instance.pk:

            cargos = Cargo.objects.filter(
                Q(pk=self.instance.cargo_id)
                | Q(pk__in=cargos.values("pk"))
            )

            delegaciones = Delegacion.objects.filter(
                Q(estado=Delegacion.ESTADO_ACTIVA)
                | Q(pk=self.instance.delegacion_id)
            )

            roles_actuales_ids = set(
                self.instance.roles.values_list(
                    "pk",
                    flat=True,
                )
            )

            self.fields["roles"].initial = roles_actuales_ids

        if actor is not None:
            from core.mixins import filtrar_por_ambito

            delegaciones = filtrar_por_ambito(
                delegaciones,
                actor,
                "id_delegacion",
            )

        self.fields["cargo"].queryset = cargos

        self.fields["delegacion"].queryset = delegaciones

        self.fields["roles"].queryset = (
            _roles_disponibles_para_actor(
                actor,
                roles_actuales_ids=roles_actuales_ids,
            )
        )

    def clean_identificador_institucional(self):
        return self.cleaned_data[
            "identificador_institucional"
        ].strip()

    def clean_delegacion(self):
        delegacion = self.cleaned_data["delegacion"]

        if not delegacion.activa:

            es_delegacion_actual = (
                self.instance
                and self.instance.pk
                and self.instance.delegacion_id == delegacion.pk
            )

            if not es_delegacion_actual:
                raise ValidationError(
                    "No se puede asignar un funcionario "
                    "a una delegación inactiva."
                )

        return delegacion


class AccesoForm(BootstrapFormMixin, forms.Form):
    """Formulario para crear o actualizar el acceso de un funcionario."""

    username = forms.CharField(
        label="Nombre de usuario",
        max_length=150,
    )

    password1 = forms.CharField(
        label="Contraseña",
        required=False,
        widget=forms.PasswordInput(
            attrs={"autocomplete": "new-password"}
        ),
    )

    password2 = forms.CharField(
        label="Repetir contraseña",
        required=False,
        widget=forms.PasswordInput(
            attrs={"autocomplete": "new-password"}
        ),
    )

    email = forms.EmailField(
        label="Correo electrónico",
        max_length=254,
        required=True,
    )

    delegaciones_autorizadas = forms.ModelMultipleChoiceField(
        label="Delegaciones autorizadas",
        queryset=Delegacion.objects.none(),
        required=False,
        widget=forms.SelectMultiple(
            attrs={"class": "form-select"}
        ),
    )

    def __init__(self, *args, usuario=None, actor=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.usuario = usuario
        self.actor = actor

        delegaciones_actuales_ids = set()

        if usuario and usuario.pk:
            self.fields["username"].initial = usuario.username
            self.fields["username"].disabled = True
            self.fields["email"].initial = usuario.email

            self.fields["password1"].help_text = (
                "Déjala vacía si no deseas cambiar la contraseña."
            )
            self.fields["password2"].help_text = (
                "Déjala vacía si no deseas cambiar la contraseña."
            )

            delegaciones_actuales_ids = set(
                usuario.delegaciones_autorizadas.values_list(
                    "pk",
                    flat=True,
                )
            )

            self.fields[
                "delegaciones_autorizadas"
            ].initial = delegaciones_actuales_ids

        else:
            self.fields["password1"].required = True
            self.fields["password2"].required = True

        delegaciones = Delegacion.objects.filter(
            Q(estado=Delegacion.ESTADO_ACTIVA)
            | Q(pk__in=delegaciones_actuales_ids)
        ).distinct()

        if actor is not None:
            from core.mixins import filtrar_por_ambito

            delegaciones = filtrar_por_ambito(
                delegaciones,
                actor,
                "id_delegacion",
            )

        self.fields[
            "delegaciones_autorizadas"
        ].queryset = delegaciones

    def clean_username(self):
        username = self.cleaned_data["username"].strip()

        duplicados = Usuario.objects.filter(
            username__iexact=username
        )

        if self.usuario and self.usuario.pk:
            duplicados = duplicados.exclude(
                pk=self.usuario.pk
            )

        if duplicados.exists():
            raise ValidationError(
                "Ese nombre de usuario ya está registrado."
            )

        return username

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()

        duplicados = Usuario.objects.filter(
            email__iexact=email
        )

        if self.usuario and self.usuario.pk:
            duplicados = duplicados.exclude(
                pk=self.usuario.pk
            )

        if duplicados.exists():
            raise ValidationError(
                "Ese correo ya está asociado a otra cuenta."
            )

        return email

    def clean(self):
        datos = super().clean()

        password1 = datos.get("password1")
        password2 = datos.get("password2")

        if not self.usuario and not password1:
            self.add_error(
                "password1",
                "La contraseña es obligatoria.",
            )

        if password1 or password2:
            if password1 != password2:
                self.add_error(
                    "password2",
                    "Las contraseñas no coinciden.",
                )
            elif password1:
                try:
                    validate_password(
                        password1,
                        user=self.usuario,
                    )
                except ValidationError as exc:
                    self.add_error("password1", exc)

        return datos

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

    roles = forms.ModelMultipleChoiceField(
        queryset=Rol.objects.all(),
        label="Roles autorizados",
        required=True,
        widget=forms.SelectMultiple(
            attrs={"class": "form-select"}
        ),
        error_messages={
            "required": "Debe asignar al menos un rol."
        },
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

    def __init__(self, *args, actor=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.actor = actor

        self.fields["email"].required = True
        self.fields["funcionario"].required = True

        delegaciones_actuales_ids = set()

        if self.instance and self.instance.pk:
            self.fields["username"].disabled = True

            self.fields["password1"].help_text = (
                "Déjala vacía si no deseas cambiar la contraseña."
            )
            self.fields["password2"].help_text = (
                "Déjala vacía si no deseas cambiar la contraseña."
            )

            delegaciones_actuales_ids = set(
                self.instance.delegaciones_autorizadas.values_list(
                    "pk",
                    flat=True,
                )
            )

            funcionario_actual_id = self.instance.funcionario_id

            funcionarios = Funcionario.objects.filter(
                Q(usuario__isnull=True)
                | Q(pk=funcionario_actual_id)
            ).filter(
                Q(estado=Funcionario.ESTADO_ACTIVO)
                | Q(pk=funcionario_actual_id)
            )

            if funcionario_actual_id:
                self.fields["roles"].initial = list(
                    Funcionario.objects.filter(
                        pk=funcionario_actual_id
                    ).values_list(
                        "roles__pk",
                        flat=True,
                    )
                )

        else:
            self.fields["password1"].required = True
            self.fields["password2"].required = True

            funcionarios = Funcionario.objects.filter(
                usuario__isnull=True,
                estado=Funcionario.ESTADO_ACTIVO,
                delegacion__estado=Delegacion.ESTADO_ACTIVA,
            )

        delegaciones = Delegacion.objects.filter(
            Q(estado=Delegacion.ESTADO_ACTIVA)
            | Q(pk__in=delegaciones_actuales_ids)
        ).distinct()

        if actor is not None:
            from core.mixins import filtrar_por_ambito

            funcionarios = filtrar_por_ambito(
                funcionarios,
                actor,
                "delegacion_id",
            )

            delegaciones = filtrar_por_ambito(
                delegaciones,
                actor,
                "id_delegacion",
            )

        self.fields["funcionario"].queryset = funcionarios
        roles_queryset = Rol.objects.all()

        if (
            actor is not None
            and getattr(actor, "is_authenticated", False)
            and not getattr(actor, "is_superuser", False)
        ):
            from core.mixins import get_permisos, get_alcances

            permisos_actor = get_permisos(actor)
            alcances_actor = get_alcances(actor)

            roles_permitidos = []

            for rol in roles_queryset:
                if (
                    rol.nombre_rol.strip().casefold()
                    == "administrador"
                ):
                    continue

                if rol.alcance_autorizado == "global":
                    continue

                if not set(
                    rol.permisos or []
                ).issubset(permisos_actor):
                    continue

                if (
                    rol.alcance_autorizado == "multiples"
                    and "multiples" not in alcances_actor
                ):
                    continue

                roles_permitidos.append(rol.pk)

            roles_actuales_ids = set()

            if self.instance and self.instance.pk:
                if self.instance.funcionario_id:
                    roles_actuales_ids = set(
                        self.instance.funcionario.roles.values_list(
                            "pk",
                            flat=True,
                        )
                    )

            roles_queryset = Rol.objects.filter(
                pk__in=(
                    set(roles_permitidos)
                    | roles_actuales_ids
                )
            )

        self.fields["roles"].queryset = roles_queryset
        self.fields[
            "delegaciones_autorizadas"
        ].queryset = delegaciones

    def clean_username(self):
        username = self.cleaned_data["username"].strip()

        duplicados = Usuario.objects.filter(
            username__iexact=username
        )

        if self.instance and self.instance.pk:
            duplicados = duplicados.exclude(
                pk=self.instance.pk
            )

        if duplicados.exists():
            raise ValidationError(
                "Ese nombre de usuario ya está registrado."
            )

        return username

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()

        duplicados = Usuario.objects.filter(
            email__iexact=email
        )

        if self.instance and self.instance.pk:
            duplicados = duplicados.exclude(
                pk=self.instance.pk
            )

        if duplicados.exists():
            raise ValidationError(
                "Ese correo ya está asociado a otra cuenta."
            )

        return email

    def clean(self):
        datos = super().clean()

        password1 = datos.get("password1")
        password2 = datos.get("password2")
        funcionario = datos.get("funcionario")
        roles = list(datos.get("roles") or [])
        delegaciones = list(
            datos.get("delegaciones_autorizadas") or []
        )

        es_nuevo = not bool(
            self.instance and self.instance.pk
        )

        funcionario_anterior_id = (
            self.instance.funcionario_id
            if self.instance and self.instance.pk
            else None
        )

        if es_nuevo and not password1:
            self.add_error(
                "password1",
                "Debe establecer una contraseña.",
            )

        if password1 or password2:
            if password1 != password2:
                self.add_error(
                    "password2",
                    "Las contraseñas no coinciden.",
                )
            elif password1:
                try:
                    validate_password(
                        password1,
                        user=self.instance,
                    )
                except ValidationError as exc:
                    self.add_error("password1", exc)

        if funcionario is None:
            self.add_error(
                "funcionario",
                "Debe asociar la cuenta a un funcionario.",
            )
            return datos

        duplicados = Usuario.objects.filter(
            funcionario=funcionario
        )

        if self.instance and self.instance.pk:
            duplicados = duplicados.exclude(
                pk=self.instance.pk
            )

        if duplicados.exists():
            self.add_error(
                "funcionario",
                "Este funcionario ya tiene una cuenta de acceso.",
            )

        cambio_funcionario = (
            funcionario_anterior_id != funcionario.pk
        )

        if cambio_funcionario and not funcionario.activo:
            self.add_error(
                "funcionario",
                "No puede asociar una cuenta nueva "
                "a un funcionario inactivo.",
            )

        if (
            cambio_funcionario
            and not funcionario.delegacion.activa
        ):
            self.add_error(
                "funcionario",
                "No puede asignar una cuenta a una "
                "delegación inactiva.",
            )

        if not roles:
            self.add_error(
                "roles",
                "Debe asignar al menos un rol autorizado.",
            )

        delegaciones_actuales_ids = set()

        if self.instance and self.instance.pk:
            delegaciones_actuales_ids = set(
                self.instance.delegaciones_autorizadas.values_list(
                    "pk",
                    flat=True,
                )
            )

        inactivas_nuevas = [
            delegacion.nombre
            for delegacion in delegaciones
            if (
                not delegacion.activa
                and delegacion.pk not in delegaciones_actuales_ids
            )
        ]

        if inactivas_nuevas:
            self.add_error(
                "delegaciones_autorizadas",
                "No puede asignar delegaciones inactivas: "
                + ", ".join(inactivas_nuevas),
            )

        alcances = {
            rol.alcance_autorizado
            for rol in roles
        }

        if (
            delegaciones
            and not ({"global", "multiples"} & alcances)
        ):
            self.add_error(
                "delegaciones_autorizadas",
                "Los roles seleccionados no permiten "
                "delegaciones adicionales.",
            )

        acceso_solicitado = datos.get("activo_acceso", False)

        if acceso_solicitado and not funcionario.activo:
            self.add_error(
                "activo_acceso",
                "No puede habilitar el acceso de un "
                "funcionario inactivo.",
            )
            datos["activo_acceso"] = False

        if (
            acceso_solicitado
            and not funcionario.delegacion.activa
        ):
            self.add_error(
                "activo_acceso",
                "No puede habilitar el acceso mientras "
                "la delegación principal esté inactiva.",
            )
            datos["activo_acceso"] = False

        if (
            not funcionario.activo
            or not funcionario.delegacion.activa
        ):
            datos["activo_acceso"] = False

        return datos
    def save(self, commit=True):
        usuario = super().save(commit=False)

        password = self.cleaned_data.get("password1")

        if password:
            usuario.set_password(password)

        funcionario = usuario.funcionario

        if (
            not funcionario
            or not funcionario.activo
            or not funcionario.delegacion.activa
        ):
            usuario.activo_acceso = False

        if commit:
            usuario.save()
            self.save_m2m()

        return usuario
    
class PerfilUsuarioForm(BootstrapFormMixin, forms.ModelForm):

    class Meta:
        model = Usuario
        fields = ["email", "foto_perfil"]

        labels = {
            "email": "Correo electrónico",
            "foto_perfil": "Fotografía de perfil",
        }

        widgets = {
            "email": forms.EmailInput(attrs={
                "placeholder": "correo@ejemplo.cl",
                "autocomplete": "email",
            }),
            "foto_perfil": forms.ClearableFileInput(attrs={
                "accept": "image/jpeg,image/png,image/webp",
            }),
        }

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()

        duplicados = Usuario.objects.filter(
            email__iexact=email
        ).exclude(pk=self.instance.pk)

        if email and duplicados.exists():
            raise ValidationError(
                "Ese correo ya está asociado a otra cuenta."
            )

        return email

    def clean_foto_perfil(self):
        imagen = self.cleaned_data.get("foto_perfil")

        if not imagen:
            return imagen

        if imagen.size > 3 * 1024 * 1024:
            raise ValidationError(
                "La fotografía no puede superar los 3 MB."
            )

        extensiones = (".jpg", ".jpeg", ".png", ".webp")

        if not imagen.name.lower().endswith(extensiones):
            raise ValidationError(
                "Utiliza una imagen JPG, JPEG, PNG o WEBP."
            )

        return imagen
