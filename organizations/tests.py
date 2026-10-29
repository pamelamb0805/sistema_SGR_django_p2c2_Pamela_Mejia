from datetime import date

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from core.exceptions import ReglaNegocioError

from .models import Cargo, Delegacion, Funcionario, FuncionarioRol, Rol, Usuario
from .services import CRUDDelegacion, CRUDFuncionario, CRUDRol, Seguridad

CLAVE = "Clave-Segura-2026"


class BaseTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.del1 = Delegacion.objects.create(
            nombre="Rural",
            direccion="Dirección de prueba 1",
            comuna="La Serena",
            ambito="Zona rural",
        )
        cls.del2 = Delegacion.objects.create(
            nombre="Centro",
            direccion="Dirección de prueba 2",
            comuna="La Serena",
            ambito="Casco urbano",
        )

        cls.cargo = Cargo.objects.create(
            nombre_cargo="Delegado",
            vigencia_desde=date(2026, 1, 1),
        )

        cls.roles = {
            nombre: Rol.objects.create(nombre_rol=nombre)
            for nombre in (
                "Administrador",
                "Coordinador",
                "Delegado",
                "Funcionario",
                "Verificador",
                "Consulta",
            )
        }

    
    def crear(self, ident, delegacion, rol, username=None):
        f = Funcionario.objects.create(identificador_institucional=ident, nombre=f"Func {ident}",
                                       cargo=self.cargo, delegacion=delegacion)
        FuncionarioRol.objects.create(funcionario=f, rol=self.roles[rol])
        if username:
            Usuario.objects.create_user(username, CLAVE, funcionario=f)
        return f


class ModeloTests(BaseTestCase):
    def test_delegacion_nombre_unico(self):
        with self.assertRaises(ValidationError):
            Delegacion(nombre="Rural", ambito="x").full_clean()

    def test_cargo_vigencia_invalida(self):
        with self.assertRaises(ValidationError):
            Cargo(nombre_cargo="X", vigencia_desde=date(2026, 5, 1), vigencia_hasta=date(2026, 4, 1)).full_clean()

    def test_usuario_inactivo_si_funcionario_inactivo(self):
        f = self.crear("F1", self.del1, "Funcionario", "u1")
        u = Usuario.objects.get(username="u1")
        self.assertTrue(u.is_active)
        f.estado = Funcionario.ESTADO_INACTIVO
        f.save()
        u.refresh_from_db()
        self.assertFalse(Usuario.objects.get(username="u1").is_active)

    def test_contrasenia_no_queda_en_texto_plano(self):
        self.crear("F1", self.del1, "Funcionario", "u1")
        self.assertNotEqual(Usuario.objects.get(username="u1").password, CLAVE)


class ServicioTests(BaseTestCase):
    def test_funcionario_requiere_al_menos_un_rol(self):
        f = Funcionario(identificador_institucional="N1", nombre="Nuevo", cargo=self.cargo, delegacion=self.del1)
        with self.assertRaises(ReglaNegocioError):
            CRUDFuncionario.crear_funcionario(f, [])
        self.assertFalse(Funcionario.objects.filter(identificador_institucional="N1").exists())

    def test_funcionario_con_varios_roles(self):
        f = Funcionario(identificador_institucional="N2", nombre="Nuevo", cargo=self.cargo, delegacion=self.del1)
        CRUDFuncionario.crear_funcionario(f, [self.roles["Funcionario"], self.roles["Verificador"]])
        self.assertEqual(f.funcionario_roles.count(), 2)
        CRUDRol.sincronizar_roles(f, [self.roles["Verificador"]])
        self.assertEqual(list(f.roles.values_list("nombre_rol", flat=True)), ["Verificador"])

    def test_no_elimina_rol_en_uso(self):
        self.crear("F1", self.del1, "Funcionario")
        with self.assertRaises(ReglaNegocioError):
            CRUDRol.eliminar_rol(self.roles["Funcionario"])

    def test_activar_desactivar_delegacion(self):
        CRUDDelegacion.activar_desactivar_delegacion(self.del1)
        self.del1.refresh_from_db()
        self.assertEqual(self.del1.estado, "Inactiva")
        CRUDDelegacion.activar_desactivar_delegacion(self.del1)
        self.del1.refresh_from_db()
        self.assertTrue(self.del1.activa)

    def test_seguridad_crear_usuario_y_credenciales(self):
        f = self.crear("F1", self.del1, "Funcionario")
        with self.assertRaises(ReglaNegocioError):
            Seguridad.crear_usuario(f, "u1", "123")          # contraseña débil
        Seguridad.crear_usuario(f, "u1", CLAVE)
        self.assertTrue(Seguridad.verificar_credenciales("u1", CLAVE)["valido"])
        self.assertFalse(Seguridad.verificar_credenciales("u1", "otra")["valido"])
        with self.assertRaises(ReglaNegocioError):           # ya tiene acceso
            Seguridad.crear_usuario(f, "u2", CLAVE)

    def test_eliminar_funcionario_borra_su_acceso(self):
        f = self.crear("F1", self.del1, "Funcionario", "u1")
        CRUDFuncionario.eliminar_funcionario(f)
        self.assertFalse(Usuario.objects.filter(username="u1").exists())


