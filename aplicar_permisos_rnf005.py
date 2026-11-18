
import ast
from pathlib import Path


# ============================================================
# RNF-005: PERMISOS POR VISTA
# Rama de trabajo: mejoras_finales
# ============================================================

CAMBIOS = {
    "organizations/views.py": {
        "DelegacionListView": ("delegaciones.ver",),
        "DelegacionCreateView": ("delegaciones.editar",),
        "DelegacionUpdateView": ("delegaciones.editar",),
        "DelegacionToggleView": ("delegaciones.editar",),

        "CargoListView": ("cargos.ver",),
        "CargoDetailView": ("cargos.ver",),
        "CargoCreateView": ("cargos.editar",),
        "CargoUpdateView": ("cargos.editar",),
        "CargoDeleteView": ("cargos.editar",),

        "ItemCreateView": ("cargos.editar",),
        "ItemToggleView": ("cargos.editar",),
        "ItemHistorialView": ("cargos.ver",),

        "RolListView": ("roles.ver",),
        "RolCreateView": ("roles.editar",),
        "RolUpdateView": ("roles.editar",),
        "RolDeleteView": ("roles.editar",),

        "FuncionarioListView": ("funcionarios.ver",),
        "FuncionarioDetailView": ("funcionarios.ver",),
        "FuncionarioCreateView": ("funcionarios.editar",),
        "FuncionarioUpdateView": ("funcionarios.editar",),
        "FuncionarioToggleView": ("funcionarios.editar",),

        "FuncionarioAccesoView": ("usuarios.editar",),
        "UsuarioListView": ("usuarios.ver",),
        "UsuarioCreateView": ("usuarios.editar",),
        "UsuarioUpdateView": ("usuarios.editar",),
        "UsuarioToggleView": ("usuarios.editar",),
    },

    "social/views.py": {
        "CasoListView": ("atenciones.ver",),
        "CasoDetailView": ("atenciones.ver",),
        "CasoCreateView": ("atenciones.registrar",),
        "CasoUpdateView": ("atenciones.editar",),
        "CasoEstadoView": ("atenciones.editar",),
        "GestionCreateView": ("atenciones.gestionar",),
        "GestionUpdateView": ("atenciones.gestionar",),
    },

    "activities/views.py": {
        "ActividadListView": ("actividades.ver",),
        "ActividadDetailView": ("actividades.ver",),
        "ActividadCreateView": ("actividades.registrar",),
        "ActividadUpdateView": ("actividades.editar",),
        "ActividadAnularView": ("actividades.editar",),
        "EvidenciaCreateView": ("actividades.editar",),
        "ValidacionBandejaView": ("validaciones.gestionar",),
        "ValidacionCreateView": ("validaciones.gestionar",),
    },

    "agenda/views.py": {
        "CompromisoListView": ("agenda.ver",),
        "CompromisoDetailView": ("agenda.ver",),
        "CompromisoCreateView": ("agenda.registrar",),
        "CompromisoUpdateView": ("agenda.editar",),
        "CompromisoEstadoView": ("agenda.estado",),
        "CompromisoReasignarView": ("agenda.reasignar",),
        "CompromisoHistorialView": ("agenda.ver",),
    },

    "measurement/views.py": {
        "PeriodoListView": ("periodos.ver",),
        "PeriodoDetailView": ("periodos.ver",),
        "PeriodoCreateView": ("periodos.editar",),
        "PeriodoUpdateView": ("periodos.editar",),
        "PeriodoCerrarView": ("periodos.cerrar",),
        "PeriodoReabrirView": ("periodos.reabrir",),
        "PeriodoRecalcularView": ("periodos.editar",),

        "MetaListView": ("metas.ver",),
        "MetaCreateView": ("metas.editar",),
        "MetaUpdateView": ("metas.editar",),
        "MetaDeleteView": ("metas.editar",),

        "AjusteListView": ("ajustes.ver",),
        "AjusteCreateView": ("ajustes.editar",),
        "AjusteUpdateView": ("ajustes.editar",),
        "AjusteDeleteView": ("ajustes.editar",),
    },

    "catalogs/views.py": {
        "CatalogoListView": ("catalogos.ver",),
        "CatalogoCreateView": ("catalogos.editar",),
        "CatalogoUpdateView": ("catalogos.editar",),
        "CatalogoToggleView": ("catalogos.editar",),
        "CatalogoHistorialView": ("catalogos.ver",),
    },

    "audit/views.py": {
        "AuditoriaListView": ("auditoria.ver",),
        "HistorialEntidadView": ("auditoria.ver",),
        "AuditoriaDetailView": ("auditoria.ver",),
        "AuditoriaExportarView": ("auditoria.exportar",),
    },
}


