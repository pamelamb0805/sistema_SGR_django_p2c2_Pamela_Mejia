
"""
Servicios de measurement.
Las fórmulas están en calculations.py y aquí se orquestan
las operaciones con la base de datos.
"""

import json
from decimal import Decimal

from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from core.exceptions import ReglaNegocioError
from core.mixins import (
    auditar,
    tiene_rol,
    ROLES_CONFIGURACION,
    ROLES_MEDICION,
)
from core.services import (
    eliminar,
    guardar,
    snapshot,
    _notificar_crud,
)
from organizations.models import Funcionario

from . import calculations as calc
from .models import (
    Ajuste,
    Indicador,
    Meta,
    Periodo,
    ReglaCalculoVersion,
)
from django.conf import settings
from types import SimpleNamespace
from datetime import datetime, time

ACTIVIDAD_VALIDADA = "Validada"
COMPROMISO_REALIZADO = "Realizado"


# ---------------------------------------------------------------------------
# VALIDACIONES GENERALES
# ---------------------------------------------------------------------------

def _exigir_rol(actor, roles, mensaje):
    """Valida permisos también en la capa de servicios."""
    if not tiene_rol(actor, *roles):
        raise ReglaNegocioError(mensaje)


def _validar_periodo(periodo):
    """Valida fechas, superposición y reglas del modelo."""
    try:
        periodo.full_clean()
    except ValidationError as exc:
        raise ReglaNegocioError("; ".join(exc.messages)) from exc


def _exigir_abierto(periodo, accion="modificar"):
    """Impide modificar períodos cerrados."""
    actual = Periodo.objects.get(pk=periodo.pk)

    if not actual.abierto:
        raise ReglaNegocioError(
            f"El período {actual} está cerrado: "
            f"no se puede {accion}. "
            "Solo un administrador puede reabrirlo."
        )

    return actual


# ---------------------------------------------------------------------------
# CRUDPeriodo
# ---------------------------------------------------------------------------


