
from datetime import date

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET

from core.mixins import (
    ROLES_SUPERVISION,
    filtrar_por_ambito,
    get_funcionario,
    tiene_rol,
)
from organizations.models import Funcionario, Delegacion
from measurement.models import Periodo
from measurement.services import CalculoIndicadores
from activities.models import Actividad, Evidencia
from agenda.models import Compromiso


def _fila(codigo, descripcion, responsable, delegacion, fecha, estado, url):
    """
    Normaliza los datos de cada fila que se entrega al modal del dashboard.

    El campo registro reúne el código y la descripción para que el
    frontend pueda mostrar una identificación legible del registro.
    """

    codigo_texto = str(codigo).strip() if codigo is not None else ""
    descripcion_texto = (
        str(descripcion).strip()
        if descripcion is not None
        else ""
    )

    registro = " · ".join(
        parte
        for parte in (codigo_texto, descripcion_texto)
        if parte
    )

    return {
        "codigo": codigo_texto or "—",
        "descripcion": descripcion_texto or "—",
        "registro": registro or "—",
        "responsable": (
            str(responsable).strip()
            if responsable is not None
            else "—"
        ),
        "delegacion": (
            str(delegacion).strip()
            if delegacion is not None
            else "—"
        ),
        "fecha": fecha.strftime("%d/%m/%Y") if fecha else "—",
        "estado": str(estado).strip() if estado is not None else "—",
        "url": url,
    }


def _mes_desde_etiqueta(etiqueta):
    """
    Convierte etiquetas como 'Nov 2026' o 'Ene 2026' en una fecha.
    Acepta abreviaturas en español e inglés.
    """

    meses = {
        "jan": 1,
        "ene": 1,
        "feb": 2,
        "mar": 3,
        "apr": 4,
        "abr": 4,
        "may": 5,
        "jun": 6,
        "jul": 7,
        "aug": 8,
        "ago": 8,
        "sep": 9,
        "set": 9,
        "oct": 10,
        "nov": 11,
        "dec": 12,
        "dic": 12,
    }

    partes = (
        etiqueta.strip()
        .lower()
        .replace(".", "")
        .split()
    )

    if len(partes) != 2:
        return None

    mes = meses.get(partes[0][:3])

    try:
        anio = int(partes[1])
        return date(anio, mes, 1) if mes else None
    except (ValueError, TypeError):
        return None


def _funcionarios_visibles(user):
    """
    Funcionarios activos dentro del ámbito territorial autorizado.
    """

    qs = Funcionario.objects.filter(
        estado=Funcionario.ESTADO_ACTIVO
    ).select_related(
        "cargo",
        "delegacion",
    )

    return filtrar_por_ambito(
        qs,
        user,
        "delegacion_id",
    )


def _actividades_dashboard(user, funcionario):
    """
    Actividades visibles para el usuario, respetando su ámbito y rol.
    """

    qs = Actividad.objects.select_related(
        "funcionario",
        "funcionario__delegacion",
        "item",
        "periodo",
    )

    qs = filtrar_por_ambito(
        qs,
        user,
        "funcionario__delegacion_id",
    )

    if not tiene_rol(user, *ROLES_SUPERVISION):
        qs = (
            qs.filter(funcionario=funcionario)
            if funcionario
            else qs.none()
        )

    return qs


def _compromisos_dashboard(user, funcionario):
    """
    Compromisos visibles para el usuario, respetando su ámbito y rol.
    """

    qs = Compromiso.objects.select_related(
        "funcionario",
        "delegacion",
        "item_medible",
    )

    qs = filtrar_por_ambito(
        qs,
        user,
        "delegacion_id",
    )

    if not tiene_rol(user, *ROLES_SUPERVISION):
        qs = (
            qs.filter(funcionario=funcionario)
            if funcionario
            else qs.none()
        )

    return qs


def _evidencias_dashboard(user, funcionario):
    """
    Evidencias visibles para el usuario, respetando el ámbito
    territorial de la actividad asociada.
    """

    qs = Evidencia.objects.select_related(
        "actividad",
        "actividad__funcionario",
        "actividad__funcionario__delegacion",
    )

    qs = filtrar_por_ambito(
        qs,
        user,
        "actividad__funcionario__delegacion_id",
    )

    if not tiene_rol(user, *ROLES_SUPERVISION):
        qs = (
            qs.filter(actividad__funcionario=funcionario)
            if funcionario
            else qs.none()
        )

    return qs


