"""
Modelos de measurement, 100 % basados en el diagrama E-R: PERIODO, META, INDICADOR, AJUSTE.

Decisión de diseño: en el E-R original PERIODO tenía FK a ACTIVIDAD y COMPROMISO. Se invirtió:
son Actividad y Compromiso quienes apuntan a Periodo (campo `periodo`), por eso PERIODO
no tiene esas dos columnas.
"""
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from organizations.models import Cargo, Funcionario, ItemMedible

from . import calculations as calc


def umbral_por_defecto():
    return Decimal(str(settings.SGR_UMBRAL_COLECTIVO))


def maximo_por_defecto():
    return Decimal(str(settings.SGR_TOPE_CUMPLIMIENTO))


# ---------------------------------------------------------------------------
# PERIODO
# ---------------------------------------------------------------------------
class PeriodoQuerySet(models.QuerySet):
    def para_fecha(self, fecha=None):
        """Período que contiene la fecha (los períodos no se superponen)."""
        fecha = fecha or timezone.localdate()
        return self.filter(fecha_inicio__lte=fecha, fecha_termino__gte=fecha).first()

    def vigente(self, fecha=None):
        fecha = fecha or timezone.localdate()
        return self.filter(estado=Periodo.ESTADO_ABIERTO, fecha_inicio__lte=fecha,
                           fecha_termino__gte=fecha).first()

    def abiertos(self):
        return self.filter(estado=Periodo.ESTADO_ABIERTO)


class Periodo(models.Model):
    ESTADO_ABIERTO = "Abierto"
    ESTADO_CERRADO = "Cerrado"
    ESTADOS = [(ESTADO_ABIERTO, "Abierto"), (ESTADO_CERRADO, "Cerrado")]

    id_periodo = models.AutoField(primary_key=True)
    fecha_inicio = models.DateField()
    fecha_termino = models.DateField()
    dias_computables = models.PositiveIntegerField(editable=False, default=0)
    estado = models.CharField(max_length=10, choices=ESTADOS, default=ESTADO_ABIERTO)
    version_parametros = models.PositiveIntegerField(default=1)

    objects = PeriodoQuerySet.as_manager()

    class Meta:
        db_table = "periodo"
        ordering = ["-fecha_inicio"]

    def __str__(self):
        return f"{self.fecha_inicio:%d/%m/%Y} – {self.fecha_termino:%d/%m/%Y}"

    @property
    def abierto(self):
        return self.estado == self.ESTADO_ABIERTO

    def clean(self):
        if self.fecha_inicio and self.fecha_termino:
            if self.fecha_termino < self.fecha_inicio:
                raise ValidationError({"fecha_termino": "La fecha de término no puede ser anterior a la de inicio."})
            superpuestos = Periodo.objects.filter(
                fecha_inicio__lte=self.fecha_termino, fecha_termino__gte=self.fecha_inicio,
            ).exclude(pk=self.pk)
            if superpuestos.exists():
                raise ValidationError("El período se superpone con otro período existente.")

    def save(self, *args, **kwargs):
        if self.fecha_inicio and self.fecha_termino and self.fecha_termino >= self.fecha_inicio:
            self.dias_computables = calc.calcular_dias_computables(self.fecha_inicio, self.fecha_termino)
        super().save(*args, **kwargs)