class VistaTests(BaseTestCase):
    def setUp(self):
        self.admin = self.crear("A1", self.del1, "Administrador", "admin1")
        self.delegado = self.crear("D1", self.del1, "Delegado", "deleg1")
        self.normal = self.crear("N1", self.del1, "Funcionario", "normal1")
        self.otro = self.crear("O1", self.del2, "Funcionario")

    def test_funcionario_comun_no_puede_crear_delegacion(self):
        self.client.login(username="normal1", password=CLAVE)
        r = self.client.post(reverse("organizations:delegacion_create"),
                             {"nombre": "Hack", "ambito": "x", "estado": "Activa"})
        self.assertRedirects(r, reverse("dashboard"), fetch_redirect_response=False)
        self.assertFalse(Delegacion.objects.filter(nombre="Hack").exists())

    def test_admin_crea_delegacion(self):
        self.client.login(username="admin1", password=CLAVE)

        respuesta = self.client.post(
            reverse("organizations:delegacion_create"),
            {
                "nombre": "Costa",
                "direccion": "Avenida Costera 123",
                "comuna": "La Serena",
                "ambito": "Borde costero",
                "estado": "Activa",
            },
        )

        self.assertRedirects(
            respuesta,
            reverse("organizations:delegacion_list"),
            fetch_redirect_response=False,
        )

        self.assertTrue(
            Delegacion.objects.filter(nombre="Costa").exists()
        )

    def test_nombre_delegacion_duplicado_se_rechaza(self):
        self.client.login(username="admin1", password=CLAVE)

        respuesta = self.client.post(
            reverse("organizations:delegacion_create"),
            {
                "nombre": "Rural",
                "direccion": "Otra dirección",
                "comuna": "La Serena",
                "ambito": "Zona de prueba",
                "estado": "Activa",
            },
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(
            Delegacion.objects.filter(nombre="Rural").count(),
            1,
        )

    def test_delegado_solo_ve_su_delegacion(self):
        self.client.login(username="deleg1", password=CLAVE)
        r = self.client.get(reverse("organizations:funcionario_list"))
        ids = {f.pk for f in r.context["funcionarios"]}
        self.assertIn(self.normal.pk, ids)
        self.assertNotIn(self.otro.pk, ids)

    def test_delegado_no_accede_a_funcionario_de_otra_delegacion(self):
        self.client.login(username="deleg1", password=CLAVE)
        r = self.client.get(reverse("organizations:funcionario_detail", args=[self.otro.pk]))
        self.assertEqual(r.status_code, 404)

    def test_funcionario_comun_no_ve_listado(self):
        self.client.login(username="normal1", password=CLAVE)
        r = self.client.get(reverse("organizations:funcionario_list"))
        self.assertRedirects(r, reverse("dashboard"), fetch_redirect_response=False)

    def test_admin_crea_funcionario_con_roles(self):
        self.client.login(username="admin1", password=CLAVE)
        r = self.client.post(reverse("organizations:funcionario_create"), {
            "identificador_institucional": "Z9", "nombre": "Zoe", "estado": "Activo",
            "cargo": self.cargo.pk, "delegacion": self.del1.pk,
            "roles": [self.roles["Funcionario"].pk, self.roles["Verificador"].pk]})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Funcionario.objects.get(identificador_institucional="Z9").funcionario_roles.count(), 2)
