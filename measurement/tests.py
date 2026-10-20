from datetime import date
from decimal import Decimal
from unittest import mock

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from core.exceptions import ReglaNegocioError
from organizations.models import Cargo, Delegacion, Funcionario, FuncionarioRol, ItemMedible, Rol, Usuario

from . import calculations as calc
from .models import Ajuste, Indicador, Meta, Periodo
from .services import CalculoIndicadores, CRUDAjuste, CRUDMeta, CRUDPeriodo

CLAVE = "Clave-Segura-2026"
D = Decimal


# ---------------------------------------------------------------------------
# Fórmulas puras: reproducen los ejemplos del PDF
# ---------------------------------------------------------------------------
class CalculationsTests(SimpleTestCase):
    INI, FIN = date(2026, 7, 1), date(2026, 9, 30)

    def test_dias_computables_ejemplo_pdf(self):
        self.assertEqual(calc.calcular_dias_computables(self.INI, self.FIN), 91)

    def test_meta_esperada_ejemplo_pdf_26_agosto(self):
        self.assertEqual(calc.calcular_meta_esperada(self.INI, self.FIN, date(2026, 8, 26)), D("61.54"))

    def test_meta_esperada_limites(self):
        self.assertEqual(calc.calcular_meta_esperada(self.INI, self.FIN, date(2026, 6, 1)), D("0"))
        self.assertEqual(calc.calcular_meta_esperada(self.INI, self.FIN, self.FIN), D("100"))
        self.assertEqual(calc.calcular_meta_esperada(self.INI, self.FIN, date(2027, 1, 1)), D("100"))  # nunca > 100

    def test_periodo_de_un_dia(self):
        self.assertEqual(calc.calcular_meta_esperada(self.INI, self.INI, self.INI), D("100"))

    def test_fecha_termino_anterior_falla(self):
        with self.assertRaises(ValueError):
            calc.calcular_dias_computables(self.FIN, self.INI)

    def test_cumplimiento(self):
        self.assertEqual(calc.calcular_porcentaje_cumplimiento(5, 10), D("50.00"))
        self.assertEqual(calc.calcular_porcentaje_cumplimiento(1, 3), D("33.33"))
        with self.assertRaises(ValueError):
            calc.calcular_porcentaje_cumplimiento(5, 0)

    def test_ponderado_respeta_tope_150(self):
        self.assertEqual(calc.calcular_cumplimiento_ponderado(D("80"), D("40"), D("150")), D("32.00"))
        self.assertEqual(calc.calcular_cumplimiento_ponderado(D("300"), D("40"), D("150")), D("60.00"))

    def test_semaforo(self):
        self.assertEqual(calc.calcular_semaforo(60, 60), "Verde")
        self.assertEqual(calc.calcular_semaforo(70, 60), "Verde")
        self.assertEqual(calc.calcular_semaforo(36, 60), "Ámbar")      # justo 60 % de lo esperado
        self.assertEqual(calc.calcular_semaforo(35.99, 60), "Rojo")
        self.assertEqual(calc.calcular_semaforo(0, 0), "Verde")         # inicio de período

    def test_umbral_colectivo(self):
        self.assertTrue(calc.esta_bajo_umbral(79.9))
        self.assertFalse(calc.esta_bajo_umbral(80))


# ---------------------------------------------------------------------------
# Datos base
# ---------------------------------------------------------------------------
class BaseTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.deleg = Delegacion.objects.create(nombre="Rural", ambito="x")
        cls.deleg2 = Delegacion.objects.create(nombre="Centro", ambito="y")
        cls.cargo = Cargo.objects.create(nombre_cargo="Terreno", vigencia_desde=date(2026, 1, 1))
        cls.otro_cargo = Cargo.objects.create(nombre_cargo="Social", vigencia_desde=date(2026, 1, 1))
        cls.item1 = ItemMedible.objects.create(nombre_item="Visitas", cargo=cls.cargo)
        cls.item2 = ItemMedible.objects.create(nombre_item="Reuniones", cargo=cls.cargo)
        cls.item_otro = ItemMedible.objects.create(nombre_item="Casos", cargo=cls.otro_cargo)
        cls.periodo = Periodo.objects.create(fecha_inicio=date(2026, 7, 1), fecha_termino=date(2026, 9, 30))
        cls.roles = {n: Rol.objects.create(nombre_rol=n) for n in
                     ("Administrador", "Coordinador", "Delegado", "Funcionario")}

    def crear_func(self, ident, rol="Funcionario", deleg=None, username=None):
        f = Funcionario.objects.create(identificador_institucional=ident, nombre=f"F {ident}",
                                       cargo=self.cargo, delegacion=deleg or self.deleg)
        FuncionarioRol.objects.create(funcionario=f, rol=self.roles[rol])
        if username:
            Usuario.objects.create_user(username, CLAVE, funcionario=f)
        return f

    def nueva_meta(self, f, item=None, pond="50", objetivo="10"):
        return Meta(funcionario=f, item=item or self.item1, periodo=self.periodo, valor_objetivo=D(objetivo),
                    unidad="visitas", ponderador=D(pond))


