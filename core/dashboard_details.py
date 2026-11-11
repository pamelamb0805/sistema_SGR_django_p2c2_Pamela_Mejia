
import calendar
from datetime import date

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET

from core.mixins import (
    ROLES_SUPERVISION,
    es_transversal,
    filtrar_por_ambito,
    get_funcionario,
    tiene_rol,
)
from organizations.models import Funcionario, Delegacion
from measurement.models import Periodo, Meta
from measurement.services import CalculoIndicadores
from activities.models import Actividad, Evidencia
from activities.services import actividades_visibles
from agenda.models import Compromiso
from agenda.services import compromisos_visibles


def _fila(codigo, descripcion, responsable, delegacion, fecha, estado, url):
    return {
        "codigo": str(codigo),
        "descripcion": str(descripcion),
        "responsable": str(responsable),
        "delegacion": str(delegacion),
        "fecha": fecha.strftime("%d/%m/%Y") if fecha else "—",
        "estado": str(estado),
        "url": url,
    }


def _mes_desde_etiqueta(etiqueta):
    meses = {
        "jan": 1, "ene": 1,
        "feb": 2,
        "mar": 3,
        "apr": 4, "abr": 4,
        "may": 5,
        "jun": 6,
        "jul": 7,
        "aug": 8, "ago": 8,
        "sep": 9, "set": 9,
        "oct": 10,
        "nov": 11,
        "dec": 12, "dic": 12,
    }

    partes = etiqueta.strip().lower().replace(".", "").split()

    if len(partes) != 2:
        return None

    mes = meses.get(partes[0][:3])

    try:
        anio = int(partes[1])
        return date(anio, mes, 1) if mes else None
    except (ValueError, TypeError):
        return None


def _funcionarios_visibles(user):
    qs = Funcionario.objects.filter(
        estado=Funcionario.ESTADO_ACTIVO
    ).select_related("cargo", "delegacion")

    return filtrar_por_ambito(qs, user, "delegacion_id")


def _actividades_dashboard(user, funcionario):
    qs = Actividad.objects.select_related(
        "funcionario",
        "funcionario__delegacion",
        "item",
        "periodo",
    )

    qs = filtrar_por_ambito(
        qs, user, "funcionario__delegacion_id"
    )

    if not tiene_rol(user, *ROLES_SUPERVISION):
        qs = qs.filter(funcionario=funcionario) if funcionario else qs.none()

    return qs


def _compromisos_dashboard(user, funcionario):
    qs = Compromiso.objects.select_related(
        "funcionario", "delegacion"
    )

    qs = filtrar_por_ambito(qs, user, "delegacion_id")

    if not tiene_rol(user, *ROLES_SUPERVISION):
        qs = qs.filter(funcionario=funcionario) if funcionario else qs.none()

    return qs


def _evidencias_dashboard(user, funcionario):
    qs = Evidencia.objects.select_related(
        "actividad",
        "actividad__funcionario",
        "actividad__funcionario__delegacion",
    )

    qs = filtrar_por_ambito(
        qs, user, "actividad__funcionario__delegacion_id"
    )

    if not tiene_rol(user, *ROLES_SUPERVISION):
        qs = (
            qs.filter(actividad__funcionario=funcionario)
            if funcionario else qs.none()
        )

    return qs


def _detalle_indicador(user, etiqueta, periodo, funcionario):
    filas = []

    funcionarios = (
        [funcionario]
        if funcionario
        else list(_funcionarios_visibles(user))
    )

    for persona in funcionarios:
        resumen = CalculoIndicadores.resumen_funcionario(
            persona, periodo, timezone.localdate()
        )

        for fila in resumen.get("filas", []):
            if fila["item"].nombre_item != etiqueta:
                continue

            filas.append(_fila(
                f"META-{fila['meta'].pk}",
                fila["item"].nombre_item,
                persona.nombre,
                persona.delegacion.nombre,
                fila["meta"].fecha_version,
                f"{fila['cumplimiento']}% de cumplimiento",
                reverse(
                    "measurement:desempeno_detalle",
                    args=[persona.pk],
                ),
            ))

    return filas


def _detalle_semaforo(user, etiqueta, periodo):
    if not tiene_rol(user, *ROLES_SUPERVISION):
        return None

    filas = []

    for persona in _funcionarios_visibles(user):
        resumen = CalculoIndicadores.resumen_funcionario(
            persona, periodo, timezone.localdate()
        )

        if resumen["semaforo"] != etiqueta:
            continue

        filas.append(_fila(
            f"FUNC-{persona.pk}",
            persona.cargo.nombre_cargo,
            persona.nombre,
            persona.delegacion.nombre,
            None,
            resumen["semaforo"],
            reverse("organizations:funcionario_list"),
        ))

    return filas


