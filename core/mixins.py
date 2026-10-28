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


def get_rol_principal(user):
    roles = get_roles(user)
    for rol in ROLES_PRIORIDAD:
        if rol in roles:
            return rol
    return next(iter(sorted(roles)), None)


def es_transversal(user):
    return tiene_rol(user, *ROLES_TRANSVERSALES)


def get_delegacion_id(user):
    funcionario = get_funcionario(user)
    return funcionario.delegacion_id if funcionario else None


def filtrar_por_ambito(queryset, user, campo="delegacion_id"):
    """
    Restringe un queryset al ámbito del usuario.
    - Administrador / Coordinador: ven todo.
    - Resto: solo registros de su propia delegación.
    - Sin funcionario asociado: nada.
    `campo` es la ruta ORM hacia la delegación, p. ej. 'funcionario__delegacion_id'.
    """
    if es_transversal(user):
        return queryset
    delegacion_id = get_delegacion_id(user)
    if delegacion_id is None:
        return queryset.none()
    return queryset.filter(**{campo: delegacion_id})


# ---------------------------------------------------------------------------
# Auditoría y denegación de acceso
# ---------------------------------------------------------------------------
def auditar(usuario, evento, entidad="", id_entidad=0, valor_anterior=None, valor_nuevo=None):
    """
    Envoltorio seguro hacia audit.services.registrar_evento (usable desde servicios).
    Nunca debe romper la operación: si audit aún no existe o falla, se informa en el log.
    """
    try:
        from audit.services import registrar_evento
    except ImportError:
        logger.debug("App audit aún no disponible; evento %s no registrado.", evento)
        return
    try:
        registrar_evento(
            usuario=usuario,
            evento=evento,
            entidad=entidad,
            id_entidad=id_entidad,
            valor_anterior=valor_anterior,
            valor_nuevo=valor_nuevo,
        )
    except Exception:  # pragma: no cover
        logger.exception("No se pudo registrar el evento de auditoría %s", evento)


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
    Exige sesión iniciada y al menos uno de los `roles_permitidos`.
    Si `roles_permitidos` está vacío, basta con estar autenticado.
    """
    roles_permitidos = ()

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not tiene_rol(request.user, *self.roles_permitidos):
            return denegar_acceso(request)
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
    Una plantilla por entidad con la variable `modo`: 'lista', 'form' o 'detalle'.
    `puede_editar` indica si el usuario puede mostrar botones de escritura.
    """
    modo = "lista"
    titulo = ""
    roles_edicion = ROLES_CONFIGURACION

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.update(
            modo=self.modo,
            titulo=self.titulo,
            puede_editar=tiene_rol(self.request.user, *self.roles_edicion),
        )
        return contexto


class GuardarMixin:
    """form_valid delegando en un servicio; los errores de regla de negocio vuelven al formulario."""
    success_url_name = ""
    mensaje_exito = "Guardado correctamente."

    def guardar(self, form):
        raise NotImplementedError

    def get_success_url(self):
        return reverse(self.success_url_name)

    def form_valid(self, form):
        try:
            self.guardar(form)
        except ReglaNegocioError as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)
        messages.success(self.request, self.mensaje_exito)
        return redirect(self.get_success_url())


class AccionPostView(RolRequeridoMixin, View):
    """Acciones que cambian datos (activar, eliminar...): solo POST, con rol exigido."""
    http_method_names = ["post"]
    roles_permitidos = ROLES_CONFIGURACION
    redirect_name = ""

    def get_objeto(self, pk):
        raise NotImplementedError

    def accion(self, request, objeto):
        """Ejecuta la acción y devuelve el mensaje de éxito."""
        raise NotImplementedError

    def get_redirect(self, objeto):
        return reverse(self.redirect_name)

    def post(self, request, pk):
        objeto = self.get_objeto(pk)
        try:
            messages.success(request, self.accion(request, objeto))
        except ReglaNegocioError as exc:
            messages.error(request, str(exc))
        return redirect(self.get_redirect(objeto))


def errores_form(form):
    """Texto plano con los errores de un formulario (para mensajes SweetAlert)."""
    return " ".join(m for lista in form.errors.values() for m in lista)

class ModalFormPageMixin:
    """
    Reutiliza el contexto del ListView de la entidad al crear o editar.
    El formulario se muestra dentro de un modal en la pantalla del listado.
    Si hay errores, conserva los datos y abre el modal nuevamente.
    """

    list_view_class = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if self.list_view_class is None:
            raise ImproperlyConfigured(
                "Debes configurar list_view_class en la vista CRUD."
            )

        # Conservar el formulario actual, incluidos sus errores.
        form = context.get("form")
        if form is None:
            form = kwargs.get("form") or self.get_form()

        # Construir el contexto de la lista utilizando su propia lógica
        # de búsqueda, filtros, paginación y ámbito autorizado.
        list_view = self.list_view_class()
        list_view.setup(self.request, *self.args, **self.kwargs)
        list_view.object_list = list_view.get_queryset()

        list_context = list_view.get_context_data(
            object_list=list_view.object_list
        )

        context.update(list_context)

        # Restaurar el formulario y señalar que debe abrirse el modal.
        context["form"] = form
        context["open_modal"] = True
        context["modo"] = "lista"
        context["titulo_modal"] = getattr(
            self, "titulo", "Formulario"
        )

        # En edición, el objeto queda disponible para el encabezado
        # del modal y para los templates que lo necesiten.
        if getattr(self, "object", None) is not None:
            context["objeto_edicion"] = self.object

        return context

class ModalFormPageMixin:
    """
    Permite que una vista de creación o edición reutilice el contexto
    de su vista de listado y abra el formulario dentro de un modal.
    """

    list_view_class = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = context.get("form")

        if self.list_view_class is None:
            raise ImproperlyConfigured(
                f"{self.__class__.__name__} debe declarar list_view_class."
            )

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

        context.update(list_context)

        # El contexto de listado no debe reemplazar el formulario ni sus errores.
        if form is not None:
            context["form"] = form

        context["view"] = self
        context["modo"] = "lista"
        context["open_modal"] = True
        context["titulo_modal"] = getattr(
            self,
            "titulo",
            "Formulario",
        )

        return context