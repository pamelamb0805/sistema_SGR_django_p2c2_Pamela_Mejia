"""
Vistas de agenda. Plantillas (templates/agenda/):
  compromiso_.html  modo: lista | form | detalle | resumen
  historial.html    línea de tiempo de transiciones de un compromiso

Permisos: la agenda es colectiva, por lo que todo el equipo de una delegación la consulta;
registrar -> Funcionario y Delegado; cambiar estado/editar -> el responsable o la supervisión;
reasignar -> Delegado (su delegación), Coordinador y Administrador.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from activities.services import actividades_visibles
from core.exceptions import ReglaNegocioError
from core.mixins import (
    ROLES_OPERATIVOS, AccionPostView, GuardarMixin, ModoMixin, RolRequeridoMixin, es_transversal,
)
from measurement.models import Periodo
from organizations.models import Delegacion, Funcionario

from .forms import CompromisoForm, EstadoForm, ReasignarForm
from .models import Compromiso
from .services import (
    CRUDCompromiso, CRUDHistorialTransiciones, supervisa, compromisos_visibles, puede_gestionar,
)


def _filtrar(qs, g):
    """Filtros de la agenda (HU-12, RF-032): responsable, estado, territorio, fechas, período, plazo."""
    for campo, filtro in (("funcionario", "funcionario_id"), ("estado", "estado"), ("periodo", "periodo_id"),
                          ("delegacion", "delegacion_id"), ("fecha_desde", "fecha_comprometida__gte"),
                          ("fecha_hasta", "fecha_comprometida__lte")):
        if g.get(campo):
            qs = qs.filter(**{filtro: g[campo]})
    if g.get("territorio", "").strip():
        qs = qs.filter(territorio__icontains=g["territorio"].strip())
    if g.get("q", "").strip():
        q = g["q"].strip()
        qs = qs.filter(solicitante__icontains=q) | qs.filter(origen__icontains=q)
    plazo = g.get("plazo")
    if plazo == "vencido":
        qs = qs.vencidos()
    elif plazo == "por_vencer":
        qs = qs.por_vencer()
    elif plazo == "abiertos":
        qs = qs.abiertos()
    return qs


class OperativoMixin(RolRequeridoMixin):
    roles_permitidos = ROLES_OPERATIVOS


class CompromisoListView(RolRequeridoMixin, ModoMixin, ListView):
    """Agenda colectiva ordenada por fecha comprometida (el agrupado por fecha se hace en la plantilla)."""
    template_name = "agenda/compromiso_.html"
    context_object_name = "compromisos"
    paginate_by = 20
    titulo = "Agenda colectiva"
    roles_edicion = ROLES_OPERATIVOS

    def get_queryset(self):
        qs = compromisos_visibles(self.request.user).prefetch_related("historial")
        return _filtrar(qs, self.request.GET)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        g = self.request.GET
        visibles = compromisos_visibles(self.request.user)
        contexto.update(
            filtros=g, estados=Compromiso.ESTADOS, periodos=Periodo.objects.all(),
            funcionarios=Funcionario.objects.filter(pk__in=visibles.values("funcionario_id")),
            delegaciones=Delegacion.objects.all() if es_transversal(self.request.user) else [],
            plazos=CRUDCompromiso.controlar_plazos(queryset=self.object_list),
            hoy=timezone.localdate(),
        )
        return contexto


class CompromisoDetailView(RolRequeridoMixin, ModoMixin, DetailView):
    template_name = "agenda/compromiso_.html"
    context_object_name = "compromiso"
    modo = "detalle"

    def get_queryset(self):
        return compromisos_visibles(self.request.user).prefetch_related("historial")

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        c, user = self.object, self.request.user
        gestiona = puede_gestionar(user, c)
        es_supervisor = supervisa(user, c.delegacion_id)
        puede_cambiar = gestiona and (not c.realizado or es_supervisor)
        contexto.update(
            titulo=f"Compromiso {c.pk}", puede_gestionar=gestiona, puedesupervisar=supervisa,
            puede_editar=gestiona and not c.realizado,
            estado_form=EstadoForm(compromiso=c) if puede_cambiar else None,
            reasignar_form=ReasignarForm(usuario=user, compromiso=c) if es_supervisor and not c.realizado else None,
            historial=CRUDHistorialTransiciones.mostrar_historial_por_compromiso(c.pk),
        )
        return contexto


class _FormularioCompromisoMixin(ModoMixin, GuardarMixin):
    model = Compromiso
    form_class = CompromisoForm
    template_name = "agenda/compromiso_.html"
    modo = "form"
    roles_edicion = ROLES_OPERATIVOS

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["usuario"] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["origenes"] = CompromisoForm.ORIGENES
        return contexto

    def get_success_url(self):
        return reverse("agenda:compromiso_detail", args=[self.object.pk])


class CompromisoCreateView(OperativoMixin, _FormularioCompromisoMixin, CreateView):
    titulo = "Nuevo compromiso"
    mensaje_exito = "Compromiso registrado en la agenda colectiva."

    def get_initial(self):
        """Si viene desde una actividad (?actividad=<id>) se precargan origen y solicitante."""
        inicial = super().get_initial()
        pk = self.request.GET.get("actividad")
        if pk and pk.isdigit():
            actividad = actividades_visibles(self.request.user).filter(pk=pk).first()
            if actividad:
                self.actividad_origen = actividad
                inicial.update(origen=f"Actividad {actividad.codigo}", solicitante=actividad.contacto)
        return inicial

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["actividad_origen"] = getattr(self, "actividad_origen", None)
        return contexto

    def guardar(self, form):
        self.object = CRUDCompromiso.crear_compromiso(form.instance, self.request.user)


class CompromisoUpdateView(OperativoMixin, _FormularioCompromisoMixin, UpdateView):
    titulo = "Editar compromiso"
    mensaje_exito = "Compromiso actualizado."

    def get_queryset(self):
        return compromisos_visibles(self.request.user)

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object.realizado or not puede_gestionar(request.user, self.object):
            messages.error(request, "Este compromiso no puede editarse (está realizado o no es de su responsabilidad).")
            return redirect("agenda:compromiso_detail", pk=self.object.pk)
        return super().get(request, *args, **kwargs)

    def guardar(self, form):
        self.object = CRUDCompromiso.modificar_compromiso(form.instance, self.request.user)


class CompromisoEstadoView(AccionPostView):
    roles_permitidos = ()      # la autorización fina se valida en el servicio

    def get_objeto(self, pk):
        return get_object_or_404(compromisos_visibles(self.request.user), pk=pk)

    def accion(self, request, objeto):
        form = EstadoForm(request.POST, compromiso=objeto)
        if not form.is_valid():
            raise ReglaNegocioError("Seleccione un estado permitido para este compromiso.")
        CRUDCompromiso.actualizar_estado(objeto, form.cleaned_data["estado"],
                                         form.cleaned_data["observacion"], request.user)
        return f"Estado actualizado a «{form.cleaned_data['estado']}»."

    def get_redirect(self, objeto):
        return reverse("agenda:compromiso_detail", args=[objeto.pk])


class CompromisoReasignarView(AccionPostView):
    roles_permitidos = ()

    def get_objeto(self, pk):
        return get_object_or_404(compromisos_visibles(self.request.user), pk=pk)

    def accion(self, request, objeto):
        form = ReasignarForm(request.POST, usuario=request.user, compromiso=objeto)
        if not form.is_valid():
            raise ReglaNegocioError("Seleccione al nuevo responsable e indique el motivo.")
        CRUDCompromiso.reasignar_responsable(objeto, form.cleaned_data["funcionario"],
                                             form.cleaned_data["motivo"], request.user)
        return f"Compromiso reasignado a {form.cleaned_data['funcionario'].nombre}."

    def get_redirect(self, objeto):
        return reverse("agenda:compromiso_detail", args=[objeto.pk])


class CompromisoHistorialView(RolRequeridoMixin, DetailView):
    template_name = "agenda/historial.html"
    context_object_name = "compromiso"

    def get_queryset(self):
        return compromisos_visibles(self.request.user)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.update(titulo=f"Historial del compromiso {self.object.pk}",
                        historial=CRUDHistorialTransiciones.mostrar_historial_por_compromiso(self.object.pk))
        return contexto


@login_required
def resumen_colectivo(request):
    """Resumen colectivo y control de plazos (RF-019, RF-021, HU-14, HU-18)."""
    g = request.GET
    visibles = compromisos_visibles(request.user)
    periodo = None
    if g.get("periodo", "").isdigit():
        periodo = Periodo.objects.filter(pk=g["periodo"]).first()
    elif "periodo" not in g:
        periodo = Periodo.objects.vigente()
    filtros = g.copy()
    if periodo:
        filtros["periodo"] = str(periodo.pk)
    qs = _filtrar(visibles.prefetch_related("historial"), filtros)
    return render(request, "agenda/compromiso_.html", {
        "modo": "resumen", "titulo": "Resumen de la agenda colectiva", "periodo": periodo,
        "filtros": g, "periodos": Periodo.objects.all(),
        "delegaciones": Delegacion.objects.all() if es_transversal(request.user) else [],
        "resumen": CRUDCompromiso.resumen_colectivo(qs),
        "plazos": CRUDCompromiso.controlar_plazos(queryset=qs), "hoy": timezone.localdate(),
    })
