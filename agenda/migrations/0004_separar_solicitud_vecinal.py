
from django.db import migrations, models
import django.utils.timezone


RELACIONES_VECINALES = [
    ("Delegado", "Delegado"),
    ("Presidente", "Presidente de junta de vecinos"),
    ("Secretario", "Secretario de junta de vecinos"),
    ("Miembro", "Ciudadano miembro de junta de vecinos"),
]

CANALES = [
    ("Presencial", "Presencial"),
]

TIPOS = [
    ("General", "Solicitud vecinal"),
    (
        "Regalo / evento día festivo",
        "Regalo / evento día festivo",
    ),
]

ESTADOS = [
    ("Creado", "Creado"),
    ("Pendiente", "Pendiente"),
    ("Proceso", "Proceso"),
    ("Concluido", "Concluido"),
]


def migrar_solicitudes_vecinales(apps, schema_editor):
    Compromiso = apps.get_model(
        "agenda",
        "Compromiso",
    )

    SolicitudVecinal = apps.get_model(
        "agenda",
        "SolicitudVecinal",
    )

    for compromiso in (
        Compromiso.objects
        .exclude(tipo_solicitud="")
        .iterator()
    ):
        solicitud = SolicitudVecinal.objects.create(
            rut_solicitante=compromiso.rut_solicitante,
            relacion_vecinal=compromiso.relacion_vecinal,
            canal=compromiso.canal_solicitud,
            tipo=compromiso.tipo_solicitud,
            categoria=compromiso.categoria_solicitud,
            descripcion=compromiso.descripcion_solicitud,
            solucion=compromiso.solucion,
            estado_solicitud=compromiso.estado_solicitud,
            fecha_creacion=compromiso.fecha_creacion,
            fecha_propuesta_solucion=(
                compromiso.fecha_propuesta_solucion
            ),
            rut_menor=compromiso.rut_menor,
            nombre_menor=compromiso.nombre_menor,
        )

        compromiso.solicitud_vecinal_id = (
            solicitud.pk
        )

        compromiso.save(
            update_fields=["solicitud_vecinal"]
        )


class Migration(migrations.Migration):

    dependencies = [
        ("agenda", "0003_solicitudes_vecinales"),
    ]

    operations = [
        migrations.CreateModel(
            name="SolicitudVecinal",
            fields=[
                (
                    "id_solicitud_vecinal",
                    models.AutoField(
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "rut_solicitante",
                    models.CharField(
                        max_length=12,
                        blank=True,
                        default="",
                        db_index=True,
                    ),
                ),
                (
                    "relacion_vecinal",
                    models.CharField(
                        max_length=20,
                        choices=RELACIONES_VECINALES,
                        blank=True,
                        default="",
                    ),
                ),
                (
                    "canal",
                    models.CharField(
                        max_length=20,
                        choices=CANALES,
                        default="Presencial",
                    ),
                ),
                (
                    "tipo",
                    models.CharField(
                        max_length=40,
                        choices=TIPOS,
                        blank=True,
                        default="",
                    ),
                ),
                (
                    "categoria",
                    models.CharField(
                        max_length=80,
                        blank=True,
                        default="",
                        db_index=True,
                    ),
                ),
                (
                    "descripcion",
                    models.TextField(
                        blank=True,
                        default="",
                    ),
                ),
                (
                    "solucion",
                    models.TextField(
                        blank=True,
                        default="",
                    ),
                ),
                (
                    "estado_solicitud",
                    models.CharField(
                        max_length=12,
                        choices=ESTADOS,
                        default="Creado",
                        db_index=True,
                    ),
                ),
                (
                    "fecha_creacion",
                    models.DateTimeField(
                        default=django.utils.timezone.now,
                        editable=False,
                        db_index=True,
                    ),
                ),
                (
                    "fecha_propuesta_solucion",
                    models.DateField(
                        null=True,
                        blank=True,
                    ),
                ),
                (
                    "rut_menor",
                    models.CharField(
                        max_length=12,
                        unique=True,
                        null=True,
                        blank=True,
                    ),
                ),
                (
                    "nombre_menor",
                    models.CharField(
                        max_length=150,
                        blank=True,
                        default="",
                    ),
                ),
            ],
            options={
                "db_table": "solicitud_vecinal",
                "ordering": [
                    "-fecha_creacion",
                    "id_solicitud_vecinal",
                ],
                "verbose_name": "solicitud vecinal",
                "verbose_name_plural": "solicitudes vecinales",
            },
        ),

        migrations.AddField(
            model_name="compromiso",
            name="solicitud_vecinal",
            field=models.ForeignKey(
                to="agenda.solicitudvecinal",
                on_delete=models.PROTECT,
                db_column="id_solicitud_vecinal",
                related_name="compromisos",
                null=True,
                blank=True,
            ),
        ),

        migrations.RunPython(
            migrar_solicitudes_vecinales,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