class PeriodoTests(BaseTestCase):
    def test_dias_computables_se_calculan(self):
        self.assertEqual(self.periodo.dias_computables, 91)

    def test_rechaza_termino_anterior_al_inicio(self):
        with self.assertRaises(ValidationError):
            Periodo(fecha_inicio=date(2027, 5, 1), fecha_termino=date(2027, 4, 1)).full_clean()

    def test_rechaza_superposicion(self):
        with self.assertRaises(ValidationError):
            Periodo(fecha_inicio=date(2026, 9, 1), fecha_termino=date(2026, 12, 31)).full_clean()

    def test_cerrar_y_reabrir(self):
        CRUDPeriodo.cerrar_periodo(self.periodo)
        self.periodo.refresh_from_db()
        self.assertFalse(self.periodo.abierto)
        with self.assertRaises(ReglaNegocioError):           # motivo obligatorio
            CRUDPeriodo.reabrir_periodo(self.periodo, "  ")
        CRUDPeriodo.reabrir_periodo(self.periodo, "Corrección de datos")
        self.periodo.refresh_from_db()
        self.assertTrue(self.periodo.abierto)
        self.assertEqual(self.periodo.version_parametros, 2)


class MetaServicioTests(BaseTestCase):
    def setUp(self):
        self.f = self.crear_func("F1")

    def test_crea_meta_con_cargo_e_indicador(self):
        meta = CRUDMeta.crear_meta(self.nueva_meta(self.f))
        self.assertEqual(meta.cargo_id, self.cargo.pk)
        self.assertTrue(Indicador.objects.filter(meta=meta).exists())

    def test_suma_no_puede_superar_100(self):
        CRUDMeta.crear_meta(self.nueva_meta(self.f, self.item1, "70"))
        with self.assertRaises(ReglaNegocioError):
            CRUDMeta.crear_meta(self.nueva_meta(self.f, self.item2, "40"))
        CRUDMeta.crear_meta(self.nueva_meta(self.f, self.item2, "30"))
        resultado = CRUDMeta.validar_suma_ponderaciones(self.cargo, self.periodo)
        self.assertTrue(resultado[0]["completa"])

    def test_meta_debe_ser_mayor_que_cero(self):
        with self.assertRaises(ReglaNegocioError):
            CRUDMeta.crear_meta(self.nueva_meta(self.f, objetivo="0"))

    def test_item_de_otro_cargo_se_rechaza(self):
        with self.assertRaises(ReglaNegocioError):
            CRUDMeta.crear_meta(self.nueva_meta(self.f, self.item_otro))

    def test_no_duplica_funcionario_item_periodo(self):
        CRUDMeta.crear_meta(self.nueva_meta(self.f, pond="10"))
        with self.assertRaises(ReglaNegocioError):
            CRUDMeta.crear_meta(self.nueva_meta(self.f, pond="10"))

    def test_periodo_cerrado_bloquea_metas_y_ajustes(self):
        meta = CRUDMeta.crear_meta(self.nueva_meta(self.f))
        CRUDPeriodo.cerrar_periodo(self.periodo)
        with self.assertRaises(ReglaNegocioError):
            CRUDMeta.crear_meta(self.nueva_meta(self.f, self.item2, "10"))
        meta.refresh_from_db()
        meta.valor_objetivo = D("99")
        with self.assertRaises(ReglaNegocioError):
            CRUDMeta.modificar_meta(meta)
        with self.assertRaises(ReglaNegocioError):
            CRUDMeta.eliminar_meta(meta)
        with self.assertRaises(ReglaNegocioError):
            CRUDAjuste.crear_ajuste(Ajuste(funcionario=self.f, periodo=self.periodo, motivo="x",
                                           valor=D("5"), efecto="Positivo"))

    def test_no_cambia_funcionario_ni_item_al_modificar(self):
        meta = CRUDMeta.crear_meta(self.nueva_meta(self.f))
        meta.item = self.item2
        with self.assertRaises(ReglaNegocioError):
            CRUDMeta.modificar_meta(meta)

    def test_aplicar_a_todo_el_cargo(self):
        self.crear_func("F2")
        self.crear_func("F3")
        res = CRUDMeta.crear_meta_para_cargo(self.nueva_meta(self.f, pond="100"))
        self.assertEqual(len(res["creadas"]), 3)
        res2 = CRUDMeta.crear_meta_para_cargo(self.nueva_meta(self.f, pond="100"))   # ya existen
        self.assertEqual(len(res2["creadas"]), 0)
        self.assertEqual(len(res2["omitidas"]), 3)


