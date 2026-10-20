"""Filtros y tags de interfaz: semáforo, badges de estado, porcentajes, Bootstrap 5."""
from django import forms, template
from django.utils.html import format_html

from core.mixins import tiene_rol

register = template.Library()

_SEMAFORO = {"verde": "success", "ambar": "warning", "ámbar": "warning", "rojo": "danger"}

_ESTADOS = {
    # Compromisos
    "ingresado": "secondary", "pendiente": "warning", "en proceso": "primary", "realizado": "success",
    # Evidencias / validaciones
    "aprobada": "success", "aprobado": "success", "rechazada": "danger", "rechazado": "danger",
    "correccion": "info", "corrección": "info", "solicitar corrección": "info",
    # Actividades
    "registrada": "secondary", "en revisión": "info", "validada": "success",
    "corrección solicitada": "warning", "anulada": "dark",
    # Generales
    "activo": "success", "activa": "success", "vigente": "success",
    "inactivo": "secondary", "inactiva": "secondary",
    "abierto": "success", "cerrado": "dark", "vencido": "danger",
}


@register.filter
def semaforo_color(valor):
    """'Verde' -> 'success' (clase Bootstrap)."""
    return _SEMAFORO.get(str(valor or "").strip().lower(), "secondary")


@register.simple_tag
def semaforo_badge(valor):
    texto = str(valor or "Sin dato")
    return format_html('<span class="badge text-bg-{}">{}</span>', semaforo_color(valor), texto)


@register.filter
def estado_color(valor):
    return _ESTADOS.get(str(valor or "").strip().lower(), "secondary")


@register.simple_tag
def estado_badge(valor):
    texto = str(valor or "—")
    return format_html('<span class="badge text-bg-{}">{}</span>', estado_color(valor), texto)


@register.filter
def porcentaje(valor, decimales=1):
    """12.345 -> '12,3 %'. None -> '—'."""
    if valor is None or valor == "":
        return "—"
    try:
        texto = f"{float(valor):.{int(decimales)}f}"
    except (TypeError, ValueError):
        return "—"
    return f"{texto.replace('.', ',')} %"


@register.filter(name="tiene_rol")
def tiene_rol_filter(user, roles):
    """{% if user|tiene_rol:"Administrador,Coordinador" %}"""
    return tiene_rol(user, *[r.strip() for r in str(roles).split(",") if r.strip()])


def _unir_clases(*grupos):
    """Une clases CSS sin repetir (conserva el orden)."""
    vistas = []
    for grupo in grupos:
        for clase in str(grupo or "").split():
            if clase not in vistas:
                vistas.append(clase)
    return " ".join(vistas)


@register.filter
def add_class(campo, css):
    """Agrega clases CSS a un campo de formulario sin duplicarlas: {{ form.x|add_class:"w-50" }}"""
    return campo.as_widget(attrs={"class": _unir_clases(campo.field.widget.attrs.get("class", ""), css)})


@register.filter
def tipo_widget(campo):
    """'checkbox' | 'select' | 'file' | 'textarea' | 'radio' | 'input' (para dibujar el campo en Bootstrap)."""
    w = campo.field.widget
    if isinstance(w, forms.CheckboxInput):
        return "checkbox"
    if isinstance(w, (forms.RadioSelect, forms.CheckboxSelectMultiple)):
        return "radio"
    if isinstance(w, forms.Select):          # incluye SelectMultiple
        return "select"
    if isinstance(w, forms.FileInput):
        return "file"
    if isinstance(w, forms.Textarea):
        return "textarea"
    return "input"


@register.filter
def bs_campo(campo, extra=""):
    """
    Dibuja el widget con las clases de Bootstrap 5, marca `is-invalid` si hay errores y enlaza
    la ayuda/errores con aria-describedby (accesibilidad). Usado por partials/_form_field.html.
    """
    base = {"checkbox": "form-check-input", "select": "form-select"}.get(tipo_widget(campo), "form-control")
    attrs = {"class": _unir_clases(campo.field.widget.attrs.get("class", ""), base, extra,
                                   "is-invalid" if campo.errors else "")}
    if campo.errors:
        attrs["aria-invalid"] = "true"
        attrs["aria-describedby"] = f"{campo.auto_id}_errores"
    elif campo.help_text:
        attrs["aria-describedby"] = f"{campo.auto_id}_ayuda"
    return campo.as_widget(attrs=attrs)


@register.filter
def ancho_pct(valor):
    """Valor -> porcentaje 0-100 con punto decimal, seguro para CSS (width) aunque la localización use coma."""
    try:
        numero = max(0.0, min(100.0, float(valor)))
    except (TypeError, ValueError):
        numero = 0.0
    return f"{numero:.1f}"


# ---------------------------------------------------------------------------
# Paginación (partials/_pagination.html)
# ---------------------------------------------------------------------------
@register.filter
def rango_paginas(page_obj):
    """Páginas a mostrar con puntos suspensivos: 1 … 4 5 [6] 7 8 … 20"""
    return list(page_obj.paginator.get_elided_page_range(page_obj.number, on_each_side=2, on_ends=1))


@register.simple_tag(takes_context=True)
def url_pagina(context, numero):
    """Enlace a otra página conservando los filtros de la búsqueda: {% url_pagina 3 %} -> ?q=ana&page=3"""
    consulta = context["request"].GET.copy()
    consulta["page"] = numero
    return "?" + consulta.urlencode()


@register.filter
def get_item(diccionario, clave):
    try:
        return diccionario.get(clave)
    except AttributeError:
        return None
