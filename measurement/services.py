"""
Servicios de measurement (equivalen a CRUDPeriodo, CRUDMeta y CalculoIndicadores del diagrama
de clases). Las fórmulas puras están en calculations.py; aquí se orquestan con la base de datos.

CONTRATO con las apps siguientes (se construyen en los próximos pasos):
- activities.Actividad: campos funcionario, item (FK ItemMedible), periodo (FK Periodo) y estado.
  Aporta al avance solo con estado == "Validada" (RN-009).
- agenda.Compromiso: campos funcionario, item_medible, periodo y estado.
  Aporta al avance solo con estado == "Realizado" (RF-020).
- Al aprobar/anular una validación o cerrar un compromiso, esas apps llaman a
  CalculoIndicadores.recalcular_para(funcionario_id, item_id, periodo_id) (RF-022, CA-01).
"""
import json
from decimal import Decimal

from django.apps import apps
from django.db import transaction
from django.utils import timezone

from core.exceptions import ReglaNegocioError
from core.mixins import auditar
from core.services import eliminar, guardar, snapshot
from organizations.models import Funcionario

from . import calculations as calc
from .models import Ajuste, Indicador, Meta, Periodo

ACTIVIDAD_VALIDADA = "Validada"
COMPROMISO_REALIZADO = "Realizado"


def _exigir_abierto(periodo, accion="modificar"):
    """RN-013: los períodos cerrados no se modifican (salvo reapertura autorizada y auditada)."""
    actual = Periodo.objects.get(pk=periodo.pk)
    if not actual.abierto:
        raise ReglaNegocioError(f"El período {actual} está cerrado: no se puede {accion}. "
                                "Solo un administrador puede reabrirlo.")
    return actual


# ---------------------------------------------------------------------------
# CRUDPeriodo (RF-005, HU-28)
# ---------------------------------------------------------------------------
class CRUDPeriodo:
    @staticmethod
    def calcular_dias_computables(fecha_inicio, fecha_termino):
        try:
            return calc.calcular_dias_computables(fecha_inicio, fecha_termino)
        except ValueError as exc:
            raise ReglaNegocioError(str(exc))

    @staticmethod
    def crear_periodo(periodo, actor=None):
        periodo.estado = Periodo.ESTADO_ABIERTO
        return guardar(periodo, actor, "periodo")

    @staticmethod
    def mostrar_todos_periodos():
        return Periodo.objects.all()

    @staticmethod
    def modificar_periodo(periodo, actor=None):
        _exigir_abierto(periodo)
        with transaction.atomic():
            guardar(periodo, actor, "periodo")
            CalculoIndicadores.recalcular_periodo(periodo)
        return periodo

    @staticmethod
    def cerrar_periodo(periodo, actor=None):
        """Congela los indicadores a la fecha de término y bloquea toda modificación (RN-013)."""
        with transaction.atomic():
            periodo = Periodo.objects.select_for_update().get(pk=periodo.pk)
            if not periodo.abierto:
                raise ReglaNegocioError("El período ya está cerrado.")
            CalculoIndicadores.recalcular_periodo(periodo, fecha=periodo.fecha_termino, forzar=True)
            anterior = snapshot(periodo)
            periodo.estado = Periodo.ESTADO_CERRADO
            periodo.save(update_fields=["estado"])
            auditar(actor, "CERRAR_PERIODO", "periodo", periodo.pk, anterior, snapshot(periodo))
        return periodo

    @staticmethod
    def reabrir_periodo(periodo, motivo, actor=None):
        """Reapertura autorizada y auditada (el rol se exige en la vista). Sube la versión de parámetros."""
        motivo = (motivo or "").strip()
        if not motivo:
            raise ReglaNegocioError("Debe indicar el motivo de la reapertura.")
        with transaction.atomic():
            periodo = Periodo.objects.select_for_update().get(pk=periodo.pk)
            if periodo.abierto:
                raise ReglaNegocioError("El período ya está abierto.")
            anterior = snapshot(periodo)
            periodo.estado = Periodo.ESTADO_ABIERTO
            periodo.version_parametros += 1
            periodo.save(update_fields=["estado", "version_parametros"])
            auditar(actor, "REABRIR_PERIODO", "periodo", periodo.pk, anterior,
                    json.dumps({"motivo": motivo, "periodo": json.loads(snapshot(periodo))}, ensure_ascii=False))
        return periodo