class IndicadoresTests(BaseTestCase):
    def setUp(self):
        self.f = self.crear_func("F1")
        self.m1 = CRUDMeta.crear_meta(self.nueva_meta(self.f, self.item1, "60", "10"))
        self.m2 = CRUDMeta.crear_meta(self.nueva_meta(self.f, self.item2, "40", "10"))

    def avance(self, valores):
        # Reemplaza el conteo de actividades/compromisos (las apps aún no existen)
        return mock.patch.object(CalculoIndicadores, "crear_avance_actual",
                                 side_effect=lambda meta: D(valores[meta.item_id]))

    def test_indicador_persistido(self):
        with self.avance({self.item1.pk: 8, self.item2.pk: 15}):
            i1 = CalculoIndicadores.recalcular_indicador_meta(self.m1, fecha=date(2026, 8, 26))
            i2 = CalculoIndicadores.recalcular_indicador_meta(self.m2, fecha=date(2026, 8, 26))
        self.assertEqual((i1.cumplimiento_pct, i1.resultado_ponderado), (D("80.00"), D("48.00")))
        self.assertEqual((i2.cumplimiento_pct, i2.resultado_ponderado), (D("150.00"), D("60.00")))
        self.assertEqual(i1.semaforo, "Verde")     # 80 >= 61,54

    def test_resumen_suma_ponderados_y_ajustes(self):
        CRUDAjuste.crear_ajuste(Ajuste(funcionario=self.f, periodo=self.periodo, motivo="Felicitación",
                                       valor=D("5"), efecto="Positivo"))
        CRUDAjuste.crear_ajuste(Ajuste(funcionario=self.f, periodo=self.periodo, motivo="Reclamo",
                                       valor=D("2"), efecto="Negativo"))
        with self.avance({self.item1.pk: 8, self.item2.pk: 15}):
            r = CalculoIndicadores.resumen_funcionario(self.f, self.periodo, fecha=date(2026, 8, 26))
        self.assertEqual(r["total_ponderado"], D("108.00"))          # 48 + 60
        self.assertEqual(r["ajustes"], D("3"))
        self.assertEqual(r["resultado_total"], D("111.00"))
        self.assertTrue(r["completa"])
        self.assertEqual(r["semaforo"], "Verde")
        self.assertEqual(len(r["filas"]), 2)

    def test_semaforo_rojo_con_poco_avance(self):
        with self.avance({self.item1.pk: 1, self.item2.pk: 0}):
            r = CalculoIndicadores.resumen_funcionario(self.f, self.periodo, fecha=date(2026, 8, 26))
        self.assertEqual(r["semaforo"], "Rojo")
        self.assertTrue(r["bajo_umbral"])

    def test_periodo_cerrado_congela_resultados(self):
        with self.avance({self.item1.pk: 10, self.item2.pk: 10}):
            CRUDPeriodo.cerrar_periodo(self.periodo)
        self.periodo.refresh_from_db()
        with self.avance({self.item1.pk: 0, self.item2.pk: 0}):      # cambios posteriores no afectan
            r = CalculoIndicadores.resumen_delegacion([self.f], self.periodo)
        self.assertEqual(r["promedio"], D("100.00"))
        self.assertEqual(r["conteo"]["Verde"], 1)

    def test_sin_actividades_el_avance_es_cero(self):
        self.assertEqual(CalculoIndicadores.crear_avance_actual(self.m1), D(0))