class CRUDPeriodo:

    @staticmethod
    def _datos_reglas_actuales():
        return {
            "tope_cumplimiento": str(settings.SGR_TOPE_CUMPLIMIENTO),
            "umbral_colectivo": str(settings.SGR_UMBRAL_COLECTIVO),
            "umbral_ambar": str(settings.SGR_SEMAFORO_AMBAR),
            "suma_ponderadores": str(settings.SGR_SUMA_PONDERADORES),
            "version_formula_cumplimiento": 1,
            "version_formula_ponderacion": 1,
            "version_formula_meta_esperada": 1,
            "version_formula_semaforo": 1,
            "version_formula_dias": 1,
        }


    @staticmethod
    def _registrar_version_reglas(periodo, actor=None, datos=None):
        """
        Cierra la versión anterior y registra una nueva versión
        de las reglas de cálculo del período.
        """
        ahora = timezone.now()

        anterior = (
            ReglaCalculoVersion.objects
            .select_for_update()
            .filter(
                periodo=periodo,
                vigente_hasta__isnull=True,
            )
            .order_by("-numero_version")
            .first()
        )

        if anterior:
            anterior.vigente_hasta = ahora
            anterior.save(update_fields=["vigente_hasta"])

        return ReglaCalculoVersion.objects.create(
            periodo=periodo,
            numero_version=periodo.version_parametros,
            vigente_desde=ahora,
            datos=datos or CRUDPeriodo._datos_reglas_actuales(),
            creado_por=(
                actor
                if getattr(actor, "is_authenticated", False)
                else None
            ),
        )


    @staticmethod
    def actualizar_reglas_periodo(periodo, datos, actor=None):
        """
        Registra una nueva versión de las reglas de cálculo,
        conserva las anteriores y recalcula el período abierto.

        Las versiones anteriores permanecen disponibles para
        consultas históricas.
        """
        _exigir_rol(
            actor,
            ROLES_CONFIGURACION,
            "Solo un Administrador puede modificar las reglas de cálculo.",
        )

        if not isinstance(datos, dict):
            raise ReglaNegocioError(
                "La configuración de reglas no es válida."
            )

        campos = (
            "tope_cumplimiento",
            "umbral_colectivo",
            "umbral_ambar",
        )

        try:
            valores = {
                campo: Decimal(str(datos[campo]))
                for campo in campos
            }
        except (KeyError, ValueError, TypeError, ArithmeticError) as exc:
            raise ReglaNegocioError(
                "Debe ingresar todos los parámetros numéricos."
            ) from exc

        if valores["tope_cumplimiento"] <= 0:
            raise ReglaNegocioError(
                "El tope de cumplimiento debe ser mayor que cero."
            )

        for campo in ("umbral_colectivo", "umbral_ambar"):
            if not Decimal("0") <= valores[campo] <= Decimal("100"):
                raise ReglaNegocioError(
                    f"{campo} debe estar entre 0 y 100."
                )

        with transaction.atomic():
            periodo = (
                Periodo.objects
                .select_for_update()
                .get(pk=periodo.pk)
            )

            if not periodo.abierto:
                raise ReglaNegocioError(
                    "No se pueden modificar las reglas de un período cerrado."
                )

            anterior = snapshot(periodo)

            version_actual = (
                ReglaCalculoVersion.objects
                .select_for_update()
                .filter(periodo=periodo)
                .order_by("-numero_version")
                .first()
            )

            configuracion = (
                dict(version_actual.datos)
                if version_actual
                else CRUDPeriodo._datos_reglas_actuales()
            )

            configuracion.update({
                campo: str(valor)
                for campo, valor in valores.items()
            })

            if (
                version_actual
                and version_actual.datos == configuracion
            ):
                return version_actual

            periodo.version_parametros += 1
            periodo.save(update_fields=["version_parametros"])

            nueva_version = CRUDPeriodo._registrar_version_reglas(
                periodo,
                actor,
                datos=configuracion,
            )

            # RF-038: los indicadores abiertos se recalculan
            # utilizando la nueva versión vigente.
            CalculoIndicadores.recalcular_periodo(
                periodo,
                fecha=timezone.localdate(),
                forzar=True,
            )

            auditar(
                actor,
                "ACTUALIZAR_REGLAS_PERIODO",
                "periodo",
                periodo.pk,
                anterior,
                json.dumps(
                    {
                        "version": nueva_version.numero_version,
                        "vigente_desde": (
                            nueva_version.vigente_desde.isoformat()
                        ),
                        "datos": nueva_version.datos,
                    },
                    ensure_ascii=False,
                    default=str,
                ),
            )

            _notificar_crud(
                "periodo",
                "actualizar",
                actor,
                periodo,
            )

            return nueva_version

    @staticmethod
    def calcular_dias_computables(fecha_inicio, fecha_termino):
        try:
            return calc.calcular_dias_computables(
                fecha_inicio,
                fecha_termino,
            )
        except ValueError as exc:
            raise ReglaNegocioError(str(exc)) from exc

    @staticmethod
    def crear_periodo(periodo, actor=None):
        _exigir_rol(
            actor,
            ROLES_MEDICION,
            "No tiene permiso para crear períodos.",
        )

        with transaction.atomic():
            periodo.estado = Periodo.ESTADO_ABIERTO
            periodo.version_parametros = 1

            _validar_periodo(periodo)

            periodo = guardar(
                periodo,
                actor,
                "periodo",
            )

            CRUDPeriodo._registrar_version_reglas(
                periodo,
                actor,
            )

        return periodo

    @staticmethod
    def mostrar_todos_periodos():
        return Periodo.objects.all()

    @staticmethod
    def modificar_periodo(periodo, actor=None):
        _exigir_rol(
            actor,
            ROLES_MEDICION,
            "No tiene permiso para modificar períodos.",
        )

        with transaction.atomic():
            original = (
                Periodo.objects
                .select_for_update()
                .get(pk=periodo.pk)
            )

            if not original.abierto:
                raise ReglaNegocioError(
                    "No se puede modificar un período cerrado."
                )

            fechas_cambiaron = (
                original.fecha_inicio != periodo.fecha_inicio
                or original.fecha_termino != periodo.fecha_termino
            )

            _validar_periodo(periodo)

            periodo.version_parametros = (
                original.version_parametros
                + (1 if fechas_cambiaron else 0)
            )

            guardar(periodo, actor, "periodo")

            if fechas_cambiaron:
                CRUDPeriodo._registrar_version_reglas(
                    periodo,
                    actor,
                )

            CalculoIndicadores.recalcular_periodo(
                periodo,
                forzar=True,
            )

        return periodo
    @staticmethod
    def cerrar_periodo(periodo, actor=None):
        """Congela los indicadores y bloquea modificaciones."""
        _exigir_rol(
            actor,
            ROLES_MEDICION,
            "No tiene permiso para cerrar períodos.",
        )

        with transaction.atomic():
            periodo = (
                Periodo.objects
                .select_for_update()
                .get(pk=periodo.pk)
            )

            if not periodo.abierto:
                raise ReglaNegocioError(
                    "El período ya está cerrado."
                )

            CalculoIndicadores.recalcular_periodo(
                periodo,
                fecha=periodo.fecha_termino,
                forzar=True,
            )

            anterior = snapshot(periodo)

            periodo.estado = Periodo.ESTADO_CERRADO
            periodo.save(update_fields=["estado"])

            auditar(
                actor,
                "CERRAR_PERIODO",
                "periodo",
                periodo.pk,
                anterior,
                snapshot(periodo),
            )

            _notificar_crud(
                "periodo",
                "actualizar",
                actor,
                periodo,
            )

        return periodo

    @staticmethod
    def reabrir_periodo(periodo, motivo, actor=None):
        """Reabre un período y registra una nueva versión de reglas."""
        _exigir_rol(
            actor,
            ROLES_CONFIGURACION,
            "Solo un Administrador puede reabrir períodos.",
        )

        motivo = (motivo or "").strip()

        if not motivo:
            raise ReglaNegocioError(
                "Debe indicar el motivo de la reapertura."
            )

        with transaction.atomic():
            periodo = (
                Periodo.objects
                .select_for_update()
                .get(pk=periodo.pk)
            )

            if periodo.abierto:
                raise ReglaNegocioError(
                    "El período ya está abierto."
                )

            anterior = snapshot(periodo)

            periodo.estado = Periodo.ESTADO_ABIERTO
            periodo.version_parametros += 1

            periodo.save(
                update_fields=[
                    "estado",
                    "version_parametros",
                ]
            )

            # RF-038: registrar la nueva versión al reabrir.
            CRUDPeriodo._registrar_version_reglas(
                periodo,
                actor,
            )

            auditar(
                actor,
                "REABRIR_PERIODO",
                "periodo",
                periodo.pk,
                anterior,
                json.dumps(
                    {
                        "motivo": motivo,
                        "periodo": json.loads(snapshot(periodo)),
                    },
                    ensure_ascii=False,
                ),
            )

            _notificar_crud(
                "periodo",
                "actualizar",
                actor,
                periodo,
            )

        return periodo

