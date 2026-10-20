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
from django.shortcuts import get_object_or_404, render
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
from organizations.models import Cargo, Delegacion, Funcionario

from .forms import AjusteForm, MetaForm, PeriodoForm, ReabrirPeriodoForm
from .models import Ajuste, Meta as MetaModel, Periodo
from .services import CalculoIndicadores, CRUDAjuste, CRUDMeta, CRUDPeriodo


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
class PeriodoListView(LecturaMixin, ModoMixin, ListView):
    model = Periodo
    template_name = "measurement/periodo_.html"
    context_object_name = "periodos"
    paginate_by = 10
    titulo = "Períodos de medición"
    roles_edicion = ROLES_MEDICION

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["puede_reabrir"] = tiene_rol(self.request.user, *ROLES_CONFIGURACION)
        contexto["reabrir_form"] = ReabrirPeriodoForm()
        return contexto


class PeriodoDetailView(LecturaMixin, ModoMixin, DetailView):
    """Resumen del período y estado de la configuración (RN-001) de cada funcionario."""
    model = Periodo
    template_name = "measurement/periodo_.html"
    context_object_name = "periodo"
    modo = "detalle"
    roles_edicion = ROLES_MEDICION

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        funcionarios = filtrar_por_ambito(
            Funcionario.objects.filter(estado=Funcionario.ESTADO_ACTIVO).select_related("cargo", "delegacion"),
            self.request.user, "delegacion_id")
        configuracion = []
        for f in funcionarios:
            suma = CRUDMeta.suma_ponderaciones(f, self.object)
            configuracion.append({"funcionario": f, "suma": suma, "completa": suma == 100,
                                  "metas": f.metas.filter(periodo=self.object).count()})
        contexto.update(
            titulo=f"Período {self.object}", configuracion=configuracion,
            total_metas=self.object.metas.count(),
            puede_reabrir=tiene_rol(self.request.user, *ROLES_CONFIGURACION),
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


class PeriodoRecalcularView(AccionPostView):
    roles_permitidos = ROLES_MEDICION
    redirect_name = "measurement:periodo_list"

    def get_objeto(self, pk):
        return get_object_or_404(Periodo, pk=pk)

    def accion(self, request, objeto):
        if not objeto.abierto:
            raise ReglaNegocioError("El período está cerrado: sus resultados no se recalculan.")
        cantidad = CalculoIndicadores.recalcular_periodo(objeto)
        return f"Se recalcularon {cantidad} indicadores."

    def get_redirect(self, objeto):
        return reverse("measurement:periodo_detail", args=[objeto.pk])


# ---------------------------------------------------------------------------
# Metas
# ---------------------------------------------------------------------------
class MetaListView(LecturaMixin, AmbitoDelegacionMixin, ModoMixin, ListView):
    model = MetaModel
    template_name = "measurement/meta_.html"
    context_object_name = "metas"
    ambito_campo = "funcionario__delegacion_id"
    paginate_by = 15
    titulo = "Metas y ponderaciones"
    roles_edicion = ROLES_MEDICION

    def get_queryset(self):
        qs = super().get_queryset().select_related("periodo", "funcionario", "item", "cargo")
        g = self.request.GET
        for campo, filtro in (("periodo", "periodo_id"), ("funcionario", "funcionario_id"),
                              ("cargo", "cargo_id"), ("item", "item_id")):
            if g.get(campo):
                qs = qs.filter(**{filtro: g[campo]})
        return qs

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        g = self.request.GET
        contexto.update(
            periodos=Periodo.objects.all(), cargos=Cargo.objects.all(),
            funcionarios=filtrar_por_ambito(Funcionario.objects.all(), self.request.user, "delegacion_id"),
            periodo_sel=g.get("periodo", ""), funcionario_sel=g.get("funcionario", ""),
            cargo_sel=g.get("cargo", ""),
        )
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
# Ajustes (incentivos y penalizaciones)
# ---------------------------------------------------------------------------
class AjusteListView(LecturaMixin, AmbitoDelegacionMixin, ModoMixin, ListView):
    model = Ajuste
    template_name = "measurement/ajuste_.html"
    context_object_name = "ajustes"
    ambito_campo = "funcionario__delegacion_id"
    paginate_by = 15
    titulo = "Incentivos y penalizaciones"
    roles_edicion = ROLES_MEDICION

    def get_queryset(self):
        qs = super().get_queryset().select_related("periodo", "funcionario", "meta")
        periodo = self.request.GET.get("periodo")
        return qs.filter(periodo_id=periodo) if periodo else qs

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.update(periodos=Periodo.objects.all(), periodo_sel=self.request.GET.get("periodo", ""))
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
        Funcionario.objects.filter(estado=Funcionario.ESTADO_ACTIVO).select_related("cargo", "delegacion"),
        request.user, "delegacion_id")
    delegacion_sel = request.GET.get("delegacion", "")
    if delegacion_sel and es_transversal(request.user):
        funcionarios = funcionarios.filter(delegacion_id=delegacion_sel)
    resumen = CalculoIndicadores.resumen_delegacion(funcionarios, periodo) if periodo else None
    return render(request, "measurement/semaforo.html", {
        "titulo": "Semáforo de delegación", "periodo": periodo, "periodos": Periodo.objects.all(),
        "resumen": resumen, "delegaciones": Delegacion.objects.all() if es_transversal(request.user) else [],
        "delegacion_sel": delegacion_sel, "hoy": timezone.localdate(),
    })
