
from django.test import SimpleTestCase

from agenda.solicitudes_services import (
    normalizar_rut,
    rut_valido,
)


class ValidadorRUTTest(SimpleTestCase):

    def test_acepta_rut_valido_con_puntos(self):
        self.assertTrue(rut_valido("12.345.678-5"))

    def test_acepta_rut_valido_sin_puntos(self):
        self.assertTrue(rut_valido("12345678-5"))

    def test_acepta_rut_sin_separadores(self):
        self.assertTrue(rut_valido("123456785"))

    def test_normaliza_rut(self):
        self.assertEqual(
            normalizar_rut("12.345.678-5"),
            "12345678-5",
        )

    def test_rechaza_letras_en_el_cuerpo(self):
        self.assertFalse(
            rut_valido("12A345678-5")
        )

    def test_rechaza_letras_arbitrarias(self):
        self.assertFalse(
            rut_valido("ABCDEFGH-5")
        )

    def test_rechaza_simbolos(self):
        self.assertFalse(
            rut_valido("12@345678-5")
        )

    def test_rechaza_digito_verificador_incorrecto(self):
        self.assertFalse(
            rut_valido("12.345.678-9")
        )

    def test_rechaza_rut_incompleto(self):
        self.assertFalse(
            rut_valido("12345-5")
        )

    def test_rechaza_normalizacion_de_entrada_invalida(self):
        self.assertEqual(
            normalizar_rut("12ABC345678-5"),
            "",
        )
