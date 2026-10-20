from django.contrib import admin

from .models import Compromiso, HistorialTransiciones


class SoloLecturaMixin:
    """Los compromisos y su historial se gestionan desde la aplicación (RNF-008)."""
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class HistorialInline(SoloLecturaMixin, admin.TabularInline):
    model = HistorialTransiciones
    extra = 0


@admin.register(Compromiso)
class CompromisoAdmin(SoloLecturaMixin, admin.ModelAdmin):
    list_display = ("id_compromiso", "solicitante", "territorio", "funcionario", "delegacion",
                    "fecha_comprometida", "estado")
    list_filter = ("estado", "delegacion", "periodo")
    search_fields = ("solicitante", "territorio", "origen")
    inlines = [HistorialInline]


@admin.register(HistorialTransiciones)
class HistorialTransicionesAdmin(SoloLecturaMixin, admin.ModelAdmin):
    list_display = ("compromiso", "estado_anterior", "estado_nuevo", "funcionario", "fecha")
    list_filter = ("estado_nuevo",)
