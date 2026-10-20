"""
Modelo de audit, basado en el diagrama E-R: AUDITORIA
(id_auditoria, evento, fecha, entidad_afectada, id_entidad_afectada, valor_anterior,
valor_nuevo, id_funcionario).

El historial es inalterable (RF-036, RNF-008, HU-30): no se modifica ni se elimina desde la
aplicación; cualquier intento se rechaza y queda registrado como un evento nuevo.
Para endurecerlo en la base, el usuario MySQL de la aplicación puede crearse sin permisos
UPDATE/DELETE sobre la tabla `auditoria` (ver README).
"""
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from organizations.models import Funcionario

EVENTO_INTENTO_ALTERACION = "INTENTO_ALTERACION_AUDITORIA"


class AuditoriaQuerySet(models.QuerySet):
    """Bloquea las operaciones masivas que alterarían el historial."""

    def _bloquear(self, accion):
        Auditoria._registrar_intento(accion, None)
        raise ValidationError(f"El historial de auditoría no admite la operación «{accion}».")

    def update(self, **kwargs):
        self._bloquear("update masivo")

    def delete(self):
        self._bloquear("delete masivo")

    def bulk_update(self, objs, fields, batch_size=None):
        self._bloquear("bulk_update")


class Auditoria(models.Model):
    id_auditoria = models.AutoField(primary_key=True)
    evento = models.CharField(max_length=40, db_index=True)
    fecha = models.DateTimeField(default=timezone.now, editable=False, db_index=True)
    entidad_afectada = models.CharField(max_length=60, blank=True, db_index=True)
    id_entidad_afectada = models.PositiveIntegerField(default=0)
    valor_anterior = models.TextField(null=True, blank=True)
    valor_nuevo = models.TextField(null=True, blank=True)
    # Nulo para acciones del superusuario técnico (sin funcionario) o del sistema
    funcionario = models.ForeignKey(Funcionario, on_delete=models.PROTECT, db_column="id_funcionario",
                                    related_name="auditorias", null=True, blank=True)

    objects = AuditoriaQuerySet.as_manager()

    class Meta:
        db_table = "auditoria"
        ordering = ["-fecha", "-id_auditoria"]
        indexes = [models.Index(fields=["entidad_afectada", "id_entidad_afectada"], name="ix_audit_entidad")]
        verbose_name = "evento de auditoría"
        verbose_name_plural = "auditoría"

    def __str__(self):
        return f"{self.fecha:%d/%m/%Y %H:%M} · {self.evento} · {self.entidad_afectada} {self.id_entidad_afectada}"

    @staticmethod
    def _registrar_intento(accion, instancia):
        """Deja constancia del intento de alteración (HU-30)."""
        Auditoria.objects.create(
            evento=EVENTO_INTENTO_ALTERACION, entidad_afectada="auditoria",
            id_entidad_afectada=getattr(instancia, "pk", None) or 0, valor_nuevo=accion)

    def save(self, *args, **kwargs):
        if not self._state.adding:
            self._registrar_intento("modificar", self)
            raise ValidationError("Los eventos de auditoría no pueden modificarse.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self._registrar_intento("eliminar", self)
        raise ValidationError("Los eventos de auditoría no pueden eliminarse.")
