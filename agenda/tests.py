from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from activities.models import Actividad
from catalogs.models import Catalogo
from core.exceptions import ReglaNegocioError
from measurement.models import Indicador, Meta, Periodo
from measurement.services import CRUDMeta, CRUDPeriodo
from organizations.models import Cargo, Delegacion, Funcionario, FuncionarioRol, ItemMedible, Rol, Usuario

from .models import Compromiso
from .services import (
    CRUDCompromiso, CRUDHistorialTransiciones, compromisos_visibles, funcionarios_asignables,
)

CLAVE = "Clave-Segura-2026"
HOY = timezone.localdate()


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class BaseTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.deleg = Delegacion.objects.create(nombre="Rural", ambito="x")
        cls.deleg2 = Delegacion.objects.create(nombre="Centro", ambito="y")
        cls.cargo = Cargo.objects.create(nombre_cargo="Terreno", vigencia_desde=HOY - timedelta(days=400))
        cls.otro_cargo = Cargo.objects.create(nombre_cargo="Social", vigencia_desde=HOY - timedelta(days=400))
        cls.item = ItemMedible.objects.create(nombre_item="Compromisos cumplidos", cargo=cls.cargo)
        cls.item_otro = ItemMedible.objects.create(nombre_item="Casos", cargo=cls.otro_cargo)
        cls.periodo = Periodo.objects.create(fecha_inicio=HOY - timedelta(days=30), fecha_termino=HOY + timedelta(days=60))
        cls.roles = {n: Rol.objects.create(nombre_rol=n) for n in
                     ("Administrador", "Coordinador", "Delegado", "Funcionario", "Verificador", "Consulta")}

    def crear_func(self, ident, rol="Funcionario", deleg=None, cargo=None):
        f = Funcionario.objects.create(identificador_institucional=ident, nombre=f"F {ident}",
                                       cargo=cargo or self.cargo, delegacion=deleg or self.deleg)
        FuncionarioRol.objects.create(funcionario=f, rol=self.roles[rol])
        u = Usuario.objects.create_user(ident.lower(), CLAVE, funcionario=f)
        return f, u

    def nuevo(self, responsable, dias=10, **extra):
        datos = dict(origen="Solicitud vecinal", solicitante="Junta de vecinos", territorio="Sector Norte",
                     fecha_comprometida=HOY + timedelta(days=dias), funcionario=responsable)
        datos.update(extra)
        return Compromiso(**datos)

    def vencer(self, compromiso, dias_atras=3):
        Compromiso.objects.filter(pk=compromiso.pk).update(fecha_comprometida=HOY - timedelta(days=dias_atras))
        compromiso.refresh_from_db()
        return compromiso


class ModeloTests(BaseTestCase):
    def setUp(self):
        self.f, self.u = self.crear_func("F1")

    def test_plazos(self):
        c = CRUDCompromiso.crear_compromiso(self.nuevo(self.f, dias=30), self.u)
        self.assertEqual(c.plazo, Compromiso.PLAZO_VIGENTE)
        c.fecha_comprometida = HOY + timedelta(days=2)
        self.assertEqual(c.plazo, Compromiso.PLAZO_POR_VENCER)
        c.fecha_comprometida = HOY - timedelta(days=1)
        self.assertEqual(c.plazo, Compromiso.PLAZO_VENCIDO)

    def test_historial_inalterable(self):
        c = CRUDCompromiso.crear_compromiso(self.nuevo(self.f), self.u)
        h = c.historial.get()
        h.observacion = "alterada"
        with self.assertRaises(ValidationError):
            h.save()
        with self.assertRaises(ValidationError):
            h.delete()


