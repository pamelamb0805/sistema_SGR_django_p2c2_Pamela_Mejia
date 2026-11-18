from django.core.management.base import BaseCommand
from django.db import transaction

from organizations.models import Funcionario, Usuario
from organizations.account_utils import crear_cuenta_funcionario


class Command(BaseCommand):
    help = (
        "Asocia cuentas de acceso a funcionarios antiguos sin usuario. "
        "Por seguridad solo simula cambios; use --apply para ejecutarlos."
    )

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Crear las cuentas; sin esta opción solo muestra el plan.")

    def handle(self, *args, **options):
        aplicar = options["apply"]
        pendientes = (
            Funcionario.objects.select_related("delegacion")
            .filter(usuario__isnull=True)
            .order_by("pk")
        )
        total = pendientes.count()
        creados = 0
        self.stdout.write(f"Funcionarios sin usuario encontrados: {total}")
        for funcionario in pendientes.iterator():
            # No tocar cuentas existentes (en particular ROOT, aunque esté vinculado a Andrea).
            if Usuario.objects.filter(funcionario_id=funcionario.pk, is_superuser=True).exists():
                self.stdout.write(self.style.WARNING(f"OMITIDO ROOT: funcionario #{funcionario.pk}"))
                continue
            if not aplicar:
                self.stdout.write(f"SIMULACIÓN: funcionario #{funcionario.pk} · {funcionario.identificador_institucional}")
                continue
            with transaction.atomic():
                _, creada = crear_cuenta_funcionario(funcionario)
            if creada:
                creados += 1
                self.stdout.write(self.style.SUCCESS(f"Cuenta creada para funcionario #{funcionario.pk}"))
        if aplicar:
            self.stdout.write(self.style.SUCCESS(f"Proceso finalizado. Cuentas creadas: {creados}"))
        else:
            self.stdout.write(self.style.WARNING("No se modificó la base de datos. Repite con --apply para ejecutar."))