# ---------------------------------------------------------------------------
# CRUDMeta
# ---------------------------------------------------------------------------

class CRUDMeta:

    @staticmethod
    def mostrar_metas_por_funcionario(funcionario, periodo=None):
        qs = Meta.objects.filter(
            funcionario=funcionario
        ).select_related(
            "item",
            "periodo",
        )

        return qs.filter(periodo=periodo) if periodo else qs

    @staticmethod
    def suma_ponderaciones(
        funcionario,
        periodo,
        excluir_meta=None,
    ):
        qs = Meta.objects.filter(
            funcionario=funcionario,
            periodo=periodo,
        )

        if excluir_meta:
            qs = qs.exclude(pk=excluir_meta)

        return sum(
            (m.ponderador for m in qs),
            Decimal("0.00"),
        )

    @staticmethod
    def validar_suma_ponderaciones(cargo, periodo):
        """
        RF-006: verifica las ponderaciones por funcionario,
        cargo y período.

        Permite identificar configuraciones pendientes,
        completas o excedidas sin impedir su configuración
        progresiva.
        """
        resultado = []

        funcionarios = Funcionario.objects.filter(
            cargo=cargo,
            estado=Funcionario.ESTADO_ACTIVO,
        ).select_related("cargo", "delegacion")

        for funcionario in funcionarios:
            suma = CRUDMeta.suma_ponderaciones(
                funcionario,
                periodo,
            )

            faltante = max(
                Decimal("0.00"),
                Decimal("100.00") - suma,
            )

            excedente = max(
                Decimal("0.00"),
                suma - Decimal("100.00"),
            )

            completa = suma == Decimal("100.00")

            if completa:
                estado = "Completa"
            elif suma < Decimal("100.00"):
                estado = "Pendiente"
            else:
                estado = "Excedida"

            resultado.append({
                "funcionario": funcionario,
                "cargo": cargo,
                "periodo": periodo,
                "suma": suma,
                "faltante": faltante,
                "excedente": excedente,
                "completa": completa,
                "estado": estado,
            })

        return resultado
    @staticmethod
    def _preparar(meta):
        meta.cargo_id = meta.funcionario.cargo_id
        meta.fecha_version = timezone.localdate()

    @staticmethod
    def _validar(meta, es_nueva, actor=None):
        _exigir_rol(
            actor,
            ROLES_MEDICION,
            "No tiene permiso para configurar metas.",
        )

        _exigir_abierto(
            meta.periodo,
            "configurar metas",
        )

        if es_nueva:
            if not meta.funcionario.activo:
                raise ReglaNegocioError(
                    "El funcionario está inactivo."
                )

            if not meta.item.vigencia:
                raise ReglaNegocioError(
                    "El ítem medible no está vigente."
                )

        duplicada = Meta.objects.filter(
            funcionario=meta.funcionario,
            item=meta.item,
            periodo=meta.periodo,
        ).exclude(
            pk=meta.pk
        ).exists()

        if duplicada:
            raise ReglaNegocioError(
                "Ya existe una meta para ese funcionario, "
                "ítem y período."
            )

        suma = (
            CRUDMeta.suma_ponderaciones(
                meta.funcionario,
                meta.periodo,
                meta.pk,
            )
            + meta.ponderador
        )

        if suma > Decimal("100"):
            raise ReglaNegocioError(
                f"La suma de ponderaciones sería {suma} %. "
                "No puede superar 100 %."
            )

        try:
            meta.full_clean()
        except ValidationError as exc:
            raise ReglaNegocioError(
                "; ".join(exc.messages)
            ) from exc

        
    @staticmethod
    def _datos_version(meta):
        return {
            "valor_objetivo": str(meta.valor_objetivo),
            "unidad": meta.unidad,
            "ponderador": str(meta.ponderador),
            "umbral_minimo": str(meta.umbral_minimo),
            "maximo_computable": str(meta.maximo_computable),
            "item_id": meta.item_id,
            "funcionario_id": meta.funcionario_id,
            "periodo_id": meta.periodo_id,
            "cargo_id": meta.cargo_id,
            "item_codigo": meta.item.codigo,
            "item_nombre": meta.item.nombre_item,
            "item_descripcion": meta.item.descripcion,
            "item_tipo": meta.item.tipo,
        }

    @staticmethod
    def _registrar_version(meta, actor=None):
        """
        Registra una fotografía inmutable de la meta.
        La versión anterior se conserva y se cierra.
        """
        from .models import MetaVersion

        ultima = (
            MetaVersion.objects
            .select_for_update()
            .filter(objeto_id=meta.pk)
            .order_by("-numero_version")
            .first()
        )

        ahora = timezone.now()

        if ultima:
            ultima.vigente_hasta = ahora
            ultima.save(update_fields=["vigente_hasta"])
            numero = ultima.numero_version + 1
        else:
            numero = 1

        datos = CRUDMeta._datos_version(meta)

        MetaVersion.objects.create(
            meta=meta,
            objeto_id=meta.pk,
            numero_version=numero,
            vigente_desde=ahora,
            datos=datos,
            creado_por=(
                actor
                if getattr(actor, "is_authenticated", False)
                else None
            ),
        )

    @staticmethod
    def crear_meta(meta, actor=None):
        _exigir_rol(
            actor,
            ROLES_MEDICION,
            "No tiene permiso para crear metas.",
        )

        with transaction.atomic():
            CRUDMeta._preparar(meta)

            CRUDMeta._validar(
                meta,
                es_nueva=True,
                actor=actor,
            )

            guardar(meta, actor, "meta")

            CRUDMeta._registrar_version(meta, actor)

            CalculoIndicadores.recalcular_indicador_meta(meta)

        return meta

    @staticmethod
    def crear_meta_para_cargo(meta_base, actor=None):
        """
        Replica una meta para funcionarios activos del mismo cargo.
        """
        _exigir_rol(
            actor,
            ROLES_MEDICION,
            "No tiene permiso para crear metas por cargo.",
        )

        creadas = []
        omitidas = []

        candidatos = Funcionario.objects.filter(
            cargo=meta_base.funcionario.cargo,
            estado=Funcionario.ESTADO_ACTIVO,
        )

        for funcionario in candidatos:
            copia = Meta(
                item=meta_base.item,
                periodo=meta_base.periodo,
                funcionario=funcionario,
                valor_objetivo=meta_base.valor_objetivo,
                unidad=meta_base.unidad,
                ponderador=meta_base.ponderador,
                umbral_minimo=meta_base.umbral_minimo,
                maximo_computable=meta_base.maximo_computable,
            )

            try:
                creada = CRUDMeta.crear_meta(
                    copia,
                    actor,
                )
                creadas.append(creada)

            except ReglaNegocioError as exc:
                omitidas.append(
                    (funcionario, str(exc))
                )

        return {
            "creadas": creadas,
            "omitidas": omitidas,
        }

    @staticmethod
    def modificar_meta(meta, actor=None):
        _exigir_rol(
            actor,
            ROLES_MEDICION,
            "No tiene permiso para modificar metas.",
        )

        with transaction.atomic():
            original = Meta.objects.select_for_update().get(
                pk=meta.pk
            )

            if (
                original.funcionario_id,
                original.item_id,
                original.periodo_id,
            ) != (
                meta.funcionario_id,
                meta.item_id,
                meta.periodo_id,
            ):
                raise ReglaNegocioError(
                    "No se puede cambiar el funcionario, "
                    "el ítem ni el período de una meta."
                )

            CRUDMeta._preparar(meta)

            CRUDMeta._validar(
                meta,
                es_nueva=False,
                actor=actor,
            )

            guardar(meta, actor, "meta")

            CRUDMeta._registrar_version(meta, actor)

            CalculoIndicadores.recalcular_indicador_meta(meta)

        return meta

    @staticmethod
    def eliminar_meta(meta, actor=None):
        _exigir_rol(
            actor,
            ROLES_MEDICION,
            "No tiene permiso para eliminar metas.",
        )

        _exigir_abierto(
            meta.periodo,
            "eliminar metas",
        )

        eliminar(
            meta,
            actor,
            "meta",
            "No se puede eliminar la meta porque tiene registros asociados.",
        )


