
from asgiref.sync import async_to_sync
from django.test import TestCase

from core.mixins import (
    ROL_ADMINISTRADOR,
    ROL_COORDINADOR,
    ROL_DELEGADO,
    ROL_FUNCIONARIO,
    ROL_VERIFICADOR,
)

from organizations.models import (
    Cargo,
    Delegacion,
    Funcionario,
)

from .consumers import SGRConsumer
from .services import (
    obtener_delegacion_id,
    modelo_es_delegacion,
    obtener_nombre_actor,
    obtener_nombre_delegacion,
    MODULOS_DISPLAY,
    ACCIONES_DISPLAY,
)


class WebSocketBaseTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.delegacion = Delegacion.objects.create(
            nombre="Delegación WebSocket",
            direccion="Dirección de prueba 123",
            comuna="La Serena",
            ambito="Urbano",
        )

        cls.cargo = Cargo.objects.create(
            nombre_cargo="Cargo WebSocket",
            vigencia_desde=__import__("datetime").date(2026, 1, 1),
        )

        cls.funcionario = Funcionario.objects.create(
            identificador_institucional="WS-001",
            nombre="Funcionario WebSocket",
            cargo=cls.cargo,
            delegacion=cls.delegacion,
        )


class WebSocketServiciosTests(WebSocketBaseTestCase):

    def test_obtener_delegacion_desde_delegacion(self):
        resultado = obtener_delegacion_id(self.delegacion)

        self.assertEqual(resultado, self.delegacion.pk)

    def test_obtener_delegacion_desde_funcionario(self):
        resultado = obtener_delegacion_id(self.funcionario)

        self.assertEqual(resultado, self.delegacion.pk)

    def test_obtener_delegacion_de_none(self):
        self.assertIsNone(obtener_delegacion_id(None))

    def test_modelo_es_delegacion(self):
        self.assertTrue(modelo_es_delegacion(self.delegacion))
        self.assertFalse(modelo_es_delegacion(self.funcionario))

    def test_obtener_nombre_delegacion_existente(self):
        nombre = obtener_nombre_delegacion(self.delegacion.pk)

        self.assertEqual(nombre, self.delegacion.nombre)

    def test_obtener_nombre_delegacion_general(self):
        nombre = obtener_nombre_delegacion(None)

        self.assertEqual(nombre, "General")

    def test_obtener_nombre_delegacion_inexistente(self):
        nombre = obtener_nombre_delegacion(999999)

        self.assertEqual(nombre, "Delegación no disponible")

    def test_obtener_nombre_actor_con_funcionario(self):
        class ActorPrueba:
            funcionario = self.funcionario

        nombre = obtener_nombre_actor(ActorPrueba())

        self.assertEqual(nombre, self.funcionario.nombre)

    def test_obtener_nombre_actor_sistema(self):
        nombre = obtener_nombre_actor(None)

        self.assertEqual(nombre, "Sistema")

    def test_nombres_de_modulos_configurados(self):
        self.assertIn("organizations", MODULOS_DISPLAY)
        self.assertIn("activities", MODULOS_DISPLAY)
        self.assertIn("measurement", MODULOS_DISPLAY)
        self.assertIn("social", MODULOS_DISPLAY)

    def test_nombres_de_acciones_configurados(self):
        self.assertEqual(ACCIONES_DISPLAY["crear"], "Creación")
        self.assertEqual(ACCIONES_DISPLAY["actualizar"], "Modificación")
        self.assertEqual(ACCIONES_DISPLAY["eliminar"], "Eliminación")


