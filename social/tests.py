
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.utils import timezone

from catalogs.models import Catalogo
from core.exceptions import ReglaNegocioError
from organizations.models import (
    Cargo,
    Delegacion,
    Funcionario,
    FuncionarioRol,
    Rol,
    Usuario,
)

from .models import AtencionSocial, UsuarioSocial
from .services import (
    CRUDAtencionSocial,
    CRUDUsuarioSocial,
    casos_visibles,
    estadisticas_atenciones,
    gestiones_visibles,
)

CLAVE = "Clave-Segura-2026"
HOY = timezone.localdate()


def dias(n):
    return HOY + timedelta(days=n)


@override_settings(
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"]
)
class BaseTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.deleg = Delegacion.objects.create(
            nombre="Gestión Social",
            direccion="Calle Uno 100",
            comuna="La Serena",
            ambito="Social",
        )

        cls.deleg2 = Delegacion.objects.create(
            nombre="Centro",
            direccion="Calle Dos 200",
            comuna="La Serena",
            ambito="Social",
        )

        cls.cargo = Cargo.objects.create(
            nombre_cargo="Trabajador social",
            vigencia_desde=dias(-400),
        )

        cls.tipo1 = Catalogo.objects.create(
            tipo_catalogo=Catalogo.TIPO_ATENCION,
            nombre="Orientación social",
            area="Social",
        )

        cls.tipo2 = Catalogo.objects.create(
            tipo_catalogo=Catalogo.TIPO_ATENCION,
            nombre="Seguimiento social",
            area="Social",
        )

        cls.tipo3 = Catalogo.objects.create(
            tipo_catalogo=Catalogo.TIPO_ATENCION,
            nombre="Cierre de caso",
            area="Social",
        )

        cls.sub1 = Catalogo.objects.create(
            tipo_catalogo=Catalogo.TIPO_SUBATENCION,
            nombre="Orientación general",
            area="Social",
            tipo_atencion_padre=cls.tipo1,
        )

        cls.sub2 = Catalogo.objects.create(
            tipo_catalogo=Catalogo.TIPO_SUBATENCION,
            nombre="Seguimiento familiar",
            area="Social",
            tipo_atencion_padre=cls.tipo2,
        )

        cls.sub3 = Catalogo.objects.create(
            tipo_catalogo=Catalogo.TIPO_SUBATENCION,
            nombre="Cierre administrativo",
            area="Social",
            tipo_atencion_padre=cls.tipo3,
        )

        cls.tipo_inactivo = Catalogo.objects.create(
            tipo_catalogo=Catalogo.TIPO_ATENCION,
            nombre="Atención antigua",
            area="Social",
            estado=Catalogo.ESTADO_INACTIVO,
        )

        cls.tipo_actividad = Catalogo.objects.create(
            tipo_catalogo=Catalogo.TIPO_ACTIVIDAD,
            nombre="Visita",
            area="Social",
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

    def crear_func(self, ident, rol="Funcionario", deleg=None):
        funcionario = Funcionario.objects.create(
            identificador_institucional=ident,
            nombre=f"Funcionario {ident}",
            cargo=self.cargo,
            delegacion=deleg or self.deleg,
        )

        FuncionarioRol.objects.create(
            funcionario=funcionario,
            rol=self.roles[rol],
        )

        usuario = Usuario.objects.create_user(
            ident.lower(),
            CLAVE,
            funcionario=funcionario,
        )

        return funcionario, usuario

    def gestion(
        self,
        tipo=None,
        sub=None,
        fecha=None,
        estado=AtencionSocial.ESTADO_REALIZADA,
        resultado="Se orientó a la persona",
    ):
        tipo = tipo or self.tipo1

        sub = sub or {
            self.tipo1.pk: self.sub1,
            self.tipo2.pk: self.sub2,
            self.tipo3.pk: self.sub3,
        }[tipo.pk]

        return AtencionSocial(
            tipo_atencion=tipo,
            subatencion=sub,
            descripcion="Descripción de la atención realizada",
            fecha=fecha or HOY,
            estado=estado,
            resultado=resultado,
        )

    def caso(self, actor, nombre="María Pérez", territorio="Sector Norte", **kw):
        return CRUDUsuarioSocial.crear_caso(
            UsuarioSocial(
                nombre=nombre,
                territorio=territorio,
            ),
            self.gestion(**kw),
            actor,
        )

    def agregar(self, caso, actor, **kw):
        gestion = self.gestion(**kw)
        gestion.usuario = caso
        return CRUDAtencionSocial.registrar_gestion(gestion, actor)


class CasoServicioTests(BaseTestCase):

    def setUp(self):
        self.funcionario, self.usuario = self.crear_func("F1")

    def test_crea_caso_con_primera_gestion(self):
        caso = self.caso(self.usuario)

        self.assertEqual(caso.estado_caso, UsuarioSocial.ESTADO_ABIERTO)
        self.assertEqual(caso.delegacion, self.deleg)
        self.assertEqual(caso.fecha_primer_registro, HOY)

        gestion = caso.gestiones.get()

        self.assertEqual(gestion.numero_gestion, 1)
        self.assertEqual(gestion.funcionario, self.funcionario)
        self.assertEqual(gestion.delegacion, self.deleg)

    def test_error_en_gestion_no_deja_caso_huerfano(self):
        with self.assertRaises(ReglaNegocioError):
            self.caso(self.usuario, resultado="")

        self.assertEqual(UsuarioSocial.objects.count(), 0)

    def test_no_duplica_identificacion_principal(self):
        caso = self.caso(self.usuario)

        with self.assertRaises(ReglaNegocioError):
            self.caso(
                self.usuario,
                nombre="maría pérez",
                territorio="SECTOR NORTE",
                tipo=self.tipo2,
            )

        self.assertEqual(UsuarioSocial.objects.count(), 1)
        self.assertEqual(caso.gestiones.count(), 1)

    def test_misma_persona_en_otra_delegacion_es_otro_caso(self):
        _, otro_usuario = self.crear_func(
            "FO",
            deleg=self.deleg2,
        )

        self.caso(self.usuario)
        self.caso(otro_usuario)

        self.assertEqual(UsuarioSocial.objects.count(), 2)

    def test_solo_operativos_crean_casos(self):
        _, verificador = self.crear_func("V1", "Verificador")
        _, administrador = self.crear_func("A1", "Administrador")

        for usuario in (verificador, administrador):
            with self.assertRaises(ReglaNegocioError):
                self.caso(usuario)


class GestionServicioTests(BaseTestCase):

    def setUp(self):
        self.funcionario, self.usuario = self.crear_func("F1")
        self.caso_social = self.caso(
            self.usuario,
            fecha=dias(-10),
        )

    def test_maximo_tres_gestiones(self):
        self.agregar(
            self.caso_social,
            self.usuario,
            tipo=self.tipo2,
            fecha=dias(-5),
        )

        self.agregar(
            self.caso_social,
            self.usuario,
            tipo=self.tipo3,
            fecha=dias(-1),
        )

        gestiones = CRUDUsuarioSocial.mostrar_historial_gestiones(
            self.caso_social.pk
        )

        self.assertEqual(
            [g.numero_gestion for g in gestiones],
            [1, 2, 3],
        )

        self.assertFalse(
            CRUDAtencionSocial.validar_maximo_tres_gestiones(
                self.caso_social.pk
            )
        )

        with self.assertRaises(ReglaNegocioError):
            self.agregar(
                self.caso_social,
                self.usuario,
                tipo=self.tipo1,
            )

        self.assertEqual(self.caso_social.gestiones.count(), 3)
        self.assertEqual(UsuarioSocial.objects.count(), 1)

    def test_limite_configurable(self):
        with override_settings(SGR_MAX_GESTIONES_SOCIAL=1):
            with self.assertRaises(ReglaNegocioError):
                self.agregar(
                    self.caso_social,
                    self.usuario,
                    tipo=self.tipo2,
                )

    def test_tipo_atencion_repetido_rechazado(self):
        with self.assertRaises(ReglaNegocioError):
            self.agregar(
                self.caso_social,
                self.usuario,
                tipo=self.tipo1,
                fecha=dias(-1),
            )

    def test_subatencion_de_otro_tipo_rechazada(self):
        gestion = self.gestion(
            tipo=self.tipo2,
            sub=self.sub1,
            fecha=dias(-1),
        )
        gestion.usuario = self.caso_social

        with self.assertRaises(ReglaNegocioError):
            CRUDAtencionSocial.registrar_gestion(
                gestion,
                self.usuario,
            )

    def test_fechas_en_orden_cronologico(self):
        with self.assertRaises(ReglaNegocioError):
            self.agregar(
                self.caso_social,
                self.usuario,
                tipo=self.tipo2,
                fecha=dias(-20),
            )

        self.agregar(
            self.caso_social,
            self.usuario,
            tipo=self.tipo2,
            fecha=dias(-10),
        )

    def test_realizada_no_puede_tener_fecha_futura(self):
        with self.assertRaises(ReglaNegocioError):
            self.agregar(
                self.caso_social,
                self.usuario,
                tipo=self.tipo2,
                fecha=dias(2),
            )

    def test_programada_puede_tener_fecha_futura(self):
        gestion = self.agregar(
            self.caso_social,
            self.usuario,
            tipo=self.tipo2,
            fecha=dias(3),
            estado=AtencionSocial.ESTADO_PROGRAMADA,
            resultado="",
        )

        self.assertEqual(
            gestion.estado,
            AtencionSocial.ESTADO_PROGRAMADA,
        )

    def test_catalogo_inactivo_rechazado(self):
        sub_inactiva = Catalogo.objects.create(
            tipo_catalogo=Catalogo.TIPO_SUBATENCION,
            nombre="Subatención inactiva",
            area="Social",
            tipo_atencion_padre=self.tipo2,
            estado=Catalogo.ESTADO_INACTIVO,
        )

        gestion = self.gestion(
            tipo=self.tipo2,
            sub=sub_inactiva,
            fecha=dias(-1),
        )
        gestion.usuario = self.caso_social

        with self.assertRaises(ReglaNegocioError):
            CRUDAtencionSocial.registrar_gestion(
                gestion,
                self.usuario,
            )

    def test_caso_cerrado_no_admite_gestiones(self):
        CRUDUsuarioSocial.cambiar_estado_caso(
            self.caso_social,
            UsuarioSocial.ESTADO_CERRADO,
            self.usuario,
        )

        with self.assertRaises(ReglaNegocioError):
            self.agregar(
                self.caso_social,
                self.usuario,
                tipo=self.tipo2,
            )

    def test_funcionario_no_puede_reabrir(self):
        CRUDUsuarioSocial.cambiar_estado_caso(
            self.caso_social,
            UsuarioSocial.ESTADO_CERRADO,
            self.usuario,
        )

        with self.assertRaises(ReglaNegocioError):
            CRUDUsuarioSocial.cambiar_estado_caso(
                self.caso_social,
                UsuarioSocial.ESTADO_ABIERTO,
                self.usuario,
            )

    def test_delegado_puede_reabrir(self):
        CRUDUsuarioSocial.cambiar_estado_caso(
            self.caso_social,
            UsuarioSocial.ESTADO_CERRADO,
            self.usuario,
        )

        _, delegado = self.crear_func("D1", "Delegado")

        CRUDUsuarioSocial.cambiar_estado_caso(
            self.caso_social,
            UsuarioSocial.ESTADO_ABIERTO,
            delegado,
        )

        self.assertEqual(
            UsuarioSocial.objects.get(pk=self.caso_social.pk).estado_caso,
            UsuarioSocial.ESTADO_ABIERTO,
        )

    def test_otra_delegacion_no_puede_escribir(self):
        _, otro_usuario = self.crear_func(
            "FO",
            deleg=self.deleg2,
        )

        with self.assertRaises(ReglaNegocioError):
            self.agregar(
                self.caso_social,
                otro_usuario,
                tipo=self.tipo2,
            )

    def test_modificar_gestion(self):
        gestion2 = self.agregar(
            self.caso_social,
            self.usuario,
            tipo=self.tipo2,
            fecha=dias(-5),
        )

        gestion3 = self.agregar(
            self.caso_social,
            self.usuario,
            tipo=self.tipo3,
            fecha=dias(-2),
        )

        gestion2.tipo_atencion = self.tipo3

        with self.assertRaises(ReglaNegocioError):
            CRUDAtencionSocial.modificar_gestion(
                gestion2,
                self.usuario,
            )

        gestion2.refresh_from_db()
        gestion2.fecha = dias(-1)

        with self.assertRaises(ReglaNegocioError):
            CRUDAtencionSocial.modificar_gestion(
                gestion2,
                self.usuario,
            )

        gestion2.refresh_from_db()
        gestion2.fecha = dias(-3)
        gestion2.resultado = "Visita reprogramada"

        CRUDAtencionSocial.modificar_gestion(
            gestion2,
            self.usuario,
        )

        gestion2.refresh_from_db()

        self.assertEqual(gestion2.fecha, dias(-3))
        self.assertEqual(gestion3.numero_gestion, 3)


class EstadisticasYVisibilidadTests(BaseTestCase):

    def test_estadisticas_cuentan_solo_gestiones_realizadas(self):
        _, usuario = self.crear_func("F1")

        caso1 = self.caso(
            usuario,
            nombre="Ana",
            fecha=dias(-9),
        )

        self.agregar(
            caso1,
            usuario,
            tipo=self.tipo2,
            fecha=dias(-3),
        )

        self.agregar(
            caso1,
            usuario,
            tipo=self.tipo3,
            fecha=dias(5),
            estado=AtencionSocial.ESTADO_PROGRAMADA,
            resultado="",
        )

        caso2 = self.caso(
            usuario,
            nombre="Luis",
            tipo=self.tipo1,
            fecha=dias(-2),
        ) if False else None

        estadisticas = estadisticas_atenciones(
            gestiones_visibles(usuario)
        )

        self.assertEqual(estadisticas["total_gestiones"], 2)
        self.assertEqual(estadisticas["total_personas"], 1)

        self.assertEqual(
            sum(x["total"] for x in estadisticas["por_tipo"]),
            2,
        )

        self.assertEqual(
            sum(x["total"] for x in estadisticas["por_subatencion"]),
            2,
        )

    def test_visibilidad_por_rol_y_delegacion(self):
        _, usuario1 = self.crear_func("F1")
        _, delegado = self.crear_func("D1", "Delegado")
        _, administrador = self.crear_func("A1", "Administrador")
        _, verificador = self.crear_func("V1", "Verificador")
        _, consulta = self.crear_func("C1", "Consulta")
        _, usuario_otro = self.crear_func(
            "FO",
            deleg=self.deleg2,
        )

        self.caso(usuario1, nombre="Ana")
        self.caso(usuario_otro, nombre="Beto")

        self.assertEqual(casos_visibles(usuario1).count(), 1)
        self.assertEqual(casos_visibles(delegado).count(), 1)
        self.assertEqual(casos_visibles(administrador).count(), 2)
        self.assertEqual(casos_visibles(verificador).count(), 0)
        self.assertEqual(casos_visibles(consulta).count(), 0)
