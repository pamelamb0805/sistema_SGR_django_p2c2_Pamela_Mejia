from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from catalogs.models import Catalogo
from core.exceptions import ReglaNegocioError
from organizations.models import Cargo, Delegacion, Funcionario, FuncionarioRol, Rol, Usuario

from .models import AtencionSocial, UsuarioSocial
from .services import (
    CRUDAtencionSocial, CRUDUsuarioSocial, casos_visibles, estadisticas_atenciones, gestiones_visibles,
)

CLAVE = "Clave-Segura-2026"
HOY = timezone.localdate()


def dias(n):
    return HOY + timedelta(days=n)


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class BaseTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.deleg = Delegacion.objects.create(nombre="Gestión Social", ambito="x")
        cls.deleg2 = Delegacion.objects.create(nombre="Centro", ambito="y")
        cls.cargo = Cargo.objects.create(nombre_cargo="Trabajador social", vigencia_desde=dias(-400))
        cls.cat = Catalogo.objects.create(tipo_catalogo="Atención", nombre="Orientación social", area="Social")
        cls.subcat = Catalogo.objects.create(tipo_catalogo="Subatención", nombre="Subsidio", area="Social")
        cls.cat_inactivo = Catalogo.objects.create(tipo_catalogo="Atención", nombre="Antigua", area="Social",
                                                   estado="Inactivo")
        cls.cat_actividad = Catalogo.objects.create(tipo_catalogo="Actividad", nombre="Visita", area="Social")
        cls.roles = {n: Rol.objects.create(nombre_rol=n) for n in
                     ("Administrador", "Coordinador", "Delegado", "Funcionario", "Verificador", "Consulta")}

    def crear_func(self, ident, rol="Funcionario", deleg=None):
        f = Funcionario.objects.create(identificador_institucional=ident, nombre=f"F {ident}",
                                       cargo=self.cargo, delegacion=deleg or self.deleg)
        FuncionarioRol.objects.create(funcionario=f, rol=self.roles[rol])
        return f, Usuario.objects.create_user(ident.lower(), CLAVE, funcionario=f)

    def gestion(self, tipo="Orientación", fecha=None, estado="Realizada", resultado="Se orientó a la persona",
                catalogo=None):
        return AtencionSocial(tipo_atencion=tipo, fecha=fecha or HOY, estado=estado, resultado=resultado,
                              catalogo=catalogo or self.cat)

    def caso(self, actor, nombre="María Pérez", territorio="Sector Norte", **kw):
        return CRUDUsuarioSocial.crear_caso(UsuarioSocial(nombre=nombre, territorio=territorio),
                                            self.gestion(**kw), actor)

    def agregar(self, caso, actor, **kw):
        g = self.gestion(**kw)
        g.usuario = caso
        return CRUDAtencionSocial.registrar_gestion(g, actor)


class CasoServicioTests(BaseTestCase):
    def setUp(self):
        self.f, self.u = self.crear_func("F1")

    def test_crea_caso_con_primera_gestion(self):
        c = self.caso(self.u)
        self.assertEqual((c.estado_caso, c.delegacion, c.fecha_primer_registro), ("Abierto", self.deleg, HOY))
        g = c.gestiones.get()
        self.assertEqual((g.numero_gestion, g.funcionario), (1, self.f))

    def test_error_en_la_gestion_no_deja_caso_huerfano(self):
        with self.assertRaises(ReglaNegocioError):
            self.caso(self.u, resultado="")        # el modelo exige resultado si fue realizada
        self.assertEqual(UsuarioSocial.objects.count(), 0)

    def test_no_duplica_la_identificacion_principal(self):
        c = self.caso(self.u)
        with self.assertRaises(ReglaNegocioError) as ctx:
            self.caso(self.u, nombre="maría pérez", territorio="SECTOR NORTE", tipo="Seguimiento")
        self.assertIn(str(c.pk), str(ctx.exception))
        self.assertEqual(UsuarioSocial.objects.count(), 1)
        self.caso(self.u, nombre="María Pérez", territorio="Sector Sur", tipo="Seguimiento")   # otro territorio: ok

    def test_misma_persona_en_otra_delegacion_es_otro_caso(self):
        _, uo = self.crear_func("FO", deleg=self.deleg2)
        self.caso(self.u)
        self.caso(uo)
        self.assertEqual(UsuarioSocial.objects.count(), 2)

    def test_solo_operativos_crean_casos(self):
        _, va = self.crear_func("V1", "Verificador")
        _, ua = self.crear_func("A1", "Administrador")
        for u in (va, ua):
            with self.assertRaises(ReglaNegocioError):
                self.caso(u)


