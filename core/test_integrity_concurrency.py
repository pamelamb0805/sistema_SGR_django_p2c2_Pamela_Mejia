from datetime import date

from django.test import TestCase

from core.services import huella_concurrencia
from organizations.models import Delegacion


class ConcurrencyFingerprintTests(TestCase):
    def setUp(self):
        self.delegacion = Delegacion.objects.create(
            nombre="Delegación Concurrencia",
            direccion="Dirección de prueba",
            comuna="La Serena",
            ambito="Urbano",
        )

    def test_huella_es_estable_para_el_mismo_estado(self):
        primera = huella_concurrencia(self.delegacion)
        segunda = huella_concurrencia(self.delegacion)
        self.assertEqual(primera, segunda)
        self.assertEqual(len(primera), 64)

    def test_huella_detecta_cambio_hecho_por_otro_usuario(self):
        huella_formulario_abierto = huella_concurrencia(self.delegacion)
        Delegacion.objects.filter(pk=self.delegacion.pk).update(nombre="Delegación modificada")
        registro_actualizado = Delegacion.objects.get(pk=self.delegacion.pk)
        huella_actual = huella_concurrencia(registro_actualizado)
        self.assertNotEqual(huella_formulario_abierto, huella_actual)
