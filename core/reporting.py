
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
    "pk": "Identificador relacionado",
}


def _obtener_filtros(request, kwargs=None, metadato_previo=None):
    """
    Obtiene los filtros utilizados para generar el informe.
    Incluye parámetros GET y parámetros de URL.
    """
    filtros = []

    if request is not None:
        for clave, valor in request.GET.items():
            valor = str(valor).strip()

            if not valor:
                continue

            etiqueta = ETIQUETAS_FILTROS.get(
                clave,
                clave.replace("_", " ").capitalize(),
            )

            filtros.append(f"{etiqueta}: {valor}")

    if kwargs:
        for clave, valor in kwargs.items():
            if valor is None:
                continue

            etiqueta = ETIQUETAS_FILTROS.get(
                clave,
                clave.replace("_", " ").capitalize(),
            )

            filtros.append(f"{etiqueta}: {valor}")

    if metadato_previo:
        previo = str(metadato_previo).strip()

        if previo and not previo.lower().startswith(
            "filtros aplicados"
        ):
            if previo not in filtros:
                filtros.append(previo)

    return (
        "; ".join(filtros)
        if filtros
        else "Sin filtros adicionales"
    )


def _contar_celdas_con_datos(hoja, numero_fila):
    return sum(
        1
        for celda in hoja[numero_fila]
        if celda.value is not None
        and str(celda.value).strip()
    )


def _buscar_fila_encabezados(hoja):
    """
    Detecta la fila que contiene los encabezados de la tabla
    principal, incluso si el informe ya tenía títulos o resúmenes.
    """
    primera_fila = 4
    ultima_fila = min(hoja.max_row, 30)

    if ultima_fila < primera_fila:
        return primera_fila

    fila_encabezados = primera_fila
    mayor_cantidad = 0

    for numero_fila in range(
        primera_fila,
        ultima_fila + 1,
    ):
        cantidad = _contar_celdas_con_datos(
            hoja,
            numero_fila,
        )

        if cantidad > mayor_cantidad:
            mayor_cantidad = cantidad
            fila_encabezados = numero_fila

    return fila_encabezados


def incorporar_metadatos_informe(
    libro,
    request,
    titulo,
    kwargs=None,
):
    """
    Agrega metadatos a todas las hojas del informe.

    Evita duplicar metadatos existentes y conserva
    los encabezados y datos originales.
    """
    fecha_generacion = timezone.localtime().strftime(
        "%d/%m/%Y %H:%M:%S"
    )

    for hoja in libro.worksheets:
        texto_titulo = str(
            hoja.cell(row=1, column=1).value or ""
        ).strip()

        texto_fecha = str(
            hoja.cell(row=2, column=1).value or ""
        ).strip()

        texto_fila_tres = str(
            hoja.cell(row=3, column=1).value or ""
        ).strip()

        # Reconoce los informes que ya tenían título y fecha.
        tiene_metadatos = (
            bool(texto_titulo)
            and "generado" in texto_fecha.lower()
        )

        if tiene_metadatos:
            # Conserva información previa, por ejemplo el período.
            metadato_previo = texto_fila_tres

        else:
            # Si no tenía metadatos, crea el espacio correspondiente.
            hoja.insert_rows(1, 3)
            metadato_previo = None

        filtros_aplicados = _obtener_filtros(
            request,
            kwargs=kwargs,
            metadato_previo=metadato_previo,
        )

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

        fila_encabezados = _buscar_fila_encabezados(hoja)

        # Congela las filas anteriores a los datos.
        hoja.freeze_panes = (
            f"A{fila_encabezados + 1}"
        )

        # Aplica filtro automático sobre la tabla principal.
        if (
            hoja.max_column >= 1
            and hoja.max_row > fila_encabezados
            and _contar_celdas_con_datos(
                hoja,
                fila_encabezados,
            ) > 0
        ):
            ultima_columna = get_column_letter(
                hoja.max_column
            )

            hoja.auto_filter.ref = (
                f"A{fila_encabezados}:"
                f"{ultima_columna}{hoja.max_row}"
            )

        hoja.column_dimensions["A"].width = max(
            hoja.column_dimensions["A"].width or 0,
            32,
        )

        # Resalta los encabezados reales, no una fila fija.
        for celda in hoja[fila_encabezados]:
            fuente = copy(celda.font)
            fuente.bold = True
            celda.font = fuente

    return libro


def informe_excel(titulo):
    """
    Decorador que agrega metadatos a las respuestas Excel
    sin modificar las consultas, filtros ni permisos originales.
    """
    def decorador(vista):
        @wraps(vista)
        def vista_con_metadatos(request, *args, **kwargs):
            respuesta = vista(
                request,
                *args,
                **kwargs,
            )

            if getattr(respuesta, "status_code", None) != 200:
                return respuesta

            content_type = respuesta.get(
                "Content-Type",
                "",
            )

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
                kwargs=kwargs,
            )

            salida = BytesIO()
            libro.save(salida)

            respuesta.content = salida.getvalue()

            return respuesta

        return vista_con_metadatos

    return decorador
