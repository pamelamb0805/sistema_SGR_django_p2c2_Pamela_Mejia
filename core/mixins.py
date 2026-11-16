"""
Roles, ámbito por delegación y mixins de acceso del SGR.

Reglas del PDF:
- Mínimo privilegio y segregación de funciones (RNF-005).
- Cada actor ve y modifica solo lo necesario para su función y delegación.
- La validación de permisos se hace en el SERVIDOR (ocultar botones no basta).
- Acceso denegado => mensaje + evento de auditoría (HU-26, CA-07).

Contrato con otras apps (se construye en los siguientes pasos):
- organizations.Usuario.funcionario  -> OneToOne a Funcionario
- Funcionario.delegacion (FK), Funcionario.funcionario_roles (related_name de FuncionarioRol)
- FuncionarioRol.rol -> Rol.nombre_rol
- audit.services.registrar_evento(usuario, evento, entidad, id_entidad, valor_anterior, valor_nuevo)
"""
import logging

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.urls import reverse
from django.views import View

from .exceptions import ReglaNegocioError

from django.core.exceptions import ImproperlyConfigured

from django.apps import apps
from django.db import transaction
from django import forms

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Nombres de rol (deben coincidir con Rol.nombre_rol en los datos de data/)
# ---------------------------------------------------------------------------
ROL_ADMINISTRADOR = "Administrador"
ROL_COORDINADOR = "Coordinador"
ROL_DELEGADO = "Delegado"
ROL_FUNCIONARIO = "Funcionario"
ROL_VERIFICADOR = "Verificador"
ROL_CONSULTA = "Consulta"

# Orden de prioridad para mostrar el "rol principal"
ROLES_PRIORIDAD = (
    ROL_ADMINISTRADOR,
    ROL_COORDINADOR,
    ROL_DELEGADO,
    ROL_VERIFICADOR,
    ROL_FUNCIONARIO,
    ROL_CONSULTA,
)

# Grupos de permisos por tipo de operación
ROLES_CONFIGURACION = (ROL_ADMINISTRADOR,)                             # delegaciones, usuarios, cargos, catálogos
ROLES_MEDICION = (ROL_ADMINISTRADOR, ROL_COORDINADOR)                  # períodos, metas, ponderaciones
ROLES_VALIDACION = (ROL_VERIFICADOR, ROL_ADMINISTRADOR)                # aprobar / rechazar evidencias
ROLES_OPERATIVOS = (ROL_FUNCIONARIO, ROL_DELEGADO)                     # registrar actividades y compromisos
ROLES_SUPERVISION = (ROL_ADMINISTRADOR, ROL_COORDINADOR, ROL_DELEGADO) # reasignar, monitorear
ROLES_TRANSVERSALES = (ROL_ADMINISTRADOR, ROL_COORDINADOR)             # ven todas las delegaciones


# ---------------------------------------------------------------------------
# Utilidades de identidad
# ---------------------------------------------------------------------------
def get_funcionario(user):
    """Funcionario asociado al usuario autenticado (o None)."""
    if not getattr(user, "is_authenticated", False):
        return None
    return getattr(user, "funcionario", None)


def get_roles(user):
    """Conjunto de nombres de rol del usuario (cacheado por request)."""
    if not getattr(user, "is_authenticated", False):
        return set()
    cache = getattr(user, "_sgr_roles", None)
    if cache is not None:
        return cache

    roles = set()
    if getattr(user, "is_superuser", False):
        roles.add(ROL_ADMINISTRADOR)
    funcionario = get_funcionario(user)
    if funcionario is not None:
        roles.update(funcionario.funcionario_roles.values_list("rol__nombre_rol", flat=True))
    user._sgr_roles = roles
    return roles


def tiene_rol(user, *roles):
    """True si el usuario posee al menos uno de los roles indicados."""
    if not roles:
        return getattr(user, "is_authenticated", False)
    return bool(get_roles(user) & set(roles))


def get_permisos(user):
    """
    Obtiene todos los permisos funcionales de los roles asignados
    al funcionario del usuario autenticado.
    """
    if not getattr(user, "is_authenticated", False):
        return set()

    if getattr(user, "is_superuser", False):
        return {"*"}

    cache = getattr(user, "_sgr_permisos", None)

    if cache is not None:
        return cache

    permisos = set()
    funcionario = get_funcionario(user)

    if funcionario is not None:
        for rol in funcionario.roles.all():
            permisos.update(rol.permisos or [])

    user._sgr_permisos = permisos

    return permisos


