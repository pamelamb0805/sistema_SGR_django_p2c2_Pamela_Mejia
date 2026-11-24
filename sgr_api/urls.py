from django.urls import path

from . import views


urlpatterns = [
    # Delegaciones.
    path(
        "delegaciones/",
        views.delegacion_list,
        name="api_delegaciones",
    ),
    path(
        "delegaciones/<int:pk>/",
        views.delegacion_detail,
        name="api_delegacion_detail",
    ),
    path(
        "delegaciones/<int:pk>/estado/",
        views.delegacion_estado,
        name="api_delegacion_estado",
    ),

    # Roles.
    path(
        "roles/",
        views.rol_list,
        name="api_roles",
    ),
    path(
        "roles/<int:pk>/",
        views.rol_detail,
        name="api_rol_detail",
    ),

    # Funcionarios.
    path(
        "funcionarios/",
        views.funcionario_list,
        name="api_funcionarios",
    ),
    path(
        "funcionarios/<int:pk>/",
        views.funcionario_detail,
        name="api_funcionario_detail",
    ),
    path(
        "funcionarios/<int:pk>/estado/",
        views.funcionario_estado,
        name="api_funcionario_estado",
    ),

    # Usuarios y accesos.
    path(
        "usuarios/",
        views.usuario_list,
        name="api_usuarios",
    ),
    path(
        "usuarios/<int:pk>/",
        views.usuario_detail,
        name="api_usuario_detail",
    ),
    path(
        "usuarios/<int:pk>/estado/",
        views.usuario_estado,
        name="api_usuario_estado",
    ),
    path(
        "usuarios/<int:pk>/contrasenia/",
        views.usuario_contrasenia,
        name="api_usuario_contrasenia",
    ),

        # Ítems medibles.
    path(
        "items/",
        views.item_list,
        name="api_items",
    ),
    path(
        "items/<int:pk>/",
        views.item_detail,
        name="api_item_detail",
    ),
    path(
        "items/<int:pk>/vigencia/",
        views.item_vigencia,
        name="api_item_vigencia",
    ),


    # Metas.
    path(
        "metas/",
        views.meta_list,
        name="api_metas",
    ),
    path(
        "metas/<int:pk>/",
        views.meta_detail,
        name="api_meta_detail",
    ),


    # Períodos de medición.
    path(
        "periodos/",
        views.periodo_list,
        name="api_periodos",
    ),
    path(
        "periodos/<int:pk>/",
        views.periodo_detail,
        name="api_periodo_detail",
    ),
    path(
        "periodos/<int:pk>/cerrar/",
        views.periodo_cerrar,
        name="api_periodo_cerrar",
    ),
    path(
        "periodos/<int:pk>/reabrir/",
        views.periodo_reabrir,
        name="api_periodo_reabrir",
    ),
    path(
        "periodos/<int:pk>/reglas/",
        views.periodo_reglas,
        name="api_periodo_reglas",
    ),
    path(
        "periodos/<int:pk>/reglas/historial/",
        views.periodo_reglas_historial,
        name="api_periodo_reglas_historial",
    ),
    path(
        "periodos/<int:pk>/recalcular/",
        views.periodo_recalcular,
        name="api_periodo_recalcular",
    ),

        # Ajustes: incentivos y penalizaciones.
    path(
        "ajustes/",
        views.ajuste_list,
        name="api_ajustes",
    ),
    path(
        "ajustes/<int:pk>/",
        views.ajuste_detail,
        name="api_ajuste_detail",
    ),

        # -------------------------------------------------------------
    # Actividades
    # -------------------------------------------------------------

    path(
        "actividades/",
        views.actividad_list,
        name="api_actividades",
    ),

    path(
        "actividades/<int:pk>/",
        views.actividad_detail,
        name="api_actividad_detail",
    ),

    path(
        "actividades/<int:pk>/anular/",
        views.actividad_anular,
        name="api_actividad_anular",
    ),

    # -------------------------------------------------------------
    # Evidencias
    # -------------------------------------------------------------

    path(
        "actividades/<int:pk>/evidencias/",
        views.actividad_evidencias,
        name="api_actividad_evidencias",
    ),

    path(
        "evidencias/<int:pk>/",
        views.evidencia_detail,
        name="api_evidencia_detail",
    ),

    path(
        "evidencias/<int:pk>/archivo/",
        views.evidencia_archivo,
        name="api_evidencia_archivo",
    ),

    # -------------------------------------------------------------
    # Validaciones
    # -------------------------------------------------------------

    path(
        "validaciones/",
        views.validacion_list,
        name="api_validaciones",
    ),

    path(
        "evidencias/<int:pk>/validaciones/",
        views.evidencia_validaciones,
        name="api_evidencia_validaciones",
    ),

    path(
        "evidencias/<int:pk>/validar/",
        views.evidencia_validar,
        name="api_evidencia_validar",
    ),


    # -------------------------------------------------------------
    # AGENDA COLECTIVA - COMPROMISOS
    # -------------------------------------------------------------

    path(
        "compromisos/",
        views.compromiso_list,
        name="api_compromisos",
    ),

    path(
        "compromisos/resumen/",
        views.compromiso_resumen,
        name="api_compromisos_resumen",
    ),

    path(
        "compromisos/<int:pk>/",
        views.compromiso_detail,
        name="api_compromiso_detail",
    ),

    path(
        "compromisos/<int:pk>/estado/",
        views.compromiso_estado,
        name="api_compromiso_estado",
    ),

    path(
        "compromisos/<int:pk>/reasignar/",
        views.compromiso_reasignar,
        name="api_compromiso_reasignar",
    ),

    path(
        "compromisos/<int:pk>/historial/",
        views.compromiso_historial,
        name="api_compromiso_historial",
    ),

        # -------------------------------------------------------------
    # ATENCIÓN SOCIAL - CASOS
    # -------------------------------------------------------------

    path(
        "casos/",
        views.caso_social_list,
        name="api_casos_sociales",
    ),

    path(
        "casos/<int:pk>/",
        views.caso_social_detail,
        name="api_caso_social_detail",
    ),

    path(
        "casos/<int:pk>/estado/",
        views.caso_social_estado,
        name="api_caso_social_estado",
    ),

    path(
        "casos/<int:pk>/gestiones/",
        views.caso_social_gestiones,
        name="api_caso_social_gestiones",
    ),

    # -------------------------------------------------------------
    # ATENCIÓN SOCIAL - GESTIONES
    # -------------------------------------------------------------

    path(
        "gestiones/<int:pk>/",
        views.gestion_social_detail,
        name="api_gestion_social_detail",
    ),

    # -------------------------------------------------------------
    # ESTADÍSTICAS SOCIALES
    # -------------------------------------------------------------

    path(
        "atenciones/estadisticas/",
        views.atencion_social_estadisticas,
        name="api_atencion_social_estadisticas",
    ),


    # -------------------------------------------------------------
    # CATÁLOGOS
    # -------------------------------------------------------------

    path(
        "catalogos/",
        views.catalogo_list,
        name="api_catalogos",
    ),

    path(
        "catalogos/por-area/",
        views.catalogo_por_area_api,
        name="api_catalogos_por_area",
    ),

    path(
        "catalogos/<int:pk>/",
        views.catalogo_detail,
        name="api_catalogo_detail",
    ),

    path(
        "catalogos/<int:pk>/estado/",
        views.catalogo_estado,
        name="api_catalogo_estado",
    ),

    path(
        "catalogos/<int:pk>/historial/",
        views.catalogo_historial,
        name="api_catalogo_historial",
    ),




]