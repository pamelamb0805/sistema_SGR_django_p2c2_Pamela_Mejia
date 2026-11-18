# Generated for the SGR neighbor-request workflow.
from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ("agenda", "0002_initial"),
    ]

    operations = [
        migrations.AddField("compromiso", "rut_solicitante", models.CharField(blank=True, db_index=True, default="", max_length=12)),
        migrations.AddField("compromiso", "relacion_vecinal", models.CharField(blank=True, choices=[("Delegado", "Delegado"), ("Presidente", "Presidente de junta de vecinos"), ("Secretario", "Secretario de junta de vecinos"), ("Miembro", "Ciudadano miembro de junta de vecinos")], default="", max_length=20)),
        migrations.AddField("compromiso", "canal_solicitud", models.CharField(choices=[("Presencial", "Presencial")], default="Presencial", max_length=20)),
        migrations.AddField("compromiso", "tipo_solicitud", models.CharField(blank=True, choices=[("General", "Solicitud vecinal"), ("Regalo / evento día festivo", "Regalo / evento día festivo")], default="", max_length=40)),
        migrations.AddField("compromiso", "categoria_solicitud", models.CharField(blank=True, db_index=True, default="", max_length=80)),
        migrations.AddField("compromiso", "descripcion_solicitud", models.TextField(blank=True, default="")),
        migrations.AddField("compromiso", "solucion", models.TextField(blank=True, default="")),
        migrations.AddField("compromiso", "estado_solicitud", models.CharField(choices=[("Creado", "Creado"), ("Pendiente", "Pendiente"), ("Proceso", "Proceso"), ("Concluido", "Concluido")], db_index=True, default="Creado", max_length=12)),
        migrations.AddField("compromiso", "fecha_creacion", models.DateTimeField(default=django.utils.timezone.now, db_index=True, editable=False)),
        migrations.AddField("compromiso", "fecha_propuesta_solucion", models.DateField(blank=True, null=True)),
        migrations.AddField("compromiso", "rut_menor", models.CharField(blank=True, max_length=12, null=True, unique=True)),
        migrations.AddField("compromiso", "nombre_menor", models.CharField(blank=True, default="", max_length=150)),
    ]