def tiene_permiso(user, *permisos):
    """
    Comprueba si el usuario posee al menos uno de los permisos
    funcionales indicados.
    """
    if not permisos:
        return False

    asignados = get_permisos(user)

    if "*" in asignados:
        return True

    return bool(asignados.intersection(permisos))


def get_rol_principal(user):
    roles = get_roles(user)
    for rol in ROLES_PRIORIDAD:
        if rol in roles:
            return rol
    return next(iter(sorted(roles)), None)



def get_alcances(user):
    """Obtiene los alcances autorizados de todos los roles del funcionario."""
    funcionario = get_funcionario(user)
    if funcionario is None:
        return set()

    return set(
        funcionario.roles.values_list("alcance_autorizado", flat=True)
    )


def get_permisos(user):
    """
    Une los permisos funcionales configurados en los roles del usuario.
    Los permisos se almacenan como listas JSON en Rol.permisos.
    """
    if not getattr(user, "is_authenticated", False):
        return set()

    if getattr(user, "is_superuser", False):
        return {"*"}

    funcionario = get_funcionario(user)
    if funcionario is None or not funcionario.activo:
        return set()

    permisos = set()
    for lista in funcionario.roles.values_list("permisos", flat=True):
        if isinstance(lista, (list, tuple, set)):
            permisos.update(str(item).strip() for item in lista if item)

    return permisos


def tiene_permiso(user, *permisos):
    """
    Comprueba permisos funcionales configurados en los roles.
    Si se solicitan varios, deben estar todos concedidos.
    """
    if not getattr(user, "is_authenticated", False):
        return False

    if getattr(user, "is_superuser", False):
        return True

    concedidos = get_permisos(user)
    if "*" in concedidos:
        return True

    if not permisos:
        return True

    return all(permiso in concedidos for permiso in permisos)


def get_delegaciones_autorizadas_ids(user):
    """Devuelve la delegación principal y las delegaciones adicionales."""
    funcionario = get_funcionario(user)

    if funcionario is None or not funcionario.activo:
        return []

    ids = set()
    if funcionario.delegacion_id:
        ids.add(funcionario.delegacion_id)

    alcances = get_alcances(user)
    if "multiples" in alcances and hasattr(user, "delegaciones_autorizadas"):
        ids.update(
            user.delegaciones_autorizadas.values_list("pk", flat=True)
        )

    return sorted(ids)


def es_transversal(user):
    """
    Determina si el usuario puede consultar todas las delegaciones.
    """
    if getattr(user, "is_superuser", False):
        return True

    return "global" in get_alcances(user)


def get_delegacion_id(user):
    """
    Obtiene la delegación principal del funcionario.
    """
    funcionario = get_funcionario(user)
    return funcionario.delegacion_id if funcionario else None


def get_delegaciones_autorizadas_ids(user):
    """
    Obtiene la delegación principal y las delegaciones adicionales.
    """
    funcionario = get_funcionario(user)

    if funcionario is None:
        return []

    ids = {funcionario.delegacion_id}

    if hasattr(user, "delegaciones_autorizadas"):
        ids.update(
            user.delegaciones_autorizadas.values_list(
                "pk",
                flat=True,
            )
        )

    return list(ids)



def filtrar_por_ambito(queryset, user, campo="delegacion_id"):
    """
    Limita los registros al ámbito territorial autorizado.

    propia: delegación principal.
    multiples: delegación principal y delegaciones adicionales autorizadas.
    global: todas las delegaciones.
    """
    if not getattr(user, "is_authenticated", False):
        return queryset.none()

    if getattr(user, "is_superuser", False):
        return queryset

    funcionario = get_funcionario(user)
    if funcionario is None or not funcionario.activo:
        return queryset.none()

    alcances = get_alcances(user)

    if "global" in alcances:
        return queryset

    if "multiples" in alcances:
        ids = get_delegaciones_autorizadas_ids(user)
        return queryset.filter(**{f"{campo}__in": ids}) if ids else queryset.none()

    if "propia" in alcances and funcionario.delegacion_id:
        return queryset.filter(**{campo: funcionario.delegacion_id})

    return queryset.none()


# ---------------------------------------------------------------------------
# Auditoría y denegación de acceso
# ---------------------------------------------------------------------------