def _detalle_indicador(user, etiqueta, periodo, funcionario):
    """
    Registros que componen el cumplimiento de un indicador.

    Si el usuario tiene un funcionario asociado, consulta su propio
    desempeño. Si es un administrador sin funcionario asociado,
    consulta los funcionarios activos de su ámbito autorizado.
    """

    filas = []

    funcionarios = (
        [funcionario]
        if funcionario
        else list(_funcionarios_visibles(user))
    )

    for persona in funcionarios:
        resumen = CalculoIndicadores.resumen_funcionario(
            persona,
            periodo,
            timezone.localdate(),
        )

        for fila in resumen.get("filas", []):
            if fila["item"].nombre_item != etiqueta:
                continue

            if funcionario and persona.pk == funcionario.pk:
                url = reverse("measurement:mi_desempeno")
            else:
                url = reverse(
                    "measurement:desempeno_funcionario",
                    args=[persona.pk],
                )

            filas.append(
                _fila(
                    f"META-{fila['meta'].pk}",
                    fila["item"].nombre_item,
                    persona.nombre,
                    persona.delegacion.nombre,
                    fila["meta"].fecha_version,
                    f"{fila['cumplimiento']}% de cumplimiento",
                    url,
                )
            )

    return filas


def _detalle_semaforo(user, etiqueta, periodo):
    """
    Funcionarios cuyo resultado individual corresponde al estado
    seleccionado en el gráfico de semáforo.
    """

    if not tiene_rol(user, *ROLES_SUPERVISION):
        return None

    filas = []

    for persona in _funcionarios_visibles(user):
        resumen = CalculoIndicadores.resumen_funcionario(
            persona,
            periodo,
            timezone.localdate(),
        )

        if resumen["semaforo"] != etiqueta:
            continue

        filas.append(
            _fila(
                f"FUNC-{persona.pk}",
                persona.cargo.nombre_cargo,
                persona.nombre,
                persona.delegacion.nombre,
                None,
                resumen["semaforo"],
                reverse(
                    "organizations:funcionario_detail",
                    args=[persona.pk],
                ),
            )
        )

    return filas


def _detalle_delegacion(user, etiqueta, periodo):
    """
    Funcionarios pertenecientes a la delegación seleccionada,
    limitados al ámbito territorial autorizado.
    """

    if not tiene_rol(user, *ROLES_SUPERVISION):
        return None

    funcionarios_visibles = _funcionarios_visibles(user)

    delegaciones_ids = (
        funcionarios_visibles
        .values_list("delegacion_id", flat=True)
        .distinct()
    )

    delegacion = Delegacion.objects.filter(
        pk__in=delegaciones_ids,
        nombre=etiqueta,
    ).first()

    if not delegacion:
        return []

    filas = []

    funcionarios_delegacion = funcionarios_visibles.filter(
        delegacion=delegacion
    )

    for persona in funcionarios_delegacion:
        resumen = CalculoIndicadores.resumen_funcionario(
            persona,
            periodo,
            timezone.localdate(),
        )

        filas.append(
            _fila(
                f"FUNC-{persona.pk}",
                persona.cargo.nombre_cargo,
                persona.nombre,
                delegacion.nombre,
                None,
                f"{resumen['total_ponderado']}% de cumplimiento",
                reverse(
                    "organizations:funcionario_detail",
                    args=[persona.pk],
                ),
            )
        )

    return filas