class GestionServicioTests(BaseTestCase):
    def setUp(self):
        self.f, self.u = self.crear_func("F1")
        self.c = self.caso(self.u, fecha=dias(-10))

    def test_ca04_tres_gestiones_diferenciadas_y_cuarta_rechazada(self):
        self.agregar(self.c, self.u, tipo="Visita domiciliaria", fecha=dias(-5))
        self.agregar(self.c, self.u, tipo="Cierre de caso", fecha=dias(-1), catalogo=self.subcat)
        secuencia = CRUDUsuarioSocial.mostrar_historial_gestiones(self.c.pk)
        self.assertEqual([g.numero_gestion for g in secuencia], [1, 2, 3])
        self.assertFalse(CRUDAtencionSocial.validar_maximo_tres_gestiones(self.c.pk))
        with self.assertRaises(ReglaNegocioError):
            self.agregar(self.c, self.u, tipo="Seguimiento")
        self.assertEqual(AtencionSocial.objects.filter(usuario=self.c).count(), 3)
        self.assertEqual(UsuarioSocial.objects.count(), 1)       # la identificación no se duplicó

    def test_limite_configurable(self):
        with override_settings(SGR_MAX_GESTIONES_SOCIAL=1):
            with self.assertRaises(ReglaNegocioError):
                self.agregar(self.c, self.u, tipo="Seguimiento")

    def test_tipo_repetido_rechazado(self):
        with self.assertRaises(ReglaNegocioError):
            self.agregar(self.c, self.u, tipo="Orientación", fecha=dias(-1))

    def test_fechas_en_orden_cronologico(self):
        with self.assertRaises(ReglaNegocioError):
            self.agregar(self.c, self.u, tipo="Seguimiento", fecha=dias(-20))
        self.agregar(self.c, self.u, tipo="Seguimiento", fecha=dias(-10))     # misma fecha: permitido

    def test_estado_y_fecha_coherentes(self):
        with self.assertRaises(ReglaNegocioError):                # realizada en el futuro
            self.agregar(self.c, self.u, tipo="Seguimiento", fecha=dias(2))
        with self.assertRaises(ReglaNegocioError):                # programada en el pasado
            self.agregar(self.c, self.u, tipo="Seguimiento", fecha=dias(-1), estado="Programada", resultado="")
        g = self.agregar(self.c, self.u, tipo="Seguimiento", fecha=dias(3), estado="Programada", resultado="")
        self.assertEqual(g.estado, "Programada")

    def test_catalogo_invalido(self):
        for cat in (self.cat_inactivo, self.cat_actividad):
            with self.assertRaises(ReglaNegocioError):
                self.agregar(self.c, self.u, tipo="Seguimiento", catalogo=cat)

    def test_caso_cerrado_no_admite_gestiones_hasta_reabrir(self):
        CRUDUsuarioSocial.cambiar_estado_caso(self.c, "Cerrado", self.u)
        with self.assertRaises(ReglaNegocioError):
            self.agregar(self.c, self.u, tipo="Seguimiento")
        with self.assertRaises(ReglaNegocioError):                       # funcionario común no reabre
            CRUDUsuarioSocial.cambiar_estado_caso(self.c, "Abierto", self.u)
        _, ud = self.crear_func("D1", "Delegado")
        CRUDUsuarioSocial.cambiar_estado_caso(self.c, "Abierto", ud)
        self.agregar(self.c, self.u, tipo="Seguimiento")

    def test_otra_delegacion_no_escribe(self):
        _, uo = self.crear_func("FO", deleg=self.deleg2)
        with self.assertRaises(ReglaNegocioError):
            self.agregar(self.c, uo, tipo="Seguimiento")

    def test_modificar_gestion(self):
        g2 = self.agregar(self.c, self.u, tipo="Visita domiciliaria", fecha=dias(-5))
        g3 = self.agregar(self.c, self.u, tipo="Cierre de caso", fecha=dias(-2))
        g2.tipo_atencion = "Cierre de caso"                              # tipo ya usado
        with self.assertRaises(ReglaNegocioError):
            CRUDAtencionSocial.modificar_gestion(g2, self.u)
        g2 = AtencionSocial.objects.get(pk=g2.pk)
        g2.fecha = dias(-1)                                              # posterior a la gestión 3
        with self.assertRaises(ReglaNegocioError):
            CRUDAtencionSocial.modificar_gestion(g2, self.u)
        g2 = AtencionSocial.objects.get(pk=g2.pk)
        g2.fecha, g2.resultado = dias(-3), "Visita reprogramada"
        CRUDAtencionSocial.modificar_gestion(g2, self.u)
        self.assertEqual(AtencionSocial.objects.get(pk=g2.pk).fecha, dias(-3))
        self.assertEqual(g3.numero_gestion, 3)

    def test_modelo_exige_resultado_si_realizada(self):
        with self.assertRaises(ValidationError):
            AtencionSocial(usuario=self.c, tipo_atencion="Seguimiento", fecha=HOY, estado="Realizada",
                           resultado="", catalogo=self.cat, funcionario=self.f, numero_gestion=2).full_clean()


