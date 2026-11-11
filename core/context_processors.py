
"""Variables disponibles en todas las plantillas del SGR."""
from django.conf import settings

from . import mixins as m


def sgr_context(request):
    contexto = {
        "sgr_parametros": {
            "tope_cumplimiento": settings.SGR_TOPE_CUMPLIMIENTO,
            "umbral_colectivo": settings.SGR_UMBRAL_COLECTIVO,
            "semaforo_ambar": settings.SGR_SEMAFORO_AMBAR,
        },
        "sgr_notificaciones": [],
    }

    user = request.user

    if not user.is_authenticated:
        return contexto

    funcionario = m.get_funcionario(user)

    contexto.update({
        "sgr_funcionario": funcionario,
        "sgr_delegacion": (
            funcionario.delegacion
            if funcionario else None
        ),
        "sgr_roles": sorted(m.get_roles(user)),
        "sgr_rol_principal": m.get_rol_principal(user),
        "sgr_es_transversal": m.es_transversal(user),

        "sgr_puede_configurar": m.tiene_rol(
            user, *m.ROLES_CONFIGURACION
        ),
        "sgr_puede_medir": m.tiene_rol(
            user, *m.ROLES_MEDICION
        ),
        "sgr_puede_validar": m.tiene_rol(
            user, *m.ROLES_VALIDACION
        ),
        "sgr_puede_registrar": m.tiene_rol(
            user, *m.ROLES_OPERATIVOS
        ),
        "sgr_puede_supervisar": m.tiene_rol(
            user, *m.ROLES_SUPERVISION
        ),
    })

    # Últimas 15 operaciones visibles para el usuario.
    try:
        from audit.models import Auditoria

        operaciones = Auditoria.objects.select_related(
            "funcionario",
            "funcionario__delegacion",
        ).all()

        operaciones = m.filtrar_por_ambito(
            operaciones,
            user,
            "funcionario__delegacion_id",
        )

        operaciones = operaciones.order_by(
            "-fecha",
            "-id_auditoria",
        )[:15]

        nombres_modulos = {
            "actividad": "Actividades",
            "actividades": "Actividades",
            "compromiso": "Agenda colectiva",
            "compromisos": "Agenda colectiva",
            "funcionario": "Funcionarios",
            "delegacion": "Delegaciones",
            "usuario": "Usuarios",
            "caso": "Atención social",
            "atencion": "Atención social",
            "atencion_social": "Atención social",
            "usuario_social": "Atención social",
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
            "LOGIN": "Inició sesión",
            "LOGOUT": "Cerró sesión",
        }

        for operacion in operaciones:
            entidad = (
                operacion.entidad_afectada or ""
            ).strip()

            clave = entidad.lower()

            operacion.modulo_display = nombres_modulos.get(
                clave,
                entidad.replace("_", " ").capitalize()
                if entidad else "Sistema",
            )

            operacion.accion_display = acciones.get(
                operacion.evento,
                operacion.evento.replace("_", " ").capitalize(),
            )

            operacion.actor_display = (
                operacion.funcionario.nombre
                if operacion.funcionario_id
                else "Sistema / técnico"
            )

            operacion.delegacion_display = (
                operacion.funcionario.delegacion.nombre
                if (
                    operacion.funcionario_id
                    and operacion.funcionario.delegacion_id
                )
                else "General"
            )

            operacion.object_label = (
                f"{entidad.replace('_', ' ').capitalize()} "
                f"#{operacion.id_entidad_afectada}"
                if operacion.id_entidad_afectada
                else entidad.replace("_", " ").capitalize()
            )

        contexto["sgr_notificaciones"] = operaciones

    except Exception:
        # Un fallo en las notificaciones no debe impedir cargar la página.
        contexto["sgr_notificaciones"] = []

    return contexto
