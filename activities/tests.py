import shutil
import tempfile
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from catalogs.models import Catalogo
from core.exceptions import ReglaNegocioError
from measurement.models import Indicador, Meta, Periodo
from measurement.services import CRUDMeta, CRUDPeriodo
from organizations.models import Cargo, Delegacion, Funcionario, FuncionarioRol, ItemMedible, Rol, Usuario

from .models import Actividad, Evidencia, Validacion
from .services import (
    CRUDActividad, CRUDEvidencia, CRUDValidacion, actividades_visibles, buscar_por_codigo,
)

CLAVE = "Clave-Segura-2026"
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 100
TMP_MEDIA = tempfile.mkdtemp()


def png(nombre="foto.png", contenido=PNG):
    return SimpleUploadedFile(nombre, contenido, content_type="image/png")


@override_settings(MEDIA_ROOT=TMP_MEDIA, PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class BaseTestCase(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP_MEDIA, ignore_errors=True)

    @classmethod
    def setUpTestData(cls):
        hoy = timezone.localdate()
        cls.deleg = Delegacion.objects.create(nombre="Rural", ambito="x")
        cls.deleg2 = Delegacion.objects.create(nombre="Centro", ambito="y")
        cls.cargo = Cargo.objects.create(nombre_cargo="Terreno", vigencia_desde=hoy - timedelta(days=400))
        cls.otro_cargo = Cargo.objects.create(nombre_cargo="Social", vigencia_desde=hoy - timedelta(days=400))
        cls.item = ItemMedible.objects.create(nombre_item="Visitas", cargo=cls.cargo)
        cls.item_otro = ItemMedible.objects.create(nombre_item="Casos", cargo=cls.otro_cargo)
        cls.catalogo = Catalogo.objects.create(tipo_catalogo="Actividad", nombre="Visita a terreno", area="General")
        cls.cat_inactivo = Catalogo.objects.create(tipo_catalogo="Actividad", nombre="Antigua", area="General",
                                                   estado="Inactivo")
        cls.cat_atencion = Catalogo.objects.create(tipo_catalogo="Atención", nombre="Social", area="General")
        cls.periodo = Periodo.objects.create(fecha_inicio=hoy - timedelta(days=30),
                                             fecha_termino=hoy + timedelta(days=30))
        cls.roles = {n: Rol.objects.create(nombre_rol=n) for n in
                     ("Administrador", "Coordinador", "Delegado", "Funcionario", "Verificador", "Consulta")}

    def crear_func(self, ident, rol, deleg=None, username=None):
        f = Funcionario.objects.create(identificador_institucional=ident, nombre=f"F {ident}",
                                       cargo=self.cargo, delegacion=deleg or self.deleg)
        FuncionarioRol.objects.create(funcionario=f, rol=self.roles[rol])
        u = Usuario.objects.create_user(username or ident.lower(), CLAVE, funcionario=f)
        return f, u

    def nueva(self, f, **extra):
        datos = dict(funcionario=f, item=self.item, catalogo=self.catalogo, accion="Visita a familia",
                     contacto="Juan", telefono="+56 9 1234 5678", fecha=timezone.localdate())
        datos.update(extra)
        return Actividad(**datos)


class ModeloTests(BaseTestCase):
    def setUp(self):
        self.f, self.u = self.crear_func("F1", "Funcionario")

    def test_codigo_derivado_del_id(self):
        a = CRUDActividad.crear_actividad(self.nueva(self.f), self.u)
        self.assertEqual(a.codigo, f"ACT-{a.pk:07d}")

    def test_telefono_invalido(self):
        with self.assertRaises(ValidationError):
            self.nueva(self.f, telefono="abc").full_clean(exclude=["periodo"])

    def test_telefono_exige_contacto(self):
        with self.assertRaises(ValidationError):
            self.nueva(self.f, contacto="").full_clean(exclude=["periodo"])

    def test_validacion_es_inmutable(self):
        a = CRUDActividad.crear_actividad(self.nueva(self.f), self.u)
        ev = CRUDEvidencia.adjuntar_evidencia(a, png(), self.u)
        v_f, v_u = self.crear_func("V1", "Verificador")
        CRUDValidacion.aprobar_evidencia(ev, "", v_u)
        v = Validacion.objects.get()
        v.decision = "Rechazada"
        with self.assertRaises(ValidationError):
            v.save()
        with self.assertRaises(ValidationError):
            v.delete()

    def test_codigo_de_evidencia_inmutable(self):
        a = CRUDActividad.crear_actividad(self.nueva(self.f), self.u)
        ev = CRUDEvidencia.adjuntar_evidencia(a, png(), self.u)
        ev.codigo_evidencia = "OTRO"
        with self.assertRaises(ValidationError):
            ev.save()


class ActividadServicioTests(BaseTestCase):
    def setUp(self):
        self.f, self.u = self.crear_func("F1", "Funcionario")

    def test_crea_y_asigna_periodo(self):
        a = CRUDActividad.crear_actividad(self.nueva(self.f), self.u)
        self.assertEqual(a.periodo, self.periodo)
        self.assertEqual(a.estado, "Registrada")

    def test_fecha_futura_rechazada(self):
        with self.assertRaises(ReglaNegocioError):
            CRUDActividad.crear_actividad(self.nueva(self.f, fecha=timezone.localdate() + timedelta(days=1)), self.u)

    def test_fecha_sin_periodo_rechazada(self):
        with self.assertRaises(ReglaNegocioError):
            CRUDActividad.crear_actividad(self.nueva(self.f, fecha=timezone.localdate() - timedelta(days=200)), self.u)

    def test_periodo_cerrado_rechazado(self):
        CRUDPeriodo.cerrar_periodo(self.periodo)
        with self.assertRaises(ReglaNegocioError):
            CRUDActividad.crear_actividad(self.nueva(self.f), self.u)

    def test_item_de_otro_cargo_rechazado(self):
        with self.assertRaises(ReglaNegocioError):
            CRUDActividad.crear_actividad(self.nueva(self.f, item=self.item_otro), self.u)

    def test_catalogo_inactivo_o_de_tipo_no_valido_rechazado(self):
        for cat in (self.cat_inactivo, self.cat_atencion):
            with self.assertRaises(ReglaNegocioError):
                CRUDActividad.crear_actividad(self.nueva(self.f, catalogo=cat), self.u)

    def test_solo_el_autor_modifica(self):
        a = CRUDActividad.crear_actividad(self.nueva(self.f), self.u)
        _, otro_u = self.crear_func("F2", "Funcionario")
        a.accion = "Cambiada"
        with self.assertRaises(ReglaNegocioError):
            CRUDActividad.modificar_actividad(a, otro_u)
        CRUDActividad.modificar_actividad(a, self.u)
        self.assertEqual(Actividad.objects.get(pk=a.pk).accion, "Cambiada")

    def test_busqueda_por_codigo(self):
        a = CRUDActividad.crear_actividad(self.nueva(self.f), self.u)
        self.assertEqual(buscar_por_codigo(a.codigo, self.u), a)
        self.assertEqual(buscar_por_codigo(a.codigo + "-E01", self.u), a)
        self.assertIsNone(buscar_por_codigo("XYZ", self.u))
        _, otro_u = self.crear_func("F2", "Funcionario")
        self.assertIsNone(buscar_por_codigo(a.codigo, otro_u))     # fuera de su ámbito


class EvidenciaServicioTests(BaseTestCase):
    def setUp(self):
        self.f, self.u = self.crear_func("F1", "Funcionario")
        self.a = CRUDActividad.crear_actividad(self.nueva(self.f), self.u)

    def test_adjunta_con_codigo_estado_y_nombre_seguro(self):
        ev = CRUDEvidencia.adjuntar_evidencia(self.a, png("../../malo.png"), self.u)
        self.assertEqual(ev.codigo_evidencia, f"{self.a.codigo}-E01")
        self.assertEqual(ev.estado_revision, "Pendiente")
        self.assertIn(ev.codigo_evidencia, ev.archivo_vinculo.name)
        self.assertNotIn("malo", ev.archivo_vinculo.name)
        self.assertEqual(len(ev.metadatos["sha256"]), 64)
        self.a.refresh_from_db()
        self.assertEqual(self.a.estado, "En revisión")

    def test_segunda_evidencia_correlativa(self):
        CRUDEvidencia.adjuntar_evidencia(self.a, png(), self.u)
        ev2 = CRUDEvidencia.adjuntar_evidencia(self.a, png(), self.u)
        self.assertTrue(ev2.codigo_evidencia.endswith("-E02"))

    def test_formatos_invalidos(self):
        with self.assertRaises(ReglaNegocioError):      # extensión no permitida
            CRUDEvidencia.adjuntar_evidencia(self.a, SimpleUploadedFile("x.exe", b"MZ" + b"0" * 50), self.u)
        with self.assertRaises(ReglaNegocioError):      # extensión png pero contenido falso
            CRUDEvidencia.adjuntar_evidencia(self.a, png(contenido=b"esto no es una imagen"), self.u)
        with self.assertRaises(ReglaNegocioError):      # vacío
            CRUDEvidencia.adjuntar_evidencia(self.a, png(contenido=b""), self.u)
        self.assertEqual(Evidencia.objects.count(), 0)

    @override_settings(SGR_EVIDENCIA_MAX_MB=1)
    def test_tamano_maximo(self):
        grande = PNG + b"0" * (1024 * 1024)
        with self.assertRaises(ReglaNegocioError):
            CRUDEvidencia.adjuntar_evidencia(self.a, png(contenido=grande), self.u)

    def test_solo_el_autor_adjunta(self):
        _, otro_u = self.crear_func("F2", "Funcionario")
        with self.assertRaises(ReglaNegocioError):
            CRUDEvidencia.adjuntar_evidencia(self.a, png(), otro_u)

    def test_no_adjunta_si_esta_validada_o_anulada(self):
        ev = CRUDEvidencia.adjuntar_evidencia(self.a, png(), self.u)
        v_f, v_u = self.crear_func("V1", "Verificador")
        CRUDValidacion.aprobar_evidencia(ev, "", v_u)
        with self.assertRaises(ReglaNegocioError):                 # Validada
            CRUDEvidencia.adjuntar_evidencia(self.a, png(), self.u)
        CRUDActividad.anular_actividad(self.a, "Duplicada", self.u)
        with self.assertRaises(ReglaNegocioError):                 # Anulada
            CRUDEvidencia.adjuntar_evidencia(self.a, png(), self.u)


class ValidacionFlujoTests(BaseTestCase):
    """Escenarios CA-01 y CA-02 del PDF, de punta a punta con el cálculo de indicadores."""

    def setUp(self):
        self.f, self.u = self.crear_func("F1", "Funcionario")
        self.v, self.vu = self.crear_func("V1", "Verificador")
        CRUDMeta.crear_meta(Meta(funcionario=self.f, item=self.item, periodo=self.periodo,
                                 valor_objetivo=Decimal("10"), unidad="visitas", ponderador=Decimal("100")))
        self.a = CRUDActividad.crear_actividad(self.nueva(self.f), self.u)
        self.ev = CRUDEvidencia.adjuntar_evidencia(self.a, png(), self.u)

    def indicador(self):
        return Indicador.objects.get(meta__funcionario=self.f)

    def test_ca01_aprobada_aporta_una_sola_vez(self):
        self.assertEqual(self.indicador().avance, Decimal("0.00"))
        CRUDValidacion.aprobar_evidencia(self.ev, "Conforme", self.vu)
        self.a.refresh_from_db()
        self.assertEqual(self.a.estado, "Validada")
        self.assertEqual(self.indicador().avance, Decimal("1.00"))
        self.assertEqual(self.indicador().cumplimiento_pct, Decimal("10.00"))
        CRUDValidacion.aprobar_evidencia(self.ev, "Revisada otra vez", self.vu)    # no suma doble
        self.assertEqual(self.indicador().avance, Decimal("1.00"))

    def test_ca02_rechazada_conserva_observacion_y_no_aporta(self):
        CRUDValidacion.rechazar_evidencia(self.ev, "Foto borrosa", self.vu)
        self.a.refresh_from_db()
        self.ev.refresh_from_db()
        self.assertEqual(self.a.estado, "Rechazada")
        self.assertEqual(self.ev.estado_revision, "Rechazada")
        self.assertEqual(self.indicador().avance, Decimal("0.00"))
        self.assertEqual(Validacion.objects.get().observacion, "Foto borrosa")
        # Corrección: nueva evidencia -> aprobación -> recién ahí aporta
        ev2 = CRUDEvidencia.adjuntar_evidencia(self.a, png(), self.u)
        self.a.refresh_from_db()
        self.assertEqual(self.a.estado, "En revisión")
        CRUDValidacion.aprobar_evidencia(ev2, "", self.vu)
        self.a.refresh_from_db()
        self.assertEqual(self.a.estado, "Validada")
        self.assertEqual(self.indicador().avance, Decimal("1.00"))

    def test_rechazo_posterior_quita_el_punto(self):
        CRUDValidacion.aprobar_evidencia(self.ev, "", self.vu)
        CRUDValidacion.rechazar_evidencia(self.ev, "Error detectado", self.vu)
        self.assertEqual(self.indicador().avance, Decimal("0.00"))
        self.assertEqual(list(self.ev.validaciones.values_list("version", flat=True)), [1, 2])

    def test_solicitar_correccion(self):
        CRUDValidacion.solicitar_correccion(self.ev, "Falta la fecha visible", self.vu)
        self.a.refresh_from_db()
        self.assertEqual(self.a.estado, "Corrección solicitada")
        self.assertTrue(self.a.editable)

    def test_observacion_obligatoria_al_rechazar(self):
        with self.assertRaises(ReglaNegocioError):
            CRUDValidacion.rechazar_evidencia(self.ev, "  ", self.vu)
        self.assertEqual(Validacion.objects.count(), 0)

    def test_no_valida_sus_propias_actividades(self):
        propia = CRUDActividad.crear_actividad(self.nueva(self.v, item=self.item), self.vu)
        ev_propia = CRUDEvidencia.adjuntar_evidencia(propia, png(), self.vu)
        with self.assertRaises(ReglaNegocioError):
            CRUDValidacion.aprobar_evidencia(ev_propia, "", self.vu)

    def test_funcionario_comun_no_valida(self):
        with self.assertRaises(ReglaNegocioError):
            CRUDValidacion.aprobar_evidencia(self.ev, "", self.u)

    def test_verificador_de_otra_delegacion_no_valida(self):
        _, vu2 = self.crear_func("V2", "Verificador", deleg=self.deleg2)
        with self.assertRaises(ReglaNegocioError):
            CRUDValidacion.aprobar_evidencia(self.ev, "", vu2)

    def test_periodo_cerrado_bloquea_validacion(self):
        CRUDPeriodo.cerrar_periodo(self.periodo)
        with self.assertRaises(ReglaNegocioError):
            CRUDValidacion.aprobar_evidencia(self.ev, "", self.vu)

    def test_anular_actividad_validada_quita_el_punto(self):
        CRUDValidacion.aprobar_evidencia(self.ev, "", self.vu)
        with self.assertRaises(ReglaNegocioError):
            CRUDActividad.anular_actividad(self.a, "", self.u)          # motivo obligatorio
        CRUDActividad.anular_actividad(self.a, "Registro duplicado", self.u)
        self.a.refresh_from_db()
        self.assertEqual(self.a.estado, "Anulada")
        self.assertEqual(self.indicador().avance, Decimal("0.00"))

    def test_historial(self):
        CRUDValidacion.rechazar_evidencia(self.ev, "No se ve", self.vu)
        historial = CRUDValidacion.mostrar_historial_validacion(self.ev.codigo_evidencia)
        self.assertEqual([h.decision for h in historial], ["Rechazada"])


class VisibilidadTests(BaseTestCase):
    def test_ambito_por_rol(self):
        f1, u1 = self.crear_func("F1", "Funcionario")
        f2, u2 = self.crear_func("F2", "Funcionario")
        fo, uo = self.crear_func("FO", "Funcionario", deleg=self.deleg2)
        _, ud = self.crear_func("D1", "Delegado")
        _, ua = self.crear_func("A1", "Administrador")
        for f, u in ((f1, u1), (f2, u2), (fo, uo)):
            CRUDActividad.crear_actividad(self.nueva(f), u)
        self.assertEqual(actividades_visibles(u1).count(), 1)     # solo las suyas
        self.assertEqual(actividades_visibles(ud).count(), 2)     # su delegación
        self.assertEqual(actividades_visibles(ua).count(), 3)     # todas


class VistaTests(BaseTestCase):
    def setUp(self):
        self.f, self.u = self.crear_func("F1", "Funcionario")
        self.f2, self.u2 = self.crear_func("F2", "Funcionario")
        self.v, self.vu = self.crear_func("V1", "Verificador")

    def datos(self, **extra):
        d = {"fecha": timezone.localdate().isoformat(), "tipo_registro": "Actividad",
             "catalogo": self.catalogo.pk, "item": self.item.pk, "accion": "Visita a familia",
             "contacto": "Juan", "telefono": "+56 9 1234 5678"}
        d.update(extra)
        return d

    def test_funcionario_registra_actividad(self):
        self.client.login(username="f1", password=CLAVE)
        r = self.client.post(reverse("activities:actividad_create"), self.datos())
        a = Actividad.objects.get()
        self.assertRedirects(r, reverse("activities:actividad_detail", args=[a.pk]), fetch_redirect_response=False)
        self.assertEqual(a.funcionario, self.f)

    def test_registro_incompleto_no_se_guarda(self):
        self.client.login(username="f1", password=CLAVE)
        r = self.client.post(reverse("activities:actividad_create"), self.datos(accion=""))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Actividad.objects.count(), 0)

    def test_verificador_no_registra_actividades(self):
        self.client.login(username="v1", password=CLAVE)
        r = self.client.post(reverse("activities:actividad_create"), self.datos())
        self.assertRedirects(r, reverse("dashboard"), fetch_redirect_response=False)

    def test_no_ve_actividad_ajena(self):
        a = CRUDActividad.crear_actividad(self.nueva(self.f), self.u)
        self.client.login(username="f2", password=CLAVE)
        self.assertEqual(self.client.get(reverse("activities:actividad_detail", args=[a.pk])).status_code, 404)

    @override_settings(MEDIA_ROOT=TMP_MEDIA)
    def test_flujo_subir_descargar_y_validar(self):
        a = CRUDActividad.crear_actividad(self.nueva(self.f), self.u)
        self.client.login(username="f1", password=CLAVE)
        r = self.client.post(reverse("activities:evidencia_create", args=[a.pk]), {"archivo": png()})
        self.assertEqual(r.status_code, 302)
        ev = Evidencia.objects.get()
        # el autor descarga su archivo
        r = self.client.get(reverse("activities:evidencia_archivo", args=[ev.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["X-Content-Type-Options"], "nosniff")
        self.client.logout()
        # otro funcionario no puede verlo
        self.client.login(username="f2", password=CLAVE)
        self.assertEqual(self.client.get(reverse("activities:evidencia_archivo", args=[ev.pk])).status_code, 404)
        self.client.logout()
        # el verificador lo ve en su bandeja y lo aprueba
        self.client.login(username="v1", password=CLAVE)
        bandeja = self.client.get(reverse("activities:validacion_bandeja"))
        self.assertEqual([e.pk for e in bandeja.context["evidencias"]], [ev.pk])
        r = self.client.post(reverse("activities:validacion_create", args=[ev.pk]),
                             {"decision": "Aprobada", "observacion": ""})
        self.assertRedirects(r, reverse("activities:validacion_bandeja"), fetch_redirect_response=False)
        a.refresh_from_db()
        self.assertEqual(a.estado, "Validada")

    def test_rechazo_sin_observacion_no_se_guarda(self):
        a = CRUDActividad.crear_actividad(self.nueva(self.f), self.u)
        ev = CRUDEvidencia.adjuntar_evidencia(a, png(), self.u)
        self.client.login(username="v1", password=CLAVE)
        r = self.client.post(reverse("activities:validacion_create", args=[ev.pk]),
                             {"decision": "Rechazada", "observacion": ""})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Validacion.objects.count(), 0)

    def test_funcionario_no_accede_a_bandeja(self):
        self.client.login(username="f1", password=CLAVE)
        r = self.client.get(reverse("activities:validacion_bandeja"))
        self.assertRedirects(r, reverse("dashboard"), fetch_redirect_response=False)

    def test_anular_desde_vista(self):
        a = CRUDActividad.crear_actividad(self.nueva(self.f), self.u)
        self.client.login(username="f1", password=CLAVE)
        self.client.post(reverse("activities:actividad_anular", args=[a.pk]), {"motivo": "Duplicada"})
        a.refresh_from_db()
        self.assertEqual(a.estado, "Anulada")

    def test_buscar_codigo(self):
        a = CRUDActividad.crear_actividad(self.nueva(self.f), self.u)
        self.client.login(username="f1", password=CLAVE)
        r = self.client.get(reverse("activities:buscar_codigo"), {"codigo": a.codigo})
        self.assertRedirects(r, reverse("activities:actividad_detail", args=[a.pk]), fetch_redirect_response=False)
