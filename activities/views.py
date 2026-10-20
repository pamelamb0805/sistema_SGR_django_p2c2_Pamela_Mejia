"""
Vistas de activities. Plantillas (templates/activities/):
  actividad_.html   modo: lista | form | detalle
  evidencia_.html   modo: form (adjuntar archivo a una actividad)
  validacion_.html  modo: lista (bandeja del verificador) | form (revisión de una evidencia)

Permisos: registrar y adjuntar -> Funcionario y Delegado (solo sobre sus propias actividades);
validar -> Verificador y Administrador, nunca sobre sus propias actividades;
consultar -> según ámbito (ver services.actividades_visibles).
"""
from django.contrib import messages
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import NoReverseMatch, reverse
from django.views.generic import CreateView, DetailView, FormView, ListView, UpdateView

from core.exceptions import ReglaNegocioError
from core.mixins import (
    ROLES_OPERATIVOS, ROLES_SUPERVISION, ROLES_VALIDACION, AccionPostView, GuardarMixin, ModoMixin,
    RolRequeridoMixin, get_funcionario, tiene_rol,
)
from measurement.models import Periodo
from organizations.models import Funcionario, ItemMedible

from .forms import ActividadForm, AnularForm, EvidenciaForm, ValidacionForm
from .models import Actividad, Evidencia, Validacion
from .services import (
    CRUDActividad, CRUDEvidencia, CRUDValidacion, actividades_visibles, buscar_por_codigo, evidencias_visibles,
)

TIPOS_MIME = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "pdf": "application/pdf"}


class OperativoMixin(RolRequeridoMixin):
    roles_permitidos = ROLES_OPERATIVOS


class VerificadorMixin(RolRequeridoMixin):
    roles_permitidos = ROLES_VALIDACION


def _es_autor(user, actividad):
    funcionario = get_funcionario(user)
    return funcionario is not None and funcionario.pk == actividad.funcionario_id


def _puede_anular(user, actividad):
    if actividad.estado == Actividad.ESTADO_ANULADA:
        return False
    if tiene_rol(user, *ROLES_SUPERVISION):
        return True
    return _es_autor(user, actividad) and actividad.estado != Actividad.ESTADO_VALIDADA


# ---------------------------------------------------------------------------
# Actividades
# ---------------------------------------------------------------------------
class ActividadListView(RolRequeridoMixin, ModoMixin, ListView):
    """Historial filtrable (RF-032): cada usuario ve solo lo que su ámbito permite."""
    template_name = "activities/actividad_.html"
    context_object_name = "actividades"
    paginate_by = 15
    titulo = "Actividades"
    roles_edicion = ROLES_OPERATIVOS

    def get_queryset(self):
        qs = actividades_visibles(self.request.user)
        g = self.request.GET
        for campo, filtro in (("estado", "estado"), ("tipo_registro", "tipo_registro"), ("item", "item_id"),
                              ("periodo", "periodo_id"), ("funcionario", "funcionario_id"),
                              ("fecha_desde", "fecha__gte"), ("fecha_hasta", "fecha__lte")):
            if g.get(campo):
                qs = qs.filter(**{filtro: g[campo]})
        if g.get("q", "").strip():
            q = g["q"].strip()
            qs = qs.filter(accion__icontains=q) | qs.filter(contacto__icontains=q)
        return qs

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        g = self.request.GET
        contexto.update(
            filtros=g, estados=Actividad.ESTADOS, tipos=Actividad.TIPOS, periodos=Periodo.objects.all(),
            items=ItemMedible.objects.select_related("cargo"),
            funcionarios=Funcionario.objects.filter(
                pk__in=actividades_visibles(self.request.user).values("funcionario_id")),
        )
        return contexto


class ActividadDetailView(RolRequeridoMixin, ModoMixin, DetailView):
    template_name = "activities/actividad_.html"
    context_object_name = "actividad"
    modo = "detalle"

    def get_queryset(self):
        return actividades_visibles(self.request.user)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        actividad, user = self.object, self.request.user
        autor_operativo = _es_autor(user, actividad) and tiene_rol(user, *ROLES_OPERATIVOS)
        contexto.update(
            titulo=f"Actividad {actividad.codigo}",
            evidencias=CRUDEvidencia.mostrar_evidencia_por_actividad(actividad),
            puede_editar=autor_operativo and actividad.editable,
            puede_adjuntar=autor_operativo and actividad.admite_evidencia,
            puede_anular=_puede_anular(user, actividad),
            puede_validar=tiene_rol(user, *ROLES_VALIDACION) and not _es_autor(user, actividad),
            anular_form=AnularForm(),
        )
        return contexto


