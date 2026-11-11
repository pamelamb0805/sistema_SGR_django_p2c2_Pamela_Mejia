
(() => {
    "use strict";

    const body = document.body;

    // No conectar en páginas públicas o de inicio de sesión.
    if (!body.classList.contains("sgr-app")) {
        return;
    }

    const moduloActual = body.dataset.sgrModule || "";
    const ruta = `${location.protocol === "https:" ? "wss:" : "ws:"}//${location.host}/ws/crud/`;

    let socket = null;
    let reintento = 1000;
    let temporizador = null;
    let actualizando = false;

    function conectar() {
        if (socket && (
            socket.readyState === WebSocket.OPEN ||
            socket.readyState === WebSocket.CONNECTING
        )) {
            return;
        }

        socket = new WebSocket(ruta);

        socket.addEventListener("open", () => {
            reintento = 1000;
            body.dataset.sgrWebsocket = "conectado";
            console.info("[SGR] WebSocket conectado.");
        });

        socket.addEventListener("message", async (evento) => {
            let mensaje;

            try {
                mensaje = JSON.parse(evento.data);
            } catch (error) {
                console.warn("[SGR] Mensaje WebSocket inválido.", error);
                return;
            }

            if (!mensaje.module || !mensaje.action) {
                return;
            }

            // Solo actualizar la vista si pertenece al módulo abierto.
            if (mensaje.module !== moduloActual) {
                return;
            }

            document.dispatchEvent(
                new CustomEvent("sgr:crud-update", {
                    detail: mensaje
                })
            );

            await actualizarListado();
        });

        socket.addEventListener("close", () => {
            body.dataset.sgrWebsocket = "desconectado";
            programarReconexion();
        });

        socket.addEventListener("error", () => {
            if (socket) {
                socket.close();
            }
        });
    }

    function programarReconexion() {
        if (temporizador) {
            return;
        }

        temporizador = window.setTimeout(() => {
            temporizador = null;
            conectar();
            reintento = Math.min(reintento * 2, 30000);
        }, reintento);
    }

    async function actualizarListado() {
        if (actualizando) {
            return;
        }

        const contenidoActual = document.querySelector("#contenido");

        if (!contenidoActual || !contenidoActual.querySelector("table")) {
            return;
        }

        actualizando = true;

        try {
            const respuesta = await fetch(location.href, {
                method: "GET",
                credentials: "same-origin",
                headers: {
                    "X-Requested-With": "XMLHttpRequest"
                }
            });

            if (!respuesta.ok) {
                return;
            }

            const html = await respuesta.text();
            const documento = new DOMParser().parseFromString(
                html,
                "text/html"
            );

            const contenidoNuevo = documento.querySelector("#contenido");

            if (!contenidoNuevo) {
                return;
            }

            const tablasActuales = contenidoActual.querySelectorAll("table");
            const tablasNuevas = contenidoNuevo.querySelectorAll("table");

            // Evitar reemplazar estructuras incompatibles.
            if (tablasActuales.length !== tablasNuevas.length) {
                return;
            }

            tablasActuales.forEach((tabla, indice) => {
                tabla.replaceWith(tablasNuevas[indice].cloneNode(true));
            });

            const selectores = [
                ".pagination",
                "[data-sgr-list-count]"
            ];

            selectores.forEach((selector) => {
                const actuales = contenidoActual.querySelectorAll(selector);
                const nuevos = contenidoNuevo.querySelectorAll(selector);

                if (actuales.length !== nuevos.length) {
                    return;
                }

                actuales.forEach((elemento, indice) => {
                    elemento.replaceWith(nuevos[indice].cloneNode(true));
                });
            });

            document.dispatchEvent(
                new CustomEvent("sgr:crud-refreshed")
            );

        } catch (error) {
            console.error(
                "[SGR] No se pudo actualizar el listado.",
                error
            );
        } finally {
            actualizando = false;
        }
    }

    // Evita conexiones innecesarias cuando la pestaña está cerrada.
    document.addEventListener("visibilitychange", () => {
        if (
            document.visibilityState === "visible" &&
            (!socket || socket.readyState === WebSocket.CLOSED)
        ) {
            conectar();
        }
    });

    conectar();
})();