class VistaTests(BaseTestCase):
    def setUp(self):
        self.admin = self.crear_func("A1", "Administrador", username="admin1")
        self.coord = self.crear_func("C1", "Coordinador", username="coord1")
        self.deleg_user = self.crear_func("D1", "Delegado", username="deleg1")
        self.normal = self.crear_func("N1", "Funcionario", username="normal1")
        self.otro = self.crear_func("O1", "Funcionario", deleg=self.deleg2)

    def test_funcionario_comun_no_crea_periodo(self):
        self.client.login(username="normal1", password=CLAVE)
        r = self.client.post(reverse("measurement:periodo_create"),
                             {"fecha_inicio": "2027-01-01", "fecha_termino": "2027-03-31"})
        self.assertRedirects(r, reverse("dashboard"), fetch_redirect_response=False)
        self.assertFalse(Periodo.objects.filter(fecha_inicio="2027-01-01").exists())

    def test_coordinador_crea_periodo(self):
        self.client.login(username="coord1", password=CLAVE)
        r = self.client.post(reverse("measurement:periodo_create"),
                             {"fecha_inicio": "2027-01-01", "fecha_termino": "2027-03-31"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Periodo.objects.get(fecha_inicio="2027-01-01").dias_computables, 89)

    def test_solo_admin_reabre_periodo(self):
        CRUDPeriodo.cerrar_periodo(self.periodo)
        url = reverse("measurement:periodo_reabrir", args=[self.periodo.pk])
        self.client.login(username="coord1", password=CLAVE)
        self.client.post(url, {"motivo": "x"})
        self.periodo.refresh_from_db()
        self.assertFalse(self.periodo.abierto)
        self.client.logout()
        self.client.login(username="admin1", password=CLAVE)
        self.client.post(url, {"motivo": "Error de digitación"})
        self.periodo.refresh_from_db()
        self.assertTrue(self.periodo.abierto)

    def test_coordinador_crea_meta_para_cargo_por_vista(self):
        self.client.login(username="coord1", password=CLAVE)
        r = self.client.post(reverse("measurement:meta_create"), {
            "periodo": self.periodo.pk, "funcionario": self.normal.pk, "item": self.item1.pk,
            "valor_objetivo": "10", "unidad": "visitas", "ponderador": "100",
            "umbral_minimo": "80", "maximo_computable": "150", "aplicar_a_cargo": "on"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Meta.objects.filter(item=self.item1).count(), 5)   # los 5 funcionarios del cargo

    def test_mi_desempeno_funciona_para_funcionario(self):
        CRUDMeta.crear_meta(self.nueva_meta(self.normal, pond="100"))
        self.client.login(username="normal1", password=CLAVE)
        r = self.client.get(reverse("measurement:mi_desempeno"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["resumen"]["funcionario"], self.normal)

    def test_delegado_no_ve_desempeno_de_otra_delegacion(self):
        self.client.login(username="deleg1", password=CLAVE)
        r = self.client.get(reverse("measurement:desempeno_funcionario", args=[self.otro.pk]))
        self.assertEqual(r.status_code, 404)
        r = self.client.get(reverse("measurement:desempeno_funcionario", args=[self.normal.pk]))
        self.assertEqual(r.status_code, 200)

    def test_semaforo_delegado_solo_su_delegacion(self):
        self.client.login(username="deleg1", password=CLAVE)
        r = self.client.get(reverse("measurement:semaforo"), {"delegacion": self.deleg2.pk})
        ids = {f["funcionario"].pk for f in r.context["resumen"]["filas"]}
        self.assertNotIn(self.otro.pk, ids)
        self.assertIn(self.normal.pk, ids)

    def test_funcionario_comun_no_accede_al_semaforo(self):
        self.client.login(username="normal1", password=CLAVE)
        r = self.client.get(reverse("measurement:semaforo"))
        self.assertRedirects(r, reverse("dashboard"), fetch_redirect_response=False)
