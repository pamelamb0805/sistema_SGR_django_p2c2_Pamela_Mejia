
from datetime import date
from io import StringIO

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from organizations.models import (
    Cargo,
    Delegacion,
    Funcionario,
    Usuario,
)

from .models import (
    Auditoria,
    ComentarioRegistro,
    Notificacion,
    EVENTO_INTENTO_ALTERACION,
)
from .services import (
    registrar_evento,
    mostrar_historial_por_entidad,
    comparar_valores,
    filtrar_auditoria,
    escribir_csv,
    crear_notificaciones,
)


class BaseAuditoriaTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.delegacion = Delegacion.objects.create(
            nombre="Delegación de prueba",
            direccion="Dirección de prueba 123",
            comuna="La Serena",
            ambito="Urbano",
        )

        cls.cargo = Cargo.objects.create(
            nombre_cargo="Funcionario de prueba",
            vigencia_desde=date(2026, 1, 1),
        )

        cls.funcionario = Funcionario.objects.create(
            identificador_institucional="AUD-001",
            nombre="Funcionario Auditoría",
            cargo=cls.cargo,
            delegacion=cls.delegacion,
        )

        cls.usuario = Usuario.objects.create_user(
            username="usuario_auditoria",
            password="Clave-Segura-2026",
            funcionario=cls.funcionario,
        )

    def crear_evento(
        self,
        evento="CREAR",
        entidad="funcionario",
        id_entidad=1,
        anterior=None,
        nuevo=None,
    ):
        return Auditoria.objects.create(
            evento=evento,
            entidad_afectada=entidad,
            id_entidad_afectada=id_entidad,
            valor_anterior=anterior,
            valor_nuevo=nuevo,
            funcionario=self.funcionario,
        )


class AuditoriaModeloTests(BaseAuditoriaTestCase):

    def test_crear_evento_auditoria(self):
        evento = self.crear_evento()

        self.assertIsNotNone(evento.pk)
        self.assertEqual(evento.evento, "CREAR")
        self.assertEqual(evento.entidad_afectada, "funcionario")
        self.assertEqual(evento.funcionario, self.funcionario)

    def test_fecha_se_asigna_automaticamente(self):
        evento = self.crear_evento()

        self.assertIsNotNone(evento.fecha)

    def test_no_se_puede_modificar_evento_existente(self):
        evento = self.crear_evento()
        evento.evento = "MODIFICADO"

        with self.assertRaises(ValidationError):
            evento.save()

        self.assertTrue(
            Auditoria.objects.filter(
                evento=EVENTO_INTENTO_ALTERACION
            ).exists()
        )

    def test_no_se_puede_eliminar_evento_existente(self):
        evento = self.crear_evento()
        identificador = evento.pk

        with self.assertRaises(ValidationError):
            evento.delete()

        self.assertTrue(
            Auditoria.objects.filter(pk=identificador).exists()
        )

        self.assertTrue(
            Auditoria.objects.filter(
                evento=EVENTO_INTENTO_ALTERACION
            ).exists()
        )

    def test_queryset_update_bloqueado(self):
        evento = self.crear_evento()

        with self.assertRaises(ValidationError):
            Auditoria.objects.filter(pk=evento.pk).update(
                evento="ALTERADO"
            )

        evento.refresh_from_db()
        self.assertEqual(evento.evento, "CREAR")

    def test_queryset_delete_bloqueado(self):
        evento = self.crear_evento()

        with self.assertRaises(ValidationError):
            Auditoria.objects.filter(pk=evento.pk).delete()

        self.assertTrue(
            Auditoria.objects.filter(pk=evento.pk).exists()
        )

    def test_bulk_update_bloqueado(self):
        evento = self.crear_evento()
        evento.evento = "ALTERADO"

        with self.assertRaises(ValidationError):
            Auditoria.objects.bulk_update(
                [evento],
                ["evento"],
            )

        evento.refresh_from_db()
        self.assertEqual(evento.evento, "CREAR")


