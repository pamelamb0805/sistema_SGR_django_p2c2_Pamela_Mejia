"""
Modelos de agenda, basados en el diagrama E-R: COMPROMISO y HISTORIAL_TRANSICIONES.

Decisiones documentadas:
- COMPROMISO agrega `periodo` (FK a Periodo, nullable): se invirtió la relación del E-R original.
  Se asigna según la fecha comprometida; si aún no existe un período para esa fecha queda vacío
  y se completa al cerrar el compromiso.
- `fecha_comprometida` es una fecha (no fecha y hora): evita depender de las tablas de zona
  horaria de MySQL y es lo que realmente se compromete.
- `item_medible` es opcional: solo los compromisos asociados a un ítem alimentan el indicador
  individual (RF-020, "cuando el ítem así lo configure").
- El historial de transiciones es inalterable (RF-018, RNF-008).
"""
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from measurement.models import Periodo
from organizations.models import Delegacion, Funcionario, ItemMedible


class CompromisoQuerySet(models.QuerySet):
    def abiertos(self):
        return self.exclude(estado=Compromiso.ESTADO_REALIZADO)

    def vencidos(self, hoy=None):
        return self.abiertos().filter(fecha_comprometida__lt=hoy or timezone.localdate())

    def por_vencer(self, hoy=None, dias=None):
        hoy = hoy or timezone.localdate()
        dias = settings.SGR_DIAS_ALERTA_VENCIMIENTO if dias is None else dias
        return self.abiertos().filter(fecha_comprometida__gte=hoy, fecha_comprometida__lte=hoy + timedelta(days=dias))


