"""
Servicios de audit.

registrar_evento() es el punto de entrada que usan TODAS las apps (a través de
core.mixins.auditar). Los eventos se guardan dentro de la misma transacción de la operación
auditada: si la operación falla y se revierte, su evento también.
"""
import csv
import json
from datetime import datetime, time, timedelta

from django.db.models import Q
from django.utils import timezone

from core.mixins import ROLES_TRANSVERSALES, tiene_rol

from .models import Auditoria

# Quién puede consultar la auditoría: Administrador y Coordinador (auditoría del sistema).
ROLES_AUDITORIA = ROLES_TRANSVERSALES


def _como_texto(valor):
    """Los valores se guardan como texto; diccionarios y listas se serializan a JSON."""
    if valor is None:
        return None
    if isinstance(valor, (dict, list, tuple)):
        return json.dumps(valor, default=str, ensure_ascii=False)
    return str(valor)


# ---------------------------------------------------------------------------
# RegistrarEvento / MostrarHistorialPorEntidad (diagrama de clases: Auditoria)
# ---------------------------------------------------------------------------
def registrar_evento(usuario=None, evento="", entidad="", id_entidad=0, valor_anterior=None, valor_nuevo=None):
    """
    Registra quién hizo qué y cuándo. `usuario` es el usuario autenticado (o None); su funcionario
    se toma de `usuario.funcionario`.
    """
    funcionario = None
    if usuario is not None and getattr(usuario, "is_authenticated", False):
        funcionario = getattr(usuario, "funcionario", None)
    return Auditoria.objects.create(
        evento=str(evento)[:40], entidad_afectada=str(entidad or "")[:60],
        id_entidad_afectada=int(id_entidad or 0),
        valor_anterior=_como_texto(valor_anterior), valor_nuevo=_como_texto(valor_nuevo),
        funcionario=funcionario)


def mostrar_historial_por_entidad(entidad, id_entidad):
    return Auditoria.objects.filter(entidad_afectada=entidad, id_entidad_afectada=id_entidad) \
        .select_related("funcionario").order_by("fecha", "id_auditoria")


# ---------------------------------------------------------------------------
# Consulta
# ---------------------------------------------------------------------------
def puede_consultar(user):
    return tiene_rol(user, *ROLES_AUDITORIA)


def _inicio_dia(fecha):
    return timezone.make_aware(datetime.combine(fecha, time.min))


def filtrar_auditoria(queryset, datos):
    """
    Aplica los filtros (HU-30) sin usar funciones de zona horaria de la base de datos.
    Devuelve (queryset, lista legible de filtros aplicados para encabezar los informes).
    """
    aplicados = []
    if datos.get("evento"):
        queryset = queryset.filter(evento=datos["evento"])
        aplicados.append(f"Evento = {datos['evento']}")
    if datos.get("entidad"):
        queryset = queryset.filter(entidad_afectada=datos["entidad"])
        aplicados.append(f"Entidad = {datos['entidad']}")
    if datos.get("id_entidad") not in (None, ""):
        queryset = queryset.filter(id_entidad_afectada=datos["id_entidad"])
        aplicados.append(f"ID de entidad = {datos['id_entidad']}")
    if datos.get("funcionario"):
        queryset = queryset.filter(funcionario=datos["funcionario"])
        aplicados.append(f"Usuario = {datos['funcionario']}")
    if datos.get("fecha_desde"):
        queryset = queryset.filter(fecha__gte=_inicio_dia(datos["fecha_desde"]))
        aplicados.append(f"Desde {datos['fecha_desde']:%d/%m/%Y}")
    if datos.get("fecha_hasta"):
        queryset = queryset.filter(fecha__lt=_inicio_dia(datos["fecha_hasta"] + timedelta(days=1)))
        aplicados.append(f"Hasta {datos['fecha_hasta']:%d/%m/%Y}")
    if (datos.get("q") or "").strip():
        q = datos["q"].strip()
        queryset = queryset.filter(Q(valor_anterior__icontains=q) | Q(valor_nuevo__icontains=q))
        aplicados.append(f"Texto contiene «{q}»")
    return queryset, aplicados


def _cargar(valor):
    if valor in (None, ""):
        return None
    try:
        return json.loads(valor)
    except (TypeError, ValueError):
        return valor


def comparar_valores(anterior, nuevo):
    """
    Lista de campos que cambiaron entre el valor anterior y el nuevo cuando ambos son registros
    JSON: [{'campo', 'anterior', 'nuevo'}]. Devuelve None si los valores no son comparables.
    """
    a, n = _cargar(anterior), _cargar(nuevo)
    if not isinstance(a, dict) and not isinstance(n, dict):
        return None
    a = a if isinstance(a, dict) else {}
    n = n if isinstance(n, dict) else {}
    return [{"campo": k, "anterior": a.get(k, "—"), "nuevo": n.get(k, "—")}
            for k in sorted(set(a) | set(n)) if a.get(k) != n.get(k)]


# ---------------------------------------------------------------------------
# Exportación (RF-033): conserva filtros, fecha de generación y encabezados legibles
# ---------------------------------------------------------------------------
def _celda(valor):
    """Evita la inyección de fórmulas al abrir el CSV en Excel."""
    texto = "" if valor is None else str(valor)
    return "'" + texto if texto[:1] in ("=", "+", "-", "@", "\t", "\r") else texto


def escribir_csv(respuesta, queryset, filtros_aplicados, generado_por=""):
    respuesta.write("\ufeff")                              # BOM: Excel reconoce UTF-8
    w = csv.writer(respuesta, delimiter=";")
    w.writerow(["Informe de auditoría del SGR"])
    w.writerow(["Generado", timezone.localtime().strftime("%d/%m/%Y %H:%M"), "Por", _celda(generado_por)])
    w.writerow(["Filtros", "; ".join(filtros_aplicados) or "Sin filtros"])
    w.writerow([])
    w.writerow(["ID", "Fecha y hora", "Usuario", "Evento", "Entidad", "ID entidad", "Valor anterior", "Valor nuevo"])
    for e in queryset.select_related("funcionario").iterator():
        w.writerow([e.pk, timezone.localtime(e.fecha).strftime("%d/%m/%Y %H:%M:%S"),
                    _celda(e.funcionario.nombre if e.funcionario else "Sistema / técnico"),
                    _celda(e.evento), _celda(e.entidad_afectada), e.id_entidad_afectada,
                    _celda(e.valor_anterior), _celda(e.valor_nuevo)])
    return respuesta
