from django.test import SimpleTestCase
from .models import Compromiso
from .solicitudes_services import normalizar_rut, rut_valido


class RutChileTests(SimpleTestCase):
    def test_normaliza_rut_con_puntos(self):
        self.assertEqual(normalizar_rut("12.345.678-5"), "12345678-5")

    def test_acepta_rut_valido(self):
        self.assertTrue(rut_valido("11.111.111-1"))

    def test_rechaza_digito_verificador_incorrecto(self):
        self.assertFalse(rut_valido("11.111.111-2"))

    def test_rechaza_rut_incompleto(self):
        self.assertFalse(rut_valido("12-K"))


class SolicitudSchemaTests(SimpleTestCase):
    def test_estados_solicitud_definidos(self):
        self.assertEqual([v for v, _ in Compromiso.ESTADOS_SOLICITUD], ["Creado", "Pendiente", "Proceso", "Concluido"])

    def test_rut_menor_es_unico_a_nivel_de_compromiso(self):
        field = Compromiso._meta.get_field("rut_menor")
        self.assertTrue(field.unique)
        self.assertTrue(field.null)

    def test_fecha_creacion_no_es_editable(self):
        self.assertFalse(Compromiso._meta.get_field("fecha_creacion").editable)
