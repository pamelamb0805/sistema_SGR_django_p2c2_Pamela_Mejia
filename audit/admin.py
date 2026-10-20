from django.contrib import admin

from .models import Auditoria


@admin.register(Auditoria)
class AuditoriaAdmin(admin.ModelAdmin):
    """Solo consulta: el historial no se agrega, modifica ni elimina desde el admin."""
    list_display = ("id_auditoria", "fecha", "funcionario", "evento", "entidad_afectada", "id_entidad_afectada")
    list_filter = ("evento", "entidad_afectada")
    search_fields = ("valor_anterior", "valor_nuevo", "funcionario__nombre")
    readonly_fields = [f.name for f in Auditoria._meta.fields]

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
