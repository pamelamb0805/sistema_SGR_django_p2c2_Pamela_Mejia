from django.contrib import admin

from .models import Actividad, Evidencia, Validacion


class SoloLecturaMixin:
    """Registros históricos: se consultan, no se alteran desde el admin (RNF-008)."""
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Actividad)
class ActividadAdmin(SoloLecturaMixin, admin.ModelAdmin):
    list_display = ("id_actividad", "fecha", "funcionario", "item", "catalogo", "estado", "periodo")
    list_filter = ("estado", "tipo_registro", "periodo")
    search_fields = ("accion", "contacto", "funcionario__nombre")


@admin.register(Evidencia)
class EvidenciaAdmin(SoloLecturaMixin, admin.ModelAdmin):
    list_display = ("codigo_evidencia", "actividad", "estado_revision", "fecha_carga")
    list_filter = ("estado_revision",)
    search_fields = ("codigo_evidencia",)


@admin.register(Validacion)
class ValidacionAdmin(SoloLecturaMixin, admin.ModelAdmin):
    list_display = ("evidencia", "version", "decision", "funcionario", "fecha")
    list_filter = ("decision",)
