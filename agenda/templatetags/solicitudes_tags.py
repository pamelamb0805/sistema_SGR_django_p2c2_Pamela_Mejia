import unicodedata
from django import template
from core.mixins import get_funcionario, tiene_rol

register = template.Library()


@register.simple_tag
def puede_ver_solicitudes(user):
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False) or tiene_rol(user, "Administrador", "Coordinador", "Delegado"):
        return True
    funcionario = get_funcionario(user)
    if funcionario is None or not funcionario.activo:
        return False
    cargo = unicodedata.normalize("NFKD", funcionario.cargo.nombre_cargo).encode("ascii", "ignore").decode().lower()
    return any(nombre in cargo for nombre in (
        "gestor social", "apoyo administrativo", "organizaciones comunitarias",
        "gestion y planificacion", "coordinador de servicios comunitarios",
    ))
