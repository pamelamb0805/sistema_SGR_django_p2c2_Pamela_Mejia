
from django.test import SimpleTestCase
from django.urls import resolve

from rest_framework.test import APIClient


class RutasAPITest(SimpleTestCase):
    """
    Comprueba que los endpoints REST principales estén registrados
    y resuelvan hacia una vista.
    """

    RUTAS = [
        # Organizaciones
        "/api/delegaciones/",
        "/api/delegaciones/1/",
        "/api/delegaciones/1/estado/",
        "/api/roles/",
        "/api/roles/1/",
        "/api/funcionarios/",
        "/api/funcionarios/1/",
        "/api/funcionarios/1/estado/",
        "/api/usuarios/",
        "/api/usuarios/1/",
        "/api/usuarios/1/estado/",
        "/api/usuarios/1/contrasenia/",
        "/api/cargos/",
        "/api/cargos/1/",
        "/api/cargos/1/items/exportar/",

        # Ítems y medición
        "/api/items/",
        "/api/items/1/",
        "/api/items/1/vigencia/",
        "/api/items/1/historial/",
        "/api/funcionarios/1/items-vigentes/",
        "/api/metas/",
        "/api/metas/1/",
        "/api/metas/1/historial/",
        "/api/periodos/",
        "/api/periodos/1/",
        "/api/periodos/1/cerrar/",
        "/api/periodos/1/reabrir/",
        "/api/periodos/1/reglas/",
        "/api/periodos/1/reglas/historial/",
        "/api/periodos/1/recalcular/",
        "/api/ajustes/",
        "/api/ajustes/1/",

        # Actividades y evidencias
        "/api/actividades/",
        "/api/actividades/1/",
        "/api/actividades/1/anular/",
        "/api/actividades/1/evidencias/",
        "/api/evidencias/1/",
        "/api/evidencias/1/archivo/",
        "/api/validaciones/",
        "/api/evidencias/1/validaciones/",
        "/api/evidencias/1/validar/",

        # Agenda colectiva
        "/api/compromisos/",
        "/api/compromisos/resumen/",
        "/api/compromisos/1/",
        "/api/compromisos/1/estado/",
        "/api/compromisos/1/reasignar/",
        "/api/compromisos/1/historial/",

        # Atención social
        "/api/casos/",
        "/api/casos/1/",
        "/api/casos/1/estado/",
        "/api/casos/1/gestiones/",
        "/api/gestiones/1/",
        "/api/atenciones/estadisticas/",

        # Catálogos
        "/api/catalogos/",
        "/api/catalogos/por-area/",
        "/api/catalogos/1/",
        "/api/catalogos/1/estado/",
        "/api/catalogos/1/historial/",

        # Auditoría, notificaciones y comentarios
        "/api/auditoria/",
        "/api/auditoria/1/",
        "/api/auditoria/historial/organizations/1/",
        "/api/notificaciones/",
        "/api/notificaciones/marcar-leidas/",
        "/api/comentarios/organizations/funcionario/1/",

        # Solicitudes vecinales y alertas
        "/api/solicitudes-vecinales/",
        "/api/solicitudes-vecinales/1/",
        "/api/solicitudes-vecinales/1/estado/",
        "/api/solicitudes-vecinales/1/historial/",
        "/api/alertas/",
        "/api/alertas/1/atender/",

        # Exportaciones
        "/api/delegaciones/exportar/",
        "/api/roles/exportar/",
        "/api/usuarios/exportar/",
        "/api/funcionarios/exportar/",
        "/api/cargos/exportar/",
        "/api/metas/exportar/",
        "/api/periodos/exportar/",
        "/api/ajustes/exportar/",
        "/api/semaforo/exportar/",
        "/api/actividades/exportar/",
        "/api/validaciones/exportar/",
        "/api/compromisos/exportar/",
        "/api/compromisos/resumen/exportar/",
        "/api/casos/exportar/",
        "/api/atenciones/estadisticas/exportar/",
        "/api/catalogos/exportar/",
        "/api/auditoria/exportar/",
    ]

    def test_todas_las_rutas_api_resuelven(self):
        """
        Ninguna ruta declarada debe producir Resolver404.
        """
        for ruta in self.RUTAS:
            with self.subTest(ruta=ruta):
                coincidencia = resolve(ruta)
                self.assertIsNotNone(coincidencia.func)


class AutenticacionAPITest(SimpleTestCase):
    """
    Comprueba que los endpoints REST protegidos no permitan
    consultas anónimas.
    """

    def setUp(self):
        self.client = APIClient()

    def test_delegaciones_requiere_autenticacion(self):
        respuesta = self.client.get("/api/delegaciones/")

        self.assertIn(
            respuesta.status_code,
            (401, 403),
            msg="El listado de delegaciones permitió acceso anónimo.",
        )

    def test_exportacion_requiere_autenticacion(self):
        respuesta = self.client.get("/api/metas/exportar/")

        self.assertIn(
            respuesta.status_code,
            (401, 403),
            msg="La exportación de metas permitió acceso anónimo.",
        )

    def test_auditoria_requiere_autenticacion(self):
        respuesta = self.client.get("/api/auditoria/")

        self.assertIn(
            respuesta.status_code,
            (401, 403),
            msg="La auditoría permitió acceso anónimo.",
        )

    def test_notificaciones_requiere_autenticacion(self):
        respuesta = self.client.get("/api/notificaciones/")

        self.assertIn(
            respuesta.status_code,
            (401, 403),
            msg="Las notificaciones permitieron acceso anónimo.",
        )
