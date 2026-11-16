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

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponse
from openpyxl import Workbook
from core.pagination import PageSizeMixin
from django.utils import timezone
from core.reporting import incorporar_metadatos_informe
from core.reporting import informe_excel

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

class ActividadListView(PageSizeMixin, RolRequeridoMixin, ModoMixin, ListView):
    """Historial de actividades con filtros completos y ámbito autorizado (RF-032)."""
    permisos_permitidos = ('actividades.ver',)

    template_name = "activities/actividad_.html"
    context_object_name = "actividades"
    paginate_by = 15
    page_size_session_key = "actividad_page_size"
    titulo = "Actividades"
    roles_edicion = ROLES_OPERATIVOS

    def get_queryset(self):
        from django.utils.dateparse import parse_date

        qs = actividades_visibles(
            self.request.user
        ).select_related(
            "funcionario",
            "funcionario__delegacion",
            "funcionario__cargo",
            "item",
            "periodo",
            "catalogo",
        )

        filtros = self.request.GET

        # Filtros por identificadores.
        for campo, filtro in (
            ("estado", "estado"),
            ("tipo_registro", "tipo_registro"),
            ("item", "item_id"),
            ("periodo", "periodo_id"),
            ("funcionario", "funcionario_id"),
            ("delegacion", "funcionario__delegacion_id"),
            ("cargo", "funcionario__cargo_id"),
        ):
            valor = filtros.get(campo, "").strip()

            if valor:
                if campo in {
                    "item",
                    "periodo",
                    "funcionario",
                    "delegacion",
                    "cargo",
                }:
                    if valor.isdigit():
                        qs = qs.filter(**{filtro: valor})
                else:
                    qs = qs.filter(**{filtro: valor})

        # Área corresponde al ámbito definido para la delegación.
        area = filtros.get("area", "").strip()

        if area:
            qs = qs.filter(
                funcionario__delegacion__ambito__icontains=area
            )

        # Rango de fechas: solo se aplican fechas válidas.
        fecha_desde = parse_date(
            filtros.get("fecha_desde", "").strip()
        )
        fecha_hasta = parse_date(
            filtros.get("fecha_hasta", "").strip()
        )

        if fecha_desde:
            qs = qs.filter(fecha__gte=fecha_desde)

        if fecha_hasta:
            qs = qs.filter(fecha__lte=fecha_hasta)

        # Búsqueda general en los datos principales del registro.
        termino = filtros.get("q", "").strip()

        if termino:
            qs = qs.filter(
                Q(accion__icontains=termino)
                | Q(contacto__icontains=termino)
                | Q(funcionario__nombre__icontains=termino)
                | Q(
                    funcionario__identificador_institucional__icontains=termino
                )
                | Q(item__nombre_item__icontains=termino)
                | Q(catalogo__nombre__icontains=termino)
                | Q(catalogo_nombre__icontains=termino)
            )

        return qs.order_by("-fecha", "-id_actividad")

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)

        base = actividades_visibles(self.request.user)

        funcionarios_autorizados = (
            Funcionario.objects.filter(
                pk__in=base.values("funcionario_id")
            )
            .select_related("delegacion", "cargo")
            .distinct()
            .order_by("nombre")
        )

        delegaciones_autorizadas = (
            funcionarios_autorizados
            .values_list(
                "delegacion_id",
                "delegacion__nombre",
            )
            .distinct()
            .order_by("delegacion__nombre")
        )

        cargos_autorizados = (
            funcionarios_autorizados
            .values_list(
                "cargo_id",
                "cargo__nombre_cargo",
            )
            .distinct()
            .order_by("cargo__nombre_cargo")
        )

        areas_autorizadas = (
            funcionarios_autorizados
            .values_list(
                "delegacion__ambito",
                flat=True,
            )
            .exclude(delegacion__ambito="")
            .distinct()
            .order_by("delegacion__ambito")
        )

        items_autorizados = (
            ItemMedible.objects.filter(
                pk__in=base.values("item_id")
            )
            .select_related("cargo")
            .distinct()
            .order_by("nombre_item")
        )

        contexto.update(
            filtros=self.request.GET,
            estados=Actividad.ESTADOS,
            tipos=Actividad.TIPOS,
            periodos=Periodo.objects.all().order_by("-fecha_inicio"),
            items=items_autorizados,
            funcionarios=funcionarios_autorizados,
            delegaciones=delegaciones_autorizadas,
            cargos=cargos_autorizados,
            areas=areas_autorizadas,
            total_resultados=self.get_queryset().count(),
        )

        return contexto