class AuditoriaServiciosTests(BaseAuditoriaTestCase):

    def test_registrar_evento_asocia_funcionario(self):
        evento = registrar_evento(
            usuario=self.usuario,
            evento="ACTUALIZAR",
            entidad="funcionario",
            id_entidad=self.funcionario.pk,
            valor_anterior={"nombre": "Anterior"},
            valor_nuevo={"nombre": "Nuevo"},
        )

        self.assertEqual(evento.funcionario, self.funcionario)
        self.assertEqual(evento.evento, "ACTUALIZAR")
        self.assertIn("Anterior", evento.valor_anterior)
        self.assertIn("Nuevo", evento.valor_nuevo)

    def test_registrar_evento_sin_usuario(self):
        evento = registrar_evento(
            usuario=None,
            evento="PROCESO_AUTOMATICO",
            entidad="sistema",
            id_entidad=0,
        )

        self.assertIsNone(evento.funcionario)
        self.assertEqual(evento.evento, "PROCESO_AUTOMATICO")

    def test_registrar_evento_serializa_diccionarios(self):
        evento = registrar_evento(
            usuario=self.usuario,
            evento="CAMBIO",
            entidad="funcionario",
            id_entidad=self.funcionario.pk,
            valor_anterior={"nombre": "Ana"},
            valor_nuevo={"nombre": "María"},
        )

        self.assertEqual(
            evento.valor_anterior,
            '{"nombre": "Ana"}',
        )

        self.assertEqual(
            evento.valor_nuevo,
            '{"nombre": "María"}',
        )

    def test_mostrar_historial_por_entidad(self):
        self.crear_evento(
            evento="CREAR",
            entidad="funcionario",
            id_entidad=10,
        )

        self.crear_evento(
            evento="ACTUALIZAR",
            entidad="funcionario",
            id_entidad=10,
        )

        self.crear_evento(
            evento="ELIMINAR",
            entidad="delegacion",
            id_entidad=20,
        )

        historial = mostrar_historial_por_entidad(
            "funcionario",
            10,
        )

        self.assertEqual(historial.count(), 2)

        self.assertTrue(
            all(
                registro.entidad_afectada == "funcionario"
                and registro.id_entidad_afectada == 10
                for registro in historial
            )
        )

    def test_comparar_valores_detecta_cambios(self):
        anterior = '{"nombre": "Ana", "estado": "Activo"}'
        nuevo = '{"nombre": "María", "estado": "Activo"}'

        cambios = comparar_valores(anterior, nuevo)

        self.assertEqual(len(cambios), 1)
        self.assertEqual(cambios[0]["campo"], "nombre")
        self.assertEqual(cambios[0]["anterior"], "Ana")
        self.assertEqual(cambios[0]["nuevo"], "María")

    def test_comparar_valores_detecta_campos_agregados(self):
        anterior = '{"nombre": "Ana"}'
        nuevo = '{"nombre": "Ana", "estado": "Activo"}'

        cambios = comparar_valores(anterior, nuevo)

        self.assertEqual(len(cambios), 1)
        self.assertEqual(cambios[0]["campo"], "estado")

    def test_comparar_valores_sin_diferencias(self):
        datos = '{"nombre": "Ana", "estado": "Activo"}'

        cambios = comparar_valores(datos, datos)

        self.assertEqual(cambios, [])

    def test_comparar_valores_no_json(self):
        cambios = comparar_valores(
            "valor anterior",
            "valor nuevo",
        )

        self.assertIsNone(cambios)

    def test_filtrar_auditoria_por_evento(self):
        self.crear_evento(evento="CREAR")
        self.crear_evento(evento="ACTUALIZAR")

        queryset, aplicados = filtrar_auditoria(
            Auditoria.objects.all(),
            {"evento": "CREAR"},
        )

        self.assertEqual(queryset.count(), 1)
        self.assertIn("Evento = CREAR", aplicados)

    def test_filtrar_auditoria_por_entidad_e_identificador(self):
        self.crear_evento(
            entidad="funcionario",
            id_entidad=10,
        )

        self.crear_evento(
            entidad="delegacion",
            id_entidad=20,
        )

        queryset, aplicados = filtrar_auditoria(
            Auditoria.objects.all(),
            {
                "entidad": "funcionario",
                "id_entidad": "10",
            },
        )

        self.assertEqual(queryset.count(), 1)
        self.assertIn("Entidad = funcionario", aplicados)
        self.assertIn("ID de entidad = 10", aplicados)

    def test_filtrar_auditoria_por_texto(self):
        self.crear_evento(
            nuevo='{"nombre": "Registro especial"}',
        )

        self.crear_evento(
            nuevo='{"nombre": "Otro registro"}',
        )

        queryset, aplicados = filtrar_auditoria(
            Auditoria.objects.all(),
            {"q": "especial"},
        )

        self.assertEqual(queryset.count(), 1)
        self.assertTrue(
            any("especial" in filtro for filtro in aplicados)
        )

    def test_exportar_csv_con_encabezados(self):
        self.crear_evento(
            evento="CREAR",
            entidad="funcionario",
            id_entidad=1,
            nuevo='{"nombre": "Prueba"}',
        )

        respuesta = StringIO()

        escribir_csv(
            respuesta,
            Auditoria.objects.all(),
            ["Evento = CREAR"],
            generado_por="Administrador",
        )

        contenido = respuesta.getvalue()

        self.assertIn("Informe de auditoría del SGR", contenido)
        self.assertIn("Fecha y hora", contenido)
        self.assertIn("Valor anterior", contenido)
        self.assertIn("Administrador", contenido)
        self.assertIn("CREAR", contenido)

    def test_exportacion_csv_protege_formulas(self):
        respuesta = StringIO()

        queryset = Auditoria.objects.none()

        escribir_csv(
            respuesta,
            queryset,
            [],
            generado_por="=HYPERLINK('sitio')",
        )

        self.assertIn(
            "'=HYPERLINK",
            respuesta.getvalue(),
        )

    def test_crear_notificaciones_ignora_entidad_no_configurada(self):
        evento = self.crear_evento(
            evento="CAMBIO",
            entidad="entidad_no_configurada",
        )

        cantidad = crear_notificaciones(evento)

        self.assertEqual(cantidad, 0)
        self.assertEqual(Notificacion.objects.count(), 0)


