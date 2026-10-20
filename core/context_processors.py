"""Variables disponibles en TODAS las plantillas (navbar, menú, permisos de UI)."""
from django.conf import settings

from . import mixins as m


def sgr_context(request):
    contexto = {
        "sgr_parametros": {
            "tope_cumplimiento": settings.SGR_TOPE_CUMPLIMIENTO,
            "umbral_colectivo": settings.SGR_UMBRAL_COLECTIVO,
            "semaforo_ambar": settings.SGR_SEMAFORO_AMBAR,
        },
    }
    user = request.user
    if not user.is_authenticated:
        return contexto

    funcionario = m.get_funcionario(user)
    contexto.update({
        "sgr_funcionario": funcionario,
        "sgr_delegacion": funcionario.delegacion if funcionario else None,
        "sgr_roles": sorted(m.get_roles(user)),
        "sgr_rol_principal": m.get_rol_principal(user),
        "sgr_es_transversal": m.es_transversal(user),
        # Banderas para mostrar u ocultar opciones del menú.
        # (La seguridad real se valida en el servidor con los mixins.)
        "sgr_puede_configurar": m.tiene_rol(user, *m.ROLES_CONFIGURACION),
        "sgr_puede_medir": m.tiene_rol(user, *m.ROLES_MEDICION),
        "sgr_puede_validar": m.tiene_rol(user, *m.ROLES_VALIDACION),
        "sgr_puede_registrar": m.tiene_rol(user, *m.ROLES_OPERATIVOS),
        "sgr_puede_supervisar": m.tiene_rol(user, *m.ROLES_SUPERVISION),
    })
    return contexto