# ---------------------------------------------------------------------------
# CRUDAjuste
# ---------------------------------------------------------------------------

class CRUDAjuste:

    @staticmethod
    def crear_ajuste(ajuste, actor=None):
        _exigir_rol(
            actor,
            ROLES_MEDICION,
            "No tiene permiso para registrar incentivos o penalizaciones.",
        )

        _exigir_abierto(
            ajuste.periodo,
            "registrar ajustes",
        )

        try:
            ajuste.full_clean()
        except ValidationError as exc:
            raise ReglaNegocioError(
                "; ".join(exc.messages)
            ) from exc

        return guardar(
            ajuste,
            actor,
            "ajuste",
        )

    @staticmethod
    def modificar_ajuste(ajuste, actor=None):
        _exigir_rol(
            actor,
            ROLES_MEDICION,
            "No tiene permiso para modificar ajustes.",
        )

        with transaction.atomic():
            original = Ajuste.objects.select_for_update().get(
                pk=ajuste.pk
            )

            _exigir_abierto(
                original.periodo,
                "modificar ajustes",
            )

            _exigir_abierto(
                ajuste.periodo,
                "modificar ajustes",
            )

            try:
                ajuste.full_clean()
            except ValidationError as exc:
                raise ReglaNegocioError(
                    "; ".join(exc.messages)
                ) from exc

            return guardar(
                ajuste,
                actor,
                "ajuste",
            )

    @staticmethod
    def eliminar_ajuste(ajuste, actor=None):
        _exigir_rol(
            actor,
            ROLES_MEDICION,
            "No tiene permiso para eliminar ajustes.",
        )

        _exigir_abierto(
            ajuste.periodo,
            "eliminar ajustes",
        )

        eliminar(
            ajuste,
            actor,
            "ajuste",
            "No se puede eliminar el ajuste.",
        )