# ---------------------------------------------------------------------------
# META
# ---------------------------------------------------------------------------
class Meta(models.Model):
    id_meta = models.AutoField(primary_key=True)
    valor_objetivo = models.DecimalField(max_digits=10, decimal_places=2,
                                         validators=[MinValueValidator(Decimal("0.01"))])   # RN-002
    unidad = models.CharField(max_length=30)
    ponderador = models.DecimalField(max_digits=5, decimal_places=2,
                                     validators=[MinValueValidator(Decimal("0.01"))])        # % del cargo
    umbral_minimo = models.DecimalField(max_digits=5, decimal_places=2, default=umbral_por_defecto)
    maximo_computable = models.DecimalField(max_digits=6, decimal_places=2, default=maximo_por_defecto,
                                            validators=[MinValueValidator(Decimal("0.01"))])
    fecha_version = models.DateField(default=timezone.localdate)
    item = models.ForeignKey(ItemMedible, on_delete=models.PROTECT, db_column="id_item", related_name="metas")
    funcionario = models.ForeignKey(Funcionario, on_delete=models.PROTECT, db_column="id_funcionario",
                                    related_name="metas")
    periodo = models.ForeignKey(Periodo, on_delete=models.PROTECT, db_column="id_periodo", related_name="metas")
    cargo = models.ForeignKey(Cargo, on_delete=models.PROTECT, db_column="id_cargo", related_name="metas")

    class Meta:
        db_table = "meta"
        ordering = ["periodo", "funcionario", "item"]
        constraints = [
            models.UniqueConstraint(fields=["funcionario", "item", "periodo"], name="uq_meta_func_item_periodo"),
        ]

    def __str__(self):
        return f"{self.item.nombre_item} – {self.funcionario} ({self.periodo})"

    def clean(self):
        errores = {}
        if self.ponderador is not None and self.ponderador > 100:
            errores["ponderador"] = "El ponderador no puede superar 100 %."
        if self.umbral_minimo is not None and not (0 <= self.umbral_minimo <= 100):
            errores["umbral_minimo"] = "El umbral mínimo debe estar entre 0 y 100 %."
        if self.funcionario_id and self.item_id and self.item.cargo_id != self.funcionario.cargo_id:
            errores["item"] = "El ítem no pertenece al cargo del funcionario."
        if errores:
            raise ValidationError(errores)


# ---------------------------------------------------------------------------
# INDICADOR (uno por meta; se recalcula, no se digita)
# ---------------------------------------------------------------------------
class Indicador(models.Model):
    id_indicador = models.AutoField(primary_key=True)
    meta = models.OneToOneField(Meta, on_delete=models.CASCADE, db_column="id_meta", related_name="indicador")
    avance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cumplimiento_pct = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    resultado_ponderado = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    semaforo = models.CharField(max_length=10, blank=True)
    fecha_calculo = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "indicador"

    def __str__(self):
        return f"Indicador de {self.meta}"


# ---------------------------------------------------------------------------
# AJUSTE (incentivos y penalizaciones, RF-025 / RN-011)
# ---------------------------------------------------------------------------
class Ajuste(models.Model):
    EFECTO_POSITIVO = "Positivo"
    EFECTO_NEGATIVO = "Negativo"
    EFECTOS = [(EFECTO_POSITIVO, "Positivo (incentivo)"), (EFECTO_NEGATIVO, "Negativo (penalización)")]

    id_ajuste = models.AutoField(primary_key=True)
    motivo = models.CharField(max_length=255)
    valor = models.DecimalField(max_digits=6, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))],
                                help_text="Puntos porcentuales sobre el resultado ponderado personal.")
    efecto = models.CharField(max_length=10, choices=EFECTOS)
    funcionario = models.ForeignKey(Funcionario, on_delete=models.PROTECT, db_column="id_funcionario",
                                    related_name="ajustes")
    periodo = models.ForeignKey(Periodo, on_delete=models.PROTECT, db_column="id_periodo", related_name="ajustes")
    meta = models.ForeignKey(Meta, on_delete=models.SET_NULL, db_column="id_meta", related_name="ajustes",
                             null=True, blank=True)

    class Meta:
        db_table = "ajuste"
        ordering = ["-id_ajuste"]

    def __str__(self):
        return f"{self.efecto} {self.valor} – {self.funcionario}"

    @property
    def puntos(self):
        """Valor con signo según el efecto."""
        return self.valor if self.efecto == self.EFECTO_POSITIVO else -self.valor

    def clean(self):
        if self.meta_id and self.funcionario_id and self.periodo_id:
            if self.meta.funcionario_id != self.funcionario_id or self.meta.periodo_id != self.periodo_id:
                raise ValidationError({"meta": "La meta debe corresponder al mismo funcionario y período."})