class CrearTests(BaseTestCase):
    def setUp(self):
        self.f, self.u = self.crear_func("F1")
        self.f2, self.u2 = self.crear_func("F2")
        self.d, self.du = self.crear_func("D1", "Delegado")
        self.fo, self.uo = self.crear_func("FO", deleg=self.deleg2)

    def test_crea_con_estado_delegacion_periodo_e_historial(self):
        c = CRUDCompromiso.crear_compromiso(self.nuevo(self.f), self.u)
        self.assertEqual(c.estado, "Ingresado")
        self.assertEqual(c.delegacion, self.deleg)
        self.assertEqual(c.periodo, self.periodo)
        h = c.historial.get()
        self.assertEqual((h.estado_anterior, h.estado_nuevo, h.funcionario), ("", "Ingresado", self.f))

    def test_fecha_pasada_rechazada(self):
        with self.assertRaises(ReglaNegocioError):
            CRUDCompromiso.crear_compromiso(self.nuevo(self.f, dias=-1), self.u)

    def test_funcionario_comun_solo_se_asigna_a_si_mismo(self):
        with self.assertRaises(ReglaNegocioError):
            CRUDCompromiso.crear_compromiso(self.nuevo(self.f2), self.u)

    def test_delegado_asigna_dentro_de_su_delegacion(self):
        CRUDCompromiso.crear_compromiso(self.nuevo(self.f2), self.du)
        with self.assertRaises(ReglaNegocioError):
            CRUDCompromiso.crear_compromiso(self.nuevo(self.fo), self.du)
        self.assertEqual(set(funcionarios_asignables(self.du)), {self.f, self.f2, self.d})

    def test_item_de_otro_cargo_rechazado(self):
        with self.assertRaises(ReglaNegocioError):
            CRUDCompromiso.crear_compromiso(self.nuevo(self.f, item_medible=self.item_otro), self.u)

    def test_sin_periodo_para_la_fecha_queda_vacio(self):
        c = CRUDCompromiso.crear_compromiso(self.nuevo(self.f, dias=500), self.u)
        self.assertIsNone(c.periodo)


class EstadoTests(BaseTestCase):
    def setUp(self):
        self.f, self.u = self.crear_func("F1")
        self.f2, self.u2 = self.crear_func("F2")
        self.d, self.du = self.crear_func("D1", "Delegado")
        self.c = CRUDCompromiso.crear_compromiso(self.nuevo(self.f), self.u)

    def test_transicion_valida_registra_historial_completo(self):
        CRUDCompromiso.actualizar_estado(self.c, "En proceso", "Iniciado", self.u)
        ultimo = self.c.historial.last()
        self.assertEqual((ultimo.estado_anterior, ultimo.estado_nuevo, ultimo.observacion, ultimo.funcionario),
                         ("Ingresado", "En proceso", "Iniciado", self.f))
        self.c.refresh_from_db()
        self.assertEqual(self.c.observacion, "Iniciado")

    def test_transicion_invalida(self):
        CRUDCompromiso.actualizar_estado(self.c, "Pendiente", "Sin materiales", self.u)
        with self.assertRaises(ReglaNegocioError):
            CRUDCompromiso.actualizar_estado(self.c, "Ingresado", "", self.u)
        with self.assertRaises(ReglaNegocioError):                       # mismo estado
            CRUDCompromiso.actualizar_estado(self.c, "Pendiente", "x", self.u)

    def test_pendiente_exige_observacion(self):
        with self.assertRaises(ReglaNegocioError):
            CRUDCompromiso.actualizar_estado(self.c, "Pendiente", "  ", self.u)

    def test_solo_responsable_o_supervision_cambian_estado(self):
        with self.assertRaises(ReglaNegocioError):
            CRUDCompromiso.actualizar_estado(self.c, "En proceso", "", self.u2)
        CRUDCompromiso.actualizar_estado(self.c, "En proceso", "", self.du)    # el delegado sí

    def test_realizado_no_se_reabre_por_el_responsable(self):
        CRUDCompromiso.actualizar_estado(self.c, "Realizado", "", self.u)
        with self.assertRaises(ReglaNegocioError):
            CRUDCompromiso.actualizar_estado(self.c, "En proceso", "Faltó algo", self.u)
        with self.assertRaises(ReglaNegocioError):                              # sin motivo
            CRUDCompromiso.actualizar_estado(self.c, "En proceso", "", self.du)
        CRUDCompromiso.actualizar_estado(self.c, "En proceso", "Reabierto por error de cierre", self.du)
        self.c.refresh_from_db()
        self.assertEqual(self.c.estado, "En proceso")

    def test_realizado_no_se_edita(self):
        CRUDCompromiso.actualizar_estado(self.c, "Realizado", "", self.u)
        self.c.refresh_from_db()
        self.c.territorio = "Otro"
        with self.assertRaises(ReglaNegocioError):
            CRUDCompromiso.modificar_compromiso(self.c, self.u)

    def test_cambio_de_fecha_exige_motivo_y_queda_en_historial(self):
        self.c.fecha_comprometida = HOY + timedelta(days=20)
        with self.assertRaises(ReglaNegocioError):
            CRUDCompromiso.modificar_compromiso(self.c, self.u)
        self.c.observacion = "Lluvias impiden el trabajo"
        CRUDCompromiso.modificar_compromiso(self.c, self.u)
        self.assertIn("Fecha reprogramada", self.c.historial.last().observacion)

    def test_responsable_no_cambia_por_edicion(self):
        self.c.funcionario = self.f2
        with self.assertRaises(ReglaNegocioError):
            CRUDCompromiso.modificar_compromiso(self.c, self.u)


