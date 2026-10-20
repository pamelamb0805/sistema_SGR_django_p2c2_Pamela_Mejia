"""Login, logout y dashboard del SGR."""
from datetime import timedelta

from django.apps import apps
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.db.models import Count
from django.shortcuts import render
from django.utils import timezone

from .mixins import (
    ROL_VERIFICADOR,
    ROLES_SUPERVISION,
    es_transversal,
    filtrar_por_ambito,
    get_funcionario,
    registrar_auditoria,
    tiene_rol,
)


class SGRLoginView(LoginView):
    template_name = "registration/login.html"
    redirect_authenticated_user = True

    def form_valid(self, form):
        response = super().form_valid(form)
        funcionario = get_funcionario(self.request.user)
        nombre = funcionario.nombre if funcionario else self.request.user.get_username()
        messages.success(self.request, f"Bienvenido/a, {nombre}.")
        registrar_auditoria(self.request, evento="LOGIN", entidad="usuario",
                            id_entidad=self.request.user.pk)
        return response

    def form_invalid(self, form):
        messages.error(self.request, "Usuario o contraseña incorrectos, o usuario inactivo.")
        return super().form_invalid(form)


def _modelo(app_label, nombre):
    """Devuelve el modelo o None si esa app aún no está instalada (desarrollo por etapas)."""
    try:
        return apps.get_model(app_label, nombre)
    except LookupError:
        return None


@login_required
def dashboard(request):
    """
    Panel inicial. Los datos se limitan al ámbito del usuario (delegación).
    Cada bloque es None si su app aún no existe; la plantilla lo omite.

    Contexto para templates/core/dashboard.html:
      datos["resumen_personal"]  semáforo y avance del funcionario en el período vigente (HU-06, HU-16)
      datos["resumen_equipo"]    consolidado de la delegación para supervisores (HU-08, HU-18)
      datos[...]                 contadores de actividades, evidencias y compromisos
    Un usuario sin funcionario asociado (p. ej. el superusuario técnico) ve el panel con un aviso,
    no un error 403.
    """
    user = request.user
    funcionario = get_funcionario(user)
    hoy = timezone.localdate()
    limite = hoy + timedelta(days=settings.SGR_DIAS_ALERTA_VENCIMIENTO)

    Funcionario = _modelo("organizations", "Funcionario")
    Delegacion = _modelo("organizations", "Delegacion")
    Actividad = _modelo("activities", "Actividad")
    Evidencia = _modelo("activities", "Evidencia")
    Compromiso = _modelo("agenda", "Compromiso")

    datos = {
        "total_delegaciones": None,
        "total_funcionarios": None,
        "mis_actividades": None,
        "evidencias_pendientes": None,
        "compromisos_por_estado": None,
        "compromisos_vencidos": None,
        "compromisos_por_vencer": None,
        "lista_vencidos": None,
        "es_verificador": tiene_rol(user, ROL_VERIFICADOR),
    }

    if Delegacion is not None and es_transversal(user):
        datos["total_delegaciones"] = Delegacion.objects.count()

    if Funcionario is not None:
        datos["total_funcionarios"] = filtrar_por_ambito(
            Funcionario.objects.all(), user, "delegacion_id").count()

    if Actividad is not None and funcionario is not None:
        datos["mis_actividades"] = Actividad.objects.filter(funcionario=funcionario).count()

    if Evidencia is not None:
        datos["evidencias_pendientes"] = filtrar_por_ambito(
            Evidencia.objects.filter(estado_revision="Pendiente"),
            user, "actividad__funcionario__delegacion_id").count()

    if Compromiso is not None:
        base = filtrar_por_ambito(Compromiso.objects.all(), user, "delegacion_id")
        abiertos = base.exclude(estado="Realizado")
        datos["compromisos_por_estado"] = {
            fila["estado"]: fila["total"]
            for fila in base.values("estado").annotate(total=Count("pk"))
        }
        vencidos = abiertos.filter(fecha_comprometida__lt=hoy)
        datos["compromisos_vencidos"] = vencidos.count()
        datos["compromisos_por_vencer"] = abiertos.filter(
            fecha_comprometida__gte=hoy,
            fecha_comprometida__lte=limite).count()
        datos["lista_vencidos"] = vencidos.select_related(
            "funcionario", "delegacion").order_by("fecha_comprometida")[:5]

    # --- Medición: semáforo personal y consolidado del equipo (si existe measurement) -----------
    datos.update({"periodo": None, "resumen_personal": None, "resumen_equipo": None})
    Periodo = _modelo("measurement", "Periodo")
    if Periodo is not None:
        from measurement.services import CalculoIndicadores

        periodo = Periodo.objects.vigente(hoy)
        datos["periodo"] = periodo
        if periodo is not None:
            if funcionario is not None:
                datos["resumen_personal"] = CalculoIndicadores.resumen_funcionario(funcionario, periodo, hoy)
            if tiene_rol(user, *ROLES_SUPERVISION) and Funcionario is not None:
                equipo = filtrar_por_ambito(
                    Funcionario.objects.filter(estado="Activo").select_related("cargo", "delegacion"),
                    user, "delegacion_id")
                datos["resumen_equipo"] = CalculoIndicadores.resumen_delegacion(equipo, periodo, hoy)

    return render(request, "core/dashboard.html", {
        "datos": datos, "hoy": hoy, "sin_funcionario": funcionario is None,
    })
