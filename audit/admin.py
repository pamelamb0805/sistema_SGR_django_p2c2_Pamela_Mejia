
from django.contrib import admin

from .models import Auditoria


@admin.register(Auditoria)
class AuditoriaAdmin(admin.ModelAdmin):
    """
    Administración de auditoría en modo exclusivamente lectura.

    Los intentos de edición y eliminación quedan registrados,
    aunque la operación sea denegada.
    """

    list_display = (
        "id_auditoria",
        "fecha",
        "funcionario",
        "evento",
        "entidad_afectada",
        "id_entidad_afectada",
    )

    list_filter = (
        "evento",
        "entidad_afectada",
    )

    search_fields = (
        "valor_anterior",
        "valor_nuevo",
        "funcionario__nombre",
    )

    readonly_fields = [
        campo.name
        for campo in Auditoria._meta.fields
    ]

    ordering = (
        "-fecha",
        "-id_auditoria",
    )

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def _registrar_intento_admin(
        self,
        request,
        accion,
        object_id,
    ):
        try:
            identificador = int(object_id)
        except (TypeError, ValueError):
            identificador = 0

        Auditoria._registrar_intento(
            accion=accion,
            usuario=request.user,
            id_entidad=identificador,
        )

    def change_view(
        self,
        request,
        object_id,
        form_url="",
        extra_context=None,
    ):
        self._registrar_intento_admin(
            request,
            "Intento de modificación desde Django Admin",
            object_id,
        )

        return super().change_view(
            request,
            object_id,
            form_url,
            extra_context,
        )

    def delete_view(
        self,
        request,
        object_id,
        extra_context=None,
    ):
        self._registrar_intento_admin(
            request,
            "Intento de eliminación desde Django Admin",
            object_id,
        )

        return super().delete_view(
            request,
            object_id,
            extra_context,
        )
