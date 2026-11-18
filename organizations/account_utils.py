"""Creación segura y uniforme de cuentas vinculadas a funcionarios."""
from django.utils.text import slugify
from .models import Usuario


def username_para_funcionario(funcionario):
    identificador = (funcionario.identificador_institucional or "").strip()
    base = slugify(identificador).replace("-", "_")[:120] or f"{funcionario.pk}"
    prefijo = "sgr_"
    candidato = f"{prefijo}{base}"
    if not Usuario.objects.filter(username__iexact=candidato).exists():
        return candidato
    # Una colisión de slug no debe impedir el alta de un funcionario legítimo.
    sufijo = f"_{funcionario.pk}"
    candidato = f"{prefijo}{base[:150-len(prefijo)-len(sufijo)]}{sufijo}"
    contador = 2
    while Usuario.objects.filter(username__iexact=candidato).exists():
        extra = f"_{funcionario.pk}_{contador}"
        candidato = f"{prefijo}{base[:150-len(prefijo)-len(extra)]}{extra}"
        contador += 1
    return candidato


def crear_cuenta_funcionario(funcionario):
    """Crea la cuenta si no existe. La contraseña queda inutilizable hasta activación."""
    existente = Usuario.objects.filter(funcionario=funcionario).first()
    if existente:
        return existente, False
    usuario = Usuario.objects.create_user(
        username=username_para_funcionario(funcionario),
        password=None,
        funcionario=funcionario,
        activo_acceso=bool(funcionario.activo and funcionario.delegacion.activa),
    )
    return usuario, True
