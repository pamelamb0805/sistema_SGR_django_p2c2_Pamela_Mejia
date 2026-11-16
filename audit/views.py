"""
Vistas de audit. Plantilla única: templates/audit/auditoria_.html (variable `modo`):
  lista | historial (eventos de una entidad) | detalle (valor anterior vs. nuevo)

Solo Administrador y Coordinador consultan la auditoría; nadie puede modificarla ni eliminarla
(las vistas son de solo lectura).
"""
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.generic import DetailView, ListView, View

from core.mixins import ModoMixin, RolRequeridoMixin, get_funcionario

from .forms import AuditoriaFiltroForm
from .models import Auditoria
from .services import (
    ROLES_AUDITORIA, comparar_valores, escribir_csv, filtrar_auditoria,
)

from openpyxl import Workbook
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.http import require_GET
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import Auditoria, Notificacion
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.urls import reverse
from django.contrib.contenttypes.models import ContentType

from .forms import ComentarioRegistroForm
from .collaboration import (
    obtener_registro_comentable,
    obtener_conversacion,
    crear_comentario,
)
from .models import ComentarioRegistro

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
    """Exporta el informe de auditoría en Excel (RF-033, RF-036)."""

    http_method_names = ["get"]

    def get(self, request):
        queryset = self.filtrar()
        funcionario = get_funcionario(request.user)

        libro = Workbook()
        hoja = libro.active
        hoja.title = "Auditoría"

        def celda_segura(valor):
            texto = "" if valor is None else str(valor)

            if texto[:1] in ("=", "+", "-", "@", "\t", "\r"):
                return "'" + texto

            return texto

        hoja.append(["Informe de auditoría del SGR"])
        hoja.append([
            "Generado",
            timezone.localtime().strftime("%d/%m/%Y %H:%M:%S"),
        ])
        hoja.append([
            "Generado por",
            celda_segura(
                funcionario.nombre
                if funcionario
                else request.user.get_username()
            ),
        ])
        hoja.append([
            "Filtros aplicados",
            celda_segura(
                "; ".join(self.filtros_aplicados)
                or "Sin filtros"
            ),
        ])
        hoja.append([])

        hoja.append([
            "ID",
            "Fecha y hora",
            "Usuario responsable",
            "Evento",
            "Entidad afectada",
            "ID de entidad",
            "Valor anterior",
            "Valor nuevo",
        ])

        for evento in queryset.select_related(
            "funcionario"
        ).iterator():

            hoja.append([
                evento.pk,
                timezone.localtime(
                    evento.fecha
                ).strftime("%d/%m/%Y %H:%M:%S"),
                celda_segura(
                    evento.funcionario.nombre
                    if evento.funcionario
                    else "Sistema / técnico"
                ),
                celda_segura(evento.evento),
                celda_segura(evento.entidad_afectada),
                evento.id_entidad_afectada,
                celda_segura(evento.valor_anterior),
                celda_segura(evento.valor_nuevo),
            ])

        respuesta = HttpResponse(
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            )
        )

        respuesta["Content-Disposition"] = (
            f'attachment; filename="auditoria_'
            f'{timezone.localtime():%Y%m%d_%H%M}.xlsx"'
        )

        respuesta["Cache-Control"] = "private, no-store"

        libro.save(respuesta)
        return respuesta

@login_required
@require_POST
def marcar_notificaciones_leidas(request):
    """
    Marca como leídas solamente las notificaciones
    pertenecientes al usuario autenticado.
    """
    from .models import Notificacion

    actualizadas = Notificacion.objects.filter(
        usuario=request.user,
        leida=False,
    ).update(
        leida=True,
        fecha_lectura=timezone.now(),
    )

    pendientes = Notificacion.objects.filter(
        usuario=request.user,
        leida=False,
    ).count()

    return JsonResponse({
        "ok": True,
        "actualizadas": actualizadas,
        "pendientes": pendientes,
    })

