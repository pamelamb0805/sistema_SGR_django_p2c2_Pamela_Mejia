
from django.test import SimpleTestCase, TestCase
from django.urls import resolve
from django.utils import timezone

from rest_framework.test import APIClient

from organizations.models import (
    Delegacion,
    Cargo,
    Rol,
    Funcionario,
    Usuario,
)
from core.mixins import filtrar_por_ambito


# ============================================================
# RUTAS REGISTRADAS
# ============================================================

class RutasAPITest(SimpleTestCase):

    RUTAS = [
        # Delegaciones
        "/api/delegaciones/",
        "/api/delegaciones/1/",
        "/api/delegaciones/1/estado/",
        "/api/delegaciones/exportar/",

        # Roles
        "/api/roles/",
        "/api/roles/1/",
        "/api/roles/exportar/",

        # Funcionarios
        "/api/funcionarios/",
        "/api/funcionarios/1/",
        "/api/funcionarios/1/estado/",
        "/api/funcionarios/1/items-vigentes/",
        "/api/funcionarios/exportar/",

        # Usuarios
        "/api/usuarios/",
        "/api/usuarios/1/",
        "/api/usuarios/1/estado/",
        "/api/usuarios/1/contrasenia/",
        "/api/usuarios/exportar/",

        # Cargos
        "/api/cargos/",
        "/api/cargos/1/",
        "/api/cargos/exportar/",
        "/api/cargos/1/items/exportar/",

        # Ítems
        "/api/items/",
        "/api/items/1/",
        "/api/items/1/vigencia/",
        "/api/items/1/historial/",

        # Metas
        "/api/metas/",
        "/api/metas/1/",
        "/api/metas/1/historial/",
        "/api/metas/exportar/",

        # Períodos
        "/api/periodos/",
        "/api/periodos/1/",
        "/api/periodos/1/cerrar/",
        "/api/periodos/1/reabrir/",
        "/api/periodos/1/reglas/",
        "/api/periodos/1/reglas/historial/",
        "/api/periodos/1/recalcular/",
        "/api/periodos/exportar/",

        # Ajustes
        "/api/ajustes/",
        "/api/ajustes/1/",
        "/api/ajustes/exportar/",

        # Semáforo
        "/api/semaforo/exportar/",

        # Actividades
        "/api/actividades/",
        "/api/actividades/1/",
        "/api/actividades/1/anular/",
        "/api/actividades/1/evidencias/",
        "/api/actividades/exportar/",

        # Evidencias
        "/api/evidencias/1/",
        "/api/evidencias/1/archivo/",
        "/api/evidencias/1/validaciones/",
        "/api/evidencias/1/validar/",

        # Validaciones
        "/api/validaciones/",
        "/api/validaciones/exportar/",

        # Compromisos
        "/api/compromisos/",
        "/api/compromisos/resumen/",
        "/api/compromisos/1/",
        "/api/compromisos/1/estado/",
        "/api/compromisos/1/reasignar/",
        "/api/compromisos/1/historial/",
        "/api/compromisos/exportar/",
        "/api/compromisos/resumen/exportar/",

        # Atención social
        "/api/casos/",
        "/api/casos/1/",
        "/api/casos/1/estado/",
        "/api/casos/1/gestiones/",
        "/api/casos/exportar/",
        "/api/gestiones/1/",
        "/api/atenciones/estadisticas/",
        "/api/atenciones/estadisticas/exportar/",

        # Catálogos
        "/api/catalogos/",
        "/api/catalogos/por-area/",
        "/api/catalogos/1/",
        "/api/catalogos/1/estado/",
        "/api/catalogos/1/historial/",
        "/api/catalogos/exportar/",

        # Auditoría
        "/api/auditoria/",
        "/api/auditoria/1/",
        "/api/auditoria/historial/organizations/1/",
        "/api/auditoria/exportar/",

        # Notificaciones
        "/api/notificaciones/",
        "/api/notificaciones/marcar-leidas/",

        # Comentarios
        "/api/comentarios/organizations/funcionario/1/",

        # Solicitudes vecinales
        "/api/solicitudes-vecinales/",
        "/api/solicitudes-vecinales/1/",
        "/api/solicitudes-vecinales/1/estado/",
        "/api/solicitudes-vecinales/1/historial/",

        # Alertas
        "/api/alertas/",
        "/api/alertas/1/atender/",
    ]

    def test_todas_las_rutas_api_resuelven(self):
        for ruta in self.RUTAS:
            with self.subTest(ruta=ruta):
                coincidencia = resolve(ruta)
                self.assertIsNotNone(coincidencia.func)