class Compromiso(models.Model):
    ESTADO_INGRESADO = "Ingresado"
    ESTADO_PENDIENTE = "Pendiente"
    ESTADO_EN_PROCESO = "En proceso"
    ESTADO_REALIZADO = "Realizado"        # único estado que puede aportar al avance (RF-020)
    ESTADOS = [(e, e) for e in (ESTADO_INGRESADO, ESTADO_PENDIENTE, ESTADO_EN_PROCESO, ESTADO_REALIZADO)]

    # Transiciones controladas (RF-018). Reabrir un realizado exige rol de supervisión y observación.
    TRANSICIONES = {
        ESTADO_INGRESADO: (ESTADO_PENDIENTE, ESTADO_EN_PROCESO, ESTADO_REALIZADO),
        ESTADO_PENDIENTE: (ESTADO_EN_PROCESO, ESTADO_REALIZADO),
        ESTADO_EN_PROCESO: (ESTADO_PENDIENTE, ESTADO_REALIZADO),
        ESTADO_REALIZADO: (ESTADO_EN_PROCESO,),
    }

    PLAZO_REALIZADO_EN_PLAZO = "Realizado en plazo"
    PLAZO_REALIZADO_FUERA = "Realizado fuera de plazo"
    PLAZO_VENCIDO = "Vencido"
    PLAZO_POR_VENCER = "Por vencer"
    PLAZO_VIGENTE = "Vigente"

    id_compromiso = models.AutoField(primary_key=True)
    origen = models.CharField(max_length=150, help_text="Ej.: solicitud interna, solicitud externa, Actividad ACT-0000123.")
    solicitante = models.CharField(max_length=150)
    territorio = models.CharField(max_length=150)
    fecha_comprometida = models.DateField()
    area_apoyo = models.CharField("área de apoyo", max_length=100, blank=True)
    estado = models.CharField(max_length=12, choices=ESTADOS, default=ESTADO_INGRESADO)
    observacion = models.TextField("observación de avance", blank=True)
    funcionario = models.ForeignKey(Funcionario, on_delete=models.PROTECT, db_column="id_funcionario",
                                    related_name="compromisos", verbose_name="responsable")
    delegacion = models.ForeignKey(Delegacion, on_delete=models.PROTECT, db_column="id_delegacion",
                                   related_name="compromisos")
    item_medible = models.ForeignKey(ItemMedible, on_delete=models.PROTECT, db_column="id_item_medible",
                                     related_name="compromisos", null=True, blank=True,
                                     verbose_name="ítem medible")
    periodo = models.ForeignKey(Periodo, on_delete=models.PROTECT, db_column="id_periodo",
                                related_name="compromisos", null=True, blank=True, editable=False)

    # Extensión de COMPROMISO para solicitudes vecinales. No crea una entidad
    # adicional y mantiene las FK del diagrama E-R original.
    CANAL_PRESENCIAL = "Presencial"
    CANALES_SOLICITUD = [(CANAL_PRESENCIAL, "Presencial")]
    TIPO_GENERAL = "General"
    TIPO_REGALO = "Regalo / evento día festivo"
    TIPOS_SOLICITUD = [(TIPO_GENERAL, "Solicitud vecinal"), (TIPO_REGALO, TIPO_REGALO)]
    ESTADO_SOLICITUD_CREADO = "Creado"
    ESTADO_SOLICITUD_PENDIENTE = "Pendiente"
    ESTADO_SOLICITUD_PROCESO = "Proceso"
    ESTADO_SOLICITUD_CONCLUIDO = "Concluido"
    ESTADOS_SOLICITUD = [(v, v) for v in (ESTADO_SOLICITUD_CREADO, ESTADO_SOLICITUD_PENDIENTE, ESTADO_SOLICITUD_PROCESO, ESTADO_SOLICITUD_CONCLUIDO)]
    RELACIONES_VECINALES = [
        ("Delegado", "Delegado"),
        ("Presidente", "Presidente de junta de vecinos"),
        ("Secretario", "Secretario de junta de vecinos"),
        ("Miembro", "Ciudadano miembro de junta de vecinos"),
    ]

    rut_solicitante = models.CharField(max_length=12, blank=True, default="", db_index=True)
    relacion_vecinal = models.CharField(max_length=20, choices=RELACIONES_VECINALES, blank=True, default="")
    canal_solicitud = models.CharField(max_length=20, choices=CANALES_SOLICITUD, default=CANAL_PRESENCIAL)
    tipo_solicitud = models.CharField(max_length=40, choices=TIPOS_SOLICITUD, blank=True, default="")
    categoria_solicitud = models.CharField(max_length=80, blank=True, default="", db_index=True)
    descripcion_solicitud = models.TextField(blank=True, default="")
    solucion = models.TextField(blank=True, default="")
    estado_solicitud = models.CharField(max_length=12, choices=ESTADOS_SOLICITUD, default=ESTADO_SOLICITUD_CREADO, db_index=True)
    fecha_creacion = models.DateTimeField(default=timezone.now, editable=False, db_index=True)
    fecha_propuesta_solucion = models.DateField(null=True, blank=True)
    # NULL permite múltiples compromisos que no son regalos; un RUT no nulo
    # solo puede existir una vez en toda la tabla y, por tanto, en el sistema.
    rut_menor = models.CharField(max_length=12, unique=True, null=True, blank=True)
    nombre_menor = models.CharField(max_length=150, blank=True, default="")

    objects = CompromisoQuerySet.as_manager()

    class Meta:
        db_table = "compromiso"
        ordering = ["fecha_comprometida", "id_compromiso"]
        indexes = [models.Index(fields=["funcionario", "item_medible", "periodo", "estado"], name="ix_comp_avance")]

    def save(self, *args, **kwargs):
        if not self.rut_menor:
            self.rut_menor = None
        # La fecha original se conserva incluso si alguien intenta modificarla
        # desde una instancia del ORM. No confiar solo en el formulario.
        if self.pk:
            original = type(self).objects.filter(pk=self.pk).values_list("fecha_creacion", flat=True).first()
            if original is not None:
                self.fecha_creacion = original
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Compromiso {self.pk}: {self.solicitante} ({self.fecha_comprometida:%d/%m/%Y})"

    def clean(self):
        errores = {}
        if self.funcionario_id and self.item_medible_id and self.item_medible.cargo_id != self.funcionario.cargo_id:
            errores["item_medible"] = "El ítem no corresponde al cargo del responsable."
        if self.tipo_solicitud == self.TIPO_REGALO:
            if not self.rut_solicitante:
                errores["rut_solicitante"] = "El RUT del adulto/tutor es obligatorio para un regalo."
            if not self.rut_menor:
                errores["rut_menor"] = "El RUT del menor es obligatorio para un regalo."
        elif self.rut_menor:
            errores["rut_menor"] = "El RUT del menor solo se utiliza en solicitudes de regalo."
        if errores:
            raise ValidationError(errores)

    @property
    def realizado(self):
        return self.estado == self.ESTADO_REALIZADO

    @property
    def fecha_cierre(self):
        """Fecha de la última transición a 'Realizado' (usa el historial; conviene prefetch)."""
        cierres = [h.fecha for h in self.historial.all() if h.estado_nuevo == self.ESTADO_REALIZADO]
        return timezone.localtime(max(cierres)).date() if cierres else None

    @property
    def fecha_registro_historica(self):
        """
        Recupera la fecha original de creación del compromiso desde
        el primer evento de auditoría. Como respaldo utiliza la primera
        transición registrada.
        """
        from audit.models import Auditoria

        evento = (
            Auditoria.objects
            .filter(
                entidad_afectada="compromiso",
                id_entidad_afectada=self.pk,
            )
            .order_by("fecha", "id_auditoria")
            .first()
        )

        if evento:
            return evento.fecha

        primera_transicion = (
            self.historial
            .order_by("fecha", "id_cambio")
            .first()
        )

        if primera_transicion:
            return primera_transicion.fecha

        return self.fecha_comprometida


    @property
    def delegacion_historica(self):
        """
        Devuelve los datos de la delegación que tenía el compromiso
        cuando fue creado.
        """
        if not self.delegacion_id:
            return None

        return (
            self.delegacion.obtener_version_historica(
                self.fecha_registro_historica
            )
            or self.delegacion.obtener_datos_actuales()
        )
    
    @property
    def plazo(self):
        """Situación respecto del plazo (RF-019)."""
        hoy = timezone.localdate()
        if self.realizado:
            cierre = self.fecha_cierre
            return self.PLAZO_REALIZADO_FUERA if cierre and cierre > self.fecha_comprometida \
                else self.PLAZO_REALIZADO_EN_PLAZO
        if self.fecha_comprometida < hoy:
            return self.PLAZO_VENCIDO
        if self.fecha_comprometida <= hoy + timedelta(days=settings.SGR_DIAS_ALERTA_VENCIMIENTO):
            return self.PLAZO_POR_VENCER
        return self.PLAZO_VIGENTE


class HistorialTransiciones(models.Model):
    id_cambio = models.AutoField(primary_key=True)
    estado_anterior = models.CharField(max_length=12, blank=True)    # vacío al registrar el compromiso
    estado_nuevo = models.CharField(max_length=12)
    fecha = models.DateTimeField(default=timezone.now, editable=False)
    observacion = models.TextField(blank=True)
    compromiso = models.ForeignKey(Compromiso, on_delete=models.PROTECT, db_column="id_compromiso",
                                   related_name="historial")
    funcionario = models.ForeignKey(Funcionario, on_delete=models.PROTECT, db_column="id_funcionario",
                                    related_name="transiciones")      # autor del cambio

    class Meta:
        db_table = "historial_transiciones"
        ordering = ["fecha", "id_cambio"]
        verbose_name = "historial de transiciones"
        verbose_name_plural = "historial de transiciones"

    def __str__(self):
        return f"{self.compromiso_id}: {self.estado_anterior or '—'} → {self.estado_nuevo}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("El historial no puede modificarse.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("El historial no puede eliminarse.")