class _FormularioActividadMixin(ModoMixin, GuardarMixin):
    model = Actividad
    form_class = ActividadForm
    template_name = "activities/actividad_.html"
    modo = "form"
    roles_edicion = ROLES_OPERATIVOS

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["funcionario"] = get_funcionario(self.request.user)
        kwargs["area"] = self.request.GET.get("area") or None
        return kwargs


class ActividadCreateView(OperativoMixin, _FormularioActividadMixin, CreateView):
    titulo = "Registrar actividad"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = Actividad(funcionario=get_funcionario(self.request.user))
        return kwargs

    def guardar(self, form):
        self.object = CRUDActividad.crear_actividad(form.instance, self.request.user)
        self.mensaje_exito = (f"Actividad registrada. Identificador: {self.object.pk} · "
                              f"Código: {self.object.codigo}. Ahora adjunte su evidencia.")

    def get_success_url(self):
        if self.object.ingreso_agenda_colectiva:
            try:   # el compromiso se completa en la app agenda (si ya está disponible)
                return reverse("agenda:compromiso_create") + f"?actividad={self.object.pk}"
            except NoReverseMatch:
                pass
        return reverse("activities:actividad_detail", args=[self.object.pk])


class ActividadUpdateView(OperativoMixin, _FormularioActividadMixin, UpdateView):
    titulo = "Editar actividad"
    mensaje_exito = "Actividad actualizada."

    def get_queryset(self):
        return actividades_visibles(self.request.user).filter(funcionario=get_funcionario(self.request.user))

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not self.object.editable:
            messages.error(request, f"Una actividad en estado «{self.object.estado}» no puede modificarse.")
            return redirect("activities:actividad_detail", pk=self.object.pk)
        return super().get(request, *args, **kwargs)

    def guardar(self, form):
        self.object = CRUDActividad.modificar_actividad(form.instance, self.request.user)

    def get_success_url(self):
        return reverse("activities:actividad_detail", args=[self.object.pk])


class ActividadAnularView(AccionPostView):
    roles_permitidos = ()   # la autorización fina se valida en accion()

    def get_objeto(self, pk):
        return get_object_or_404(actividades_visibles(self.request.user), pk=pk)

    def accion(self, request, objeto):
        form = AnularForm(request.POST)
        if not _puede_anular(request.user, objeto):
            raise ReglaNegocioError("No tiene permiso para anular esta actividad.")
        if not form.is_valid():
            raise ReglaNegocioError("Debe indicar el motivo de la anulación.")
        CRUDActividad.anular_actividad(objeto, form.cleaned_data["motivo"], request.user)
        return f"Actividad {objeto.codigo} anulada: ya no aporta al avance."

    def get_redirect(self, objeto):
        return reverse("activities:actividad_detail", args=[objeto.pk])


def buscar_codigo(request):
    """Busca una actividad por su código (ACT-0000123 o ACT-0000123-E01), HU-10."""
    if not request.user.is_authenticated:
        return redirect("login")
    actividad = buscar_por_codigo(request.GET.get("codigo", ""), request.user)
    if actividad is None:
        messages.error(request, "No se encontró ninguna actividad con ese código en su ámbito.")
        return redirect("activities:actividad_list")
    return redirect("activities:actividad_detail", pk=actividad.pk)


