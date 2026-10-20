"""
Modelos de activities, basados en el diagrama E-R: ACTIVIDAD, EVIDENCIA, VALIDACION.

Decisiones documentadas:
- ACTIVIDAD agrega `periodo` (FK a Periodo): se invirtió la relación del E-R original.
  El período se asigna automáticamente según la fecha de la actividad.
- El código único de la actividad (RF-011) no se guarda como columna: se deriva de su id
  (ACT-0000123), por lo que es único e inmutable. Cada evidencia guarda su propio código
  (ACT-0000123-E01), con relación uno a muchos (RN-010).
- EVIDENCIA.archivo_vinculo: en el E-R figura "activo_vinculo" (error de tipeo); se usa el
  nombre del diagrama de clases y del PDF.
- VALIDACION es un registro histórico: no se modifica ni se elimina (RNF-008).
"""
import os

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

from catalogs.models import Catalogo
from measurement.models import Periodo
from organizations.models import Funcionario, ItemMedible

validar_telefono = RegexValidator(
    r"^\+?\d[\d\s-]{7,14}$", "Teléfono inválido. Use solo números, espacios o guiones (8 a 15 dígitos).")


# ---------------------------------------------------------------------------
# ACTIVIDAD
# ---------------------------------------------------------------------------
class Actividad(models.Model):
    TIPO_ACTIVIDAD, TIPO_SOLICITUD, TIPO_PROBLEMA = "Actividad", "Solicitud", "Problema"
    TIPOS = [(TIPO_ACTIVIDAD, "Actividad"), (TIPO_SOLICITUD, "Solicitud"), (TIPO_PROBLEMA, "Problema")]

    ESTADO_REGISTRADA = "Registrada"
    ESTADO_EN_REVISION = "En revisión"
    ESTADO_VALIDADA = "Validada"                  # único estado que aporta al avance (RN-009)
    ESTADO_RECHAZADA = "Rechazada"
    ESTADO_CORRECCION = "Corrección solicitada"
    ESTADO_ANULADA = "Anulada"
    ESTADOS = [(e, e) for e in (ESTADO_REGISTRADA, ESTADO_EN_REVISION, ESTADO_VALIDADA,
                                ESTADO_RECHAZADA, ESTADO_CORRECCION, ESTADO_ANULADA)]
    ESTADOS_EDITABLES = (ESTADO_REGISTRADA, ESTADO_RECHAZADA, ESTADO_CORRECCION)
    # Mientras está en revisión no se edita, pero se pueden sumar más evidencias (RN-010: 1 a muchos)
    ESTADOS_ADMITEN_EVIDENCIA = ESTADOS_EDITABLES + (ESTADO_EN_REVISION,)

    id_actividad = models.AutoField(primary_key=True)
    fecha = models.DateField(default=timezone.localdate)
    tipo_registro = models.CharField(max_length=10, choices=TIPOS, default=TIPO_ACTIVIDAD)
    accion = models.TextField("acción ejecutada")
    contacto = models.CharField(max_length=150, blank=True)
    telefono = models.CharField(max_length=20, blank=True, validators=[validar_telefono])
    ingreso_agenda_colectiva = models.BooleanField("ingresar a la agenda colectiva", default=False)
    estado = models.CharField(max_length=25, choices=ESTADOS, default=ESTADO_REGISTRADA)
    funcionario = models.ForeignKey(Funcionario, on_delete=models.PROTECT, db_column="id_funcionario",
                                    related_name="actividades")
    item = models.ForeignKey(ItemMedible, on_delete=models.PROTECT, db_column="id_item",
                             related_name="actividades", verbose_name="ítem medible")
    catalogo = models.ForeignKey(Catalogo, on_delete=models.PROTECT, db_column="id_catalogo",
                                 related_name="actividades", verbose_name="actividad / servicio")
    periodo = models.ForeignKey(Periodo, on_delete=models.PROTECT, db_column="id_periodo",
                                related_name="actividades", editable=False)

    class Meta:
        db_table = "actividad"
        ordering = ["-fecha", "-id_actividad"]
        indexes = [models.Index(fields=["funcionario", "item", "periodo", "estado"], name="ix_act_avance")]

    def __str__(self):
        return f"{self.codigo} – {self.fecha:%d/%m/%Y}"

    @property
    def codigo(self):
        """Identificador único e inmutable de la actividad (RF-011)."""
        return f"ACT-{self.pk:07d}" if self.pk else ""

    @property
    def editable(self):
        return self.estado in self.ESTADOS_EDITABLES

    @property
    def admite_evidencia(self):
        return self.estado in self.ESTADOS_ADMITEN_EVIDENCIA

    def clean(self):
        if self.telefono and not self.contacto.strip():
            raise ValidationError({"contacto": "Indique el nombre del contacto cuando registra un teléfono."})
        if self.fecha and self.fecha > timezone.localdate():
            raise ValidationError({"fecha": "La fecha de la actividad no puede ser futura."})
        if self.funcionario_id and self.item_id and self.item.cargo_id != self.funcionario.cargo_id:
            raise ValidationError({"item": "El ítem no corresponde al cargo del funcionario."})


