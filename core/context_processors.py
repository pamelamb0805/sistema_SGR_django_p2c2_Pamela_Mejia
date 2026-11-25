
"""Variables disponibles en todas las plantillas del SGR."""
from django.conf import settings

from . import mixins as m
from organizations.models import Delegacion


def sgr_context(request):
    contexto = {
        "sgr_parametros": {
            "tope_cumplimiento": settings.SGR_TOPE_CUMPLIMIENTO,
            "umbral_colectivo": settings.SGR_UMBRAL_COLECTIVO,
            "semaforo_ambar": settings.SGR_SEMAFORO_AMBAR,
        },
        "sgr_notificaciones": [],
        "sgr_notificaciones_no_leidas": 0,
    }

    user = request.user

    if not user.is_authenticated:
        return contexto

    funcionario = m.get_funcionario(user)

    contexto.update({
        "sgr_funcionario": funcionario,
        "sgr_delegacion": (
            Delegacion.objects.filter(pk=m.get_delegacion_activa(user)).first()
            if m.get_delegacion_activa(user) else None
        ),
        "sgr_delegaciones_contexto": Delegacion.objects.filter(
            pk__in=m.get_delegaciones_autorizadas_ids(user),
            estado="Activa",
        ).order_by("nombre"),
        "sgr_delegacion_activa_id": m.get_delegacion_activa(user),
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

    try:
        from audit.models import Notificacion

        notificaciones = Notificacion.objects.filter(
            usuario=user,
        ).select_related(
            "auditoria",
            "auditoria__funcionario",
            "auditoria__funcionario__delegacion",
            "delegacion",
        ).order_by(
            "-fecha_creacion",
            "-id_notificacion",
        )

        contexto["sgr_notificaciones_no_leidas"] = (
            notificaciones.filter(leida=False).count()
        )

        notificaciones = notificaciones[:15]

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

        resultado = []

        for notificacion in notificaciones:
            operacion = notificacion.auditoria

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
                notificacion.delegacion.nombre
                if notificacion.delegacion_id
                else "General"
            )

            operacion.object_label = (
                f"{entidad.replace('_', ' ').capitalize()} "
                f"#{operacion.id_entidad_afectada}"
                if operacion.id_entidad_afectada
                else entidad.replace("_", " ").capitalize()
            )

            notificacion.operacion = operacion
            resultado.append(notificacion)

        contexto["sgr_notificaciones"] = resultado

    except Exception:
        contexto["sgr_notificaciones"] = []
        contexto["sgr_notificaciones_no_leidas"] = 0

    return contexto