# ---------------------------------------------------------------------------
# Evidencias
# ---------------------------------------------------------------------------
class EvidenciaCreateView(OperativoMixin, ModoMixin, GuardarMixin, FormView):
    form_class = EvidenciaForm
    template_name = "activities/evidencia_.html"
    modo, titulo = "form", "Adjuntar evidencia"
    roles_edicion = ROLES_OPERATIVOS

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            self.actividad = get_object_or_404(
                actividades_visibles(request.user).filter(funcionario=get_funcionario(request.user)),
                pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.update(actividad=self.actividad, evidencias=self.actividad.evidencias.all())
        return contexto

    def guardar(self, form):
        evidencia = CRUDEvidencia.adjuntar_evidencia(self.actividad, form.cleaned_data["archivo"], self.request.user)
        self.mensaje_exito = f"Evidencia {evidencia.codigo_evidencia} adjuntada. Quedó pendiente de revisión."

    def get_success_url(self):
        return reverse("activities:actividad_detail", args=[self.actividad.pk])


def evidencia_archivo(request, pk):
    """Entrega controlada del archivo (nunca por URL pública): solo si el usuario puede ver la actividad."""
    if not request.user.is_authenticated:
        return redirect("login")
    evidencia = get_object_or_404(evidencias_visibles(request.user), pk=pk)
    if not evidencia.archivo_vinculo:
        raise Http404
    respuesta = FileResponse(evidencia.archivo_vinculo.open("rb"),
                             content_type=TIPOS_MIME.get(evidencia.extension, "application/octet-stream"))
    modo = "attachment" if request.GET.get("descargar") else "inline"
    respuesta["Content-Disposition"] = f'{modo}; filename="{evidencia.codigo_evidencia}.{evidencia.extension}"'
    respuesta["X-Content-Type-Options"] = "nosniff"
    respuesta["Cache-Control"] = "private, no-store"
    return respuesta


# ---------------------------------------------------------------------------
# Validación (verificador)
# ---------------------------------------------------------------------------
class ValidacionBandejaView(VerificadorMixin, ModoMixin, ListView):
    """Evidencias pendientes de revisión dentro del ámbito del verificador (sin las propias)."""
    template_name = "activities/validacion_.html"
    context_object_name = "evidencias"
    paginate_by = 15
    titulo = "Evidencias pendientes de validación"
    roles_edicion = ROLES_VALIDACION

    def get_queryset(self):
        funcionario = get_funcionario(self.request.user)
        qs = evidencias_visibles(self.request.user).filter(estado_revision=Evidencia.ESTADO_PENDIENTE) \
            .exclude(actividad__funcionario=funcionario).order_by("fecha_carga")
        g = self.request.GET
        if g.get("funcionario"):
            qs = qs.filter(actividad__funcionario_id=g["funcionario"])
        if g.get("item"):
            qs = qs.filter(actividad__item_id=g["item"])
        return qs

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.update(
            items=ItemMedible.objects.select_related("cargo"),
            funcionarios=Funcionario.objects.filter(
                pk__in=evidencias_visibles(self.request.user).values("actividad__funcionario_id")),
            filtros=self.request.GET)
        return contexto


class ValidacionCreateView(VerificadorMixin, ModoMixin, GuardarMixin, FormView):
    form_class = ValidacionForm
    template_name = "activities/validacion_.html"
    modo, titulo = "form", "Revisar evidencia"
    roles_edicion = ROLES_VALIDACION
    success_url_name = "activities:validacion_bandeja"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            self.evidencia = get_object_or_404(evidencias_visibles(request.user), pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.update(
            evidencia=self.evidencia, actividad=self.evidencia.actividad,
            historial=CRUDValidacion.mostrar_historial_validacion(self.evidencia.codigo_evidencia),
            es_propia=_es_autor(self.request.user, self.evidencia.actividad))
        return contexto

    def guardar(self, form):
        decision, obs = form.cleaned_data["decision"], form.cleaned_data["observacion"]
        accion = {Validacion.DECISION_APROBADA: CRUDValidacion.aprobar_evidencia,
                  Validacion.DECISION_RECHAZADA: CRUDValidacion.rechazar_evidencia,
                  Validacion.DECISION_CORRECCION: CRUDValidacion.solicitar_correccion}[decision]
        accion(self.evidencia, obs, self.request.user)
        self.mensaje_exito = {
            Validacion.DECISION_APROBADA: "Evidencia aprobada: la actividad aporta al avance.",
            Validacion.DECISION_RECHAZADA: "Evidencia rechazada: la actividad no aporta al avance.",
            Validacion.DECISION_CORRECCION: "Se solicitó corrección al funcionario.",
        }[decision]