def _detalle_delegacion(user, etiqueta, periodo):
    if not tiene_rol(user, *ROLES_SUPERVISION):
        return None

    delegaciones_ids = _funcionarios_visibles(user).values_list(
        "delegacion_id", flat=True
    ).distinct()

    delegacion = Delegacion.objects.filter(
        pk__in=delegaciones_ids,
        nombre=etiqueta,
    ).first()

    if not delegacion:
        return []

    filas = []

    for persona in _funcionarios_visibles(user).filter(
        delegacion=delegacion
    ):
        resumen = CalculoIndicadores.resumen_funcionario(
            persona, periodo, timezone.localdate()
        )

        filas.append(_fila(
            f"FUNC-{persona.pk}",
            persona.cargo.nombre_cargo,
            persona.nombre,
            delegacion.nombre,
            None,
            f"{resumen['total_ponderado']}% de cumplimiento",
            reverse("organizations:funcionario_list"),
        ))

    return filas


@login_required
@require_GET
def dashboard_detalle(request):
    tipo = request.GET.get("tipo", "").strip()
    etiqueta = request.GET.get("etiqueta", "").strip()

    if not tipo or not etiqueta:
        return JsonResponse(
            {"ok": False, "mensaje": "Selección incompleta."},
            status=400,
        )

    user = request.user
    funcionario = get_funcionario(user)
    hoy = timezone.localdate()
    periodo = Periodo.objects.vigente(hoy)

    filas = None

    if tipo == "personal":
        if periodo is None:
            filas = []
        else:
            filas = _detalle_indicador(
                user, etiqueta, periodo, funcionario
            )

    elif tipo == "semaforo":
        if periodo is None:
            filas = []
        else:
            filas = _detalle_semaforo(user, etiqueta, periodo)

    elif tipo == "delegaciones":
        if periodo is None:
            filas = []
        else:
            filas = _detalle_delegacion(user, etiqueta, periodo)

    elif tipo == "agenda":
        qs = _compromisos_dashboard(user, funcionario).filter(
            estado=etiqueta
        )

        filas = [
            _fila(
                f"COMP-{c.pk}",
                c.origen,
                c.funcionario.nombre,
                c.delegacion.nombre,
                c.fecha_comprometida,
                c.estado,
                reverse("agenda:compromiso_detail", args=[c.pk]),
            )
            for c in qs.order_by("-fecha_comprometida")[:100]
        ]

    elif tipo == "evolucion":
        mes = _mes_desde_etiqueta(etiqueta)

        if mes is None:
            return JsonResponse(
                {"ok": False, "mensaje": "Mes no válido."},
                status=400,
            )

        if mes.month == 12:
            siguiente = date(mes.year + 1, 1, 1)
        else:
            siguiente = date(mes.year, mes.month + 1, 1)

        qs = _actividades_dashboard(user, funcionario).filter(
            fecha__gte=mes,
            fecha__lt=siguiente,
        )

        filas = [
            _fila(
                actividad.codigo,
                actividad.accion,
                actividad.funcionario.nombre,
                actividad.funcionario.delegacion.nombre,
                actividad.fecha,
                actividad.estado,
                reverse(
                    "activities:actividad_detail",
                    args=[actividad.pk],
                ),
            )
            for actividad in qs.order_by("-fecha")[:100]
        ]

    elif tipo == "evidencias":
        qs = _evidencias_dashboard(user, funcionario).filter(
            estado_revision=etiqueta
        )

        filas = [
            _fila(
                evidencia.codigo_evidencia,
                evidencia.actividad.accion,
                evidencia.actividad.funcionario.nombre,
                evidencia.actividad.funcionario.delegacion.nombre,
                evidencia.fecha_carga.date(),
                evidencia.estado_revision,
                reverse(
                    "activities:actividad_detail",
                    args=[evidencia.actividad_id],
                ),
            )
            for evidencia in qs.order_by("-fecha_carga")[:100]
        ]

    else:
        return JsonResponse(
            {"ok": False, "mensaje": "Tipo de gráfico no válido."},
            status=400,
        )

    if filas is None:
        return JsonResponse(
            {"ok": False, "mensaje": "No tienes permiso para consultar este detalle."},
            status=403,
        )

    return JsonResponse({
        "ok": True,
        "titulo": etiqueta,
        "total": len(filas),
        "filas": filas,
    })