class IndicadorTests(BaseTestCase):
    """RF-020: el compromiso realizado aporta al ítem una sola vez; períodos cerrados no se alteran."""

    def setUp(self):
        self.f, self.u = self.crear_func("F1")
        self.d, self.du = self.crear_func("D1", "Delegado")
        CRUDMeta.crear_meta(Meta(funcionario=self.f, item=self.item, periodo=self.periodo,
                                 valor_objetivo=Decimal("4"), unidad="compromisos", ponderador=Decimal("100")))
        self.c = CRUDCompromiso.crear_compromiso(self.nuevo(self.f, item_medible=self.item), self.u)

    def avance(self):
        return Indicador.objects.get(meta__funcionario=self.f).avance

    def test_realizar_aporta_una_vez_y_reabrir_lo_quita(self):
        self.assertEqual(self.avance(), Decimal("0.00"))
        CRUDCompromiso.actualizar_estado(self.c, "Realizado", "Hecho", self.u)
        self.assertEqual(self.avance(), Decimal("1.00"))
        CRUDCompromiso.actualizar_estado(self.c, "En proceso", "Reabierto", self.du)
        self.assertEqual(self.avance(), Decimal("0.00"))

    def test_sin_item_no_aporta(self):
        sin_item = CRUDCompromiso.crear_compromiso(self.nuevo(self.f), self.u)
        CRUDCompromiso.actualizar_estado(sin_item, "Realizado", "", self.u)
        self.assertEqual(self.avance(), Decimal("0.00"))

    def test_periodo_cerrado_con_item_bloquea_el_cierre(self):
        CRUDPeriodo.cerrar_periodo(self.periodo)
        with self.assertRaises(ReglaNegocioError):
            CRUDCompromiso.actualizar_estado(self.c, "Realizado", "", self.u)
        CRUDCompromiso.actualizar_estado(self.c, "En proceso", "", self.u)       # otros estados sí


class ReasignarPlazosResumenTests(BaseTestCase):
    def setUp(self):
        self.f, self.u = self.crear_func("F1")
        self.f2, self.u2 = self.crear_func("F2")
        self.fo, self.uo = self.crear_func("FO", deleg=self.deleg2)
        self.fs, self.us = self.crear_func("FS", cargo=self.otro_cargo)
        self.d, self.du = self.crear_func("D1", "Delegado")
        self.a, self.au = self.crear_func("A1", "Administrador")
        self.c = CRUDCompromiso.crear_compromiso(self.nuevo(self.f), self.u)

    def test_reasignar_registra_motivo_y_responsables(self):
        CRUDCompromiso.reasignar_responsable(self.c, self.f2, "Funcionario ausente por licencia", self.du)
        self.c.refresh_from_db()
        self.assertEqual(self.c.funcionario, self.f2)
        ultimo = self.c.historial.last()
        self.assertIn("F F1", ultimo.observacion)
        self.assertIn("F F2", ultimo.observacion)
        self.assertIn("licencia", ultimo.observacion)
        self.assertEqual(ultimo.funcionario, self.d)

    def test_reglas_de_reasignacion(self):
        with self.assertRaises(ReglaNegocioError):                       # motivo
            CRUDCompromiso.reasignar_responsable(self.c, self.f2, " ", self.du)
        with self.assertRaises(ReglaNegocioError):                       # funcionario común no reasigna
            CRUDCompromiso.reasignar_responsable(self.c, self.f2, "x", self.u)
        with self.assertRaises(ReglaNegocioError):                       # delegado, otra delegación
            CRUDCompromiso.reasignar_responsable(self.c, self.fo, "x", self.du)
        CRUDCompromiso.reasignar_responsable(self.c, self.fo, "Traslado de zona", self.au)   # admin sí
        self.c.refresh_from_db()
        self.assertEqual(self.c.delegacion, self.deleg2)

    def test_reasignar_con_item_de_otro_cargo_falla(self):
        c = CRUDCompromiso.crear_compromiso(self.nuevo(self.f, item_medible=self.item), self.u)
        with self.assertRaises(ReglaNegocioError):
            CRUDCompromiso.reasignar_responsable(c, self.fs, "x", self.du)

    def test_no_reasigna_realizado(self):
        CRUDCompromiso.actualizar_estado(self.c, "Realizado", "", self.u)
        with self.assertRaises(ReglaNegocioError):
            CRUDCompromiso.reasignar_responsable(self.c, self.f2, "x", self.du)

    def test_controlar_plazos(self):
        vencido = self.vencer(CRUDCompromiso.crear_compromiso(self.nuevo(self.f), self.u))
        por_vencer = CRUDCompromiso.crear_compromiso(self.nuevo(self.f, dias=2), self.u)
        fuera = self.vencer(CRUDCompromiso.crear_compromiso(self.nuevo(self.f), self.u), 5)
        CRUDCompromiso.actualizar_estado(fuera, "Realizado", "Con retraso", self.u)   # cierre hoy > fecha
        en_plazo = CRUDCompromiso.crear_compromiso(self.nuevo(self.f, dias=5), self.u)
        CRUDCompromiso.actualizar_estado(en_plazo, "Realizado", "", self.u)
        r = CRUDCompromiso.controlar_plazos()
        self.assertEqual(set(r["vencidos"].values_list("pk", flat=True)), {vencido.pk})
        self.assertEqual(set(r["por_vencer"].values_list("pk", flat=True)), {por_vencer.pk, self.c.pk} - {self.c.pk})
        self.assertEqual([c.pk for c in r["realizados_fuera_de_plazo"]], [fuera.pk])
        en_plazo.refresh_from_db()
        self.assertEqual(en_plazo.plazo, Compromiso.PLAZO_REALIZADO_EN_PLAZO)

    def test_resumen_colectivo_porcentajes_y_totales(self):
        for estado in ("Realizado", "Realizado", "En proceso"):
            c = CRUDCompromiso.crear_compromiso(self.nuevo(self.f), self.u)
            if estado != "Ingresado":
                CRUDCompromiso.actualizar_estado(c, estado, "", self.u)
        r = CRUDCompromiso.resumen_colectivo(compromisos_visibles(self.du))
        fila = next(f for f in r["filas"] if f["nombre"] == "F F1")
        self.assertEqual(fila["total"], 4)                         # los 3 de arriba + self.c (Ingresado)
        self.assertEqual(fila["realizados"], 2)
        self.assertEqual(fila["pct_realizado"], Decimal("50.00"))
        self.assertEqual(fila["pct_pendiente"], Decimal("50.00"))
        self.assertEqual(r["total"]["total"], sum(f["total"] for f in r["filas"]))

    def test_historial_servicio(self):
        CRUDCompromiso.actualizar_estado(self.c, "En proceso", "", self.u)
        self.assertEqual(CRUDHistorialTransiciones.mostrar_historial_por_compromiso(self.c.pk).count(), 2)


