"""
Vistas de audit. Plantilla única: templates/audit/auditoria_.html (variable `modo`):
  lista | historial (eventos de una entidad) | detalle (valor anterior vs. nuevo)

Solo Administrador y Coordinador consultan la auditoría; nadie puede modificarla ni eliminarla
(las vistas son de solo lectura).
"""
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.generic import DetailView, ListView, View

from core.mixins import ModoMixin, RolRequeridoMixin, get_funcionario

from .forms import AuditoriaFiltroForm
from .models import Auditoria
from .services import (
    ROLES_AUDITORIA, comparar_valores, escribir_csv, filtrar_auditoria,
)


class AuditoriaMixin(RolRequeridoMixin):
    roles_permitidos = ROLES_AUDITORIA


class FiltrosMixin:
    """Valida los filtros del GET y arma el queryset; los filtros inválidos se ignoran con aviso en el formulario."""
    fijos = {}            # filtros impuestos por la URL (p. ej. entidad e id en el historial)

    def filtrar(self):
        self.filtro_form = AuditoriaFiltroForm(self.request.GET or None)
        datos = dict(self.filtro_form.cleaned_data) if self.filtro_form.is_valid() else {}
        datos.update(self.fijos)
        qs, self.filtros_aplicados = filtrar_auditoria(Auditoria.objects.select_related("funcionario"), datos)
        return qs


class AuditoriaListView(AuditoriaMixin, FiltrosMixin, ModoMixin, ListView):
    template_name = "audit/auditoria_.html"
    context_object_name = "eventos"
    paginate_by = 25
    titulo = "Auditoría de cambios"
    modo = "lista"
    roles_edicion = ()

    def get_queryset(self):
        return self.filtrar()

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.update(filtro_form=self.filtro_form, filtros_aplicados=self.filtros_aplicados)
        return contexto


class HistorialEntidadView(AuditoriaListView):
    """Historial completo de un registro: /audit/historial/<entidad>/<id>/ (HU-30, CA-09)."""
    modo = "historial"

    def dispatch(self, request, *args, **kwargs):
        self.fijos = {"entidad": kwargs["entidad"], "id_entidad": kwargs["pk"]}
        self.titulo = f"Historial de {kwargs['entidad']} N° {kwargs['pk']}"
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.update(entidad=self.kwargs["entidad"], id_entidad=self.kwargs["pk"])
        return contexto


class AuditoriaDetailView(AuditoriaMixin, ModoMixin, DetailView):
    template_name = "audit/auditoria_.html"
    context_object_name = "evento"
    model = Auditoria
    modo = "detalle"
    roles_edicion = ()

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        e = self.object
        contexto.update(titulo=f"Evento {e.pk}: {e.evento}", diferencias=comparar_valores(e.valor_anterior, e.valor_nuevo))
        return contexto


class AuditoriaExportarView(AuditoriaMixin, FiltrosMixin, View):
    """CSV con los mismos filtros de la pantalla, fecha de generación y encabezados legibles (RF-033)."""
    http_method_names = ["get"]

    def get(self, request):
        qs = self.filtrar()
        funcionario = get_funcionario(request.user)
        respuesta = HttpResponse(content_type="text/csv; charset=utf-8")
        respuesta["Content-Disposition"] = f'attachment; filename="auditoria_{timezone.localtime():%Y%m%d_%H%M}.csv"'
        respuesta["Cache-Control"] = "private, no-store"
        escribir_csv(respuesta, qs, self.filtros_aplicados,
                     generado_por=funcionario.nombre if funcionario else request.user.get_username())
        return respuesta
