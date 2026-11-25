
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from organizations import views as organizations_views
from measurement import views as measurement_views
from activities import views as activities_views
from agenda import views as agenda_views
from social import views as social_views
from catalogs import views as catalogs_views


def crear_endpoint_exportacion(vista_original, nombre):
    """
    Adapta una exportación Excel existente a un endpoint REST.

    La vista original conserva sus filtros, permisos, ámbito,
    metadatos del informe y generación del archivo.
    """

    @api_view(["GET"])
    @permission_classes([IsAuthenticated])
    def endpoint(request, *args, **kwargs):
        return vista_original(
            request._request,
            *args,
            **kwargs,
        )

    endpoint.__name__ = nombre
    endpoint.__qualname__ = nombre

    return endpoint


# ---------------------------------------------------------------------
# ORGANIZACIONES
# ---------------------------------------------------------------------

exportar_delegaciones_api = crear_endpoint_exportacion(
    organizations_views.exportar_delegaciones_excel,
    "exportar_delegaciones_api",
)

exportar_roles_api = crear_endpoint_exportacion(
    organizations_views.exportar_roles_excel,
    "exportar_roles_api",
)

exportar_usuarios_api = crear_endpoint_exportacion(
    organizations_views.exportar_usuarios_excel,
    "exportar_usuarios_api",
)

exportar_items_api = crear_endpoint_exportacion(
    organizations_views.exportar_items_excel,
    "exportar_items_api",
)

exportar_funcionarios_api = crear_endpoint_exportacion(
    organizations_views.exportar_funcionarios_excel,
    "exportar_funcionarios_api",
)

exportar_cargos_api = crear_endpoint_exportacion(
    organizations_views.exportar_cargos_excel,
    "exportar_cargos_api",
)


# ---------------------------------------------------------------------
# MEDICIÓN
# ---------------------------------------------------------------------

exportar_metas_api = crear_endpoint_exportacion(
    measurement_views.exportar_metas_excel,
    "exportar_metas_api",
)

exportar_periodos_api = crear_endpoint_exportacion(
    measurement_views.exportar_periodos_excel,
    "exportar_periodos_api",
)

exportar_ajustes_api = crear_endpoint_exportacion(
    measurement_views.exportar_ajustes_excel,
    "exportar_ajustes_api",
)

exportar_semaforo_api = crear_endpoint_exportacion(
    measurement_views.exportar_semaforo_excel,
    "exportar_semaforo_api",
)


# ---------------------------------------------------------------------
# ACTIVIDADES Y EVIDENCIAS
# ---------------------------------------------------------------------

exportar_actividades_api = crear_endpoint_exportacion(
    activities_views.exportar_actividades_excel,
    "exportar_actividades_api",
)

exportar_validaciones_api = crear_endpoint_exportacion(
    activities_views.exportar_validaciones_excel,
    "exportar_validaciones_api",
)


# ---------------------------------------------------------------------
# AGENDA COLECTIVA
# ---------------------------------------------------------------------

exportar_compromisos_api = crear_endpoint_exportacion(
    agenda_views.exportar_compromisos_excel,
    "exportar_compromisos_api",
)

exportar_resumen_agenda_api = crear_endpoint_exportacion(
    agenda_views.exportar_resumen_colectivo_excel,
    "exportar_resumen_agenda_api",
)


# ---------------------------------------------------------------------
# ATENCIÓN SOCIAL
# ---------------------------------------------------------------------

exportar_casos_sociales_api = crear_endpoint_exportacion(
    social_views.exportar_casos_excel,
    "exportar_casos_sociales_api",
)

exportar_estadisticas_sociales_api = crear_endpoint_exportacion(
    social_views.exportar_estadisticas_excel,
    "exportar_estadisticas_sociales_api",
)


# ---------------------------------------------------------------------
# CATÁLOGOS
# ---------------------------------------------------------------------

exportar_catalogos_api = crear_endpoint_exportacion(
    catalogs_views.exportar_catalogos_excel,
    "exportar_catalogos_api",
)
