import re
from datetime import timedelta

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from organizations.models import Cargo, Delegacion, Funcionario, PasswordResetCode, Usuario
from core.views import RESET_SESSION_KEY, CODIGO_VIGENCIA_SEGUNDOS


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class RecuperacionClaveTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        delegacion = Delegacion.objects.create(
            codigo="REC-01", nombre="Delegación Recuperación",
            direccion="Calle 1", comuna="La Serena", ambito="General",
        )
        cargo = Cargo.objects.create(
            nombre_cargo="Cargo recuperación", vigencia_desde=timezone.localdate(),
        )
        funcionario = Funcionario.objects.create(
            identificador_institucional="REC-F1", nombre="Usuario Recuperación",
            cargo=cargo, delegacion=delegacion,
        )
        cls.usuario = Usuario.objects.create_user(
            "recuperacion", "Clave-Anterior-Segura-2026", funcionario=funcionario,
            email="recuperacion@example.test",
        )

    def test_solicitud_existente_envia_codigo_hash_y_expira_en_configuracion(self):
        respuesta = self.client.post(
            reverse("recuperar_clave"), {"email": self.usuario.email},
        )
        self.assertRedirects(respuesta, reverse("validar_codigo"), fetch_redirect_response=False)
        self.assertEqual(len(mail.outbox), 1)
        codigo = re.search(r"\b(\d{6})\b", mail.outbox[0].body).group(1)
        registro = PasswordResetCode.objects.get(user=self.usuario)
        self.assertNotEqual(registro.code_hash, codigo)
        self.assertGreaterEqual(
            (registro.expires_at - timezone.now()).total_seconds(),
            CODIGO_VIGENCIA_SEGUNDOS - 3,
        )
        self.assertEqual(self.client.session[RESET_SESSION_KEY]["verificado"], False)

    def test_correo_no_registrado_no_revela_existencia(self):
        respuesta = self.client.post(
            reverse("recuperar_clave"), {"email": "desconocido@example.test"},
        )
        self.assertRedirects(respuesta, reverse("validar_codigo"), fetch_redirect_response=False)
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(PasswordResetCode.objects.count(), 0)

    def test_codigo_incorrecto_incrementa_intentos(self):
        self.client.post(reverse("recuperar_clave"), {"email": self.usuario.email})
        registro = PasswordResetCode.objects.get(user=self.usuario)
        respuesta = self.client.post(reverse("validar_codigo"), {"codigo": "000000"})
        registro.refresh_from_db()
        self.assertEqual(registro.attempts, 1)
        self.assertEqual(respuesta.status_code, 200)

    def test_codigo_vencido_se_invalida(self):
        registro = PasswordResetCode.objects.create(
            user=self.usuario, code_hash="0" * 64,
            expires_at=timezone.now() - timedelta(seconds=1),
        )
        session = self.client.session
        session[RESET_SESSION_KEY] = {
            "email": self.usuario.email, "codigo_id": registro.pk,
            "emitido": 0, "reenviados": 0, "verificado": False,
        }
        session.save()
        respuesta = self.client.get(reverse("validar_codigo"))
        registro.refresh_from_db()
        self.assertTrue(registro.is_used)
        self.assertRedirects(respuesta, reverse("recuperar_clave"), fetch_redirect_response=False)

    def test_flujo_completo_invalida_codigo_y_cambia_clave(self):
        self.client.post(reverse("recuperar_clave"), {"email": self.usuario.email})
        codigo = re.search(r"\b(\d{6})\b", mail.outbox[-1].body).group(1)
        respuesta = self.client.post(reverse("validar_codigo"), {"codigo": codigo})
        self.assertRedirects(respuesta, reverse("nueva_clave"), fetch_redirect_response=False)

        nueva = "Nueva-Clave-Segura-2026!"
        respuesta = self.client.post(reverse("nueva_clave"), {
            "password1": nueva, "password2": nueva,
        })
        self.assertRedirects(respuesta, reverse("login"), fetch_redirect_response=False)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password(nueva))
        self.assertFalse(self.usuario.check_password("Clave-Anterior-Segura-2026"))
        self.assertTrue(PasswordResetCode.objects.get(user=self.usuario).is_used)
