"""
Vistas de measurement. Una plantilla por entidad (templates/measurement/):
  periodo_.html   modo: lista | form | detalle
  meta_.html      modo: lista | form
  ajuste_.html    modo: lista | form
  indicador_.html panel de desempeño (modo: personal | funcionario)
  semaforo.html   tablero de delegación

Permisos: configurar períodos/metas/ajustes -> Administrador y Coordinador;
reabrir un período -> solo Administrador; lectura -> Administrador, Coordinador y Delegado
(este último solo su delegación); cada funcionario ve su propio panel.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from core.decorators import funcionario_requerido
from core.exceptions import ReglaNegocioError
from core.mixins import (
    ROLES_CONFIGURACION, ROLES_MEDICION, ROLES_SUPERVISION, AccionPostView, AmbitoDelegacionMixin,
    GuardarMixin, ModoMixin, RolRequeridoMixin, denegar_acceso, es_transversal,
    filtrar_por_ambito, get_funcionario, tiene_rol,
)
from organizations.models import Cargo, Delegacion, Funcionario, ItemMedible

from .forms import (
    AjusteForm,
    MetaForm,
    PeriodoForm,
    ReabrirPeriodoForm,
    ReglasCalculoForm,
)
from .models import (
    Ajuste,
    Meta as MetaModel,
    MetaVersion,
    Periodo,
    ReglaCalculoVersion,
)
from .services import CalculoIndicadores, CRUDAjuste, CRUDMeta, CRUDPeriodo

from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from openpyxl import Workbook
from django.core.paginator import Paginator
from core.pagination import PageSizeMixin, PAGE_SIZE_OPTIONS, get_page_size

class LecturaMixin(RolRequeridoMixin):
    roles_permitidos = ROLES_SUPERVISION


class MedicionMixin(RolRequeridoMixin):
    roles_permitidos = ROLES_MEDICION


def _periodo_seleccionado(request):
    """Período pedido por ?periodo=, o el vigente, o el más reciente."""
    pk = request.GET.get("periodo")
    if pk and pk.isdigit():
        return Periodo.objects.filter(pk=pk).first()
    return Periodo.objects.vigente() or Periodo.objects.first()


# ---------------------------------------------------------------------------
# Períodos
# ---------------------------------------------------------------------------

class PeriodoListView(PageSizeMixin, LecturaMixin, ModoMixin, ListView):
    model = Periodo
    template_name = "measurement/periodo_.html"
    context_object_name = "periodos"
    paginate_by = 10
    page_size_session_key = "periodo_page_size"
    titulo = "Períodos de medición"
    roles_edicion = ROLES_MEDICION

    def get_queryset(self):
        qs = super().get_queryset()
        filtros = self.request.GET

        estado = filtros.get("estado", "").strip()
        if estado in dict(Periodo.ESTADOS):
            qs = qs.filter(estado=estado)

        fecha_desde = filtros.get("fecha_desde", "").strip()
        if fecha_desde:
            qs = qs.filter(fecha_termino__gte=fecha_desde)

        fecha_hasta = filtros.get("fecha_hasta", "").strip()
        if fecha_hasta:
            qs = qs.filter(fecha_inicio__lte=fecha_hasta)

        q = filtros.get("q", "").strip()
        if q:
            from datetime import datetime

            fecha_busqueda = None
            for formato in ("%d/%m/%Y", "%Y-%m-%d"):
                try:
                    fecha_busqueda = datetime.strptime(q, formato).date()
                    break
                except ValueError:
                    continue

            if fecha_busqueda:
                qs = qs.filter(
                    Q(fecha_inicio=fecha_busqueda)
                    | Q(fecha_termino=fecha_busqueda)
                )
            else:
                qs = qs.none()

        return qs.order_by("-fecha_inicio")

def get_context_data(self, **kwargs):
    contexto = super().get_context_data(**kwargs)

    funcionarios = filtrar_por_ambito(
        Funcionario.objects.filter(
            estado=Funcionario.ESTADO_ACTIVO
        ).select_related("cargo", "delegacion"),
        self.request.user,
        "delegacion_id",
    )

    configuracion = []

    for funcionario in funcionarios:
        suma = CRUDMeta.suma_ponderaciones(
            funcionario,
            self.object,
        )

        faltante = max(0, 100 - suma)
        excedente = max(0, suma - 100)

        if suma == 100:
            estado = "Completa"
        elif suma < 100:
            estado = "Pendiente"
        else:
            estado = "Excedida"

        configuracion.append({
            "funcionario": funcionario,
            "suma": suma,
            "faltante": faltante,
            "excedente": excedente,
            "completa": estado == "Completa",
            "estado": estado,
            "metas": funcionario.metas.filter(
                periodo=self.object
            ).count(),
        })

    contexto.update(
        titulo=f"Período {self.object}",
        configuracion=configuracion,
        total_metas=self.object.metas.count(),
        puede_reabrir=tiene_rol(
            self.request.user,
            *ROLES_CONFIGURACION,
        ),
        puede_configurar_reglas=tiene_rol(
            self.request.user,
            *ROLES_CONFIGURACION,
        ),
        puede_editar=tiene_rol(
            self.request.user,
            *ROLES_MEDICION,
        ),
        reabrir_form=ReabrirPeriodoForm(),
    )

    return contexto


class PeriodoDetailView(LecturaMixin, ModoMixin, DetailView):
    """Resumen del período y estado de ponderaciones por funcionario."""

    model = Periodo
    template_name = "measurement/periodo_.html"
    context_object_name = "periodo"
    modo = "detalle"
    roles_edicion = ROLES_MEDICION

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)

        funcionarios = filtrar_por_ambito(
            Funcionario.objects.filter(
                estado=Funcionario.ESTADO_ACTIVO
            ).select_related(
                "cargo",
                "delegacion",
            ),
            self.request.user,
            "delegacion_id",
        )

        configuracion = []

        for funcionario in funcionarios:
            suma = CRUDMeta.suma_ponderaciones(
                funcionario,
                self.object,
            )

            faltante = max(0, 100 - suma)
            excedente = max(0, suma - 100)

            if suma == 100:
                estado = "Completa"
            elif suma < 100:
                estado = "Pendiente"
            else:
                estado = "Excedida"

            configuracion.append({
                "funcionario": funcionario,
                "suma": suma,
                "faltante": faltante,
                "excedente": excedente,
                "completa": estado == "Completa",
                "estado": estado,
                "metas": funcionario.metas.filter(
                    periodo=self.object
                ).count(),
            })

        contexto.update(
            titulo=f"Período {self.object}",
            configuracion=configuracion,
            total_metas=self.object.metas.count(),

            puede_configurar_reglas=tiene_rol(
                self.request.user,
                *ROLES_CONFIGURACION,
            ),

            puede_ver_historial_reglas=tiene_rol(
                self.request.user,
                *ROLES_SUPERVISION,
            ),

            puede_editar=tiene_rol(
                self.request.user,
                *ROLES_MEDICION,
            ),

            puede_reabrir=tiene_rol(
                self.request.user,
                *ROLES_CONFIGURACION,
            ),

            reabrir_form=ReabrirPeriodoForm(),
        )

        return contexto

class PeriodoFormMixin(MedicionMixin, ModoMixin, GuardarMixin):
    model = Periodo
    form_class = PeriodoForm
    template_name = "measurement/periodo_.html"
    modo = "form"
    roles_edicion = ROLES_MEDICION
    success_url_name = "measurement:periodo_list"


class PeriodoCreateView(PeriodoFormMixin, CreateView):
    titulo = "Nuevo período"
    mensaje_exito = "Período creado. Los días computables se calcularon automáticamente."

    def guardar(self, form):
        self.object = CRUDPeriodo.crear_periodo(form.instance, self.request.user)


class PeriodoUpdateView(PeriodoFormMixin, UpdateView):
    titulo = "Editar período"
    mensaje_exito = "Período actualizado; los indicadores se recalcularon."

    def guardar(self, form):
        self.object = CRUDPeriodo.modificar_periodo(form.instance, self.request.user)


class PeriodoCerrarView(AccionPostView):
    roles_permitidos = ROLES_MEDICION
    redirect_name = "measurement:periodo_list"

    def get_objeto(self, pk):
        return get_object_or_404(Periodo, pk=pk)

    def accion(self, request, objeto):
        CRUDPeriodo.cerrar_periodo(objeto, request.user)
        return f"Período {objeto} cerrado. Sus resultados quedaron congelados."


class PeriodoReabrirView(AccionPostView):
    roles_permitidos = ROLES_CONFIGURACION        # solo Administrador (RN-013)
    redirect_name = "measurement:periodo_list"

    def get_objeto(self, pk):
        return get_object_or_404(Periodo, pk=pk)

    def accion(self, request, objeto):
        CRUDPeriodo.reabrir_periodo(objeto, request.POST.get("motivo", ""), request.user)
        return f"Período {objeto} reabierto. Quedó registrado en la auditoría."


@login_required
def configurar_reglas_periodo(request, pk):
    """
    Permite al Administrador configurar reglas de cálculo
    para un período abierto y conservar sus versiones.
    """
    if not tiene_rol(request.user, *ROLES_CONFIGURACION):
        return denegar_acceso(request)

    periodo = get_object_or_404(Periodo, pk=pk)

    if not periodo.abierto:
        messages.error(
            request,
            "No se pueden modificar las reglas de un período cerrado.",
        )
        return redirect(
            "measurement:periodo_detail",
            pk=periodo.pk,
        )

    version_actual = (
        ReglaCalculoVersion.objects
        .filter(periodo=periodo)
        .order_by("-numero_version")
        .first()
    )

    configuracion = (
        version_actual.datos
        if version_actual
        else CRUDPeriodo._datos_reglas_actuales()
    )

    if request.method == "POST":
        form = ReglasCalculoForm(request.POST)

        if form.is_valid():
            try:
                nueva_version = CRUDPeriodo.actualizar_reglas_periodo(
                    periodo,
                    form.cleaned_data,
                    request.user,
                )

                messages.success(
                    request,
                    (
                        "Reglas actualizadas correctamente. "
                        f"Se registró la versión "
                        f"{nueva_version.numero_version}."
                    ),
                )

                return redirect(
                    "measurement:periodo_detail",
                    pk=periodo.pk,
                )

            except ReglaNegocioError as exc:
                messages.error(request, str(exc))

    else:
        form = ReglasCalculoForm(
            initial={
                "tope_cumplimiento": configuracion.get(
                    "tope_cumplimiento",
                    150,
                ),
                "umbral_colectivo": configuracion.get(
                    "umbral_colectivo",
                    60,
                ),
                "umbral_ambar": configuracion.get(
                    "umbral_ambar",
                    60,
                ),
            }
        )

    return render(
        request,
        "measurement/reglas_periodo.html",
        {
            "titulo": "Configurar reglas de cálculo",
            "periodo": periodo,
            "form": form,
            "version_actual": version_actual,
        },
    )

@login_required
def historial_reglas_periodo(request, pk):
    """
    Consulta el historial de versiones de reglas de cálculo
    de un período, sin permitir modificar versiones anteriores.
    """
    if not tiene_rol(request.user, *ROLES_SUPERVISION):
        return denegar_acceso(request)

    periodo = get_object_or_404(
        Periodo,
        pk=pk,
    )

    versiones = (
        ReglaCalculoVersion.objects
        .filter(periodo=periodo)
        .select_related("creado_por")
        .order_by("-numero_version")
    )

    return render(
        request,
        "measurement/reglas_historial.html",
        {
            "titulo": "Historial de reglas de cálculo",
            "periodo": periodo,
            "versiones": versiones,
            "total_versiones": versiones.count(),
        },
    )


class PeriodoRecalcularView(AccionPostView):
    roles_permitidos = ROLES_MEDICION
    redirect_name = "measurement:periodo_list"

    def get_objeto(self, pk):
        return get_object_or_404(Periodo, pk=pk)

    def accion(self, request, objeto):
        if not objeto.abierto:
            raise ReglaNegocioError(
                "El período está cerrado: sus resultados no se recalculan."
            )

        cantidad = CalculoIndicadores.recalcular_periodo(objeto)

        return f"Se recalcularon {cantidad} indicadores."

    def get_redirect(self, objeto):
        return reverse(
            "measurement:periodo_detail",
            args=[objeto.pk],
        )


@login_required
def items_vigentes_funcionario(request, funcionario_id):
    """
    Devuelve exclusivamente los ítems vigentes del cargo
    del funcionario seleccionado y dentro del ámbito autorizado.
    """

    if not tiene_rol(request.user, *ROLES_MEDICION):
        return JsonResponse(
            {"error": "No tienes permiso para consultar estos ítems."},
            status=403,
        )

    funcionario = (
        filtrar_por_ambito(
            Funcionario.objects.select_related(
                "cargo",
                "delegacion",
            ),
            request.user,
            "delegacion_id",
        )
        .filter(
            pk=funcionario_id,
            estado=Funcionario.ESTADO_ACTIVO,
        )
        .first()
    )

    if funcionario is None:
        return JsonResponse(
            {
                "error": (
                    "Funcionario no encontrado o fuera de tu ámbito."
                )
            },
            status=404,
        )

    items = (
        ItemMedible.objects.filter(
            cargo_id=funcionario.cargo_id,
            vigencia=True,
        )
        .order_by("nombre_item")
    )

    return JsonResponse({
        "cargo": funcionario.cargo.nombre_cargo,
        "items": [
            {
                "id": item.pk,
                "codigo": item.codigo,
                "nombre": item.nombre_item,
                "tipo": item.tipo,
            }
            for item in items
        ],
    })

# ---------------------------------------------------------------------------
# Metas
# ---------------------------------------------------------------------------



class MetaListView(
    LecturaMixin,
    AmbitoDelegacionMixin,
    ModoMixin,
    ListView,
):
    model = MetaModel
    template_name = "measurement/meta_.html"
    context_object_name = "metas"
    ambito_campo = "funcionario__delegacion_id"
    paginate_by = 15
    titulo = "Metas y ponderaciones"
    roles_edicion = ROLES_MEDICION

    def get_queryset(self):
        qs = super().get_queryset().select_related(
            "periodo",
            "funcionario",
            "funcionario__delegacion",
            "item",
            "cargo",
        )

        filtros = self.request.GET

        for campo, filtro in (
            ("periodo", "periodo_id"),
            ("funcionario", "funcionario_id"),
            ("cargo", "cargo_id"),
            ("item", "item_id"),
        ):
            valor = filtros.get(campo, "").strip()

            if valor.isdigit():
                qs = qs.filter(**{filtro: valor})

        return qs.order_by(
            "periodo",
            "funcionario__nombre",
            "item__nombre_item",
        )

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        filtros = self.request.GET

        periodo_sel = filtros.get("periodo", "").strip()
        funcionario_sel = filtros.get("funcionario", "").strip()
        cargo_sel = filtros.get("cargo", "").strip()
        item_sel = filtros.get("item", "").strip()

        # Solo funcionarios dentro del ámbito autorizado.
        funcionarios_autorizados = filtrar_por_ambito(
            Funcionario.objects.filter(
                estado=Funcionario.ESTADO_ACTIVO,
            ).select_related(
                "cargo",
                "delegacion",
            ),
            self.request.user,
            "delegacion_id",
        )

        # Los cargos disponibles se limitan a los de funcionarios
        # que el usuario está autorizado a consultar.
        cargos_autorizados = Cargo.objects.filter(
            pk__in=funcionarios_autorizados.values_list(
                "cargo_id",
                flat=True,
            )
        ).distinct()

        # Los ítems disponibles también respetan esos cargos.
        items_autorizados = ItemMedible.objects.filter(
            cargo__in=cargos_autorizados,
            vigencia=True,
        ).select_related(
            "cargo",
        ).order_by(
            "cargo__nombre_cargo",
            "nombre_item",
        )

        contexto.update(
            periodos=Periodo.objects.all(),
            cargos=cargos_autorizados,
            funcionarios=funcionarios_autorizados,
            items=items_autorizados,
            periodo_sel=periodo_sel,
            funcionario_sel=funcionario_sel,
            cargo_sel=cargo_sel,
            item_sel=item_sel,
            resumen_ponderaciones=[],
            cargo_resumen=None,
            periodo_resumen=None,
        )

        # El resumen se calcula solamente cuando se seleccionan
        # un cargo y un período válidos dentro del ámbito autorizado.
        if cargo_sel.isdigit() and periodo_sel.isdigit():
            cargo = cargos_autorizados.filter(
                pk=cargo_sel,
            ).first()

            periodo = Periodo.objects.filter(
                pk=periodo_sel,
            ).first()

            if cargo and periodo:
                funcionarios_resumen = funcionarios_autorizados.filter(
                    cargo=cargo,
                )

                if funcionario_sel.isdigit():
                    funcionarios_resumen = funcionarios_resumen.filter(
                        pk=funcionario_sel,
                    )

                contexto["resumen_ponderaciones"] = (
                    CRUDMeta.resumen_configuracion_cargo(
                        cargo,
                        periodo,
                        funcionarios_resumen,
                    )
                )

                contexto["cargo_resumen"] = cargo
                contexto["periodo_resumen"] = periodo

        return contexto


class MetaFormMixin(MedicionMixin, ModoMixin, GuardarMixin):
    model = MetaModel
    form_class = MetaForm
    template_name = "measurement/meta_.html"
    modo = "form"
    roles_edicion = ROLES_MEDICION
    success_url_name = "measurement:meta_list"


class MetaCreateView(MetaFormMixin, CreateView):
    titulo = "Nueva meta"
    mensaje_exito = "Meta creada."

    def guardar(self, form):
        if form.cleaned_data.get("aplicar_a_cargo"):
            resultado = CRUDMeta.crear_meta_para_cargo(form.instance, self.request.user)
            if not resultado["creadas"]:
                detalle = "; ".join(f"{f}: {m}" for f, m in resultado["omitidas"][:3])
                raise ReglaNegocioError(f"No se creó ninguna meta. {detalle}")
            self.mensaje_exito = f"Se crearon {len(resultado['creadas'])} metas para el cargo."
            if resultado["omitidas"]:
                messages.warning(self.request, f"{len(resultado['omitidas'])} funcionarios se omitieron: "
                                 + "; ".join(f"{f}: {m}" for f, m in resultado["omitidas"][:3]))
        else:
            self.object = CRUDMeta.crear_meta(form.instance, self.request.user)


class MetaUpdateView(MetaFormMixin, UpdateView):
    titulo = "Editar meta"
    mensaje_exito = "Meta actualizada y versionada."

    def guardar(self, form):
        self.object = CRUDMeta.modificar_meta(form.instance, self.request.user)


class MetaDeleteView(AccionPostView):
    roles_permitidos = ROLES_MEDICION
    redirect_name = "measurement:meta_list"

    def get_objeto(self, pk):
        return get_object_or_404(MetaModel, pk=pk)

    def accion(self, request, objeto):
        CRUDMeta.eliminar_meta(objeto, request.user)
        return "Meta eliminada."

# ---------------------------------------------------------------------------
# Historial de versiones de metas (RF-038)
# ---------------------------------------------------------------------------

@login_required
def meta_historial(request, pk):
    """
    Muestra el historial de parámetros de una meta,
    limitado al ámbito de delegación autorizado.
    """
    if not tiene_rol(request.user, *ROLES_SUPERVISION):
        return denegar_acceso(request)

    metas = filtrar_por_ambito(
        MetaModel.objects.select_related(
            "funcionario",
            "funcionario__delegacion",
            "item",
            "periodo",
            "cargo",
        ),
        request.user,
        "funcionario__delegacion_id",
    )

    meta = get_object_or_404(metas, pk=pk)

    versiones = (
        MetaVersion.objects
        .filter(objeto_id=meta.pk)
        .select_related("creado_por")
        .order_by("-numero_version")
    )

    return render(
        request,
        "measurement/meta_historial.html",
        {
            "titulo": "Historial de versiones",
            "meta": meta,
            "versiones": versiones,
            "total_versiones": versiones.count(),
        },
    )

# ---------------------------------------------------------------------------
# Ajustes (incentivos y penalizaciones)
# ---------------------------------------------------------------------------

class AjusteListView(PageSizeMixin, LecturaMixin, AmbitoDelegacionMixin, ModoMixin, ListView):
    model = Ajuste
    template_name = "measurement/ajuste_.html"
    context_object_name = "ajustes"
    ambito_campo = "funcionario__delegacion_id"
    paginate_by = 15
    page_size_session_key = "ajuste_page_size"
    titulo = "Incentivos y penalizaciones"
    roles_edicion = ROLES_MEDICION

    def get_queryset(self):
        qs = super().get_queryset().select_related(
            "periodo", "funcionario", "meta", "meta__item"
        )
        filtros = self.request.GET

        periodo = filtros.get("periodo", "").strip()
        if periodo:
            qs = qs.filter(periodo_id=periodo)

        funcionario = filtros.get("funcionario", "").strip()
        if funcionario:
            qs = qs.filter(funcionario_id=funcionario)

        efecto = filtros.get("efecto", "").strip()
        if efecto in dict(Ajuste.EFECTOS):
            qs = qs.filter(efecto=efecto)

        q = filtros.get("q", "").strip()
        if q:
            qs = qs.filter(
                Q(motivo__icontains=q)
                | Q(funcionario__nombre__icontains=q)
                | Q(meta__item__nombre_item__icontains=q)
            )

        return qs.order_by("-id_ajuste")

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        filtros = self.request.GET

        contexto.update(
            periodos=Periodo.objects.all(),
            funcionarios=Funcionario.objects.filter(
                pk__in=super().get_queryset().values("funcionario_id")
            ).distinct().order_by("nombre"),
            periodo_sel=filtros.get("periodo", ""),
            funcionario_sel=filtros.get("funcionario", ""),
            efecto_sel=filtros.get("efecto", ""),
            q=filtros.get("q", ""),
            total_resultados=self.get_queryset().count(),
        )
        return contexto

class AjusteCreateView(MedicionMixin, ModoMixin, GuardarMixin, CreateView):
    model = Ajuste
    form_class = AjusteForm
    template_name = "measurement/ajuste_.html"
    modo, titulo = "form", "Nuevo ajuste"
    roles_edicion = ROLES_MEDICION
    success_url_name = "measurement:ajuste_list"
    mensaje_exito = "Ajuste registrado."

    def guardar(self, form):
        self.object = CRUDAjuste.crear_ajuste(form.instance, self.request.user)


class AjusteUpdateView(MedicionMixin, ModoMixin, GuardarMixin, UpdateView):
    model = Ajuste
    form_class = AjusteForm
    template_name = "measurement/ajuste_.html"
    modo, titulo = "form", "Editar ajuste"
    roles_edicion = ROLES_MEDICION
    success_url_name = "measurement:ajuste_list"
    mensaje_exito = "Ajuste actualizado."

    def get_queryset(self):
        return filtrar_por_ambito(
            Ajuste.objects.select_related("funcionario", "periodo", "meta"),
            self.request.user,
            "funcionario__delegacion_id"
        )

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()

        if not self.object.periodo.abierto:
            messages.error(
                request,
                "No se pueden modificar ajustes de períodos cerrados."
            )
            return redirect("measurement:ajuste_list")

        return super().dispatch(request, *args, **kwargs)

    def guardar(self, form):
        self.object = CRUDAjuste.modificar_ajuste(
            form.instance,
            self.request.user
        )

class AjusteDeleteView(AccionPostView):
    roles_permitidos = ROLES_MEDICION
    redirect_name = "measurement:ajuste_list"

    def get_objeto(self, pk):
        return get_object_or_404(Ajuste, pk=pk)

    def accion(self, request, objeto):
        CRUDAjuste.eliminar_ajuste(objeto, request.user)
        return "Ajuste eliminado."


# ---------------------------------------------------------------------------
# Paneles de desempeño y semáforo
# ---------------------------------------------------------------------------
def _contexto_panel(request, funcionario, modo, titulo):
    periodo = _periodo_seleccionado(request)
    resumen = CalculoIndicadores.resumen_funcionario(funcionario, periodo) if periodo else None
    return {"modo": modo, "titulo": titulo, "funcionario": funcionario, "periodo": periodo,
            "periodos": Periodo.objects.all(), "resumen": resumen, "hoy": timezone.localdate()}


@login_required
@funcionario_requerido
def mi_desempeno(request):
    """Ficha y tablero personal (RF-008, RF-028, HU-06, HU-16)."""
    funcionario = get_funcionario(request.user)
    return render(request, "measurement/indicador_.html",
                  _contexto_panel(request, funcionario, "personal", "Mi desempeño"))


@login_required
def desempeno_funcionario(request, pk):
    """Panel de un funcionario para supervisión, dentro del ámbito del usuario (CA-07)."""
    if not tiene_rol(request.user, *ROLES_SUPERVISION):
        return denegar_acceso(request)
    qs = filtrar_por_ambito(Funcionario.objects.select_related("cargo", "delegacion"), request.user,
                            "delegacion_id")
    funcionario = get_object_or_404(qs, pk=pk)
    return render(request, "measurement/indicador_.html",
                  _contexto_panel(request, funcionario, "funcionario", f"Desempeño: {funcionario.nombre}"))

@login_required
def semaforo(request):
    """Tablero de delegación (RF-029, HU-08, HU-18, HU-21)."""
    if not tiene_rol(request.user, *ROLES_SUPERVISION):
        return denegar_acceso(request)

    periodo = _periodo_seleccionado(request)

    funcionarios = filtrar_por_ambito(
        Funcionario.objects.filter(
            estado=Funcionario.ESTADO_ACTIVO
        ).select_related("cargo", "delegacion"),
        request.user,
        "delegacion_id",
    )

    delegacion_sel = request.GET.get("delegacion", "")

    if delegacion_sel and es_transversal(request.user):
        funcionarios = funcionarios.filter(
            delegacion_id=delegacion_sel
        )

    resumen = (
        CalculoIndicadores.resumen_delegacion(funcionarios, periodo)
        if periodo
        else None
    )

    page_size = get_page_size(
        request,
        "semaforo_page_size",
    )

    page_obj = None

    if resumen:
        paginator = Paginator(resumen["filas"], page_size)
        page_obj = paginator.get_page(request.GET.get("page"))
        resumen["filas"] = page_obj.object_list

    return render(request, "measurement/semaforo.html", {
        "titulo": "Semáforo de delegación",
        "periodo": periodo,
        "periodos": Periodo.objects.all(),
        "resumen": resumen,
        "delegaciones": (
            Delegacion.objects.all()
            if es_transversal(request.user)
            else []
        ),
        "delegacion_sel": delegacion_sel,
        "hoy": timezone.localdate(),
        "page_obj": page_obj,
        "page_size": page_size,
        "page_size_options": PAGE_SIZE_OPTIONS,
    })


@login_required
def exportar_metas_excel(request):
    """Exporta metas respetando el nombre histórico del ítem en períodos cerrados."""

    if not tiene_rol(request.user, *ROLES_SUPERVISION):
        return HttpResponse("No autorizado", status=403)

    queryset = filtrar_por_ambito(
        MetaModel.objects.select_related(
            "periodo",
            "funcionario",
            "funcionario__delegacion",
            "cargo",
            "item",
        ),
        request.user,
        "funcionario__delegacion_id",
    )

    g = request.GET

    for campo, filtro in (
        ("periodo", "periodo_id"),
        ("funcionario", "funcionario_id"),
        ("cargo", "cargo_id"),
        ("item", "item_id"),
    ):
        if g.get(campo):
            queryset = queryset.filter(**{filtro: g[campo]})

    q = g.get("q", "").strip()
    if q:
        queryset = queryset.filter(
            Q(item__nombre_item__icontains=q)
            | Q(funcionario__nombre__icontains=q)
            | Q(cargo__nombre_cargo__icontains=q)
        )

    libro = Workbook()
    hoja = libro.active
    hoja.title = "Metas"

    hoja.append([
        "Período",
        "Funcionario",
        "Delegación",
        "Cargo",
        "Ítem medible",
        "Objetivo",
        "Unidad",
        "Ponderación (%)",
        "Umbral mínimo (%)",
        "Máximo computable (%)",
    ])

    for meta in queryset.order_by(
        "periodo",
        "funcionario__nombre",
        "item__nombre_item",
    ):
        if meta.periodo.abierto:
            datos_historicos = CRUDMeta._datos_version(meta)
        else:
            datos_historicos = CalculoIndicadores._datos_meta_historicos(
                meta,
                meta.periodo.fecha_termino,
            )

        nombre_item = datos_historicos.get(
            "item_nombre",
            meta.item.nombre_item,
        )

        hoja.append([
            str(meta.periodo),
            meta.funcionario.nombre,
            meta.funcionario.delegacion.nombre,
            meta.cargo.nombre_cargo,
            nombre_item,
            float(meta.valor_objetivo),
            meta.unidad,
            float(meta.ponderador),
            float(meta.umbral_minimo),
            float(meta.maximo_computable),
        ])

    respuesta = HttpResponse(
        content_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        )
    )
    respuesta["Content-Disposition"] = (
        'attachment; filename="metas_filtradas.xlsx"'
    )
    respuesta["Cache-Control"] = "private, no-store"

    libro.save(respuesta)
    return respuesta


@login_required
def exportar_periodos_excel(request):
    """Exporta todos los períodos que coinciden con los filtros."""

    if not tiene_rol(request.user, *ROLES_SUPERVISION):
        return HttpResponse("No autorizado", status=403)

    queryset = Periodo.objects.all()
    filtros = request.GET

    estado = filtros.get("estado", "").strip()
    if estado in dict(Periodo.ESTADOS):
        queryset = queryset.filter(estado=estado)

    fecha_desde = filtros.get("fecha_desde", "").strip()
    if fecha_desde:
        queryset = queryset.filter(fecha_termino__gte=fecha_desde)

    fecha_hasta = filtros.get("fecha_hasta", "").strip()
    if fecha_hasta:
        queryset = queryset.filter(fecha_inicio__lte=fecha_hasta)

    q = filtros.get("q", "").strip()
    if q:
        from datetime import datetime

        fecha_busqueda = None

        for formato in ("%d/%m/%Y", "%Y-%m-%d"):
            try:
                fecha_busqueda = datetime.strptime(q, formato).date()
                break
            except ValueError:
                continue

        if fecha_busqueda:
            queryset = queryset.filter(
                Q(fecha_inicio=fecha_busqueda)
                | Q(fecha_termino=fecha_busqueda)
            )
        else:
            queryset = queryset.none()

    libro = Workbook()
    hoja = libro.active
    hoja.title = "Períodos"

    hoja.append(["Informe de períodos de medición"])
    hoja.append([
        "Generado",
        timezone.localtime().strftime("%d/%m/%Y %H:%M"),
    ])
    hoja.append([])
    hoja.append([
        "ID",
        "Fecha de inicio",
        "Fecha de término",
        "Días computables",
        "Estado",
        "Versión de parámetros",
    ])

    for periodo in queryset.order_by("-fecha_inicio"):
        hoja.append([
            periodo.pk,
            periodo.fecha_inicio.strftime("%d/%m/%Y"),
            periodo.fecha_termino.strftime("%d/%m/%Y"),
            periodo.dias_computables,
            periodo.estado,
            periodo.version_parametros,
        ])

    respuesta = HttpResponse(
        content_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        )
    )
    respuesta["Content-Disposition"] = (
        'attachment; filename="periodos_filtrados.xlsx"'
    )
    respuesta["Cache-Control"] = "private, no-store"
    libro.save(respuesta)
    return respuesta



@login_required
def exportar_ajustes_excel(request):
    """Exporta ajustes respetando el nombre histórico del ítem asociado."""

    if not tiene_rol(request.user, *ROLES_SUPERVISION):
        return HttpResponse("No autorizado", status=403)

    queryset = filtrar_por_ambito(
        Ajuste.objects.select_related(
            "periodo",
            "funcionario",
            "funcionario__delegacion",
            "meta",
            "meta__item",
        ),
        request.user,
        "funcionario__delegacion_id",
    )

    filtros = request.GET

    periodo = filtros.get("periodo", "").strip()
    if periodo:
        queryset = queryset.filter(periodo_id=periodo)

    funcionario = filtros.get("funcionario", "").strip()
    if funcionario:
        queryset = queryset.filter(funcionario_id=funcionario)

    efecto = filtros.get("efecto", "").strip()
    if efecto in dict(Ajuste.EFECTOS):
        queryset = queryset.filter(efecto=efecto)

    q = filtros.get("q", "").strip()
    if q:
        queryset = queryset.filter(
            Q(motivo__icontains=q)
            | Q(funcionario__nombre__icontains=q)
            | Q(meta__item__nombre_item__icontains=q)
        )

    libro = Workbook()
    hoja = libro.active
    hoja.title = "Incentivos y penalizaciones"

    hoja.append(["Informe de incentivos y penalizaciones"])
    hoja.append([
        "Generado",
        timezone.localtime().strftime("%d/%m/%Y %H:%M"),
    ])
    hoja.append([])
    hoja.append([
        "ID",
        "Funcionario",
        "Delegación",
        "Período",
        "Efecto",
        "Valor",
        "Puntos con signo",
        "Motivo",
        "Ítem asociado",
    ])

    for ajuste in queryset.order_by("-id_ajuste"):
        nombre_item = ""

        if ajuste.meta_id:
            if ajuste.periodo.abierto:
                datos_historicos = CRUDMeta._datos_version(
                    ajuste.meta
                )
            else:
                datos_historicos = (
                    CalculoIndicadores._datos_meta_historicos(
                        ajuste.meta,
                        ajuste.periodo.fecha_termino,
                    )
                )

            nombre_item = datos_historicos.get(
                "item_nombre",
                ajuste.meta.item.nombre_item,
            )

        hoja.append([
            ajuste.pk,
            ajuste.funcionario.nombre,
            ajuste.funcionario.delegacion.nombre,
            str(ajuste.periodo),
            ajuste.efecto,
            float(ajuste.valor),
            float(ajuste.puntos),
            ajuste.motivo,
            nombre_item,
        ])

    respuesta = HttpResponse(
        content_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        )
    )
    respuesta["Content-Disposition"] = (
        'attachment; filename="incentivos_penalizaciones.xlsx"'
    )
    respuesta["Cache-Control"] = "private, no-store"

    libro.save(respuesta)
    return respuesta


@login_required
def exportar_semaforo_excel(request):
    """Exporta el semáforo completo de la delegación o ámbito autorizado."""

    if not tiene_rol(request.user, *ROLES_SUPERVISION):
        return HttpResponse("No autorizado", status=403)

    periodo = _periodo_seleccionado(request)

    if periodo is None:
        return HttpResponse(
            "No existe un período disponible para generar el informe.",
            status=400,
        )

    funcionarios = filtrar_por_ambito(
        Funcionario.objects.filter(
            estado=Funcionario.ESTADO_ACTIVO
        ).select_related("cargo", "delegacion"),
        request.user,
        "delegacion_id",
    )

    delegacion_sel = request.GET.get("delegacion", "")

    if delegacion_sel and es_transversal(request.user):
        funcionarios = funcionarios.filter(
            delegacion_id=delegacion_sel
        )

    resumen = CalculoIndicadores.resumen_delegacion(
        funcionarios,
        periodo,
    )

    libro = Workbook()
    hoja = libro.active
    hoja.title = "Semáforo"

    hoja.append(["Semáforo de delegación"])
    hoja.append([
        "Generado",
        timezone.localtime().strftime("%d/%m/%Y %H:%M"),
    ])
    hoja.append(["Período", str(periodo)])
    hoja.append([
        "Meta esperada al día",
        float(resumen["meta_esperada"]),
    ])
    hoja.append(["Promedio ponderado", float(resumen["promedio"])])
    hoja.append(["Resultado general", resumen["semaforo"]])
    hoja.append(["Funcionarios evaluados", resumen["total_funcionarios"]])
    hoja.append([])
    hoja.append([
        "Funcionario",
        "Delegación",
        "Cargo",
        "Resultado ponderado",
        "Ajustes",
        "Resultado total",
        "Meta esperada",
        "Semáforo",
        "Suma ponderadores",
        "Configuración completa",
        "Bajo umbral",
    ])

    for fila in resumen["filas"]:
        funcionario = fila["funcionario"]

        hoja.append([
            funcionario.nombre,
            funcionario.delegacion.nombre,
            funcionario.cargo.nombre_cargo,
            float(fila["total_ponderado"]),
            float(fila["ajustes"]),
            float(fila["resultado_total"]),
            float(fila["meta_esperada"]),
            fila["semaforo"],
            float(fila["suma_ponderadores"]),
            "Sí" if fila["completa"] else "No",
            "Sí" if fila["bajo_umbral"] else "No",
        ])

    respuesta = HttpResponse(
        content_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        )
    )
    respuesta["Content-Disposition"] = (
        'attachment; filename="semaforo_delegacion.xlsx"'
    )
    respuesta["Cache-Control"] = "private, no-store"
    libro.save(respuesta)
    return respuesta
