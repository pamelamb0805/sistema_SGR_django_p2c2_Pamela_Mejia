
(() => {
    "use strict";

    function inicializarSelectorAtencion() {
        const formularios = document.querySelectorAll(
            "[data-subatenciones-url]"
        );

        formularios.forEach((formulario) => {
            const tipo = formulario.querySelector(
                "#id_tipo_atencion"
            );

            const subatencion = formulario.querySelector(
                "#id_subatencion"
            );

            if (!tipo || !subatencion) {
                return;
            }

            const url = formulario.dataset.subatencionesUrl;
            let solicitudActual = null;

            async function cargarSubatenciones(conservarSeleccion = false) {
                const seleccionAnterior = conservarSeleccion
                    ? subatencion.value
                    : "";

                subatencion.replaceChildren();

                const opcionInicial = document.createElement("option");
                opcionInicial.value = "";
                opcionInicial.textContent = "Seleccione una subatención";
                subatencion.appendChild(opcionInicial);

                if (!tipo.value) {
                    subatencion.disabled = true;
                    return;
                }

                if (solicitudActual) {
                    solicitudActual.abort();
                }

                solicitudActual = new AbortController();

                subatencion.disabled = true;

                const parametros = new URLSearchParams({
                    tipo_atencion: tipo.value
                });

                try {
                    const respuesta = await fetch(
                        `${url}?${parametros.toString()}`,
                        {
                            method: "GET",
                            credentials: "same-origin",
                            headers: {
                                "X-Requested-With": "XMLHttpRequest"
                            },
                            signal: solicitudActual.signal
                        }
                    );

                    if (!respuesta.ok) {
                        throw new Error(
                            "No fue posible cargar las subatenciones."
                        );
                    }

                    const datos = await respuesta.json();

                    datos.subatenciones.forEach((elemento) => {
                        const opcion = document.createElement("option");

                        opcion.value = elemento.id;
                        opcion.textContent = elemento.nombre;

                        if (
                            conservarSeleccion &&
                            String(elemento.id) === String(seleccionAnterior)
                        ) {
                            opcion.selected = true;
                        }

                        subatencion.appendChild(opcion);
                    });

                    if (datos.subatenciones.length === 0) {
                        opcionInicial.textContent =
                            "No hay subatenciones activas disponibles";
                    }

                    subatencion.disabled =
                        datos.subatenciones.length === 0;

                } catch (error) {
                    if (error.name !== "AbortError") {
                        console.error(
                            "[SGR] Error al cargar subatenciones:",
                            error
                        );

                        opcionInicial.textContent =
                            "No se pudieron cargar las subatenciones";
                        subatencion.disabled = true;
                    }
                }
            }

            tipo.addEventListener("change", () => {
                cargarSubatenciones(false);
            });

            if (tipo.value) {
                cargarSubatenciones(true);
            } else {
                subatencion.disabled = true;
            }
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener(
            "DOMContentLoaded",
            inicializarSelectorAtencion
        );
    } else {
        inicializarSelectorAtencion();
    }
})();
