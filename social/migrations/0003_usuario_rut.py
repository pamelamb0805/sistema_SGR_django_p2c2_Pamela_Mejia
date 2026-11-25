from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("social", "0002_atencionsocial_subatencion_nombre_and_more")]
    operations = [
        migrations.AddField(
            model_name="usuariosocial",
            name="rut",
            field=models.CharField(blank=True, max_length=12, null=True, unique=True, help_text="RUT chileno normalizado, sin puntos y con guion."),
        ),
    ]