class ComentarioRegistroTests(BaseAuditoriaTestCase):

    def setUp(self):
        self.content_type = ContentType.objects.get_for_model(
            Funcionario,
            for_concrete_model=False,
        )

    def crear_comentario(self, mensaje="Comentario de prueba"):
        return ComentarioRegistro.objects.create(
            content_type=self.content_type,
            object_id=self.funcionario.pk,
            autor=self.usuario,
            funcionario=self.funcionario,
            delegacion=self.delegacion,
            mensaje=mensaje,
        )

    def test_crear_comentario(self):
        comentario = self.crear_comentario()

        self.assertIsNotNone(comentario.pk)
        self.assertEqual(comentario.autor, self.usuario)
        self.assertEqual(comentario.mensaje, "Comentario de prueba")
        self.assertEqual(comentario.object_id, self.funcionario.pk)

    def test_comentario_elimina_espacios_exteriores(self):
        comentario = self.crear_comentario("  Mensaje válido  ")

        self.assertEqual(comentario.mensaje, "Mensaje válido")

    def test_no_permite_comentario_vacio(self):
        with self.assertRaises(ValidationError):
            self.crear_comentario("   ")

    def test_no_permite_modificar_comentario_publicado(self):
        comentario = self.crear_comentario()
        comentario.mensaje = "Mensaje modificado"

        with self.assertRaises(ValidationError):
            comentario.save()

    def test_no_permite_eliminar_comentario_publicado(self):
        comentario = self.crear_comentario()

        with self.assertRaises(ValidationError):
            comentario.delete()

        self.assertTrue(
            ComentarioRegistro.objects.filter(
                pk=comentario.pk
            ).exists()
        )

    def test_permite_respuesta_en_misma_conversacion(self):
        padre = self.crear_comentario("Mensaje inicial")

        respuesta = ComentarioRegistro.objects.create(
            content_type=self.content_type,
            object_id=self.funcionario.pk,
            autor=self.usuario,
            funcionario=self.funcionario,
            delegacion=self.delegacion,
            respuesta_a=padre,
            mensaje="Respuesta",
        )

        self.assertEqual(respuesta.respuesta_a, padre)
        self.assertEqual(padre.respuestas.count(), 1)

    def test_rechaza_respuesta_de_otro_registro(self):
        padre = self.crear_comentario("Mensaje inicial")

        otro_funcionario = Funcionario.objects.create(
            identificador_institucional="AUD-002",
            nombre="Otro funcionario",
            cargo=self.cargo,
            delegacion=self.delegacion,
        )

        with self.assertRaises(ValidationError):
            ComentarioRegistro.objects.create(
                content_type=self.content_type,
                object_id=otro_funcionario.pk,
                autor=self.usuario,
                funcionario=self.funcionario,
                delegacion=self.delegacion,
                respuesta_a=padre,
                mensaje="Respuesta inválida",
            )