class ActividadDetailView(RolRequeridoMixin, ModoMixin, DetailView):
    permisos_permitidos = ('actividades.ver',)
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
    permisos_permitidos = ('actividades.registrar',)
    titulo = "Registrar actividad"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()

        kwargs["funcionario"] = get_funcionario(
            self.request.user
        )

        kwargs["area"] = (
            self.request.GET.get("area") or None
        )

        kwargs["instance"] = Actividad(
            funcionario=get_funcionario(self.request.user)
        )

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
    permisos_permitidos = ('actividades.editar',)
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
    permisos_permitidos = ('actividades.editar',)
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
    permisos_permitidos = ('actividades.editar',)
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
class ValidacionBandejaView(PageSizeMixin, VerificadorMixin, ModoMixin, ListView):
    """Bandeja filtrable de evidencias pendientes dentro del ámbito autorizado."""
    permisos_permitidos = ('validaciones.gestionar',)
    template_name = "activities/validacion_.html"
    context_object_name = "evidencias"
    paginate_by = 15
    page_size_session_key = "validacion_page_size"
    titulo = "Evidencias pendientes de validación"
    roles_edicion = ROLES_VALIDACION

    def get_queryset(self):
        funcionario = get_funcionario(self.request.user)

        qs = evidencias_visibles(self.request.user).filter(
            estado_revision=Evidencia.ESTADO_PENDIENTE
        )

        if funcionario is not None:
            qs = qs.exclude(actividad__funcionario=funcionario)
        else:
            qs = qs.none()

        filtros = self.request.GET

        if filtros.get("funcionario"):
            qs = qs.filter(
                actividad__funcionario_id=filtros["funcionario"]
            )

        if filtros.get("item"):
            qs = qs.filter(
                actividad__item_id=filtros["item"]
            )

        if filtros.get("fecha_desde"):
            qs = qs.filter(
                fecha_carga__date__gte=filtros["fecha_desde"]
            )

        if filtros.get("fecha_hasta"):
            qs = qs.filter(
                fecha_carga__date__lte=filtros["fecha_hasta"]
            )

        q = filtros.get("q", "").strip()
        if q:
            qs = qs.filter(
                Q(codigo_evidencia__icontains=q)
                | Q(actividad__accion__icontains=q)
                | Q(actividad__funcionario__nombre__icontains=q)
                | Q(actividad__item__nombre_item__icontains=q)
            )

        return qs.select_related(
            "actividad",
            "actividad__funcionario",
            "actividad__item",
        ).order_by("fecha_carga")

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)

        funcionario = get_funcionario(self.request.user)
        visibles = evidencias_visibles(self.request.user).filter(
            estado_revision=Evidencia.ESTADO_PENDIENTE
        )

        if funcionario is not None:
            visibles = visibles.exclude(actividad__funcionario=funcionario)
        else:
            visibles = visibles.none()

        filtros = self.request.GET

        contexto.update(
            items=ItemMedible.objects.filter(
                pk__in=visibles.values("actividad__item_id")
            ).distinct().order_by("nombre_item"),

            funcionarios=Funcionario.objects.filter(
                pk__in=visibles.values("actividad__funcionario_id")
            ).distinct().order_by("nombre"),

            filtros=filtros,
            q=filtros.get("q", ""),
            fecha_desde=filtros.get("fecha_desde", ""),
            fecha_hasta=filtros.get("fecha_hasta", ""),
            total_resultados=self.get_queryset().count(),
        )

        return contexto