@login_required
@require_GET
def obtener_notificaciones(request):
    """
    Devuelve las últimas 15 notificaciones persistentes
    del usuario autenticado.
    """
    from .models import Notificacion

    queryset = Notificacion.objects.filter(
        usuario=request.user,
    ).select_related(
        "auditoria",
        "auditoria__funcionario",
        "delegacion",
    ).order_by(
        "-fecha_creacion",
        "-id_notificacion",
    )

    pendientes = queryset.filter(
        leida=False
    ).count()

    resultado = []

    for notificacion in queryset[:15]:
        auditoria = notificacion.auditoria
        entidad = auditoria.entidad_afectada or ""

        nombres_modulos = {
            "actividad": "Actividades",
            "compromiso": "Agenda colectiva",
            "funcionario": "Funcionarios",
            "delegacion": "Delegaciones",
            "caso": "Atención social",
            "atencion_social": "Atención social",
            "gestion": "Atención social",
            "meta": "Metas",
            "periodo": "Períodos",
            "evidencia": "Evidencias",
            "validacion": "Validación de evidencias",
            "ajuste": "Incentivos y penalizaciones",
            "indicador": "Indicadores",
            "rol": "Roles",
            "cargo": "Cargos",
            "catalogo": "Catálogos",
            "item_medible": "Ítems medibles",
        }

        acciones = {
            "CREAR": "Creó",
            "MODIFICAR": "Modificó",
            "ELIMINAR": "Eliminó",
        }

        funcionario = auditoria.funcionario

        resultado.append({
            "id": notificacion.id_notificacion,
            "leida": notificacion.leida,
            "modulo": nombres_modulos.get(
                entidad.lower(),
                entidad.replace("_", " ").capitalize(),
            ),
            "accion": acciones.get(
                auditoria.evento,
                auditoria.evento,
            ),
            "objeto": (
                f"{entidad.replace('_', ' ').capitalize()} "
                f"#{auditoria.id_entidad_afectada}"
            ),
            "actor": (
                funcionario.nombre
                if funcionario
                else "Sistema / técnico"
            ),
            "delegacion": (
                notificacion.delegacion.nombre
                if notificacion.delegacion_id
                else "General"
            ),
            "fecha": notificacion.fecha_creacion.isoformat(),
        })

    return JsonResponse({
        "ok": True,
        "pendientes": pendientes,
        "notificaciones": resultado,
    })

class NotificacionHistorialView(LoginRequiredMixin, ListView):
    """
    Historial permanente de notificaciones del usuario autenticado.

    Incluye notificaciones leídas y pendientes.
    No modifica ni elimina registros.
    """

    model = Notificacion
    template_name = "audit/notificaciones.html"
    context_object_name = "notificaciones"
    paginate_by = 25

    def get_queryset(self):
        return (
            Notificacion.objects
            .filter(usuario=self.request.user)
            .select_related(
                "auditoria",
                "auditoria__funcionario",
                "delegacion",
            )
            .order_by(
                "-fecha_creacion",
                "-id_notificacion",
            )
        )

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)

        queryset = self.get_queryset()

        contexto["total_notificaciones"] = queryset.count()
        contexto["total_pendientes"] = queryset.filter(
            leida=False
        ).count()

        return contexto


@login_required
def comentarios_registro(request, app_label, model_name, pk):
    """
    Muestra y permite responder la conversación de un registro.

    Comprueba la autenticación, el rol y el ámbito territorial
    antes de mostrar o guardar comentarios.
    """

    try:
        registro, delegacion_id = obtener_registro_comentable(
            request.user,
            app_label,
            model_name,
            pk,
        )

    except PermissionDenied as exc:
        messages.error(request, str(exc))
        return redirect("dashboard")

    conversacion = obtener_conversacion(
        registro,
        delegacion_id,
    )

    if request.method == "POST":
        form = ComentarioRegistroForm(request.POST)

        if form.is_valid():
            respuesta_a = None
            respuesta_id = form.cleaned_data.get("respuesta_a")

            if respuesta_id:
                respuesta_a = conversacion.filter(
                    pk=respuesta_id
                ).first()

                if respuesta_a is None:
                    form.add_error(
                        "respuesta_a",
                        "La respuesta seleccionada no pertenece "
                        "a esta conversación.",
                    )

            if not form.errors:
                try:
                    crear_comentario(
                        registro=registro,
                        delegacion_id=delegacion_id,
                        usuario=request.user,
                        mensaje=form.cleaned_data["mensaje"],
                        respuesta_a=respuesta_a,
                    )

                    messages.success(
                        request,
                        "Comentario publicado correctamente.",
                    )

                    return redirect(
                        "audit:comentarios_registro",
                        app_label=app_label,
                        model_name=model_name,
                        pk=pk,
                    )

                except Exception:
                    messages.error(
                        request,
                        "No fue posible publicar el comentario. "
                        "Intente nuevamente.",
                    )

    else:
        respuesta_inicial = request.GET.get("responder", "")

        if respuesta_inicial.isdigit():
            respuesta_inicial = int(respuesta_inicial)

            if not conversacion.filter(
                pk=respuesta_inicial
            ).exists():
                respuesta_inicial = ""
        else:
            respuesta_inicial = ""

        form = ComentarioRegistroForm(
            initial={
                "respuesta_a": respuesta_inicial,
            }
        )

    tipo = ContentType.objects.get_for_model(
        registro,
        for_concrete_model=False,
    )

    contexto = {
        "titulo": f"Conversación · {registro}",
        "registro": registro,
        "comentarios": conversacion,
        "form": form,
        "tipo_registro": tipo.model,
        "app_label": app_label,
        "model_name": model_name,
    }

    return render(
        request,
        "audit/comentarios_registro.html",
        contexto,
    )