# ---------------------------------------------------------------------------
# UTILIDADES DE INDICADORES
# ---------------------------------------------------------------------------

def _modelo(app_label, nombre):
    try:
        return apps.get_model(app_label, nombre)
    except LookupError:
        return None


# ---------------------------------------------------------------------------
# CalculoIndicadores
# ---------------------------------------------------------------------------

class CalculoIndicadores:

    @staticmethod
    def _reglas_periodo(periodo, fecha=None):
        """
        Recupera las reglas que estaban vigentes al finalizar
        el día consultado, respetando fecha y hora de registro.
        """
        fecha = fecha or timezone.localdate()

        if isinstance(fecha, datetime):
            fecha = fecha.date()

        instante = timezone.make_aware(
            datetime.combine(fecha, time.max)
        )

        versiones = (
            ReglaCalculoVersion.objects
            .filter(
                periodo=periodo,
                vigente_desde__lte=instante,
            )
            .order_by(
                "-vigente_desde",
                "-numero_version",
            )
        )

        version = versiones.filter(
            vigente_hasta__isnull=True,
        ).first()

        if version is None:
            version = versiones.filter(
                vigente_hasta__gt=instante,
            ).first()

        if version:
            return version.datos

        # Compatibilidad con períodos anteriores al versionamiento.
        return CRUDPeriodo._datos_reglas_actuales()

    @staticmethod
    def crear_avance_actual(meta):
        """
        Avance = actividades validadas + compromisos realizados.
        """
        total = 0

        Actividad = _modelo(
            "activities",
            "Actividad",
        )

        if Actividad is not None:
            total += Actividad.objects.filter(
                funcionario_id=meta.funcionario_id,
                item_id=meta.item_id,
                periodo_id=meta.periodo_id,
                estado=ACTIVIDAD_VALIDADA,
            ).count()

        Compromiso = _modelo(
            "agenda",
            "Compromiso",
        )

        if Compromiso is not None:
            total += Compromiso.objects.filter(
                funcionario_id=meta.funcionario_id,
                item_medible_id=meta.item_id,
                periodo_id=meta.periodo_id,
                estado=COMPROMISO_REALIZADO,
            ).count()

        return Decimal(total)

    @staticmethod
    def calcular_porcentaje_cumplimiento(meta, avance=None):
        if avance is None:
            avance = CalculoIndicadores.crear_avance_actual(meta)

        return calc.calcular_porcentaje_cumplimiento(
            avance,
            meta.valor_objetivo,
        )

    @staticmethod
    def calcular_cumplimiento_ponderado(
        meta,
        cumplimiento=None,
    ):
        if cumplimiento is None:
            cumplimiento = (
                CalculoIndicadores.calcular_porcentaje_cumplimiento(
                    meta
                )
            )

        return calc.calcular_cumplimiento_ponderado(
            cumplimiento,
            meta.ponderador,
            meta.maximo_computable,
        )

    @staticmethod
    def calcular_meta_esperada_al_dia(periodo, fecha=None):
        return calc.calcular_meta_esperada(
            periodo.fecha_inicio,
            periodo.fecha_termino,
            fecha or timezone.localdate(),
        )

    @staticmethod
    def calcular_semaforo(meta, cumplimiento=None, fecha=None):
        if cumplimiento is None:
            cumplimiento = (
                CalculoIndicadores.calcular_porcentaje_cumplimiento(
                    meta
                )
            )

        fecha_calculo = fecha or timezone.localdate()

        esperada = (
            CalculoIndicadores.calcular_meta_esperada_al_dia(
                meta.periodo,
                fecha_calculo,
            )
        )

        reglas = CalculoIndicadores._reglas_periodo(
            meta.periodo,
            fecha_calculo,
        )

        return calc.calcular_semaforo(
            cumplimiento,
            esperada,
            umbral_ambar=reglas["umbral_ambar"],
        )


    @staticmethod
    def _valores_meta(meta, fecha, datos_historicos=None):
        """
        Calcula los indicadores usando la versión histórica
        de la meta y las reglas vigentes en la fecha consultada.
        """
        datos = datos_historicos or CRUDMeta._datos_version(meta)

        valor_objetivo = Decimal(
            str(datos["valor_objetivo"])
        )

        ponderador = Decimal(
            str(datos["ponderador"])
        )

        maximo_computable = Decimal(
            str(datos["maximo_computable"])
        )

        reglas = CalculoIndicadores._reglas_periodo(
            meta.periodo,
            fecha,
        )

        tope_reglas = Decimal(
            str(
                reglas.get(
                    "tope_cumplimiento",
                    maximo_computable,
                )
            )
        )

        maximo_aplicable = min(
            maximo_computable,
            tope_reglas,
        )

        avance = CalculoIndicadores.crear_avance_actual(meta)

        cumplimiento = calc.calcular_porcentaje_cumplimiento(
            avance,
            valor_objetivo,
        )

        ponderado = calc.calcular_cumplimiento_ponderado(
            cumplimiento,
            ponderador,
            maximo_aplicable,
        )

        esperada = (
            CalculoIndicadores.calcular_meta_esperada_al_dia(
                meta.periodo,
                fecha,
            )
        )

        return {
            "avance": calc.redondear(avance),
            "cumplimiento": cumplimiento,
            "ponderado": ponderado,
            "semaforo": calc.calcular_semaforo(
                cumplimiento,
                esperada,
                umbral_ambar=reglas["umbral_ambar"],
            ),
        }


    @staticmethod
    def _datos_meta_historicos(meta, fecha):
        """
        Recupera la versión de la meta vigente al finalizar
        el día consultado.

        Las versiones posteriores no pueden reemplazar los
        parámetros históricos de una meta.
        """
        from .models import MetaVersion

        if isinstance(fecha, datetime):
            fecha = fecha.date()

        instante = timezone.make_aware(
            datetime.combine(fecha, time.max)
        )

        versiones = (
            MetaVersion.objects
            .filter(
                objeto_id=meta.pk,
                vigente_desde__lte=instante,
            )
            .order_by(
                "-vigente_desde",
                "-numero_version",
            )
        )

        version = versiones.filter(
            vigente_hasta__isnull=True,
        ).first()

        if version is None:
            version = versiones.filter(
                vigente_hasta__gt=instante,
            ).first()

        if version:
            return version.datos

        # Compatibilidad con metas antiguas sin historial.
        return CRUDMeta._datos_version(meta)


    # -----------------------------------------------------------------------
    # PERSISTENCIA
    # -----------------------------------------------------------------------

    @staticmethod
    def recalcular_indicador_meta(
        meta,
        fecha=None,
        forzar=False,
    ):
        """Recalcula usando los parámetros vigentes en la fecha indicada."""
        if not meta.periodo.abierto and not forzar:
            return Indicador.objects.filter(
                meta=meta
            ).first()

        fecha_calculo = fecha or timezone.localdate()

        if not meta.periodo.abierto or forzar:
            datos_historicos = (
                CalculoIndicadores._datos_meta_historicos(
                    meta,
                    fecha_calculo,
                )
            )
        else:
            datos_historicos = CRUDMeta._datos_version(meta)

        valores = CalculoIndicadores._valores_meta(
            meta,
            fecha_calculo,
            datos_historicos=datos_historicos,
        )

        indicador, _ = Indicador.objects.update_or_create(
            meta=meta,
            defaults={
                "avance": valores["avance"],
                "cumplimiento_pct": valores["cumplimiento"],
                "resultado_ponderado": valores["ponderado"],
                "semaforo": valores["semaforo"],
                "fecha_calculo": timezone.now(),
            },
        )

        return indicador
    @staticmethod
    def recalcular_para(
        funcionario_id,
        item_id,
        periodo_id,
    ):
        metas = Meta.objects.filter(
            funcionario_id=funcionario_id,
            item_id=item_id,
            periodo_id=periodo_id,
        ).select_related("periodo")

        return [
            CalculoIndicadores.recalcular_indicador_meta(meta)
            for meta in metas
        ]

    @staticmethod
    def recalcular_periodo(
        periodo,
        fecha=None,
        forzar=False,
    ):
        metas = Meta.objects.filter(
            periodo=periodo
        ).select_related("periodo")

        for meta in metas:
            CalculoIndicadores.recalcular_indicador_meta(
                meta,
                fecha=fecha,
                forzar=forzar,
            )

        return metas.count()

    # -----------------------------------------------------------------------
    # RESÚMENES
    # -----------------------------------------------------------------------

    @staticmethod
    def resumen_funcionario(
        funcionario,
        periodo,
        fecha=None,
    ):
        """
        Genera el resumen del funcionario utilizando las versiones
        históricas de metas, ítems y reglas cuando el período está cerrado.
        """
        cerrado = not periodo.abierto

        fecha = (
            periodo.fecha_termino
            if cerrado
            else (fecha or timezone.localdate())
        )

        esperada = (
            CalculoIndicadores.calcular_meta_esperada_al_dia(
                periodo,
                fecha,
            )
        )

        reglas = CalculoIndicadores._reglas_periodo(
            periodo,
            fecha,
        )

        filas = []
        total = Decimal("0.00")
        suma_pond = Decimal("0.00")

        metas = Meta.objects.filter(
            funcionario=funcionario,
            periodo=periodo,
        ).select_related(
            "item",
            "periodo",
        )

        for meta in metas:

            # Recuperar la versión de la meta vigente en la fecha.
            if cerrado:
                datos_historicos = (
                    CalculoIndicadores._datos_meta_historicos(
                        meta,
                        fecha,
                    )
                )
            else:
                datos_historicos = CRUDMeta._datos_version(meta)

            ponderador_historico = Decimal(
                str(datos_historicos["ponderador"])
            )

            umbral_historico = Decimal(
                str(datos_historicos["umbral_minimo"])
            )

            # Recuperar la versión histórica del ítem.
            if cerrado:
                from django.db.models import Q
                from organizations.models import ItemMedibleVersion

                instante_cierre = timezone.make_aware(
                    datetime.combine(fecha, time.max)
                )

                version_item = (
                    ItemMedibleVersion.objects
                    .filter(
                        objeto_id=meta.item_id,
                        vigente_desde__lte=instante_cierre,
                    )
                    .filter(
                        Q(vigente_hasta__isnull=True)
                        | Q(vigente_hasta__gt=instante_cierre)
                    )
                    .order_by(
                        "-vigente_desde",
                        "-numero_version",
                    )
                    .first()
                )

                # La versión del ítem tiene prioridad.
                # Si no existe, se utiliza la fotografía de la meta.
                datos_item = (
                    version_item.datos
                    if version_item
                    else datos_historicos
                )

                item_historico = SimpleNamespace(
                    pk=meta.item_id,
                    codigo=datos_item.get(
                        "codigo",
                        datos_item.get(
                            "item_codigo",
                            meta.item.codigo,
                        ),
                    ),
                    nombre_item=datos_item.get(
                        "nombre_item",
                        datos_item.get(
                            "item_nombre",
                            meta.item.nombre_item,
                        ),
                    ),
                    descripcion=datos_item.get(
                        "descripcion",
                        datos_item.get(
                            "item_descripcion",
                            meta.item.descripcion,
                        ),
                    ),
                    tipo=datos_item.get(
                        "tipo",
                        datos_item.get(
                            "item_tipo",
                            meta.item.tipo,
                        ),
                    ),
                    vigencia=datos_item.get(
                        "vigencia",
                        meta.item.vigencia,
                    ),
                )
            else:
                item_historico = meta.item

            # Los indicadores de períodos cerrados se consultan
            # sin recalcularlos ni reemplazarlos.
            guardado = (
                Indicador.objects.filter(
                    meta=meta
                ).first()
                if cerrado
                else None
            )

            if guardado:
                valores = {
                    "avance": guardado.avance,
                    "cumplimiento": guardado.cumplimiento_pct,
                    "ponderado": guardado.resultado_ponderado,
                    "semaforo": guardado.semaforo,
                }
            else:
                valores = CalculoIndicadores._valores_meta(
                    meta,
                    fecha,
                    datos_historicos=datos_historicos,
                )

            cumple = valores["cumplimiento"] >= 100

            bajo_umbral = (
                valores["cumplimiento"] < umbral_historico
            )

            filas.append({
                "meta": meta,
                "item": item_historico,
                "datos_historicos": datos_historicos,
                "ponderador_historico": ponderador_historico,
                "umbral_historico": umbral_historico,
                **valores,
                "cumple": cumple,
                "bajo_umbral": bajo_umbral,
            })

            total += valores["ponderado"]
            suma_pond += ponderador_historico

        ajustes = sum(
            (
                ajuste.puntos
                for ajuste in Ajuste.objects.filter(
                    funcionario=funcionario,
                    periodo=periodo,
                )
            ),
            Decimal("0.00"),
        )

        total = calc.redondear(total)

        return {
            "funcionario": funcionario,
            "periodo": periodo,
            "filas": filas,
            "total_ponderado": total,
            "ajustes": ajustes,
            "resultado_total": calc.redondear(
                total + ajustes
            ),
            "meta_esperada": esperada,
            "semaforo": calc.calcular_semaforo(
                total,
                esperada,
                umbral_ambar=reglas["umbral_ambar"],
            ),
            "suma_ponderadores": suma_pond,
            "completa": (
                suma_pond == Decimal("100")
            ),
            "bajo_umbral": calc.esta_bajo_umbral(
                total,
                reglas["umbral_colectivo"],
            ),
        }

    @staticmethod
    def resumen_delegacion(
        funcionarios,
        periodo,
        fecha=None,
    ):
        filas = [
            CalculoIndicadores.resumen_funcionario(
                funcionario,
                periodo,
                fecha,
            )
            for funcionario in funcionarios
        ]

        cerrado = not periodo.abierto

        esperada = (
            CalculoIndicadores.calcular_meta_esperada_al_dia(
                periodo,
                periodo.fecha_termino if cerrado else fecha,
            )
        )

        fecha_reglas = (
            periodo.fecha_termino
            if cerrado
            else (fecha or timezone.localdate())
        )

        reglas = CalculoIndicadores._reglas_periodo(
            periodo,
            fecha_reglas,
        )

        promedio = (
            calc.redondear(
                sum(
                    (
                        fila["total_ponderado"]
                        for fila in filas
                    ),
                    Decimal("0"),
                ) / len(filas)
            )
            if filas
            else Decimal("0.00")
        )

        conteo = {
            semaforo: sum(
                1
                for fila in filas
                if fila["semaforo"] == semaforo
            )
            for semaforo in (
                calc.SEMAFORO_VERDE,
                calc.SEMAFORO_AMBAR,
                calc.SEMAFORO_ROJO,
            )
        }

        return {
            "filas": filas,
            "promedio": promedio,
            "meta_esperada": esperada,
            "semaforo": (
                calc.calcular_semaforo(
                    promedio,
                    esperada,
                    umbral_ambar=reglas["umbral_ambar"],
                )
                if filas
                else ""
            ),
            "conteo": conteo,
            "total_funcionarios": len(filas),
            "bajo_umbral": [
                fila
                for fila in filas
                if fila["bajo_umbral"]
            ],
        }
