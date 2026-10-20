"""
Modelo de catalogs, basado en el diagrama E-R: CATALOGO
(id_catalogo, tipo_catalogo, nombre, area, estado).

Cumple RF-004 y HU-27:
- Tipos de actividad, servicio, atención y subatención por área.
- Un elemento desactivado no se ofrece en registros nuevos pero se conserva en los antiguos
  (las FK desde Actividad y AtencionSocial usarán on_delete=PROTECT).
"""
from django.core.exceptions import ValidationError
from django.db import models


class CatalogoQuerySet(models.QuerySet):
    def activos(self):
        return self.filter(estado=Catalogo.ESTADO_ACTIVO)

    def disponibles(self, area=None, tipo=None):
        """
        Opciones que un formulario debe mostrar: solo activas y aplicables al área
        (las del área indicada más las de área 'General').
        """
        qs = self.activos()
        if area:
            qs = qs.filter(models.Q(area__iexact=area) | models.Q(area__iexact=Catalogo.AREA_GENERAL))
        if tipo:
            qs = qs.filter(tipo_catalogo=tipo)
        return qs


class Catalogo(models.Model):
    TIPO_ACTIVIDAD = "Actividad"
    TIPO_SERVICIO = "Servicio"
    TIPO_ATENCION = "Atención"
    TIPO_SUBATENCION = "Subatención"
    TIPOS = [
        (TIPO_ACTIVIDAD, "Actividad"),
        (TIPO_SERVICIO, "Servicio"),
        (TIPO_ATENCION, "Atención"),
        (TIPO_SUBATENCION, "Subatención"),
    ]

    ESTADO_ACTIVO = "Activo"
    ESTADO_INACTIVO = "Inactivo"
    ESTADOS = [(ESTADO_ACTIVO, "Activo"), (ESTADO_INACTIVO, "Inactivo")]

    AREA_GENERAL = "General"   # aplica a todas las áreas

    id_catalogo = models.AutoField(primary_key=True)
    tipo_catalogo = models.CharField(max_length=15, choices=TIPOS)
    nombre = models.CharField(max_length=150)
    area = models.CharField(max_length=100, default=AREA_GENERAL)
    estado = models.CharField(max_length=10, choices=ESTADOS, default=ESTADO_ACTIVO)

    objects = CatalogoQuerySet.as_manager()

    class Meta:
        db_table = "catalogo"
        ordering = ["tipo_catalogo", "area", "nombre"]
        constraints = [
            models.UniqueConstraint(fields=["tipo_catalogo", "area", "nombre"], name="uq_catalogo_tipo_area_nombre"),
        ]
        verbose_name = "elemento de catálogo"
        verbose_name_plural = "catálogo"

    def __str__(self):
        return f"{self.nombre} ({self.area})"

    @property
    def activo(self):
        return self.estado == self.ESTADO_ACTIVO

    def clean(self):
        self.nombre = (self.nombre or "").strip()
        self.area = (self.area or "").strip()
        if self.nombre and self.area and self.tipo_catalogo:
            duplicado = Catalogo.objects.filter(
                tipo_catalogo=self.tipo_catalogo, area__iexact=self.area, nombre__iexact=self.nombre,
            ).exclude(pk=self.pk).exists()
            if duplicado:
                raise ValidationError("Ya existe un elemento con ese nombre en el mismo catálogo y área.")

    def en_uso(self):
        """True si algún registro (actividad, atención social...) ya referencia este elemento."""
        if not self.pk:
            return False
        for relacion in self._meta.related_objects:
            if relacion.one_to_many and getattr(self, relacion.get_accessor_name()).exists():
                return True
        return False