# ---------------------------------------------------------------------------
# CRUDMeta (RF-006, RF-007, HU-04, HU-05)
# ---------------------------------------------------------------------------
class CRUDMeta:
    @staticmethod
    def mostrar_metas_por_funcionario(funcionario, periodo=None):
        qs = Meta.objects.filter(funcionario=funcionario).select_related("item", "periodo")
        return qs.filter(periodo=periodo) if periodo else qs

    @staticmethod
    def suma_ponderaciones(funcionario, periodo, excluir_meta=None):
        qs = Meta.objects.filter(funcionario=funcionario, periodo=periodo)
        if excluir_meta:
            qs = qs.exclude(pk=excluir_meta)
        return sum((m.ponderador for m in qs), Decimal("0.00"))

    @staticmethod
    def validar_suma_ponderaciones(cargo, periodo):
        """
        RN-001: la suma de ponderadores aplicables debe ser 100 %. Devuelve, por cada funcionario
        activo del cargo, su suma y si la configuración está completa.
        """
        resultado = []
        for f in Funcionario.objects.filter(cargo=cargo, estado=Funcionario.ESTADO_ACTIVO):
            suma = CRUDMeta.suma_ponderaciones(f, periodo)
            resultado.append({"funcionario": f, "suma": suma, "completa": suma == Decimal("100")})
        return resultado

    # -- validaciones internas ------------------------------------------------
    @staticmethod
    def _preparar(meta):
        meta.cargo_id = meta.funcionario.cargo_id
        meta.fecha_version = timezone.localdate()          # versión de la meta (RF-007)

    @staticmethod
    def _validar(meta, es_nueva):
        _exigir_abierto(meta.periodo, "configurar metas")
        if es_nueva:
            if not meta.funcionario.activo:
                raise ReglaNegocioError("El funcionario está inactivo.")
            if not meta.item.vigencia:
                raise ReglaNegocioError("El ítem medible no está vigente.")
        duplicada = Meta.objects.filter(funcionario=meta.funcionario, item=meta.item,
                                        periodo=meta.periodo).exclude(pk=meta.pk).exists()
        if duplicada:
            raise ReglaNegocioError("Ya existe una meta para ese funcionario, ítem y período.")
        suma = CRUDMeta.suma_ponderaciones(meta.funcionario, meta.periodo, meta.pk) + meta.ponderador
        if suma > Decimal("100"):
            raise ReglaNegocioError(
                f"La suma de ponderaciones del funcionario sería {suma} %: no puede superar 100 % (RN-001).")

    # -- operaciones ----------------------------------------------------------
    @staticmethod
    def crear_meta(meta, actor=None):
        with transaction.atomic():
            CRUDMeta._preparar(meta)
            CRUDMeta._validar(meta, es_nueva=True)
            guardar(meta, actor, "meta")
            CalculoIndicadores.recalcular_indicador_meta(meta)
        return meta

    @staticmethod
    def crear_meta_para_cargo(meta_base, actor=None):
        """
        Replica la meta para todos los funcionarios activos del mismo cargo.
        Devuelve {'creadas': [...], 'omitidas': [(funcionario, motivo), ...]}.
        """
        creadas, omitidas = [], []
        candidatos = Funcionario.objects.filter(cargo=meta_base.funcionario.cargo,
                                                estado=Funcionario.ESTADO_ACTIVO)
        for f in candidatos:
            copia = Meta(item=meta_base.item, periodo=meta_base.periodo, funcionario=f,
                         valor_objetivo=meta_base.valor_objetivo, unidad=meta_base.unidad,
                         ponderador=meta_base.ponderador, umbral_minimo=meta_base.umbral_minimo,
                         maximo_computable=meta_base.maximo_computable)
            try:
                creadas.append(CRUDMeta.crear_meta(copia, actor))
            except ReglaNegocioError as exc:
                omitidas.append((f, str(exc)))
        return {"creadas": creadas, "omitidas": omitidas}

    @staticmethod
    def modificar_meta(meta, actor=None):
        original = Meta.objects.get(pk=meta.pk)
        if (original.funcionario_id, original.item_id, original.periodo_id) != \
                (meta.funcionario_id, meta.item_id, meta.periodo_id):
            raise ReglaNegocioError("No se puede cambiar el funcionario, el ítem ni el período de una meta.")
        with transaction.atomic():
            CRUDMeta._preparar(meta)
            CRUDMeta._validar(meta, es_nueva=False)
            guardar(meta, actor, "meta")
            CalculoIndicadores.recalcular_indicador_meta(meta)
        return meta

    @staticmethod
    def eliminar_meta(meta, actor=None):
        _exigir_abierto(meta.periodo, "eliminar metas")
        eliminar(meta, actor, "meta", "No se puede eliminar la meta porque tiene registros asociados.")


