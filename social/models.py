"""
Modelos de social, basados en el diagrama E-R: USUARIO (aquí UsuarioSocial, tabla `usuario`)
y ATENCION_SOCIAL.

Reglas del PDF: un caso (persona usuaria) registra hasta 3 gestiones relacionadas, con tipos y
fechas diferenciadas, sin duplicar la identificación principal (RF-015, RN-012, CA-04).

Privacidad (RNF-009): solo se guardan nombre y territorio; no hay RUT, teléfono ni dirección.
"""
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from catalogs.models import Catalogo
from organizations.models import Delegacion, Funcionario

MAX_GESTIONES = 3     # RN-012 (el límite vigente se lee de settings.SGR_MAX_GESTIONES_SOCIAL en los servicios)


# ---------------------------------------------------------------------------
# USUARIO (persona atendida) = caso
# ---------------------------------------------------------------------------
class UsuarioSocial(models.Model):
    ESTADO_ABIERTO = "Abierto"
    ESTADO_SEGUIMIENTO = "En seguimiento"
    ESTADO_CERRADO = "Cerrado"
    ESTADOS = [(e, e) for e in (ESTADO_ABIERTO, ESTADO_SEGUIMIENTO, ESTADO_CERRADO)]

    id_usuario = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=150)
    territorio = models.CharField(max_length=150)
    fecha_primer_registro = models.DateField(default=timezone.localdate, editable=False)
    estado_caso = models.CharField(max_length=15, choices=ESTADOS, default=ESTADO_ABIERTO)
    delegacion = models.ForeignKey(Delegacion, on_delete=models.PROTECT, db_column="id_delegacion",
                                   related_name="usuarios_sociales")

    class Meta:
        db_table = "usuario"
        ordering = ["-fecha_primer_registro", "nombre"]
        constraints = [
            # La identificación principal no se duplica: una persona = un caso por delegación
            models.UniqueConstraint(fields=["delegacion", "nombre", "territorio"], name="uq_usuario_persona"),
        ]
        verbose_name = "usuario social"
        verbose_name_plural = "usuarios sociales"

    def __str__(self):
        return f"{self.nombre} ({self.territorio})"

    @property
    def cerrado(self):
        return self.estado_caso == self.ESTADO_CERRADO

    def clean(self):
        self.nombre = (self.nombre or "").strip()
        self.territorio = (self.territorio or "").strip()
        if self.nombre and self.territorio and self.delegacion_id:
            duplicado = UsuarioSocial.objects.filter(
                delegacion_id=self.delegacion_id, nombre__iexact=self.nombre, territorio__iexact=self.territorio,
            ).exclude(pk=self.pk).first()
            if duplicado:
                raise ValidationError(
                    f"Ya existe un caso para esta persona en el mismo territorio (caso N° {duplicado.pk}). "
                    "Registre una nueva gestión en ese caso en lugar de crear otro.")


# ---------------------------------------------------------------------------
# ATENCION_SOCIAL (gestión)
# ---------------------------------------------------------------------------
class AtencionSocial(models.Model):
    ESTADO_PROGRAMADA = "Programada"
    ESTADO_REALIZADA = "Realizada"
    ESTADOS = [
        (ESTADO_PROGRAMADA, "Programada"),
        (ESTADO_REALIZADA, "Realizada"),
    ]

    id_atencion_social = models.AutoField(primary_key=True)

    numero_gestion = models.PositiveSmallIntegerField(
        editable=False,
        validators=[
            MinValueValidator(1),
            MaxValueValidator(MAX_GESTIONES),
        ],
    )

    # Catálogo de Tipo de Atención.
    tipo_atencion = models.ForeignKey(
        Catalogo,
        on_delete=models.PROTECT,
        db_column="id_tipo_atencion",
        related_name="atenciones_como_tipo",
        limit_choices_to={"tipo_catalogo": Catalogo.TIPO_ATENCION},
    )

    # Subatención perteneciente al Tipo de Atención seleccionado.
    subatencion = models.ForeignKey(
        Catalogo,
        on_delete=models.PROTECT,
        db_column="id_subatencion",
        related_name="atenciones_como_subatencion",
        limit_choices_to={"tipo_catalogo": Catalogo.TIPO_SUBATENCION},
    )

    descripcion = models.TextField()

    # Fecha de la gestión.
    fecha = models.DateField(default=timezone.localdate)

    # Momento de registro: se asigna automáticamente desde Django.
    fecha_registro = models.DateTimeField(
        default=timezone.now,
        editable=False,
    )

    resultado = models.TextField(blank=True)

    estado = models.CharField(
        max_length=12,
        choices=ESTADOS,
        default=ESTADO_REALIZADA,
    )

    usuario = models.ForeignKey(
        UsuarioSocial,
        on_delete=models.PROTECT,
        db_column="id_usuario",
        related_name="gestiones",
    )

    funcionario = models.ForeignKey(
        Funcionario,
        on_delete=models.PROTECT,
        db_column="id_funcionario",
        related_name="atenciones_sociales",
    )

    delegacion = models.ForeignKey(
        Delegacion,
        on_delete=models.PROTECT,
        db_column="id_delegacion",
        related_name="atenciones_sociales",
    )

    class Meta:
        db_table = "atencion_social"
        ordering = ["usuario", "numero_gestion"]
        constraints = [
            models.UniqueConstraint(
                fields=["usuario", "numero_gestion"],
                name="uq_atencion_numero",
            ),
            models.UniqueConstraint(
                fields=["usuario", "tipo_atencion"],
                name="uq_atencion_tipo",
            ),
        ]
        verbose_name = "atención social"
        verbose_name_plural = "atenciones sociales"

    def __str__(self):
        return (
            f"Gestión {self.numero_gestion} – "
            f"{self.tipo_atencion.nombre} "
            f"({self.fecha:%d/%m/%Y})"
        )

    def clean(self):
        errores = {}

        if self.tipo_atencion_id and (
            self.tipo_atencion.tipo_catalogo != Catalogo.TIPO_ATENCION
        ):
            errores["tipo_atencion"] = (
                "Debe seleccionar un elemento del catálogo Tipo de Atención."
            )

        if self.subatencion_id:
            if self.subatencion.tipo_catalogo != Catalogo.TIPO_SUBATENCION:
                errores["subatencion"] = (
                    "Debe seleccionar una Subatención."
                )
            elif (
                self.tipo_atencion_id
                and self.subatencion.tipo_atencion_padre_id
                != self.tipo_atencion_id
            ):
                errores["subatencion"] = (
                    "La Subatención debe pertenecer al Tipo de Atención seleccionado."
                )

        if self.tipo_atencion_id and not self.tipo_atencion.activo:
            errores["tipo_atencion"] = (
                "El Tipo de Atención seleccionado está inactivo."
            )

        if self.subatencion_id and not self.subatencion.activo:
            errores["subatencion"] = (
                "La Subatención seleccionada está inactiva."
            )

        if (
            self.estado == self.ESTADO_REALIZADA
            and self.fecha
            and self.fecha > timezone.localdate()
        ):
            errores["fecha"] = (
                "Una gestión realizada no puede tener fecha futura. "
                "Si es una visita agendada, márquela como Programada."
            )

        if (
            self.estado == self.ESTADO_REALIZADA
            and not (self.resultado or "").strip()
        ):
            errores["resultado"] = (
                "Indique el resultado de la gestión realizada."
            )

        if errores:
            raise ValidationError(errores)