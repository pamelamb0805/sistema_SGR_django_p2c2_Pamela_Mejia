from datetime import date

from django.test import TestCase, RequestFactory
from django.contrib import admin
from django.core.management import call_command
from io import StringIO

from core.mixins import (
    ROL_ADMIN_SISTEMA, get_alcances, get_permisos, tiene_rol,
    filtrar_por_ambito,
)
from organizations.models import Cargo, Delegacion, Funcionario, FuncionarioRol, Rol, Usuario
from organizations.account_utils import crear_cuenta_funcionario
from organizations.services import CRUDFuncionario
from organizations.admin import FuncionarioAdmin


class AccountAndAdminSistemaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.d1 = Delegacion.objects.create(nombre="Centro", direccion="A", comuna="La Serena", ambito="Urbano")
        cls.d2 = Delegacion.objects.create(nombre="Rural", direccion="B", comuna="La Serena", ambito="Rural")
        cls.cargo = Cargo.objects.create(nombre_cargo="Funcionario", vigencia_desde=date(2026, 1, 1))
        cls.admin_sistema = Rol.objects.create(nombre_rol=ROL_ADMIN_SISTEMA, permisos=["*"], alcance_autorizado="global")
        cls.rol_funcionario = Rol.objects.create(nombre_rol="Funcionario", permisos=["agenda.ver"], alcance_autorizado="propia")

    def crear_funcionario(self, ident, delegacion):
        return Funcionario.objects.create(identificador_institucional=ident, nombre=ident, cargo=self.cargo, delegacion=delegacion)

    def test_crear_cuenta_automaticamente_con_password_inutilizable(self):
        f = self.crear_funcionario("FUNC-001", self.d1)
        usuario, creada = crear_cuenta_funcionario(f)
        self.assertTrue(creada)
        self.assertEqual(usuario.funcionario_id, f.pk)
        self.assertTrue(usuario.has_usable_password() is False)
        self.assertTrue(usuario.activo_acceso)

    def test_crear_cuenta_es_idempotente_y_no_duplica(self):
        f = self.crear_funcionario("FUNC-002", self.d1)
        primera, creada = crear_cuenta_funcionario(f)
        segunda, creada_otra_vez = crear_cuenta_funcionario(f)
        self.assertTrue(creada)
        self.assertFalse(creada_otra_vez)
        self.assertEqual(primera.pk, segunda.pk)
        self.assertEqual(Usuario.objects.filter(funcionario=f).count(), 1)

    def test_servicio_de_alta_crea_automaticamente_la_cuenta_vinculada(self):
        f = Funcionario(identificador_institucional="FUNC-003", nombre="FUNC-003", cargo=self.cargo, delegacion=self.d1)
        CRUDFuncionario.crear_funcionario(f, [self.rol_funcionario])
        usuario = Usuario.objects.get(funcionario=f)
        self.assertFalse(usuario.has_usable_password())
        self.assertTrue(usuario.activo_acceso)

    def test_alta_directa_en_django_admin_crea_cuenta_vinculada(self):
        root = Usuario.objects.create_superuser("ROOT-ADMIN-TEST", "Clave-Segura-2026")
        request = RequestFactory().post("/admin/organizations/funcionario/add/")
        request.user = root
        funcionario = Funcionario(
            identificador_institucional="ADMIN-FORM-001",
            nombre="Alta desde Django Admin",
            cargo=self.cargo,
            delegacion=self.d1,
        )
        admin_funcionario = FuncionarioAdmin(Funcionario, admin.site)
        admin_funcionario.save_model(request, funcionario, None, False)
        cuenta = Usuario.objects.get(funcionario=funcionario)
        self.assertTrue(cuenta.username.startswith("sgr_"))
        self.assertFalse(cuenta.has_usable_password())

    def test_comando_antiguos_es_dry_run_por_defecto_y_no_crea_cuentas(self):
        f = self.crear_funcionario("LEGACY-001", self.d1)
        salida = StringIO()
        call_command("asociar_usuarios_funcionarios", stdout=salida)
        self.assertFalse(Usuario.objects.filter(funcionario=f).exists())
        self.assertIn("No se modificó la base de datos", salida.getvalue())

    def test_comando_antiguos_aplica_sin_duplicar_y_preserva_root(self):
        f = self.crear_funcionario("LEGACY-002", self.d1)
        root_funcionario = self.crear_funcionario("ROOT-LINK", self.d1)
        root = Usuario.objects.create_superuser("ROOT", "Clave-Segura-2026", funcionario=root_funcionario)
        call_command("asociar_usuarios_funcionarios", "--apply", stdout=StringIO())
        call_command("asociar_usuarios_funcionarios", "--apply", stdout=StringIO())
        self.assertEqual(Usuario.objects.filter(funcionario=f).count(), 1)
        root.refresh_from_db()
        self.assertTrue(root.is_superuser)
        self.assertEqual(root.funcionario_id, root_funcionario.pk)
        self.assertEqual(root.username, "ROOT")

    def test_admin_sistema_no_conserva_acceso_si_funcionario_se_inactiva(self):
        f = self.crear_funcionario("ADMIN-INACTIVO", self.d1)
        FuncionarioRol.objects.create(funcionario=f, rol=self.admin_sistema)
        user = Usuario.objects.create_user("admin_sistema_inactivo", "Clave-Segura-2026", funcionario=f)
        f.estado = Funcionario.ESTADO_INACTIVO
        f.save(update_fields=["estado"])
        user.refresh_from_db()
        self.assertFalse(user.is_active)
        self.assertFalse(tiene_rol(user, "Administrador"))
        self.assertEqual(get_permisos(user), set())
        self.assertEqual(get_alcances(user), set())

    def test_admin_sistema_concede_permisos_roles_y_ambito_global_sin_superuser(self):
        f = self.crear_funcionario("ADMIN-TEST", self.d1)
        FuncionarioRol.objects.create(funcionario=f, rol=self.admin_sistema)
        user = Usuario.objects.create_user("admin_sistema_test", "Clave-Segura-2026", funcionario=f)
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.is_staff)
        self.assertTrue(tiene_rol(user, "Administrador"))
        self.assertTrue(tiene_rol(user, "Verificador"))
        self.assertIn("*", get_permisos(user))
        self.assertIn("global", get_alcances(user))
        visibles = filtrar_por_ambito(Delegacion.objects.all(), user, "id_delegacion")
        self.assertSetEqual(set(visibles.values_list("pk", flat=True)), {self.d1.pk, self.d2.pk})