# ---------------------------------------------------------------------------
# CRUDAjuste (RF-025)
# ---------------------------------------------------------------------------
class CRUDAjuste:
    @staticmethod
    def crear_ajuste(ajuste, actor=None):
        _exigir_abierto(ajuste.periodo, "registrar ajustes")
        return guardar(ajuste, actor, "ajuste")

    @staticmethod
    def eliminar_ajuste(ajuste, actor=None):
        _exigir_abierto(ajuste.periodo, "eliminar ajustes")
        eliminar(ajuste, actor, "ajuste", "No se puede eliminar el ajuste.")


# ---------------------------------------------------------------------------
# CalculoIndicadores (RF-022 a RF-029)
# ---------------------------------------------------------------------------
def _modelo(app_label, nombre):
    try:
        return apps.get_model(app_label, nombre)
    except LookupError:
        return None


class CalculoIndicadores:
    # -- cálculo por meta -----------------------------------------------------
    @staticmethod
    def crear_avance_actual(meta):
        """
        Avance actual = actividades validadas + compromisos realizados asociados al ítem,
        funcionario y período (RN-003, RN-009). Cada registro aporta una sola vez.
        """
        total = 0
        Actividad = _modelo("activities", "Actividad")
        if Actividad is not None:
            total += Actividad.objects.filter(
                funcionario_id=meta.funcionario_id, item_id=meta.item_id,
                periodo_id=meta.periodo_id, estado=ACTIVIDAD_VALIDADA).count()
        Compromiso = _modelo("agenda", "Compromiso")
        if Compromiso is not None:
            total += Compromiso.objects.filter(
                funcionario_id=meta.funcionario_id, item_medible_id=meta.item_id,
                periodo_id=meta.periodo_id, estado=COMPROMISO_REALIZADO).count()
        return Decimal(total)

    @staticmethod
    def calcular_porcentaje_cumplimiento(meta, avance=None):
        avance = CalculoIndicadores.crear_avance_actual(meta) if avance is None else avance
        return calc.calcular_porcentaje_cumplimiento(avance, meta.valor_objetivo)

    @staticmethod
    def calcular_cumplimiento_ponderado(meta, cumplimiento=None):
        cumplimiento = CalculoIndicadores.calcular_porcentaje_cumplimiento(meta) \
            if cumplimiento is None else cumplimiento
        return calc.calcular_cumplimiento_ponderado(cumplimiento, meta.ponderador, meta.maximo_computable)

    @staticmethod
    def calcular_meta_esperada_al_dia(periodo, fecha=None):
        return calc.calcular_meta_esperada(periodo.fecha_inicio, periodo.fecha_termino,
                                           fecha or timezone.localdate())

    @staticmethod
    def calcular_semaforo(meta, cumplimiento=None, fecha=None):
        cumplimiento = CalculoIndicadores.calcular_porcentaje_cumplimiento(meta) \
            if cumplimiento is None else cumplimiento
        esperada = CalculoIndicadores.calcular_meta_esperada_al_dia(meta.periodo, fecha)
        return calc.calcular_semaforo(cumplimiento, esperada)

    @staticmethod
    def _valores_meta(meta, fecha):
        avance = CalculoIndicadores.crear_avance_actual(meta)
        cumplimiento = calc.calcular_porcentaje_cumplimiento(avance, meta.valor_objetivo)
        ponderado = calc.calcular_cumplimiento_ponderado(cumplimiento, meta.ponderador, meta.maximo_computable)
        esperada = CalculoIndicadores.calcular_meta_esperada_al_dia(meta.periodo, fecha)
        return {"avance": calc.redondear(avance), "cumplimiento": cumplimiento, "ponderado": ponderado,
                "semaforo": calc.calcular_semaforo(cumplimiento, esperada)}

    # -- persistencia ---------------------------------------------------------
    @staticmethod
    def recalcular_indicador_meta(meta, fecha=None, forzar=False):
        """Crea o actualiza el Indicador de la meta. Los períodos cerrados no se recalculan (RN-013)."""
        if not meta.periodo.abierto and not forzar:
            return Indicador.objects.filter(meta=meta).first()
        v = CalculoIndicadores._valores_meta(meta, fecha)
        indicador, _ = Indicador.objects.update_or_create(meta=meta, defaults={
            "avance": v["avance"], "cumplimiento_pct": v["cumplimiento"],
            "resultado_ponderado": v["ponderado"], "semaforo": v["semaforo"],
            "fecha_calculo": timezone.now()})
        return indicador

    @staticmethod
    def recalcular_para(funcionario_id, item_id, periodo_id):
        """Punto de entrada para activities/agenda tras validar, rechazar, anular o cerrar un registro."""
        metas = Meta.objects.filter(funcionario_id=funcionario_id, item_id=item_id,
                                    periodo_id=periodo_id).select_related("periodo")
        return [CalculoIndicadores.recalcular_indicador_meta(m) for m in metas]

    @staticmethod
    def recalcular_periodo(periodo, fecha=None, forzar=False):
        metas = Meta.objects.filter(periodo=periodo).select_related("periodo")
        for meta in metas:
            CalculoIndicadores.recalcular_indicador_meta(meta, fecha=fecha, forzar=forzar)
        return metas.count()

    # -- resúmenes para paneles ----------------------------------------------
    @staticmethod
    def resumen_funcionario(funcionario, periodo, fecha=None):
        """
        Datos del panel personal (RF-008, RF-028): una fila por meta, total ponderado,
        ajustes, meta esperada al día y semáforo. En períodos cerrados usa los valores congelados.
        """
        cerrado = not periodo.abierto
        fecha = periodo.fecha_termino if cerrado else (fecha or timezone.localdate())
        esperada = CalculoIndicadores.calcular_meta_esperada_al_dia(periodo, fecha)

        filas, total, suma_pond = [], Decimal("0.00"), Decimal("0.00")
        metas = Meta.objects.filter(funcionario=funcionario, periodo=periodo).select_related("item", "periodo")
        for meta in metas:
            guardado = Indicador.objects.filter(meta=meta).first() if cerrado else None
            if guardado:
                v = {"avance": guardado.avance, "cumplimiento": guardado.cumplimiento_pct,
                     "ponderado": guardado.resultado_ponderado, "semaforo": guardado.semaforo}
            else:
                v = CalculoIndicadores._valores_meta(meta, fecha)
            filas.append({"meta": meta, "item": meta.item, **v,
                          "cumple": v["cumplimiento"] >= 100,
                          "bajo_umbral": v["cumplimiento"] < meta.umbral_minimo})
            total += v["ponderado"]
            suma_pond += meta.ponderador

        ajustes = sum((a.puntos for a in Ajuste.objects.filter(funcionario=funcionario, periodo=periodo)),
                      Decimal("0.00"))
        total = calc.redondear(total)
        return {
            "funcionario": funcionario, "periodo": periodo, "filas": filas,
            "total_ponderado": total, "ajustes": ajustes, "resultado_total": calc.redondear(total + ajustes),
            "meta_esperada": esperada, "semaforo": calc.calcular_semaforo(total, esperada),
            "suma_ponderadores": suma_pond, "completa": suma_pond == Decimal("100"),
            "bajo_umbral": calc.esta_bajo_umbral(total),
        }

    @staticmethod
    def resumen_delegacion(funcionarios, periodo, fecha=None):
        """Consolida a los funcionarios entregados: el total sale de sus propios registros (RF-029)."""
        filas = [CalculoIndicadores.resumen_funcionario(f, periodo, fecha) for f in funcionarios]
        cerrado = not periodo.abierto
        esperada = CalculoIndicadores.calcular_meta_esperada_al_dia(
            periodo, periodo.fecha_termino if cerrado else fecha)
        promedio = calc.redondear(sum((f["total_ponderado"] for f in filas), Decimal("0")) / len(filas)) \
            if filas else Decimal("0.00")
        conteo = {s: sum(1 for f in filas if f["semaforo"] == s)
                  for s in (calc.SEMAFORO_VERDE, calc.SEMAFORO_AMBAR, calc.SEMAFORO_ROJO)}
        return {"filas": filas, "promedio": promedio, "meta_esperada": esperada,
                "semaforo": calc.calcular_semaforo(promedio, esperada) if filas else "",
                "conteo": conteo, "total_funcionarios": len(filas),
                "bajo_umbral": [f for f in filas if f["bajo_umbral"]]}