class EstadisticasYVisibilidadTests(BaseTestCase):
    def test_estadisticas_cuentan_cada_gestion_realizada_una_sola_vez(self):
        _, u1 = self.crear_func("F1")
        c1 = self.caso(u1, nombre="Ana", fecha=dias(-9))
        self.agregar(c1, u1, tipo="Seguimiento", fecha=dias(-3))
        self.agregar(c1, u1, tipo="Cierre de caso", fecha=dias(5), estado="Programada", resultado="")
        c2 = self.caso(u1, nombre="Luis", fecha=dias(-2), tipo="Derivación a red", catalogo=self.subcat)
        stats = estadisticas_atenciones(gestiones_visibles(u1))
        self.assertEqual(stats["total_gestiones"], 3)         # la programada no cuenta
        self.assertEqual(stats["total_personas"], 2)
        self.assertEqual(sum(t["total"] for t in stats["por_tipo"]), 3)
        self.assertEqual(sum(t["total"] for t in stats["por_catalogo"]), 3)
        self.assertEqual(c2.gestiones.count(), 1)

    def test_visibilidad_por_rol_y_delegacion(self):
        _, u1 = self.crear_func("F1")
        _, ud = self.crear_func("D1", "Delegado")
        _, ua = self.crear_func("A1", "Administrador")
        _, uv = self.crear_func("V1", "Verificador")
        _, uc = self.crear_func("C1", "Consulta")
        _, uo = self.crear_func("FO", deleg=self.deleg2)
        self.caso(u1, nombre="Ana")
        self.caso(uo, nombre="Beto")
        self.assertEqual(casos_visibles(u1).count(), 1)
        self.assertEqual(casos_visibles(ud).count(), 1)
        self.assertEqual(casos_visibles(ua).count(), 2)
        self.assertEqual(casos_visibles(uv).count(), 0)        # privacidad: sin acceso
        self.assertEqual(casos_visibles(uc).count(), 0)