@login_required
@require_GET
def dashboard_detalle(request):
    """
    Endpoint JSON para los siete gráficos interactivos del dashboard.

    Cada consulta reutiliza los mismos criterios de ámbito y visibilidad
    que se aplican al construir los datos de los gráficos.
    """

    tipo = request.GET.get("tipo", "").strip()
    etiqueta = request.GET.get("etiqueta", "").strip()

    if not tipo or not etiqueta:
        return JsonResponse(
            {
                "ok": False,
                "mensaje": "Selección incompleta.",
            },
            status=400,
        )

    user = request.user
    funcionario = get_funcionario(user)
    hoy = timezone.localdate()
    periodo = Periodo.objects.vigente(hoy)

    filas = None

    # 1. Cumplimiento por indicador.
    if tipo == "personal":
        if periodo is None:
            filas = []
        else:
            filas = _detalle_indicador(
                user,
                etiqueta,
                periodo,
                funcionario,
            )

    # 2. Semáforo de desempeño.
    elif tipo == "semaforo":
        if periodo is None:
            filas = []
        else:
            filas = _detalle_semaforo(
                user,
                etiqueta,
                periodo,
            )

    # 3. Cumplimiento por delegación.
    elif tipo == "delegaciones":
        if periodo is None:
            filas = []
        else:
            filas = _detalle_delegacion(
                user,
                etiqueta,
                periodo,
            )

    # 4. Compromisos por estado.
    
    # 4. Compromisos y solicitudes vecinales por estado.
    elif tipo == "agenda":
        qs = (
            _compromisos_dashboard(
                user,
                funcionario,
            )
            .filter(estado=etiqueta)
            .select_related(
                "funcionario",
                "delegacion",
                "solicitud_vecinal",
            )
            .order_by("-fecha_comprometida")
        )

        filas = []
        solicitudes_incluidas = set()

        for compromiso in qs[:300]:
            solicitud = compromiso.solicitud_vecinal

            # Los compromisos internos se muestran como COMP.
            if solicitud is None:
                filas.append(
                    _fila(
                        f"COMP-{compromiso.pk}",
                        compromiso.origen,
                        compromiso.funcionario.nombre,
                        compromiso.delegacion.nombre,
                        compromiso.fecha_comprometida,
                        compromiso.estado,
                        reverse(
                            "agenda:compromiso_detail",
                            args=[compromiso.pk],
                        ),
                    )
                )
                continue

            # Una solicitud puede originar varios compromisos.
            # En el dashboard se muestra una sola fila SOL por solicitud.
            if solicitud.pk in solicitudes_incluidas:
                continue

            solicitudes_incluidas.add(solicitud.pk)

            filas.append(
                _fila(
                    f"SOL-{solicitud.pk}",
                    solicitud.descripcion or solicitud.categoria,
                    compromiso.funcionario.nombre,
                    compromiso.delegacion.nombre,
                    solicitud.fecha_creacion.date(),
                    solicitud.estado_solicitud,
                    reverse(
                        "solicitudes:detalle",
                        args=[solicitud.pk],
                    ),
                )
            )


    # 5. Compromisos por trabajo.
    elif tipo == "trabajo":
        qs = _compromisos_dashboard(
            user,
            funcionario,
        )

        if etiqueta == "Sin trabajo asociado":
            qs = qs.filter(
                item_medible__isnull=True
            )
        else:
            qs = qs.filter(
                item_medible__nombre_item=etiqueta
            )

        filas = [
            _fila(
                f"COMP-{compromiso.pk}",
                compromiso.origen,
                compromiso.funcionario.nombre,
                compromiso.delegacion.nombre,
                compromiso.fecha_comprometida,
                compromiso.estado,
                reverse(
                    "agenda:compromiso_detail",
                    args=[compromiso.pk],
                ),
            )
            for compromiso in qs.order_by(
                "-fecha_comprometida"
            )[:100]
        ]

    # 6. Evolución mensual de actividades.
    elif tipo == "evolucion":
        mes = _mes_desde_etiqueta(etiqueta)

        if mes is None:
            return JsonResponse(
                {
                    "ok": False,
                    "mensaje": "Mes no válido.",
                },
                status=400,
            )

        if mes.month == 12:
            siguiente = date(
                mes.year + 1,
                1,
                1,
            )
        else:
            siguiente = date(
                mes.year,
                mes.month + 1,
                1,
            )

        qs = _actividades_dashboard(
            user,
            funcionario,
        )

        # El gráfico principal utiliza el período vigente cuando existe.
        # El detalle debe aplicar exactamente el mismo filtro.
        if periodo is not None:
            qs = qs.filter(periodo=periodo)

        qs = qs.filter(
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
            for actividad in qs.order_by(
                "-fecha",
                "-id_actividad",
            )[:100]
        ]

    # 7. Estado de evidencias.
    elif tipo == "evidencias":
        qs = _evidencias_dashboard(
            user,
            funcionario,
        ).filter(
            estado_revision=etiqueta,
        )

        filas = [
            _fila(
                evidencia.codigo_evidencia,
                evidencia.actividad.accion,
                evidencia.actividad.funcionario.nombre,
                evidencia.actividad.funcionario.delegacion.nombre,
                timezone.localtime(
                    evidencia.fecha_carga
                ).date(),
                evidencia.estado_revision,
                reverse(
                    "activities:actividad_detail",
                    args=[evidencia.actividad_id],
                ),
            )
            for evidencia in qs.order_by(
                "-fecha_carga",
                "-id_evidencia",
            )[:100]
        ]

    else:
        return JsonResponse(
            {
                "ok": False,
                "mensaje": "Tipo de gráfico no válido.",
            },
            status=400,
        )

    if filas is None:
        return JsonResponse(
            {
                "ok": False,
                "mensaje": (
                    "No tienes permiso para consultar este detalle."
                ),
            },
            status=403,
        )

    return JsonResponse(
        {
            "ok": True,
            "titulo": etiqueta,
            "total": len(filas),
            "filas": filas,
        }
    )
