from datetime import date

from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.urls import reverse

from core.middleware import DelegacionActivaMiddleware
from core.mixins import filtrar_por_ambito, get_delegaciones_autorizadas_ids
from organizations.models import Cargo, Delegacion, Funcionario, Rol, Usuario


class ContextoDelegacionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.delegacion_principal = Delegacion.objects.create(
            codigo="CTX-01", nombre="Delegación Principal",
            direccion="Calle 1", comuna="La Serena", ambito="Norte",
        )
        cls.delegacion_extra = Delegacion.objects.create(
            codigo="CTX-02", nombre="Delegación Extra",
            direccion="Calle 2", comuna="La Serena", ambito="Sur",
        )
        cls.delegacion_ajena = Delegacion.objects.create(
            codigo="CTX-03", nombre="Delegación No autorizada",
            direccion="Calle 3", comuna="La Serena", ambito="Este",
        )
        cls.cargo = Cargo.objects.create(
            nombre_cargo="Cargo contexto", vigencia_desde=date(2026, 1, 1),
        )
        cls.rol = Rol.objects.create(
            nombre_rol="Coordinador contexto", alcance_autorizado="multiples",
        )
        funcionario = Funcionario.objects.create(
            identificador_institucional="CTX-FUNC",
            nombre="Funcionario Contexto",
            cargo=cls.cargo,
            delegacion=cls.delegacion_principal,
        )
        funcionario.roles.add(cls.rol)
        cls.usuario = Usuario.objects.create_user(
            "ctx-user", "Clave-Segura-2026", funcionario=funcionario,
        )
        cls.usuario.delegaciones_autorizadas.add(cls.delegacion_extra)

    def test_ids_autorizados_incluyen_principal_y_adicionales(self):
        ids = set(get_delegaciones_autorizadas_ids(self.usuario))
        self.assertEqual(ids, {self.delegacion_principal.pk, self.delegacion_extra.pk})
        self.assertNotIn(self.delegacion_ajena.pk, ids)

    def test_middleware_descarta_delegacion_no_autorizada(self):
        request = RequestFactory().get("/")
        request.user = self.usuario
        request.session = {"sgr_delegacion_activa": self.delegacion_ajena.pk}
        middleware = DelegacionActivaMiddleware(lambda req: HttpResponse("ok"))
        middleware(request)
        self.assertEqual(
            request.session["sgr_delegacion_activa"],
            self.delegacion_principal.pk,
        )
        self.assertEqual(
            request.user._sgr_delegacion_activa_id,
            self.delegacion_principal.pk,
        )

    def test_middleware_acepta_delegacion_adicional_autorizada(self):
        request = RequestFactory().get("/")
        request.user = self.usuario
        request.session = {"sgr_delegacion_activa": self.delegacion_extra.pk}
        middleware = DelegacionActivaMiddleware(lambda req: HttpResponse("ok"))
        middleware(request)
        self.assertEqual(request.user._sgr_delegacion_activa_id, self.delegacion_extra.pk)

    def test_filtro_respeta_contexto_activo_y_no_solo_todas_las_autorizadas(self):
        self.usuario._sgr_delegacion_activa_id = self.delegacion_extra.pk
        queryset = filtrar_por_ambito(
            Delegacion.objects.all(), self.usuario, "id_delegacion",
        )
        self.assertEqual(list(queryset.values_list("pk", flat=True)), [self.delegacion_extra.pk])
    def test_endpoint_cambia_contexto_solo_a_delegacion_autorizada(self):
        self.client.force_login(self.usuario)
        respuesta = self.client.post(
            reverse("cambiar_delegacion_activa"),
            {"delegacion_id": self.delegacion_extra.pk},
        )
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(
            self.client.session["sgr_delegacion_activa"],
            self.delegacion_extra.pk,
        )