class VistaTests(BaseTestCase):
    def setUp(self):
        self.f, self.u = self.crear_func("F1")
        self.fo, self.uo = self.crear_func("FO", deleg=self.deleg2)
        self.d, self.ud = self.crear_func("D1", "Delegado")
        self.v, self.uv = self.crear_func("V1", "Verificador")
        self.a, self.ua = self.crear_func("A1", "Administrador")

    def datos_caso(self, **extra):
        d = {"nombre": "María Pérez", "territorio": "Sector Norte", "tipo_atencion": "Orientación",
             "catalogo": self.cat.pk, "fecha": HOY.isoformat(), "estado": "Realizada", "resultado": "Orientada"}
        d.update(extra)
        return d

    def test_funcionario_crea_caso(self):
        self.client.login(username="f1", password=CLAVE)
        r = self.client.post(reverse("social:caso_create"), self.datos_caso())
        caso = UsuarioSocial.objects.get()
        self.assertRedirects(r, reverse("social:caso_detail", args=[caso.pk]), fetch_redirect_response=False)
        self.assertEqual(caso.gestiones.count(), 1)

    def test_duplicado_muestra_error_y_no_crea(self):
        self.caso(self.u)
        self.client.login(username="f1", password=CLAVE)
        r = self.client.post(reverse("social:caso_create"), self.datos_caso())
        self.assertEqual(r.status_code, 200)
        self.assertEqual(UsuarioSocial.objects.count(), 1)

    def test_roles_sin_acceso_son_denegados(self):
        for usuario in ("v1",):
            self.client.login(username=usuario, password=CLAVE)
            r = self.client.get(reverse("social:caso_list"))
            self.assertRedirects(r, reverse("dashboard"), fetch_redirect_response=False)
            self.client.logout()

    def test_otra_delegacion_recibe_404(self):
        c = self.caso(self.u)
        self.client.login(username="fo", password=CLAVE)
        self.assertEqual(self.client.get(reverse("social:caso_detail", args=[c.pk])).status_code, 404)

    def test_detalle_muestra_la_secuencia_completa(self):
        c = self.caso(self.u, fecha=dias(-5))
        self.agregar(c, self.u, tipo="Seguimiento", fecha=dias(-2))
        self.client.login(username="d1", password=CLAVE)
        r = self.client.get(reverse("social:caso_detail", args=[c.pk]))
        self.assertEqual([g.numero_gestion for g in r.context["gestiones"]], [1, 2])
        self.assertEqual(r.context["restantes"], 1)
        self.assertTrue(r.context["puede_agregar"])

    def test_nueva_gestion_por_vista_y_cuarta_bloqueada(self):
        c = self.caso(self.u, fecha=dias(-8))
        self.client.login(username="f1", password=CLAVE)
        url = reverse("social:gestion_create", args=[c.pk])
        for tipo, fecha in (("Seguimiento", -5), ("Cierre de caso", -1)):
            r = self.client.post(url, {"tipo_atencion": tipo, "catalogo": self.cat.pk, "fecha": dias(fecha).isoformat(),
                                       "estado": "Realizada", "resultado": "Ok"})
            self.assertEqual(r.status_code, 302)
        self.assertEqual(c.gestiones.count(), 3)
        r = self.client.get(url)                                    # ya no hay cupo
        self.assertRedirects(r, reverse("social:caso_detail", args=[c.pk]), fetch_redirect_response=False)

    def test_admin_no_registra_gestiones(self):
        c = self.caso(self.u)
        self.client.login(username="a1", password=CLAVE)
        r = self.client.get(reverse("social:gestion_create", args=[c.pk]))
        self.assertRedirects(r, reverse("dashboard"), fetch_redirect_response=False)
        self.assertEqual(self.client.get(reverse("social:caso_detail", args=[c.pk])).status_code, 200)  # sí consulta

    def test_cambio_de_estado_y_reapertura(self):
        c = self.caso(self.u)
        url = reverse("social:caso_estado", args=[c.pk])
        self.client.login(username="f1", password=CLAVE)
        self.client.post(url, {"estado_caso": "Cerrado"})
        c.refresh_from_db()
        self.assertEqual(c.estado_caso, "Cerrado")
        self.client.post(url, {"estado_caso": "Abierto"})            # funcionario: no reabre
        c.refresh_from_db()
        self.assertEqual(c.estado_caso, "Cerrado")
        self.client.logout()
        self.client.login(username="d1", password=CLAVE)
        self.client.post(url, {"estado_caso": "Abierto"})
        c.refresh_from_db()
        self.assertEqual(c.estado_caso, "Abierto")

    def test_listado_con_conteo_y_estadisticas(self):
        c = self.caso(self.u)
        self.agregar(c, self.u, tipo="Seguimiento")
        self.client.login(username="d1", password=CLAVE)
        r = self.client.get(reverse("social:caso_list"))
        self.assertEqual(r.context["casos"][0].total_gestiones, 2)
        r = self.client.get(reverse("social:estadisticas"))
        self.assertEqual(r.context["estadisticas"]["total_gestiones"], 2)
        self.assertEqual(r.context["estadisticas"]["total_personas"], 1)