class ValidacionCreateView(VerificadorMixin, ModoMixin, GuardarMixin, FormView):
    permisos_permitidos = ('validaciones.gestionar',)
    form_class = ValidacionForm
    template_name = "activities/validacion_.html"
    modo, titulo = "form", "Revisar evidencia"
    roles_edicion = ROLES_VALIDACION
    success_url_name = "activities:validacion_bandeja"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            funcionario = get_funcionario(request.user)

            qs = evidencias_visibles(request.user).filter(
                estado_revision=Evidencia.ESTADO_PENDIENTE
            )

            if funcionario is not None:
                qs = qs.exclude(actividad__funcionario=funcionario)
            else:
                qs = qs.none()

            self.evidencia = get_object_or_404(
                qs.select_related(
                    "actividad",
                    "actividad__funcionario",
                    "actividad__item",
                ),
                pk=kwargs["pk"],
            )

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)

        contexto.update(
            evidencia=self.evidencia,
            actividad=self.evidencia.actividad,
            historial=CRUDValidacion.mostrar_historial_validacion(
                self.evidencia.codigo_evidencia
            ),
            es_propia=_es_autor(
                self.request.user,
                self.evidencia.actividad,
            ),
        )

        return contexto

    def guardar(self, form):
        decision = form.cleaned_data["decision"]
        observacion = form.cleaned_data["observacion"]

        accion = {
            Validacion.DECISION_APROBADA: CRUDValidacion.aprobar_evidencia,
            Validacion.DECISION_RECHAZADA: CRUDValidacion.rechazar_evidencia,
            Validacion.DECISION_CORRECCION: CRUDValidacion.solicitar_correccion,
        }[decision]

        accion(self.evidencia, observacion, self.request.user)

        self.mensaje_exito = {
            Validacion.DECISION_APROBADA:
                "Evidencia aprobada: la actividad aporta al avance.",
            Validacion.DECISION_RECHAZADA:
                "Evidencia rechazada: la actividad no aporta al avance.",
            Validacion.DECISION_CORRECCION:
                "Se solicitó corrección al funcionario.",
        }[decision]
        
@login_required
@informe_excel("Informe de actividades")
def exportar_actividades_excel(request):
    """Exporta las actividades aplicando los mismos filtros y permisos (RF-032/RF-033)."""
    from django.utils.dateparse import parse_date

    queryset = actividades_visibles(
        request.user
    ).select_related(
        "funcionario",
        "funcionario__delegacion",
        "funcionario__cargo",
        "item",
        "catalogo",
        "periodo",
    )

    filtros = request.GET

    for campo, filtro in (
        ("estado", "estado"),
        ("tipo_registro", "tipo_registro"),
        ("item", "item_id"),
        ("periodo", "periodo_id"),
        ("funcionario", "funcionario_id"),
        ("delegacion", "funcionario__delegacion_id"),
        ("cargo", "funcionario__cargo_id"),
    ):
        valor = filtros.get(campo, "").strip()

        if not valor:
            continue

        if campo in {
            "item",
            "periodo",
            "funcionario",
            "delegacion",
            "cargo",
        }:
            if valor.isdigit():
                queryset = queryset.filter(**{filtro: valor})
        else:
            queryset = queryset.filter(**{filtro: valor})

    area = filtros.get("area", "").strip()

    if area:
        queryset = queryset.filter(
            funcionario__delegacion__ambito__icontains=area
        )

    fecha_desde = parse_date(
        filtros.get("fecha_desde", "").strip()
    )
    fecha_hasta = parse_date(
        filtros.get("fecha_hasta", "").strip()
    )

    if fecha_desde:
        queryset = queryset.filter(fecha__gte=fecha_desde)

    if fecha_hasta:
        queryset = queryset.filter(fecha__lte=fecha_hasta)

    termino = filtros.get("q", "").strip()

    if termino:
        queryset = queryset.filter(
            Q(accion__icontains=termino)
            | Q(contacto__icontains=termino)
            | Q(funcionario__nombre__icontains=termino)
            | Q(
                funcionario__identificador_institucional__icontains=termino
            )
            | Q(item__nombre_item__icontains=termino)
            | Q(catalogo__nombre__icontains=termino)
            | Q(catalogo_nombre__icontains=termino)
        )

    libro = Workbook()
    hoja = libro.active
    hoja.title = "Actividades"

    hoja.append([
        "Código",
        "Fecha",
        "Tipo",
        "Funcionario",
        "Delegación",
        "Área / ámbito",
        "Cargo",
        "Ítem medible",
        "Actividad o servicio",
        "Acción ejecutada",
        "Contacto",
        "Estado",
        "Período",
    ])

    for actividad in queryset.order_by(
        "-fecha",
        "-id_actividad",
    ):
        hoja.append([
            actividad.codigo,
            actividad.fecha.strftime("%d/%m/%Y"),
            actividad.tipo_registro,
            actividad.funcionario.nombre,
            actividad.funcionario.delegacion.nombre,
            actividad.funcionario.delegacion.ambito,
            actividad.funcionario.cargo.nombre_cargo,
            actividad.item_nombre_historico,
            (
                actividad.catalogo_nombre
                or actividad.catalogo.nombre
            ),
            actividad.accion,
            actividad.contacto,
            actividad.estado,
            str(actividad.periodo),
        ])

    respuesta = HttpResponse(
        content_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        )
    )

    respuesta["Content-Disposition"] = (
        'attachment; filename="actividades_filtradas.xlsx"'
    )
    respuesta["Cache-Control"] = "private, no-store"

    libro.save(respuesta)

    return respuesta