def auditar(
    usuario,
    evento,
    entidad="",
    id_entidad=0,
    valor_anterior=None,
    valor_nuevo=None,
):
    """
    Registra operaciones críticas de forma obligatoria.

    Si no es posible guardar el evento de auditoría, propaga
    el error para que la transacción de la operación principal
    pueda revertirse.

    Las notificaciones son complementarias: su fallo no debe
    invalidar un evento de auditoría que ya fue registrado.
    """
    from audit.services import (
        registrar_evento,
        crear_notificaciones,
    )

    # El registro de auditoría es obligatorio.
    # No ocultar excepciones de esta operación.
    auditoria = registrar_evento(
        usuario=usuario,
        evento=evento,
        entidad=entidad,
        id_entidad=id_entidad,
        valor_anterior=valor_anterior,
        valor_nuevo=valor_nuevo,
    )

    # Las operaciones CRUD normales ya crean notificaciones
    # desde core.services.
    if evento not in ("CREAR", "MODIFICAR", "ELIMINAR"):
        if evento == "LOGIN" and entidad == "usuario":
            delegacion_notificacion = None
        else:
            delegacion_notificacion = get_delegacion_id(usuario)

        try:
            crear_notificaciones(
                auditoria,
                delegacion_id=delegacion_notificacion,
            )
        except Exception:
            logger.exception(
                "La auditoría quedó registrada, pero no se "
                "pudieron crear las notificaciones del evento %s.",
                evento,
            )

    # Los CRUD normales ya publican su evento desde core.services.
    if evento in ("CREAR", "MODIFICAR", "ELIMINAR"):
        return auditoria

    entidades = {
        "delegacion": (
            "organizations",
            "Delegacion",
            "organizations",
        ),
        "cargo": (
            "organizations",
            "Cargo",
            "organizations",
        ),
        "item_medible": (
            "organizations",
            "ItemMedible",
            "organizations",
        ),
        "rol": (
            "organizations",
            "Rol",
            "organizations",
        ),
        "funcionario": (
            "organizations",
            "Funcionario",
            "organizations",
        ),
        "usuario": (
            "organizations",
            "Usuario",
            "organizations",
        ),
        "catalogo": (
            "catalogs",
            "Catalogo",
            "catalogs",
        ),
        "periodo": (
            "measurement",
            "Periodo",
            "measurement",
        ),
        "meta": (
            "measurement",
            "Meta",
            "measurement",
        ),
        "ajuste": (
            "measurement",
            "Ajuste",
            "measurement",
        ),
        "actividad": (
            "activities",
            "Actividad",
            "activities",
        ),
        "evidencia": (
            "activities",
            "Evidencia",
            "activities",
        ),
        "validacion": (
            "activities",
            "Validacion",
            "activities",
        ),
        "compromiso": (
            "agenda",
            "Compromiso",
            "agenda",
        ),
        "usuario_social": (
            "social",
            "UsuarioSocial",
            "social",
        ),
        "atencion_social": (
            "social",
            "AtencionSocial",
            "social",
        ),
    }

    configuracion = entidades.get(str(entidad).lower())

    if not configuracion or not id_entidad:
        return auditoria

    app_label, modelo, modulo = configuracion

    def publicar():
        try:
            modelo_objeto = apps.get_model(
                app_label,
                modelo,
            )

            objeto = modelo_objeto.objects.filter(
                pk=id_entidad,
            ).first()

            if objeto is None:
                return

            from websocket.services import publish_crud_event

            publish_crud_event(
                module=modulo,
                action=str(evento).lower(),
                actor=usuario,
                objeto=objeto,
            )

        except Exception:
            logger.exception(
                "No se pudo publicar el evento especial %s.",
                evento,
            )

    transaction.on_commit(publicar)

    return auditoria


def registrar_auditoria(request, evento, entidad="", id_entidad=0, valor_anterior=None, valor_nuevo=None):
    """Versión para vistas: toma el usuario desde el request."""
    auditar(request.user, evento, entidad, id_entidad, valor_anterior, valor_nuevo)


def denegar_acceso(request, detalle="No tiene permisos para acceder a esta sección."):
    messages.error(request, detalle)
    registrar_auditoria(
        request,
        evento="ACCESO_DENEGADO",
        entidad="ruta",
        id_entidad=0,
        valor_nuevo=request.path,
    )
    return redirect("dashboard")


