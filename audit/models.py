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
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey


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
    def _registrar_intento(
        accion,
        instancia=None,
        usuario=None,
        id_entidad=None,
    ):
        """
        Registra un intento de modificación o eliminación
        del historial de auditoría.

        Cuando se conoce al usuario que realiza el intento,
        conserva su funcionario asociado y su identificador.
        """
        funcionario = None
        nombre_usuario = "Usuario no identificado"

        if usuario is not None:
            nombre_usuario = (
                usuario.get_username()
                if hasattr(usuario, "get_username")
                else str(usuario)
            )

            funcionario = getattr(
                usuario,
                "funcionario",
                None,
            )

        identificador = (
            getattr(instancia, "pk", None)
            or id_entidad
            or 0
        )

        Auditoria.objects.create(
            evento=EVENTO_INTENTO_ALTERACION,
            entidad_afectada="auditoria",
            id_entidad_afectada=identificador,
            valor_nuevo=(
                f"Acción: {accion}; "
                f"Usuario: {nombre_usuario}"
            ),
            funcionario=funcionario,
        )


    def save(self, *args, **kwargs):
        if not self._state.adding:
            self._registrar_intento("modificar", self)
            raise ValidationError("Los eventos de auditoría no pueden modificarse.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self._registrar_intento("eliminar", self)
        raise ValidationError("Los eventos de auditoría no pueden eliminarse.")

class Notificacion(models.Model):
    """
    Notificación persistente asociada a un evento de auditoría.

    Cada usuario tiene su propio estado de lectura.
    La notificación no desaparece al cerrar sesión ni recargar la página.
    """

    id_notificacion = models.AutoField(primary_key=True)

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notificaciones",
        verbose_name="Usuario destinatario",
    )

    auditoria = models.ForeignKey(
        Auditoria,
        on_delete=models.PROTECT,
        related_name="notificaciones",
        verbose_name="Evento de auditoría",
    )

    delegacion = models.ForeignKey(
        "organizations.Delegacion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notificaciones",
        verbose_name="Delegación relacionada",
    )

    leida = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name="Leída",
    )

    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name="Fecha de creación",
    )

    fecha_lectura = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fecha de lectura",
    )

    class Meta:
        db_table = "notificacion_usuario"

        ordering = [
            "-fecha_creacion",
            "-id_notificacion",
        ]

        constraints = [
            models.UniqueConstraint(
                fields=["usuario", "auditoria"],
                name="uq_notificacion_usuario_auditoria",
            ),
        ]

        indexes = [
            models.Index(
                fields=["usuario", "leida", "fecha_creacion"],
                name="ix_notif_usuario_leida",
            ),
        ]

        verbose_name = "notificación"
        verbose_name_plural = "notificaciones"

    def __str__(self):
        estado = "Leída" if self.leida else "Pendiente"

        return (
            f"{self.usuario} · "
            f"Auditoría #{self.auditoria_id} · "
            f"{estado}"
        )


class ComentarioRegistro(models.Model):
    """
    Conversación asociada a un registro del SGR.

    Conserva autor, funcionario, delegación, fecha y referencia
    al objeto mediante ContentType.
    Los mensajes no pueden modificarse ni eliminarse.
    """

    id_comentario = models.AutoField(primary_key=True)

    content_type = models.ForeignKey(
        "contenttypes.ContentType",
        on_delete=models.PROTECT,
        related_name="comentarios_sgr",
    )

    object_id = models.PositiveIntegerField(db_index=True)

    content_object = GenericForeignKey(
        "content_type",
        "object_id",
    )

    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="comentarios_sgr",
    )

    funcionario = models.ForeignKey(
        Funcionario,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="comentarios_sgr",
    )

    delegacion = models.ForeignKey(
        "organizations.Delegacion",
        on_delete=models.PROTECT,
        related_name="comentarios_sgr",
    )

    respuesta_a = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="respuestas",
    )

    mensaje = models.TextField()

    fecha_creacion = models.DateTimeField(
        default=timezone.now,
        editable=False,
        db_index=True,
    )

    class Meta:
        db_table = "comentario_registro"
        ordering = ["fecha_creacion", "id_comentario"]
        indexes = [
            models.Index(
                fields=["content_type", "object_id", "fecha_creacion"],
                name="ix_comentario_registro",
            ),
            models.Index(
                fields=["delegacion", "fecha_creacion"],
                name="ix_comentario_delegacion",
            ),
        ]
        verbose_name = "comentario de registro"
        verbose_name_plural = "comentarios de registros"

    def __str__(self):
        return (
            f"Comentario #{self.pk} · "
            f"{self.autor} · {self.fecha_creacion:%d/%m/%Y %H:%M}"
        )

    def clean(self):
        self.mensaje = (self.mensaje or "").strip()

        if not self.mensaje:
            raise ValidationError({
                "mensaje": "El comentario no puede estar vacío."
            })

        if self.respuesta_a_id:
            padre = self.respuesta_a

            if (
                padre.content_type_id != self.content_type_id
                or padre.object_id != self.object_id
                or padre.delegacion_id != self.delegacion_id
            ):
                raise ValidationError({
                    "respuesta_a": (
                        "La respuesta debe pertenecer a la misma "
                        "conversación y registro."
                    )
                })

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError(
                "Los comentarios publicados no pueden modificarse."
            )

        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(
            "Los comentarios publicados no pueden eliminarse."
        )

class AlertaOperativa(models.Model):
    """
    Alerta operativa persistente del RF-037.
    Cada usuario conserva su propio estado de atención.
    """

    ESTADO_PENDIENTE = "Pendiente"
    ESTADO_ATENDIDA = "Atendida"

    ESTADOS = [
        (ESTADO_PENDIENTE, "Pendiente"),
        (ESTADO_ATENDIDA, "Atendida"),
    ]

    id_alerta = models.AutoField(primary_key=True)

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="alertas_operativas",
    )

    clave = models.CharField(
        max_length=64,
        db_index=True,
    )

    tipo = models.CharField(max_length=40)
    titulo = models.CharField(max_length=180)
    motivo = models.TextField()
    responsable = models.CharField(max_length=180)
    fecha = models.DateField()
    url = models.CharField(max_length=500, blank=True)
    nivel = models.CharField(max_length=20, default="warning")
    prioridad = models.PositiveSmallIntegerField(default=10)

    estado = models.CharField(
        max_length=15,
        choices=ESTADOS,
        default=ESTADO_PENDIENTE,
        db_index=True,
    )

    fecha_generacion = models.DateTimeField(
        auto_now=True,
    )

    fecha_atencion = models.DateTimeField(
        null=True,
        blank=True,
    )

    atendida_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="alertas_atendidas",
    )

    class Meta:
        db_table = "alerta_operativa"
        ordering = ["prioridad", "fecha", "id_alerta"]
        constraints = [
            models.UniqueConstraint(
                fields=["usuario", "clave"],
                name="uq_alerta_usuario_clave",
            ),
        ]
        indexes = [
            models.Index(
                fields=["usuario", "estado"],
                name="ix_alerta_usuario_estado",
            ),
        ]
        verbose_name = "alerta operativa"
        verbose_name_plural = "alertas operativas"

    def __str__(self):
        return f"{self.titulo} - {self.estado}"