class WebSocketAutorizacionTests(TestCase):

    def crear_consumer(
        self,
        delegaciones=None,
        roles=None,
        transversal=False,
    ):
        consumer = SGRConsumer()

        consumer.delegaciones_autorizadas = set(
            delegaciones or []
        )

        consumer.roles = set(roles or [])

        consumer.transversal = transversal

        return consumer

    def puede_recibir(self, consumer, payload):
        return async_to_sync(
            consumer.puede_recibir_evento
        )(payload)

    def test_funcionario_recibe_evento_de_actividad_autorizada(self):
        consumer = self.crear_consumer(
            delegaciones=[1],
            roles=[ROL_FUNCIONARIO],
        )

        resultado = self.puede_recibir(
            consumer,
            {
                "module": "activities",
                "delegacion_id": 1,
            },
        )

        self.assertTrue(resultado)

    def test_funcionario_no_recibe_evento_de_otra_delegacion(self):
        consumer = self.crear_consumer(
            delegaciones=[1],
            roles=[ROL_FUNCIONARIO],
        )

        resultado = self.puede_recibir(
            consumer,
            {
                "module": "activities",
                "delegacion_id": 2,
            },
        )

        self.assertFalse(resultado)

    def test_administrador_recibe_evento_de_organizaciones(self):
        consumer = self.crear_consumer(
            delegaciones=[],
            roles=[ROL_ADMINISTRADOR],
            transversal=True,
        )

        resultado = self.puede_recibir(
            consumer,
            {
                "module": "organizations",
                "delegacion_id": None,
            },
        )

        self.assertTrue(resultado)

    def test_funcionario_no_recibe_evento_de_organizaciones(self):
        consumer = self.crear_consumer(
            delegaciones=[1],
            roles=[ROL_FUNCIONARIO],
        )

        resultado = self.puede_recibir(
            consumer,
            {
                "module": "organizations",
                "delegacion_id": None,
            },
        )

        self.assertFalse(resultado)

    def test_coordinador_recibe_evento_de_medicion(self):
        consumer = self.crear_consumer(
            delegaciones=[1],
            roles=[ROL_COORDINADOR],
        )

        resultado = self.puede_recibir(
            consumer,
            {
                "module": "measurement",
                "delegacion_id": 1,
            },
        )

        self.assertTrue(resultado)

    def test_funcionario_no_recibe_evento_de_medicion(self):
        consumer = self.crear_consumer(
            delegaciones=[1],
            roles=[ROL_FUNCIONARIO],
        )

        resultado = self.puede_recibir(
            consumer,
            {
                "module": "measurement",
                "delegacion_id": 1,
            },
        )

        self.assertFalse(resultado)

    def test_verificador_recibe_evento_de_actividades(self):
        consumer = self.crear_consumer(
            delegaciones=[1],
            roles=[ROL_VERIFICADOR],
        )

        resultado = self.puede_recibir(
            consumer,
            {
                "module": "activities",
                "delegacion_id": 1,
            },
        )

        self.assertTrue(resultado)

    def test_delegado_recibe_evento_de_agenda(self):
        consumer = self.crear_consumer(
            delegaciones=[1],
            roles=[ROL_DELEGADO],
        )

        resultado = self.puede_recibir(
            consumer,
            {
                "module": "agenda",
                "delegacion_id": 1,
            },
        )

        self.assertTrue(resultado)

    def test_rechaza_modulo_no_configurado(self):
        consumer = self.crear_consumer(
            delegaciones=[1],
            roles=[ROL_ADMINISTRADOR],
            transversal=True,
        )

        resultado = self.puede_recibir(
            consumer,
            {
                "module": "modulo_inexistente",
                "delegacion_id": None,
            },
        )

        self.assertFalse(resultado)

    def test_rechaza_identificador_de_delegacion_invalido(self):
        consumer = self.crear_consumer(
            delegaciones=[1],
            roles=[ROL_FUNCIONARIO],
        )

        resultado = self.puede_recibir(
            consumer,
            {
                "module": "activities",
                "delegacion_id": "delegacion-invalida",
            },
        )

        self.assertFalse(resultado)

    def test_usuario_transversal_puede_recibir_evento_de_otra_delegacion(self):
        consumer = self.crear_consumer(
            delegaciones=[],
            roles=[ROL_ADMINISTRADOR],
            transversal=True,
        )

        resultado = self.puede_recibir(
            consumer,
            {
                "module": "organizations",
                "delegacion_id": 999,
            },
        )

        self.assertTrue(resultado)

    def test_sin_rol_autorizado_no_recibe_evento(self):
        consumer = self.crear_consumer(
            delegaciones=[1],
            roles=[],
        )

        resultado = self.puede_recibir(
            consumer,
            {
                "module": "activities",
                "delegacion_id": 1,
            },
        )

        self.assertFalse(resultado)