# ---------------------------------------------------------------------------
# Mixins para vistas basadas en clases
# ---------------------------------------------------------------------------


class RolRequeridoMixin(LoginRequiredMixin):
    """
    Exige autenticación, rol permitido y, cuando se declara,
    los permisos funcionales correspondientes.
    """
    roles_permitidos = ()
    permisos_requeridos = ()

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        if not tiene_rol(request.user, *self.roles_permitidos):
            return denegar_acceso(request)

        if self.permisos_requeridos and not tiene_permiso(
            request.user, *self.permisos_requeridos
        ):
            return denegar_acceso(
                request,
                "Su rol no tiene autorización para realizar esta operación.",
            )

        return super().dispatch(request, *args, **kwargs)


class PermisoRequeridoMixin:
    """
    Exige permisos funcionales configurados en Rol.permisos.
    Se puede combinar con RolRequeridoMixin en vistas basadas en clases.
    """
    permisos_requeridos = ()

    def dispatch(self, request, *args, **kwargs):
        if self.permisos_requeridos and not tiene_permiso(
            request.user, *self.permisos_requeridos
        ):
            return denegar_acceso(
                request,
                "Su rol no tiene autorización para realizar esta operación.",
            )

        return super().dispatch(request, *args, **kwargs)


class AmbitoDelegacionMixin:
    """
    Para ListView/DetailView/UpdateView/DeleteView: filtra el queryset por la
    delegación del usuario. Un objeto fuera del ámbito responde 404 (CA-07).
    Definir `ambito_campo` con la ruta a la delegación del modelo.
    """
    ambito_campo = "delegacion_id"

    def get_queryset(self):
        queryset = super().get_queryset()
        return filtrar_por_ambito(queryset, self.request.user, self.ambito_campo)


# ---------------------------------------------------------------------------
# Bloques reutilizables para vistas CRUD (todas las apps)
# ---------------------------------------------------------------------------


class ModoMixin:
    """
    Controla la presentación de botones según los permisos funcionales.
    Ocultar botones no reemplaza la autorización del servidor.
    """

    modo = "lista"
    titulo = ""
    roles_edicion = ()
    permisos_edicion = ()

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)

        usuario = self.request.user

        puede_editar = bool(
            usuario.is_authenticated
            and self.permisos_edicion
            and tiene_permiso(
                usuario,
                *self.permisos_edicion,
            )
        )

        contexto.update(
            modo=self.modo,
            titulo=self.titulo,
            puede_editar=puede_editar,
        )

        return contexto

