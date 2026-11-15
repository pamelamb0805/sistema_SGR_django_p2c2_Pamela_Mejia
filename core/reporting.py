
from functools import wraps
from io import BytesIO
from copy import copy

from django.utils import timezone

from openpyxl import load_workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter


ETIQUETAS_FILTROS = {
    "q": "Búsqueda",
    "estado": "Estado",
    "estado_caso": "Estado del caso",
    "tipo_registro": "Tipo de registro",
    "tipo_atencion": "Tipo de atención",
    "subatencion": "Subatención",
    "item": "Ítem medible",
    "item_id": "Ítem medible",
    "periodo": "Período",
    "periodo_id": "Período",
    "funcionario": "Funcionario",
    "funcionario_id": "Funcionario",
    "delegacion": "Delegación",
    "delegacion_id": "Delegación",
    "cargo": "Cargo",
    "cargo_id": "Cargo",
    "area": "Área / ámbito",
    "fecha_desde": "Fecha desde",
    "fecha_hasta": "Fecha hasta",
    "fecha_inicio": "Fecha de inicio",
    "fecha_termino": "Fecha de término",
    "efecto": "Efecto",
    "territorio": "Territorio",
    "alcance": "Alcance autorizado",
}


def _obtener_filtros(request):
    """
    Convierte los parámetros GET en una descripción legible
    para incorporarla al archivo exportado.
    """
    if request is None:
        return "Sin filtros adicionales"

    filtros = []

    for clave, valor in request.GET.items():
        valor = str(valor).strip()

        if not valor:
            continue

        etiqueta = ETIQUETAS_FILTROS.get(
            clave,
            clave.replace("_", " ").capitalize(),
        )

        filtros.append(f"{etiqueta}: {valor}")

    return "; ".join(filtros) if filtros else "Sin filtros adicionales"


def incorporar_metadatos_informe(libro, request, titulo):
    """
    Incorpora título, fecha de generación y filtros aplicados
    en todas las hojas del informe, sin eliminar sus datos.
    """
    fecha_generacion = timezone.localtime().strftime(
        "%d/%m/%Y %H:%M:%S"
    )

    filtros_aplicados = _obtener_filtros(request)

    for hoja in libro.worksheets:
        hoja.insert_rows(1, 3)

        hoja.cell(
            row=1,
            column=1,
            value=titulo,
        )

        hoja.cell(
            row=2,
            column=1,
            value=f"Fecha de generación: {fecha_generacion}",
        )

        hoja.cell(
            row=3,
            column=1,
            value=f"Filtros aplicados: {filtros_aplicados}",
        )

        hoja.cell(row=1, column=1).font = Font(
            bold=True,
            size=14,
        )

        hoja.cell(row=2, column=1).font = Font(
            italic=True,
            size=10,
        )

        hoja.cell(row=3, column=1).font = Font(
            italic=True,
            size=10,
        )

        # La fila 4 contiene los encabezados originales.
        hoja.freeze_panes = "A5"

        # Ajusta el filtro automático para que use los encabezados
        # originales, ahora ubicados en la fila 4.
        if hoja.max_column >= 1 and hoja.max_row >= 4:
            ultima_columna = get_column_letter(hoja.max_column)
            hoja.auto_filter.ref = (
                f"A4:{ultima_columna}{hoja.max_row}"
            )

        # Evita que el texto de los metadatos quede oculto.
        hoja.column_dimensions["A"].width = max(
            hoja.column_dimensions["A"].width or 0,
            32,
        )

        # Conserva las fuentes existentes de los encabezados.
        for celda in hoja[4]:
            fuente = copy(celda.font)
            fuente.bold = True
            celda.font = fuente

    return libro


def informe_excel(titulo):
    """
    Decorador para agregar metadatos a las respuestas Excel
    de las vistas de exportación, sin cambiar sus consultas,
    filtros, permisos ni construcción de las hojas.
    """
    def decorador(vista):
        @wraps(vista)
        def vista_con_metadatos(request, *args, **kwargs):
            respuesta = vista(request, *args, **kwargs)

            if getattr(respuesta, "status_code", None) != 200:
                return respuesta

            content_type = respuesta.get("Content-Type", "")

            if "spreadsheetml" not in content_type:
                return respuesta

            contenido = respuesta.content

            if not contenido:
                return respuesta

            archivo = BytesIO(contenido)
            libro = load_workbook(archivo)

            incorporar_metadatos_informe(
                libro=libro,
                request=request,
                titulo=titulo,
            )

            salida = BytesIO()
            libro.save(salida)

            respuesta.content = salida.getvalue()

            return respuesta

        return vista_con_metadatos

    return decorador
