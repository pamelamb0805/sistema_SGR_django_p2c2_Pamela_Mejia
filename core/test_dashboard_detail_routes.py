from datetime import date, timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from agenda.models import Compromiso
from organizations.models import Cargo, Delegacion, Funcionario, FuncionarioRol, Rol, Usuario


class DashboardDetailRouteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.delegacion = Delegacion.objects.create(
            nombre="Centro",
            direccion="Dirección de prueba",
            comuna="La Serena",
            ambito="Urbano",
        )
        cls.cargo = Cargo.objects.create(
            nombre_cargo="Administrador de prueba",
            vigencia_desde=date(2026, 1, 1),
        )
        cls.rol = Rol.objects.create(
            nombre_rol="Administrador",
            permisos=["*"],
            alcance_autorizado="propia",
        )
        cls.funcionario = Funcionario.objects.create(
            identificador_institucional="DASH-001",
            nombre="Funcionario Dashboard",
            cargo=cls.cargo,
            delegacion=cls.delegacion,
        )
        FuncionarioRol.objects.create(funcionario=cls.funcionario, rol=cls.rol)
        cls.usuario = Usuario.objects.create_user(
            "dashboard_admin",
            "Clave-Segura-2026",
            funcionario=cls.funcionario,
        )


    def test_detalle_dashboard_envia_compromiso_a_agenda_y_solicitud_a_su_vista(self):
        from agenda.models import SolicitudVecinal

        fecha = timezone.localdate() + timedelta(days=3)

        compromiso = Compromiso.objects.create(
            origen="Solicitud interna",
            solicitante="Vecino de prueba",
            territorio="Centro",
            fecha_comprometida=fecha,
            funcionario=self.funcionario,
            delegacion=self.delegacion,
            estado=Compromiso.ESTADO_INGRESADO,
        )

        solicitud = SolicitudVecinal.objects.create(
            rut_solicitante="12345678-5",
            relacion_vecinal="Presidente",
            canal=SolicitudVecinal.CANAL_PRESENCIAL,
            tipo=SolicitudVecinal.TIPO_GENERAL,
            categoria="Organizaciones comunitarias",
            descripcion="Solicitud de prueba",
            estado_solicitud=SolicitudVecinal.ESTADO_CREADO,
        )

        compromiso_vecinal = Compromiso.objects.create(
            origen="Solicitud vecinal",
            solicitante="Vecina de prueba",
            territorio="Centro",
            fecha_comprometida=fecha,
            funcionario=self.funcionario,
            delegacion=self.delegacion,
            estado=Compromiso.ESTADO_INGRESADO,
            solicitud_vecinal=solicitud,
        )

        self.client.force_login(self.usuario)

        respuesta = self.client.get(
            reverse("dashboard_detalle"),
            {
                "tipo": "agenda",
                "etiqueta": Compromiso.ESTADO_INGRESADO,
            },
        )

        self.assertEqual(respuesta.status_code, 200)

        filas = respuesta.json()["filas"]
        urls = {
            fila["codigo"]: fila["url"]
            for fila in filas
        }

        self.assertEqual(
            urls[f"COMP-{compromiso.pk}"],
            reverse(
                "agenda:compromiso_detail",
                args=[compromiso.pk],
            ),
        )

        self.assertEqual(
            urls[f"SOL-{solicitud.pk}"],
            reverse(
                "solicitudes:detalle",
                args=[solicitud.pk],
            ),
        )

        self.assertNotIn(
            f"COMP-{compromiso_vecinal.pk}",
            urls,
        )