class VistaTests(BaseTestCase):
    def setUp(self):
        self.f, self.u = self.crear_func("F1")
        self.f2, self.u2 = self.crear_func("F2")
        self.fo, self.uo = self.crear_func("FO", deleg=self.deleg2)
        self.d, self.du = self.crear_func("D1", "Delegado")
        self.v, self.vu = self.crear_func("V1", "Verificador")

    def datos(self, **extra):
        d = {"origen": "Solicitud vecinal", "solicitante": "Junta de vecinos", "territorio": "Sector Norte",
             "fecha_comprometida": (HOY + timedelta(days=7)).isoformat(), "funcionario": self.f.pk,
             "area_apoyo": "Obras", "observacion": ""}
        d.update(extra)
        return d

    def test_funcionario_crea_compromiso(self):
        self.client.login(username="f1", password=CLAVE)
        r = self.client.post(reverse("agenda:compromiso_create"), self.datos())
        c = Compromiso.objects.get()
        self.assertRedirects(r, reverse("agenda:compromiso_detail", args=[c.pk]), fetch_redirect_response=False)

    def test_responsable_y_fecha_son_obligatorios(self):
        self.client.login(username="f1", password=CLAVE)
        r = self.client.post(reverse("agenda:compromiso_create"), self.datos(fecha_comprometida=""))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Compromiso.objects.count(), 0)

    def test_verificador_no_crea(self):
        self.client.login(username="v1", password=CLAVE)
        r = self.client.post(reverse("agenda:compromiso_create"), self.datos())
        self.assertRedirects(r, reverse("dashboard"), fetch_redirect_response=False)

    def test_agenda_visible_para_el_equipo_pero_no_otra_delegacion(self):
        c = CRUDCompromiso.crear_compromiso(self.nuevo(self.f), self.u)
        self.client.login(username="f2", password=CLAVE)                 # compañero: la ve
        self.assertEqual(self.client.get(reverse("agenda:compromiso_detail", args=[c.pk])).status_code, 200)
        self.client.logout()
        self.client.login(username="fo", password=CLAVE)                 # otra delegación: no
        self.assertEqual(self.client.get(reverse("agenda:compromiso_detail", args=[c.pk])).status_code, 404)
        self.assertEqual(list(self.client.get(reverse("agenda:compromiso_list")).context["compromisos"]), [])

    def test_companero_no_cambia_estado_ajeno(self):
        c = CRUDCompromiso.crear_compromiso(self.nuevo(self.f), self.u)
        self.client.login(username="f2", password=CLAVE)
        self.client.post(reverse("agenda:compromiso_estado", args=[c.pk]), {"estado": "En proceso"})
        c.refresh_from_db()
        self.assertEqual(c.estado, "Ingresado")

    def test_cambio_de_estado_por_vista(self):
        c = CRUDCompromiso.crear_compromiso(self.nuevo(self.f), self.u)
        self.client.login(username="f1", password=CLAVE)
        self.client.post(reverse("agenda:compromiso_estado", args=[c.pk]),
                         {"estado": "Pendiente", "observacion": "Falta material"})
        c.refresh_from_db()
        self.assertEqual(c.estado, "Pendiente")
        self.assertEqual(c.historial.count(), 2)

    def test_estado_no_permitido_se_rechaza(self):
        c = CRUDCompromiso.crear_compromiso(self.nuevo(self.f), self.u)
        CRUDCompromiso.actualizar_estado(c, "En proceso", "", self.u)
        self.client.login(username="f1", password=CLAVE)
        self.client.post(reverse("agenda:compromiso_estado", args=[c.pk]), {"estado": "Ingresado"})
        c.refresh_from_db()
        self.assertEqual(c.estado, "En proceso")

    def test_reasignar_solo_delegado(self):
        c = CRUDCompromiso.crear_compromiso(self.nuevo(self.f), self.u)
        url = reverse("agenda:compromiso_reasignar", args=[c.pk])
        self.client.login(username="f1", password=CLAVE)
        self.client.post(url, {"funcionario": self.f2.pk, "motivo": "Prueba"})
        c.refresh_from_db()
        self.assertEqual(c.funcionario, self.f)
        self.client.logout()
        self.client.login(username="d1", password=CLAVE)
        self.client.post(url, {"funcionario": self.f2.pk, "motivo": "Ausencia"})
        c.refresh_from_db()
        self.assertEqual(c.funcionario, self.f2)

    def test_precarga_desde_actividad(self):
        cat = Catalogo.objects.create(tipo_catalogo="Actividad", nombre="Visita", area="General")
        act = Actividad.objects.create(
            fecha=HOY, accion="Visita", contacto="María Pérez", funcionario=self.f, item=self.item,
            catalogo=cat, periodo=self.periodo, ingreso_agenda_colectiva=True)
        self.client.login(username="f1", password=CLAVE)
        r = self.client.get(reverse("agenda:compromiso_create"), {"actividad": act.pk})
        self.assertEqual(r.context["form"].initial["origen"], f"Actividad {act.codigo}")
        self.assertEqual(r.context["form"].initial["solicitante"], "María Pérez")

    def test_resumen_coincide_con_el_detalle_filtrado(self):
        for _ in range(3):
            CRUDCompromiso.crear_compromiso(self.nuevo(self.f), self.u)
        CRUDCompromiso.crear_compromiso(self.nuevo(self.f2), self.u2)
        self.client.login(username="d1", password=CLAVE)
        lista = self.client.get(reverse("agenda:compromiso_list"), {"periodo": self.periodo.pk})
        resumen = self.client.get(reverse("agenda:resumen"), {"periodo": self.periodo.pk})
        self.assertEqual(lista.context["paginator"].count, resumen.context["resumen"]["total"]["total"])

    def test_filtro_por_plazo(self):
        vencido = self.vencer(CRUDCompromiso.crear_compromiso(self.nuevo(self.f), self.u))
        CRUDCompromiso.crear_compromiso(self.nuevo(self.f, dias=30), self.u)
        self.client.login(username="f1", password=CLAVE)
        r = self.client.get(reverse("agenda:compromiso_list"), {"plazo": "vencido"})
        self.assertEqual([c.pk for c in r.context["compromisos"]], [vencido.pk])

    def test_dashboard_destaca_vencidos(self):
        self.vencer(CRUDCompromiso.crear_compromiso(self.nuevo(self.f), self.u))
        self.client.login(username="f1", password=CLAVE)
        r = self.client.get(reverse("dashboard"))
        self.assertEqual(r.context["datos"]["compromisos_vencidos"], 1)
        self.assertEqual(r.context["datos"]["compromisos_por_estado"], {"Ingresado": 1})
