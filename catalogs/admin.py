from django.contrib import admin

from .models import Catalogo


@admin.register(Catalogo)
class CatalogoAdmin(admin.ModelAdmin):
    list_display = ("id_catalogo", "tipo_catalogo", "nombre", "area", "estado")
    list_filter = ("tipo_catalogo", "area", "estado")
    search_fields = ("nombre", "area")