@login_required
@informe_excel("Informe de validación de evidencias")
def exportar_validaciones_excel(request):
    """Exporta las evidencias pendientes dentro del ámbito autorizado."""

    if not tiene_rol(request.user, *ROLES_VALIDACION):
        return HttpResponse("No autorizado", status=403)

    funcionario = get_funcionario(request.user)

    queryset = evidencias_visibles(request.user).filter(
        estado_revision=Evidencia.ESTADO_PENDIENTE
    )

    if funcionario is not None:
        queryset = queryset.exclude(
            actividad__funcionario=funcionario
        )
    else:
        queryset = queryset.none()

    filtros = request.GET

    if filtros.get("funcionario"):
        queryset = queryset.filter(
            actividad__funcionario_id=filtros["funcionario"]
        )

    if filtros.get("item"):
        queryset = queryset.filter(
            actividad__item_id=filtros["item"]
        )

    if filtros.get("fecha_desde"):
        queryset = queryset.filter(
            fecha_carga__date__gte=filtros["fecha_desde"]
        )

    if filtros.get("fecha_hasta"):
        queryset = queryset.filter(
            fecha_carga__date__lte=filtros["fecha_hasta"]
        )

    q = filtros.get("q", "").strip()

    if q:
        queryset = queryset.filter(
            Q(codigo_evidencia__icontains=q)
            | Q(actividad__accion__icontains=q)
            | Q(actividad__funcionario__nombre__icontains=q)
            | Q(actividad__item__nombre_item__icontains=q)
        )

    queryset = queryset.select_related(
        "actividad",
        "actividad__funcionario",
        "actividad__item",
        "actividad__catalogo",
        "actividad__periodo",
    ).order_by("fecha_carga")

    libro = Workbook()
    hoja = libro.active
    hoja.title = "Validación evidencias"

    hoja.append(["Informe de validación de evidencias"])
    hoja.append([
        "Generado",
        timezone.localtime().strftime("%d/%m/%Y %H:%M"),
    ])
    hoja.append([])
    hoja.append([
        "Código evidencia",
        "Actividad",
        "Funcionario",
        "Ítem medible",
        "Fecha de carga",
        "Estado",
        "Archivo",
    ])

    for evidencia in queryset.iterator():
        actividad = evidencia.actividad

        hoja.append([
            evidencia.codigo_evidencia,
            actividad.codigo,
            actividad.funcionario.nombre,
            actividad.item_nombre_historico,
            timezone.localtime(evidencia.fecha_carga).strftime(
                "%d/%m/%Y %H:%M"
            ),
            evidencia.estado_revision,
            (
                f"{evidencia.codigo_evidencia}.{evidencia.extension}"
                if evidencia.archivo_vinculo else ""
            ),
        ])

    respuesta = HttpResponse(
        content_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        )
    )
    respuesta["Content-Disposition"] = (
        'attachment; filename="validacion_evidencias.xlsx"'
    )
    respuesta["Cache-Control"] = "private, no-store"

    libro.save(respuesta)
    return respuesta