# ---------------------------------------------------------------------------
# EVIDENCIA
# ---------------------------------------------------------------------------
def ruta_evidencia(instance, filename):
    """Nombre seguro: se usa el código de la evidencia, nunca el nombre que trae el archivo."""
    extension = os.path.splitext(filename)[1].lower()
    return f"evidencias/{timezone.now():%Y/%m}/{instance.codigo_evidencia}{extension}"


class Evidencia(models.Model):
    ESTADO_PENDIENTE = "Pendiente"
    ESTADO_APROBADA = "Aprobada"
    ESTADO_RECHAZADA = "Rechazada"
    ESTADO_CORRECCION = "Corrección"
    ESTADOS = [(e, e) for e in (ESTADO_PENDIENTE, ESTADO_APROBADA, ESTADO_RECHAZADA, ESTADO_CORRECCION)]

    id_evidencia = models.AutoField(primary_key=True)
    codigo_evidencia = models.CharField(max_length=30, unique=True, editable=False)
    archivo_vinculo = models.FileField(upload_to=ruta_evidencia, max_length=255)
    fecha_carga = models.DateTimeField(default=timezone.now, editable=False)
    metadatos = models.JSONField(default=dict, blank=True)
    estado_revision = models.CharField(max_length=12, choices=ESTADOS, default=ESTADO_PENDIENTE)
    actividad = models.ForeignKey(Actividad, on_delete=models.PROTECT, db_column="id_actividad",
                                  related_name="evidencias")
    funcionario = models.ForeignKey(Funcionario, on_delete=models.PROTECT, db_column="id_funcionario",
                                    related_name="evidencias_cargadas")   # autor de la carga

    class Meta:
        db_table = "evidencia"
        ordering = ["actividad", "id_evidencia"]

    def __str__(self):
        return self.codigo_evidencia

    @property
    def extension(self):
        return os.path.splitext(self.archivo_vinculo.name)[1].lower().lstrip(".")

    @property
    def es_imagen(self):
        return self.extension in ("jpg", "jpeg", "png")

    def save(self, *args, **kwargs):
        if self.pk:   # el código es inmutable (RN-010)
            original = Evidencia.objects.filter(pk=self.pk).values_list("codigo_evidencia", flat=True).first()
            if original and original != self.codigo_evidencia:
                raise ValidationError("El código de evidencia es inmutable.")
        super().save(*args, **kwargs)


# ---------------------------------------------------------------------------
# VALIDACION (historial inalterable de decisiones)
# ---------------------------------------------------------------------------
class Validacion(models.Model):
    DECISION_APROBADA = "Aprobada"
    DECISION_RECHAZADA = "Rechazada"
    DECISION_CORRECCION = "Corrección"
    DECISIONES = [(d, d) for d in (DECISION_APROBADA, DECISION_RECHAZADA, DECISION_CORRECCION)]

    id_validacion = models.AutoField(primary_key=True)
    decision = models.CharField(max_length=12, choices=DECISIONES)
    fecha = models.DateTimeField(default=timezone.now, editable=False)
    observacion = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)
    evidencia = models.ForeignKey(Evidencia, on_delete=models.PROTECT, db_column="id_evidencia",
                                  related_name="validaciones")
    funcionario = models.ForeignKey(Funcionario, on_delete=models.PROTECT, db_column="id_funcionario",
                                    related_name="validaciones")           # verificador

    class Meta:
        db_table = "validacion"
        ordering = ["evidencia", "version"]
        constraints = [models.UniqueConstraint(fields=["evidencia", "version"], name="uq_validacion_version")]

    def __str__(self):
        return f"{self.evidencia} v{self.version}: {self.decision}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Las validaciones no pueden modificarse: registre una nueva revisión.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Las validaciones no pueden eliminarse.")
