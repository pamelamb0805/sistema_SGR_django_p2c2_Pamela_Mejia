from django.conf import settings
from django.db import models
from core.models import BaseModel

# Create your models here.

# Modelo catalogo --Pamela 
#Eva2 verbose_name y return --> esp -> pm
class Catalog(BaseModel):
    catalog_id = models.CharField(max_length=50, unique=True, verbose_name="Código de catálogo")
    name = models.CharField(max_length=150, verbose_name="Nombre")
    description = models.TextField(blank=True, null=True, verbose_name="Descripción")
    status = models.CharField(max_length=50, blank=True, null=True, verbose_name="Estado")

    class Meta:
        verbose_name = "Catálogo"
        verbose_name_plural = "Catálogos"
        ordering = ["name"]

    def __str__(self):
        return f"{self.catalog_id} - {self.name}"

# Modelo producto --Pamela
#Eva2 verbose_name y return --> esp -> pm
class Product(BaseModel):
    product_id = models.CharField(max_length=50, unique=True, verbose_name="Código de producto")
    name = models.CharField(max_length=150, verbose_name="Nombre")
    description = models.TextField(blank=True, null=True, verbose_name="Descripción")
    # CORREGIDO: Se agregó "verbose_name=" que faltaba
    kwh = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, verbose_name="Consumo (kWh)")
    manufacturer = models.CharField(max_length=150, blank=True, null=True, verbose_name="Fabricante")
    model = models.CharField(max_length=150, blank=True, null=True, verbose_name="Modelo")
    sku = models.CharField(max_length=100, unique=True, verbose_name="SKU")

    catalog = models.ForeignKey(
        Catalog,
        on_delete=models.PROTECT,
        related_name="products",
        verbose_name="Catálogo"
    )
    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Productos"
        ordering = ["name"]

    def __str__(self):
        return f"{self.sku} - {self.name}"

# Modelo device --Pamela
#Eva2 verbose_name y return --> esp -> pm
class Device(BaseModel):
    device_id = models.CharField(max_length=50, unique=True, verbose_name="Código de dispositivo")
    internal_name = models.CharField(max_length=150, verbose_name="Nombre interno")
    description = models.TextField(blank=True, null=True, verbose_name="Descripción")
    reference_power = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, verbose_name="Potencia de referencia (kW)")
    serial_number = models.CharField(max_length=100, unique=True, blank=True, null=True, verbose_name="Número de serie")
    status = models.CharField(max_length=50, blank=True, null=True, verbose_name="Estado")

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="devices",
        verbose_name="Producto"
    )
    zone = models.ForeignKey(
        "organizations.Zone",
        on_delete=models.PROTECT,
        related_name="devices",
        verbose_name="Zona"
    )
    class Meta:
        verbose_name = "Dispositivo"
        verbose_name_plural = "Dispositivos"
        ordering = ["internal_name"]

    def __str__(self):
        return f"{self.device_id} - {self.internal_name}"

# Modelo Measurement --Pamela
#Eva2 verbose_name y return --> esp -> pm
class Measurement(BaseModel):
    measurement_id = models.CharField(max_length=50, unique=True, verbose_name="Código de medición")
    value = models.DecimalField(max_digits=12, decimal_places=4, verbose_name="Valor")
    unit = models.CharField(max_length=50, verbose_name="Unidad de medida")
    datetime = models.DateTimeField(verbose_name="Fecha y hora de lectura")
    status = models.CharField(max_length=50, blank=True, null=True, verbose_name="Estado")
    origin = models.CharField(max_length=50, verbose_name="Origen")

    device = models.ForeignKey(
        Device,
        on_delete=models.PROTECT,
        related_name="measurements",
        verbose_name="Dispositivo"
    )
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="measurements",
        blank=True,
        null=True,
        verbose_name="Usuario registrador"
    )

    class Meta:
        verbose_name = "Medición"
        verbose_name_plural = "Mediciones"
        ordering = ["-datetime"]  # Mostrar mediciones más recientes --> pm

    def __str__(self):
        return f"{self.measurement_id} ({self.value} {self.unit})"


# Modelo alert_rule --Pamela
#Eva2 verbose_name y return --> esp -> pm
class AlertRule(BaseModel):
    alert_rule_id = models.CharField(max_length=50, unique=True, verbose_name="Código de regla de alerta")
    name = models.CharField(max_length=150, verbose_name="Nombre de la regla")
    severity = models.CharField(max_length=50, verbose_name="Severidad")
    unit = models.CharField(max_length=50, blank=True, null=True, verbose_name="Unidad de medida")
    min_limit = models.DecimalField(max_digits=12, decimal_places=4, blank=True, null=True, verbose_name="Límite mínimo")
    max_limit = models.DecimalField(max_digits=12, decimal_places=4, blank=True, null=True, verbose_name="Límite máximo")
    status = models.CharField(max_length=50, blank=True, null=True, verbose_name="Estado")

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="alert_rules",
        verbose_name="Producto",
    )

    class Meta:
        verbose_name = "Regla de alerta"
        verbose_name_plural = "Reglas de alerta"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.severity})"


