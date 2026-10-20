from django.contrib import admin

from .models import Ajuste, Indicador, Meta, Periodo


@admin.register(Periodo)
class PeriodoAdmin(admin.ModelAdmin):
    list_display = ("id_periodo", "fecha_inicio", "fecha_termino", "dias_computables", "estado", "version_parametros")
    list_filter = ("estado",)
    readonly_fields = ("dias_computables",)


@admin.register(Meta)
class MetaAdmin(admin.ModelAdmin):
    list_display = ("id_meta", "funcionario", "item", "periodo", "valor_objetivo", "ponderador", "fecha_version")
    list_filter = ("periodo", "cargo")
    search_fields = ("funcionario__nombre", "item__nombre_item")


@admin.register(Indicador)
class IndicadorAdmin(admin.ModelAdmin):
    list_display = ("id_indicador", "meta", "avance", "cumplimiento_pct", "resultado_ponderado", "semaforo", "fecha_calculo")
    list_filter = ("semaforo",)


@admin.register(Ajuste)
class AjusteAdmin(admin.ModelAdmin):
    list_display = ("id_ajuste", "funcionario", "periodo", "efecto", "valor", "motivo")
    list_filter = ("efecto", "periodo")