# ============================================================
# FUNCIONES AUXILIARES
# ============================================================

def obtener_asignacion_permiso(nodo):
    """
    Comprueba si una instrucción asigna permisos_permitidos
    directamente dentro de una clase.
    """

    if isinstance(nodo, ast.Assign):
        return any(
            isinstance(target, ast.Name)
            and target.id == "permisos_permitidos"
            for target in nodo.targets
        )

    if isinstance(nodo, ast.AnnAssign):
        return (
            isinstance(nodo.target, ast.Name)
            and nodo.target.id == "permisos_permitidos"
        )

    return False


def es_docstring(nodo):
    """
    Detecta el docstring de una clase usando ast.Constant.
    Compatible con Python moderno.
    """

    return (
        isinstance(nodo, ast.Expr)
        and isinstance(nodo.value, ast.Constant)
        and isinstance(nodo.value.value, str)
    )


def buscar_clases(arbol):
    """
    Devuelve las clases declaradas directamente en el módulo.
    """

    return {
        nodo.name: nodo
        for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.ClassDef)
    }


def construir_edicion(ruta, contenido, clases_objetivo):
    """
    Analiza un archivo y prepara las modificaciones.
    No escribe nada todavía.
    """

    arbol = ast.parse(contenido, filename=str(ruta))
    clases = buscar_clases(arbol)

    faltantes = [
        nombre
        for nombre in clases_objetivo
        if nombre not in clases
    ]

    if faltantes:
        raise ValueError(
            f"Clases no encontradas en {ruta}: "
            + ", ".join(faltantes)
        )

    lineas = contenido.splitlines(keepends=True)
    ediciones = []

    for nombre_clase, permisos in clases_objetivo.items():
        clase = clases[nombre_clase]

        valor = repr(tuple(permisos))

        nueva_linea = (
            f"    permisos_permitidos = {valor}\n"
        )

        asignacion_existente = None

        for nodo in clase.body:
            if obtener_asignacion_permiso(nodo):
                asignacion_existente = nodo
                break

        if asignacion_existente is not None:
            # Reemplaza la asignación anterior completa.
            inicio = asignacion_existente.lineno - 1
            fin = asignacion_existente.end_lineno

            ediciones.append(
                (inicio, fin, [nueva_linea])
            )

        else:
            # Si existe docstring, insertar después.
            if clase.body and es_docstring(clase.body[0]):
                posicion = clase.body[0].end_lineno

            # Si no existe docstring, insertar antes
            # de la primera instrucción de la clase.
            elif clase.body:
                posicion = clase.body[0].lineno - 1

            else:
                posicion = clase.end_lineno

            ediciones.append(
                (posicion, posicion, [nueva_linea])
            )

    # Aplicar desde abajo hacia arriba para no alterar
    # las posiciones de las líneas pendientes.
    for inicio, fin, reemplazo in sorted(
        ediciones,
        key=lambda elemento: elemento[0],
        reverse=True,
    ):
        lineas[inicio:fin] = reemplazo

    resultado = "".join(lineas)

    # Verificación sintáctica antes de guardar.
    ast.parse(resultado, filename=str(ruta))

    return resultado


# ============================================================
# EJECUCIÓN
# ============================================================

def main():
    raiz = Path(__file__).resolve().parent

    archivos_preparados = {}
    errores = []

    print("\n========================================")
    print(" RNF-005: CONFIGURACIÓN DE PERMISOS")
    print("========================================\n")

    # Primero validar todos los archivos.
    for archivo, clases in CAMBIOS.items():
        ruta = raiz / archivo

        if not ruta.exists():
            errores.append(
                f"No existe el archivo: {archivo}"
            )
            continue

        try:
            contenido = ruta.read_text(encoding="utf-8")

            resultado = construir_edicion(
                ruta,
                contenido,
                clases,
            )

            archivos_preparados[ruta] = resultado

            print(f"[VALIDADO] {archivo}")

        except Exception as error:
            errores.append(
                f"{archivo}: {error}"
            )

    # No modificar ningún archivo si hay errores.
    if errores:
        print("\n[ERROR] No se modificó ningún archivo.\n")

        for error in errores:
            print(" -", error)

        return

    # Guardar únicamente después de validar todo.
    for ruta, resultado in archivos_preparados.items():
        ruta.write_text(
            resultado,
            encoding="utf-8",
            newline="",
        )

        print(f"[ACTUALIZADO] {ruta.relative_to(raiz)}")

    print("\n========================================")
    print(" PROCESO FINALIZADO")
    print("========================================")
    print(
        f"Archivos actualizados: "
        f"{len(archivos_preparados)}"
    )
    print("\nRevisa el git diff antes de continuar.")


if __name__ == "__main__":
    main()