# ============================================================
# AUTENTICACIÓN
# ============================================================

class AutenticacionAPITest(SimpleTestCase):

    ENDPOINTS = RutasAPITest.RUTAS

    def setUp(self):
        self.client = APIClient()

    def test_todos_los_endpoints_requieren_autenticacion(self):
        """
        Comprueba que ningún endpoint de la API permita
        solicitudes anónimas.
        """
        for ruta in self.ENDPOINTS:
            with self.subTest(ruta=ruta):
                respuesta = self.client.get(ruta)

                self.assertIn(
                    respuesta.status_code,
                    (401, 403),
                    msg=(
                        f"El endpoint {ruta} permitió una solicitud "
                        f"anónima. HTTP {respuesta.status_code}."
                    ),
                )


# ============================================================
# PREPARACIÓN DE USUARIOS Y DELEGACIONES
# ============================================================

class BaseAPITest(TestCase):

    @classmethod
    def setUpTestData(cls):

        cls.delegacion_a = Delegacion.objects.create(
            nombre="Delegación API A",
            direccion="Dirección A",
            comuna="La Serena",
            ambito="Territorial A",
        )

        cls.delegacion_b = Delegacion.objects.create(
            nombre="Delegación API B",
            direccion="Dirección B",
            comuna="La Serena",
            ambito="Territorial B",
        )

        cls.cargo = Cargo.objects.create(
            nombre_cargo="Cargo de pruebas API",
            vigencia_desde=timezone.localdate(),
        )

    def crear_usuario(
        self,
        username,
        delegacion,
        alcance="propia",
        nombre_rol="Coordinador",
        permisos=None,
    ):

        rol = Rol.objects.create(
            nombre_rol=f"{nombre_rol} {username}",
            descripcion="Rol de pruebas automatizadas",
            permisos=permisos or [],
            alcance_autorizado=alcance,
        )

        funcionario = Funcionario.objects.create(
            identificador_institucional=f"TEST-{username}",
            nombre=f"Funcionario {username}",
            estado=Funcionario.ESTADO_ACTIVO,
            cargo=self.cargo,
            delegacion=delegacion,
        )

        funcionario.roles.add(rol)

        usuario = Usuario.objects.create_user(
            username=username,
            password="PruebaSegura-2026!",
            funcionario=funcionario,
        )

        return usuario


# ============================================================
# PERMISOS DE LA API DE DELEGACIONES
# ============================================================

