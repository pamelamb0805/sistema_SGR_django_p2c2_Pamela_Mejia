"""
Helpers de servicio compartidos por todas las apps: guardar y eliminar con
validación, transacción y auditoría (valor anterior / valor nuevo).
"""
import json

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.forms.models import model_to_dict

from .exceptions import ReglaNegocioError
from .mixins import auditar

# Nunca se escriben en la auditoría
_EXCLUIDOS = ["password", "groups", "user_permissions", "roles"]


def snapshot(instancia):
    """Representación JSON del registro para auditoría (sin contraseñas)."""
    return json.dumps(model_to_dict(instancia, exclude=_EXCLUIDOS), default=str, ensure_ascii=False)


def mensaje_validacion(exc):
    if hasattr(exc, "error_dict"):
        return " ".join(m for lista in exc.message_dict.values() for m in lista)
    return " ".join(exc.messages)


def guardar(instancia, actor, entidad):
    """Crea o modifica validando, en transacción y con auditoría."""
    try:
        instancia.full_clean()
    except ValidationError as exc:
        raise ReglaNegocioError(mensaje_validacion(exc))
    with transaction.atomic():
        creado = instancia.pk is None
        anterior = None if creado else snapshot(type(instancia).objects.select_for_update().get(pk=instancia.pk))
        instancia.save()
        auditar(actor, "CREAR" if creado else "MODIFICAR", entidad, instancia.pk, anterior, snapshot(instancia))
    return instancia


def eliminar(instancia, actor, entidad, mensaje_en_uso):
    pk, anterior = instancia.pk, snapshot(instancia)
    try:
        with transaction.atomic():
            instancia.delete()
    except (ProtectedError, IntegrityError):
        raise ReglaNegocioError(mensaje_en_uso)
    auditar(actor, "ELIMINAR", entidad, pk, anterior, None)
