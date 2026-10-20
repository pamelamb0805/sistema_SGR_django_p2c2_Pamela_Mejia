from django.contrib import admin

from .models import AtencionSocial, UsuarioSocial


class SoloLecturaMixin:
    """Datos personales: no se consultan ni editan desde el admin técnico (RNF-009)."""
    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class AtencionInline(SoloLecturaMixin, admin.TabularInline):
    model = AtencionSocial
    extra = 0
    fields = ("numero_gestion", "tipo_atencion", "fecha", "estado")


@admin.register(UsuarioSocial)
class UsuarioSocialAdmin(SoloLecturaMixin, admin.ModelAdmin):
    list_display = ("id_usuario", "nombre", "territorio", "delegacion", "estado_caso", "fecha_primer_registro")
    list_filter = ("estado_caso", "delegacion")
    search_fields = ("nombre", "territorio")
    inlines = [AtencionInline]


@admin.register(AtencionSocial)
class AtencionSocialAdmin(SoloLecturaMixin, admin.ModelAdmin):
    list_display = ("usuario", "numero_gestion", "tipo_atencion", "fecha", "estado", "funcionario")
    list_filter = ("tipo_atencion", "estado")