# Modelo alert_event --Pamela
#Eva2 verbose_name y return --> esp -> pm
class AlertEvent(BaseModel):
    alert_event_id = models.CharField(max_length=50, unique=True, verbose_name="Código de evento de alerta")
    min_limit_snapshot = models.DecimalField(max_digits=12, decimal_places=4, blank=True, null=True, verbose_name="Límite mínimo (snapshot)")
    max_limit_snapshot = models.DecimalField(max_digits=12, decimal_places=4, blank=True, null=True, verbose_name="Límite máximo (snapshot)")
    status = models.CharField(max_length=50, blank=True, null=True, verbose_name="Estado")
    observations = models.TextField(blank=True, null=True, verbose_name="Observaciones")
    acknowledged_at = models.DateTimeField(blank=True, null=True, verbose_name="Fecha de reconocimiento")
    resolved_at = models.DateTimeField(blank=True, null=True, verbose_name="Fecha de resolución")

    acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="acknowledged_alert_events",
        blank=True,
        null=True,
        verbose_name="Reconocido por"
    )
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="resolved_alert_events",
        blank=True,
        null=True,
        verbose_name="Resuelto por"
    )
    measurement = models.ForeignKey(
        Measurement,
        on_delete=models.PROTECT,
        related_name="alert_events",
        verbose_name="Medición relacionada",
    )
    device = models.ForeignKey(
        Device,
        on_delete=models.PROTECT,
        related_name="alert_events",
        verbose_name="Dispositivo",
    )
    alert_rule = models.ForeignKey(
        AlertRule,
        on_delete=models.PROTECT,
        related_name="alert_events",
        verbose_name="Regla de alerta"
    )

    class Meta:
        verbose_name = "Evento de alerta"
        verbose_name_plural = "Eventos de alerta"
        ordering = ["-created_at"]  # Muestra primero las alertas más recientes

    def __str__(self):
        return f"Alerta {self.alert_event_id} ({self.device.internal_name if self.device else 'Sin dispositivo'})"


# Modelo MaintenanceRequest
#Eva2 verbose_name y return --> esp -> pm
class MaintenanceRequest(BaseModel):
    maintenance_request_id = models.CharField(max_length=50, unique=True, verbose_name="Código de solicitud")
    request_type = models.CharField(max_length=100, blank=True, null=True, verbose_name="Tipo de solicitud")
    reason = models.CharField(max_length=255, blank=True, null=True, verbose_name="Motivo")
    priority = models.CharField(max_length=50, blank=True, null=True, verbose_name="Prioridad")
    status = models.CharField(max_length=50, blank=True, null=True, verbose_name="Estado")
    scheduled_date = models.DateTimeField(blank=True, null=True, verbose_name="Fecha programada")
    actual_date = models.DateTimeField(blank=True, null=True, verbose_name="Fecha real de ejecución")
    diagnosis = models.TextField(blank=True, null=True, verbose_name="Diagnóstico")
    actions_text = models.TextField(blank=True, null=True, verbose_name="Acciones realizadas")
    observations = models.TextField(blank=True, null=True, verbose_name="Observaciones")
    cost = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, verbose_name="Costo")
    closed_at = models.DateTimeField(blank=True, null=True, verbose_name="Fecha de cierre")
    
    device = models.ForeignKey(
        Device,
        on_delete=models.PROTECT,
        related_name="maintenance_requests",
        blank=True,
        null=True,
        verbose_name="Dispositivo"
    )
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="maintenance_requests",
        verbose_name="Organización"
    )
    request_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="requested_maintenance_requests",
        verbose_name="Solicitado por"
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="assigned_maintenance_requests",
        blank=True,
        null=True,
        verbose_name="Asignado a"
    )

    class Meta:
        verbose_name = "Solicitud de mantenimiento"
        verbose_name_plural = "Solicitudes de mantenimiento"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Solicitud {self.maintenance_request_id} ({self.priority or 'Sin prioridad'})"


# Modelo History
#Eva2 verbose_name y return --> esp -> pm
class History(BaseModel):
    history_id = models.CharField(max_length=50, unique=True, verbose_name="Código de historial")
    start_date = models.DateTimeField(blank=True, null=True, verbose_name="Fecha de inicio")
    end_date = models.DateTimeField(blank=True, null=True, verbose_name="Fecha de término")
    reason = models.CharField(max_length=255, blank=True, null=True, verbose_name="Razón")

    device = models.ForeignKey(
        Device,
        on_delete=models.PROTECT,
        related_name="histories",
        verbose_name="Dispositivo"
    )
    zone = models.ForeignKey(
        "organizations.Zone",
        on_delete=models.PROTECT,
        related_name="histories",
        blank=True,
        null=True,
        verbose_name="Zona",
    )

    class Meta:
        verbose_name = "Historial"
        verbose_name_plural = "Historiales"
        ordering = ["-start_date"]

    def __str__(self):
        return f"Historial {self.history_id} - {self.device.internal_name if self.device else 'Sin dispositivo'}"