class PermisosDelegacionesAPITest(BaseAPITest):

    def setUp(self):
        self.client = APIClient()

    def test_usuario_sin_permiso_no_consulta_delegaciones(self):

        usuario = self.crear_usuario(
            username="sin_permiso",
            delegacion=self.delegacion_a,
            permisos=[],
        )

        self.client.force_authenticate(user=usuario)

        respuesta = self.client.get("/api/delegaciones/")

        self.assertEqual(respuesta.status_code, 403)

    def test_usuario_con_permiso_consulta_su_delegacion(self):

        usuario = self.crear_usuario(
            username="consulta_a",
            delegacion=self.delegacion_a,
            permisos=["delegaciones.ver"],
        )

        self.client.force_authenticate(user=usuario)

        respuesta = self.client.get("/api/delegaciones/")

        self.assertEqual(respuesta.status_code, 200)

        ids = {
            elemento["id_delegacion"]
            for elemento in respuesta.data
        }

        self.assertIn(self.delegacion_a.pk, ids)
        self.assertNotIn(self.delegacion_b.pk, ids)

    def test_usuario_no_consulta_delegacion_ajena(self):

        usuario = self.crear_usuario(
            username="consulta_detalle",
            delegacion=self.delegacion_a,
            permisos=["delegaciones.ver"],
        )

        self.client.force_authenticate(user=usuario)

        respuesta = self.client.get(
            f"/api/delegaciones/{self.delegacion_b.pk}/"
        )

        self.assertEqual(respuesta.status_code, 404)

    def test_usuario_consulta_su_delegacion_por_id(self):

        usuario = self.crear_usuario(
            username="consulta_propia",
            delegacion=self.delegacion_a,
            permisos=["delegaciones.ver"],
        )

        self.client.force_authenticate(user=usuario)

        respuesta = self.client.get(
            f"/api/delegaciones/{self.delegacion_a.pk}/"
        )

        self.assertEqual(respuesta.status_code, 200)

    def test_usuario_sin_permiso_edicion_no_crea_delegacion(self):

        usuario = self.crear_usuario(
            username="sin_edicion",
            delegacion=self.delegacion_a,
            permisos=["delegaciones.ver"],
        )

        self.client.force_authenticate(user=usuario)

        respuesta = self.client.post(
            "/api/delegaciones/",
            {
                "nombre": "Delegación no autorizada",
                "direccion": "Dirección de prueba",
                "comuna": "La Serena",
                "ambito": "Prueba",
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 403)


# ============================================================
# REGLAS DE ÁMBITO TERRITORIAL
# ============================================================

class AmbitoTerritorialAPITest(BaseAPITest):

    def test_alcance_propio_solo_devuelve_delegacion_principal(self):

        usuario = self.crear_usuario(
            username="ambito_propio",
            delegacion=self.delegacion_a,
            alcance="propia",
        )

        queryset = filtrar_por_ambito(
            Delegacion.objects.all(),
            usuario,
            campo="id_delegacion",
        )

        ids = set(queryset.values_list("pk", flat=True))

        self.assertEqual(ids, {self.delegacion_a.pk})

    def test_alcance_multiples_incluye_delegaciones_autorizadas(self):

        usuario = self.crear_usuario(
            username="ambito_multiple",
            delegacion=self.delegacion_a,
            alcance="multiples",
        )

        usuario.delegaciones_autorizadas.add(
            self.delegacion_b
        )

        queryset = filtrar_por_ambito(
            Delegacion.objects.all(),
            usuario,
            campo="id_delegacion",
        )

        ids = set(queryset.values_list("pk", flat=True))

        self.assertEqual(
            ids,
            {
                self.delegacion_a.pk,
                self.delegacion_b.pk,
            },
        )

    def test_alcance_global_incluye_todas_las_delegaciones(self):

        usuario = self.crear_usuario(
            username="ambito_global",
            delegacion=self.delegacion_a,
            alcance="global",
        )

        queryset = filtrar_por_ambito(
            Delegacion.objects.all(),
            usuario,
            campo="id_delegacion",
        )

        ids = set(queryset.values_list("pk", flat=True))

        self.assertEqual(
            ids,
            set(
                Delegacion.objects.values_list(
                    "pk",
                    flat=True,
                )
            ),
        )

    def test_usuario_inactivo_no_obtiene_registros(self):

        usuario = self.crear_usuario(
            username="ambito_inactivo",
            delegacion=self.delegacion_a,
            alcance="propia",
        )

        usuario.funcionario.estado = Funcionario.ESTADO_INACTIVO
        usuario.funcionario.save(update_fields=["estado"])

        queryset = filtrar_por_ambito(
            Delegacion.objects.all(),
            usuario,
            campo="id_delegacion",
        )

        self.assertFalse(queryset.exists())

    def test_usuario_sin_funcionario_no_obtiene_registros(self):

        usuario = Usuario.objects.create_user(
            username="sin_funcionario_api",
            password="PruebaSegura-2026!",
        )

        queryset = filtrar_por_ambito(
            Delegacion.objects.all(),
            usuario,
            campo="id_delegacion",
        )

        self.assertFalse(queryset.exists())

    def test_usuario_no_autenticado_no_obtiene_registros(self):

        usuario = Usuario(
            username="anonimo_api",
        )

        usuario.is_authenticated = False

        queryset = filtrar_por_ambito(
            Delegacion.objects.all(),
            usuario,
            campo="id_delegacion",
        )

        self.assertFalse(queryset.exists())
