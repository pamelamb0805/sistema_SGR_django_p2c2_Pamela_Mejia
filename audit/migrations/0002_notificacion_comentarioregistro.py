
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("audit", "0001_initial"),
        ("organizations", "0001_initial"),
        ("contenttypes", "0002_remove_content_type_name"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Notificacion",
            fields=[
                (
                    "id_notificacion",
                    models.AutoField(
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "leida",
                    models.BooleanField(
                        default=False,
                        db_index=True,
                        verbose_name="Leída",
                    ),
                ),
                (
                    "fecha_creacion",
                    models.DateTimeField(
                        auto_now_add=True,
                        db_index=True,
                        verbose_name="Fecha de creación",
                    ),
                ),
                (
                    "fecha_lectura",
                    models.DateTimeField(
                        null=True,
                        blank=True,
                        verbose_name="Fecha de lectura",
                    ),
                ),
                (
                    "auditoria",
                    models.ForeignKey(
                        to="audit.auditoria",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="notificaciones",
                        verbose_name="Evento de auditoría",
                    ),
                ),
                (
                    "delegacion",
                    models.ForeignKey(
                        to="organizations.delegacion",
                        on_delete=django.db.models.deletion.SET_NULL,
                        null=True,
                        blank=True,
                        related_name="notificaciones",
                        verbose_name="Delegación relacionada",
                    ),
                ),
                (
                    "usuario",
                    models.ForeignKey(
                        to=settings.AUTH_USER_MODEL,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notificaciones",
                        verbose_name="Usuario destinatario",
                    ),
                ),
            ],
            options={
                "verbose_name": "notificación",
                "verbose_name_plural": "notificaciones",
                "db_table": "notificacion_usuario",
                "ordering": [
                    "-fecha_creacion",
                    "-id_notificacion",
                ],
                "indexes": [
                    models.Index(
                        fields=["usuario", "leida", "fecha_creacion"],
                        name="ix_notif_usuario_leida",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("usuario", "auditoria"),
                        name="uq_notificacion_usuario_auditoria",
                    ),
                ],
            },
        ),

        migrations.CreateModel(
            name="ComentarioRegistro",
            fields=[
                (
                    "id_comentario",
                    models.AutoField(
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "object_id",
                    models.PositiveIntegerField(
                        db_index=True,
                    ),
                ),
                (
                    "mensaje",
                    models.TextField(),
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
                    "autor",
                    models.ForeignKey(
                        to=settings.AUTH_USER_MODEL,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="comentarios_sgr",
                    ),
                ),
                (
                    "content_type",
                    models.ForeignKey(
                        to="contenttypes.contenttype",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="comentarios_sgr",
                    ),
                ),
                (
                    "delegacion",
                    models.ForeignKey(
                        to="organizations.delegacion",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="comentarios_sgr",
                    ),
                ),
                (
                    "funcionario",
                    models.ForeignKey(
                        to="organizations.funcionario",
                        on_delete=django.db.models.deletion.PROTECT,
                        null=True,
                        blank=True,
                        related_name="comentarios_sgr",
                    ),
                ),
                (
                    "respuesta_a",
                    models.ForeignKey(
                        to="audit.comentarioregistro",
                        on_delete=django.db.models.deletion.PROTECT,
                        null=True,
                        blank=True,
                        related_name="respuestas",
                    ),
                ),
            ],
            options={
                "verbose_name": "comentario de registro",
                "verbose_name_plural": "comentarios de registros",
                "db_table": "comentario_registro",
                "ordering": [
                    "fecha_creacion",
                    "id_comentario",
                ],
                "indexes": [
                    models.Index(
                        fields=[
                            "content_type",
                            "object_id",
                            "fecha_creacion",
                        ],
                        name="ix_comentario_registro",
                    ),
                    models.Index(
                        fields=[
                            "delegacion",
                            "fecha_creacion",
                        ],
                        name="ix_comentario_delegacion",
                    ),
                ],
            },
        ),
    ]