class GuardarMixin:
    """
    Guardado centralizado con control de concurrencia optimista.

    Cada formulario de edición recibe una huella del registro
    cuando se abre.

    Al guardar:
    1. Bloquea la fila en la base de datos.
    2. Calcula nuevamente su huella.
    3. Compara la huella actual con la enviada por el formulario.
    4. Si hubo una modificación previa, rechaza el guardado.
    5. Si no hubo cambios, ejecuta el guardado dentro
       de la misma transacción.
    """

    success_url_name = ""
    mensaje_exito = "Guardado correctamente."

    campo_version_concurrencia = "_sgr_version"

    mensaje_conflicto_concurrencia = (
        "Este registro fue modificado por otro usuario después "
        "de que abriste el formulario. No se guardaron tus cambios "
        "para evitar sobrescribir información. Actualiza la página, "
        "revisa los datos actuales y vuelve a realizar tu modificación."
    )

    def guardar(self, form):
        raise NotImplementedError

    def get_success_url(self):
        return reverse(self.success_url_name)

    def get_form(self, form_class=None):
        """
        Incorpora un campo oculto con la huella del registro
        cuando se trata de una edición.
        """

        form = super().get_form(form_class)

        instancia = getattr(
            self,
            "object",
            None,
        )

        if instancia is None or not instancia.pk:
            return form

        from core.services import huella_concurrencia

        form.fields[
            self.campo_version_concurrencia
        ] = forms.CharField(
            required=True,
            widget=forms.HiddenInput(),
        )

        # Solo se genera la huella inicial al mostrar el formulario.
        # En un POST se conserva el valor enviado por el navegador.
        if not form.is_bound:
            form.initial[
                self.campo_version_concurrencia
            ] = huella_concurrencia(instancia)

        return form

    def form_valid(self, form):
        """
        Ejecuta el guardado verificando que el registro no haya
        cambiado desde que se abrió el formulario.
        """

        instancia = getattr(
            self,
            "object",
            None,
        )

        # -----------------------------------------------------
        # CREACIÓN: no requiere comparar una versión anterior.
        # -----------------------------------------------------

        if instancia is None or not instancia.pk:
            try:
                self.guardar(form)

            except ReglaNegocioError as exc:
                form.add_error(None, str(exc))
                return self.form_invalid(form)

            messages.success(
                self.request,
                self.mensaje_exito,
            )

            return redirect(self.get_success_url())

        # -----------------------------------------------------
        # EDICIÓN: control de concurrencia.
        # -----------------------------------------------------

        from core.services import huella_concurrencia

        version_enviada = form.cleaned_data.get(
            self.campo_version_concurrencia
        )

        try:
            with transaction.atomic():

                # Bloquea el registro hasta finalizar la operación.
                registro_actual = (
                    type(instancia)
                    ._base_manager
                    .select_for_update()
                    .get(pk=instancia.pk)
                )

                version_actual = huella_concurrencia(
                    registro_actual
                )

                # Detecta si otro usuario guardó primero.
                if (
                    not version_enviada
                    or version_enviada != version_actual
                ):
                    form.add_error(
                        None,
                        self.mensaje_conflicto_concurrencia,
                    )

                    return self.form_invalid(form)

                # La fila permanece bloqueada mientras se ejecuta
                # el servicio CRUD y se confirma la transacción.
                self.guardar(form)

        except type(instancia).DoesNotExist:
            form.add_error(
                None,
                "El registro ya no existe. No se puede guardar "
                "la modificación.",
            )

            return self.form_invalid(form)

        except ReglaNegocioError as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)

        messages.success(
            self.request,
            self.mensaje_exito,
        )

        return redirect(self.get_success_url())


class AccionPostView(RolRequeridoMixin, View):
    """
    Acciones que modifican información.

    Cada subclase debe declarar permisos_permitidos.
    Solo acepta POST y verifica autorización en el servidor.
    """

    http_method_names = ["post"]
    roles_permitidos = ()
    permisos_permitidos = ()
    redirect_name = ""

    def get_objeto(self, pk):
        raise NotImplementedError

    def accion(self, request, objeto):
        raise NotImplementedError

    def get_redirect(self, objeto):
        return reverse(self.redirect_name)

    def post(self, request, pk):
        objeto = self.get_objeto(pk)

        try:
            mensaje = self.accion(request, objeto)
            messages.success(request, mensaje)

        except ReglaNegocioError as exc:
            messages.error(request, str(exc))

        return redirect(self.get_redirect(objeto))

def errores_form(form):
    """Texto plano con los errores de un formulario (para mensajes SweetAlert)."""
    return " ".join(m for lista in form.errors.values() for m in lista)


class ModalFormPageMixin:
    """
    Permite que las vistas de creación y edición reutilicen el listado
    de la entidad y muestren el formulario dentro de un modal.

    Si el formulario tiene errores, conserva los datos y solicita
    que el modal vuelva a abrirse.
    """

    list_view_class = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if self.list_view_class is None:
            raise ImproperlyConfigured(
                f"{self.__class__.__name__} debe declarar list_view_class."
            )

        # Preservar el formulario actual, incluidos sus errores.
        form = context.get("form")
        if form is None:
            form = kwargs.get("form")

        if form is None:
            form = self.get_form()

        # Preparar el listado usando su propio queryset y filtros.
        list_view = self.list_view_class()
        list_view.setup(
            self.request,
            *getattr(self, "args", ()),
            **getattr(self, "kwargs", {}),
        )

        list_view.object_list = list_view.get_queryset()

        list_context = list_view.get_context_data(
            object_list=list_view.object_list
        )

        # Incorporar datos de búsqueda, filtros y paginación.
        context.update(list_context)

        # Restaurar los datos del formulario después de actualizar
        # el contexto, para no perder los errores de validación.
        context["form"] = form
        context["view"] = self
        context["modo"] = "lista"
        context["open_modal"] = True
        context["titulo_modal"] = getattr(
            self,
            "titulo",
            "Formulario",
        )

        # Dejar disponible el objeto en las vistas de edición.
        if getattr(self, "object", None) is not None:
            context["objeto_edicion"] = self.object

        return context
