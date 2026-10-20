"""
Fórmulas puras del SGR (sin base de datos), equivalentes a CalculoIndicadores del
diagrama de clases. Todas usan Decimal y redondean a 2 decimales (mitad hacia arriba).

Línea base académica del PDF (sección 13.1):
- cumplimiento (%)  = avance aprobado / meta del período x 100          (RN-004)
- ponderado         = ponderador x min(cumplimiento, tope) / 100         (RN-005)
- meta esperada (%) = días transcurridos / días computables totales x 100 (RN-007)
- semáforo          = verde / ámbar / rojo según RN-008

CONVENCIÓN DE DÍAS (decisión documentada): se replica el ejemplo del PDF:
  1/07/2026 -> 30/09/2026 = 91 días computables; al 26/08/2026 han transcurrido 56 días,
  56/91 = 61,54 %. Es decir, días = (fecha final - fecha inicial); el día de inicio es el
  día 0 y el día de término completa el 100 %. Si la institución define otra regla
  (p. ej. contar ambos extremos o excluir fines de semana), se cambia SOLO en este archivo.
"""
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings

CIEN = Decimal("100")

SEMAFORO_VERDE = "Verde"
SEMAFORO_AMBAR = "Ámbar"
SEMAFORO_ROJO = "Rojo"


def d(valor):
    """Convierte a Decimal sin pasar por errores de coma flotante."""
    return valor if isinstance(valor, Decimal) else Decimal(str(valor))


def redondear(valor, decimales=2):
    return d(valor).quantize(Decimal(1).scaleb(-decimales), rounding=ROUND_HALF_UP)


# ---------------------------------------------------------------------------
# Días y meta esperada (RF-005, RF-026, RN-007)
# ---------------------------------------------------------------------------
def calcular_dias_computables(fecha_inicio: date, fecha_termino: date) -> int:
    if fecha_termino < fecha_inicio:
        raise ValueError("La fecha de término no puede ser anterior a la de inicio.")
    return (fecha_termino - fecha_inicio).days


def calcular_dias_transcurridos(fecha_inicio: date, fecha_termino: date, fecha: date) -> int:
    total = calcular_dias_computables(fecha_inicio, fecha_termino)
    if fecha <= fecha_inicio:
        return 0
    if fecha >= fecha_termino:
        return total
    return (fecha - fecha_inicio).days


def calcular_meta_esperada(fecha_inicio: date, fecha_termino: date, fecha: date) -> Decimal:
    """Avance acumulado esperado al día, entre 0 y 100 (nunca supera el 100 %)."""
    total = calcular_dias_computables(fecha_inicio, fecha_termino)
    if total == 0:   # período de un solo día
        return CIEN if fecha >= fecha_inicio else Decimal("0.00")
    transcurridos = calcular_dias_transcurridos(fecha_inicio, fecha_termino, fecha)
    return min(CIEN, redondear(Decimal(transcurridos) / Decimal(total) * CIEN))


# ---------------------------------------------------------------------------
# Cumplimiento y ponderación (RF-023, RF-024, RN-004, RN-005)
# ---------------------------------------------------------------------------
def calcular_porcentaje_cumplimiento(avance, meta) -> Decimal:
    meta = d(meta)
    if meta <= 0:
        raise ValueError("La meta debe ser mayor que cero.")
    return redondear(d(avance) / meta * CIEN)


def calcular_cumplimiento_computable(cumplimiento, maximo_computable) -> Decimal:
    """Cumplimiento limitado al máximo computable configurado (150 % por defecto)."""
    return min(d(cumplimiento), d(maximo_computable))


def calcular_cumplimiento_ponderado(cumplimiento, ponderador, maximo_computable) -> Decimal:
    computable = calcular_cumplimiento_computable(cumplimiento, maximo_computable)
    return redondear(d(ponderador) * computable / CIEN)


# ---------------------------------------------------------------------------
# Semáforo (RF-027, RN-008) y umbral colectivo (RN-006)
# ---------------------------------------------------------------------------
def calcular_semaforo(avance_pct, esperada_pct, umbral_ambar=None) -> str:
    """
    Verde : avance >= esperado
    Ámbar : avance >= 60 % del esperado y < esperado
    Rojo  : avance < 60 % del esperado
    `umbral_ambar` (60 por defecto) es configurable en settings.SGR_SEMAFORO_AMBAR.
    """
    avance, esperada = d(avance_pct), d(esperada_pct)
    umbral = d(settings.SGR_SEMAFORO_AMBAR if umbral_ambar is None else umbral_ambar)
    if avance >= esperada:
        return SEMAFORO_VERDE
    if avance >= esperada * umbral / CIEN:
        return SEMAFORO_AMBAR
    return SEMAFORO_ROJO


def esta_bajo_umbral(resultado_pct, umbral_pct=None) -> bool:
    umbral = d(settings.SGR_UMBRAL_COLECTIVO if umbral_pct is None else umbral_pct)
    return d(resultado_pct) < umbral
