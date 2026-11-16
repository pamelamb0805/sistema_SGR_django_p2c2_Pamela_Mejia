
from django.conf import settings
from django.db.models import Count, Max

from activities.models import Actividad
from measurement.calculations import calcular_dias_transcurridos


def construir_resumen_actividad_reciente(
    funcionarios,
    periodo,
    hoy,
):
    """
    RF-030: calcula actividad reciente por funcionario dentro
    del período vigente.

    Solo considera actividades validadas y fechas no futuras.
    El queryset recibido debe estar limitado al ámbito autorizado.
    """
    if periodo is None:
        return []

    fecha_inicio = periodo.fecha_inicio
    fecha_fin = min(hoy, periodo.fecha_termino)

    if fecha_fin < fecha_inicio:
        return []

    dias_transcurridos = max(
        calcular_dias_transcurridos(
            fecha_inicio,
            periodo.fecha_termino,
            fecha_fin,
        ),
        1,
    )

    umbral = getattr(
        settings,
        "SGR_DIAS_SIN_REGISTRO_ALERTA",
        7,
    )

    funcionarios_lista = list(
        funcionarios.select_related(
            "delegacion",
        ).order_by(
            "delegacion__nombre",
            "nombre",
        )
    )

    if not funcionarios_lista:
        return []

    ids_funcionarios = [
        funcionario.pk
        for funcionario in funcionarios_lista
    ]

    agregados = (
        Actividad.objects.filter(
            funcionario_id__in=ids_funcionarios,
            periodo=periodo,
            estado=Actividad.ESTADO_VALIDADA,
            fecha__gte=fecha_inicio,
            fecha__lte=fecha_fin,
        )
        .values("funcionario_id")
        .annotate(
            cantidad=Count("pk"),
            ultimo_registro=Max("fecha"),
        )
    )

    resumen_por_funcionario = {
        fila["funcionario_id"]: fila
        for fila in agregados
    }

    resultado = []

    for funcionario in funcionarios_lista:
        datos = resumen_por_funcionario.get(
            funcionario.pk,
            {},
        )

        cantidad = datos.get("cantidad", 0)
        ultimo_registro = datos.get("ultimo_registro")

        fecha_referencia = ultimo_registro or fecha_inicio

        dias_sin_ingreso = max(
            (hoy - fecha_referencia).days,
            0,
        )

        promedio_diario = round(
            cantidad / dias_transcurridos,
            2,
        )

        resultado.append({
            "funcionario": funcionario,
            "delegacion": funcionario.delegacion.nombre,
            "ultimo_registro": ultimo_registro,
            "dias_sin_ingreso": dias_sin_ingreso,
            "cantidad_registros": cantidad,
            "promedio_diario": promedio_diario,
            "sin_registros": cantidad == 0,
            "alerta_ausencia": (
                dias_sin_ingreso >= umbral
            ),
        })

    resultado.sort(
        key=lambda fila: (
            not fila["alerta_ausencia"],
            -fila["dias_sin_ingreso"],
            fila["funcionario"].nombre.lower(),
        )
    )

    return resultado
