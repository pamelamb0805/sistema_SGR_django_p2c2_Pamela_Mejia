
(() => {
    "use strict";

    const body = document.body;

    if (!body.classList.contains("sgr-app")) {
        return;
    }

    const moduloActual = body.dataset.sgrModule || "";

    const ruta = `${location.protocol === "https:" ? "wss:" : "ws:"}//${location.host}/ws/sgr/`;

    const listaNotificaciones = document.getElementById(
        "sgrNotificationList"
    );

    const contadorNotificaciones = document.getElementById(
        "sgrNotificationCount"
    );

    const botonMarcarLeidas = document.getElementById(
        "sgrMarkNotificationsRead"
    );

    const dropdownNotificaciones = document.getElementById(
        "sgrNotificationDropdown"
    );

    const menuNotificaciones = document.getElementById(
        "sgrNotificationMenu"
    );

    let socket = null;
    let reintento = 1000;
    let temporizador = null;
    let actualizando = false;

    // ---------------------------------------------------------
    // MENÚ DE NOTIFICACIONES
    // ---------------------------------------------------------

    if (dropdownNotificaciones && menuNotificaciones) {
        dropdownNotificaciones.addEventListener("click", async (evento) => {
            evento.preventDefault();
            evento.stopPropagation();

            const abierto = menuNotificaciones.classList.toggle("show");

            dropdownNotificaciones.setAttribute(
                "aria-expanded",
                String(abierto)
            );

            if (abierto) {
                await cargarNotificaciones();
                await marcarLeidas();
            }
        });

        document.addEventListener("click", (evento) => {
            if (
                !dropdownNotificaciones.closest(".dropdown").contains(
                    evento.target
                )
            ) {
                menuNotificaciones.classList.remove("show");

                dropdownNotificaciones.setAttribute(
                    "aria-expanded",
                    "false"
                );
            }
        });
    }

    // ---------------------------------------------------------
    // CONTADOR DE NOTIFICACIONES
    // ---------------------------------------------------------

    function actualizarContador(totalPendientes = null) {
        if (!listaNotificaciones || !contadorNotificaciones) {
            return;
        }

        const pendientes = totalPendientes === null
            ? listaNotificaciones.querySelectorAll(
                ".sgr-notification-unread"
            ).length
            : Number(totalPendientes);

        if (pendientes > 0) {
            contadorNotificaciones.textContent =
                pendientes > 99 ? "99+" : String(pendientes);

            contadorNotificaciones.hidden = false;
            contadorNotificaciones.classList.remove("d-none");
        } else {
            contadorNotificaciones.textContent = "0";
            contadorNotificaciones.hidden = true;
            contadorNotificaciones.classList.add("d-none");
        }
    }

    // ---------------------------------------------------------
    // FORMATO DE FECHA
    // ---------------------------------------------------------

    function formatearFecha(fecha) {
        if (!fecha) {
            return "Fecha no disponible";
        }

        const valor = new Date(fecha);

        if (Number.isNaN(valor.getTime())) {
            return "Fecha no disponible";
        }

        return valor.toLocaleString("es-CL", {
            day: "2-digit",
            month: "2-digit",
            year: "numeric",
            hour: "2-digit",
            minute: "2-digit"
        });
    }

    // ---------------------------------------------------------
    // CARGAR NOTIFICACIONES PERSISTENTES
    // ---------------------------------------------------------

    async function cargarNotificaciones() {
        if (!listaNotificaciones) {
            return;
        }

        const url = listaNotificaciones.dataset.listUrl;

        if (!url) {
            console.error(
                "[SGR] No se encontró la URL de notificaciones."
            );
            return;
        }

        try {
            const respuesta = await fetch(url, {
                method: "GET",
                credentials: "same-origin",
                headers: {
                    "X-Requested-With": "XMLHttpRequest",
                    "Accept": "application/json"
                }
            });

            if (!respuesta.ok) {
                throw new Error(`Error HTTP ${respuesta.status}`);
            }

            const resultado = await respuesta.json();

            if (!resultado.ok) {
                throw new Error(
                    "El servidor no pudo cargar las notificaciones."
                );
            }

            listaNotificaciones.replaceChildren();

            if (!resultado.notificaciones.length) {
                const vacio = document.createElement("div");

                vacio.id = "sgrNotificationEmpty";
                vacio.className = "sgr-notification-empty";
                vacio.textContent = "No hay notificaciones recientes.";

                listaNotificaciones.appendChild(vacio);
            } else {
                resultado.notificaciones.forEach((notificacion) => {
                    const elemento = document.createElement("div");

                    elemento.className = "sgr-notification-item";

                    if (!notificacion.leida) {
                        elemento.classList.add(
                            "sgr-notification-unread"
                        );
                    }

                    elemento.dataset.notificationId = notificacion.id;

                    const fila = document.createElement("div");
                    fila.className = "d-flex align-items-start gap-2";

                    const icono = document.createElement("i");
                    icono.className =
                        "bi bi-activity text-primary mt-1";

                    const contenido = document.createElement("div");
                    contenido.className = "flex-grow-1";

                    const titulo = document.createElement("div");
                    titulo.className = "sgr-notification-title";
                    titulo.textContent =
                        `${notificacion.modulo} · ${notificacion.accion}`;

                    const objeto = document.createElement("span");
                    objeto.className = "sgr-notification-detail";
                    objeto.textContent = notificacion.objeto;

                    const actor = document.createElement("span");
                    actor.className = "sgr-notification-detail";
                    actor.textContent = `● ${notificacion.actor}`;

                    const delegacion = document.createElement("span");
                    delegacion.className = "sgr-notification-detail";
                    delegacion.textContent =
                        `◆ ${notificacion.delegacion}`;

                    const fecha = document.createElement("span");
                    fecha.className = "sgr-notification-date";
                    fecha.textContent =
                        formatearFecha(notificacion.fecha);

                    contenido.append(
                        titulo,
                        objeto,
                        actor,
                        delegacion,
                        fecha
                    );

                    fila.append(icono, contenido);
                    elemento.appendChild(fila);
                    listaNotificaciones.appendChild(elemento);
                });
            }

            actualizarContador(resultado.pendientes);

        } catch (error) {
            console.error(
                "[SGR] No se pudieron cargar las notificaciones.",
                error
            );
        }
    }

    // ---------------------------------------------------------
    // MARCAR NOTIFICACIONES COMO LEÍDAS
    // ---------------------------------------------------------

    async function marcarLeidas() {
        if (!listaNotificaciones || !botonMarcarLeidas) {
            return;
        }

        const url = botonMarcarLeidas.dataset.markReadUrl;

        const csrfToken = document.querySelector(
            '#sgrNotificationCsrf input[name="csrfmiddlewaretoken"]'
        )?.value;

        if (!url || !csrfToken) {
            console.error(
                "[SGR] No se encontró la URL o el token CSRF."
            );
            return;
        }

        botonMarcarLeidas.disabled = true;

        try {
            const respuesta = await fetch(url, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "X-CSRFToken": csrfToken,
                    "X-Requested-With": "XMLHttpRequest",
                    "Accept": "application/json"
                }
            });

            if (!respuesta.ok) {
                throw new Error(`Error HTTP ${respuesta.status}`);
            }

            const resultado = await respuesta.json();

            if (!resultado.ok) {
                throw new Error(
                    "El servidor no confirmó la operación."
                );
            }

            listaNotificaciones
                .querySelectorAll(".sgr-notification-unread")
                .forEach((elemento) => {
                    elemento.classList.remove(
                        "sgr-notification-unread"
                    );
                });

            actualizarContador(resultado.pendientes);

        } catch (error) {
            console.error(
                "[SGR] No se pudieron marcar las notificaciones.",
                error
            );

        } finally {
            botonMarcarLeidas.disabled = false;
        }
    }

    if (botonMarcarLeidas) {
        botonMarcarLeidas.addEventListener("click", (evento) => {
            evento.preventDefault();
            evento.stopPropagation();
            marcarLeidas();
        });
    }

    // ---------------------------------------------------------
    // ACTUALIZACIÓN DE TABLAS CRUD
    // ---------------------------------------------------------

    async function actualizarListado() {
        if (actualizando) {
            return;
        }

        const contenidoActual = document.querySelector("#contenido");

        if (
            !contenidoActual ||
            !contenidoActual.querySelector("table")
        ) {
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

            const contenidoNuevo = documento.querySelector(
                "#contenido"
            );

            if (!contenidoNuevo) {
                return;
            }

            const tablasActuales =
                contenidoActual.querySelectorAll("table");

            const tablasNuevas =
                contenidoNuevo.querySelectorAll("table");

            if (
                tablasActuales.length !== tablasNuevas.length
            ) {
                return;
            }

            tablasActuales.forEach((tabla, indice) => {
                tabla.replaceWith(
                    tablasNuevas[indice].cloneNode(true)
                );
            });

            const selectores = [
                ".pagination",
                "[data-sgr-list-count]"
            ];

            selectores.forEach((selector) => {
                const actuales =
                    contenidoActual.querySelectorAll(selector);

                const nuevos =
                    contenidoNuevo.querySelectorAll(selector);

                if (actuales.length !== nuevos.length) {
                    return;
                }

                actuales.forEach((elemento, indice) => {
                    elemento.replaceWith(
                        nuevos[indice].cloneNode(true)
                    );
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

    // ---------------------------------------------------------
    // CONEXIÓN WEBSOCKET
    // ---------------------------------------------------------

    function conectar() {
        if (
            socket &&
            (
                socket.readyState === WebSocket.OPEN ||
                socket.readyState === WebSocket.CONNECTING
            )
        ) {
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
                console.warn(
                    "[SGR] Mensaje WebSocket inválido.",
                    error
                );
                return;
            }

            if (!mensaje.module || !mensaje.action) {
                return;
            }

            // Actualizar notificaciones en cualquier módulo.
            if (mensaje.type === "crud_update") {
                await cargarNotificaciones();

                document.dispatchEvent(
                    new CustomEvent("sgr:notification", {
                        detail: mensaje
                    })
                );
            }

            // Actualizar tabla solamente en el módulo correspondiente.
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

    // ---------------------------------------------------------
    // RECONEXIÓN AUTOMÁTICA
    // ---------------------------------------------------------

    function programarReconexion() {
        if (temporizador) {
            return;
        }

        temporizador = window.setTimeout(() => {
            temporizador = null;

            conectar();

            reintento = Math.min(
                reintento * 2,
                30000
            );
        }, reintento);
    }

    // ---------------------------------------------------------
    // RECONEXIÓN AL VOLVER A LA PESTAÑA
    // ---------------------------------------------------------

    document.addEventListener("visibilitychange", () => {
        if (
            document.visibilityState === "visible" &&
            (
                !socket ||
                socket.readyState === WebSocket.CLOSED
            )
        ) {
            conectar();
        }
    });

    // ---------------------------------------------------------
    // INICIALIZACIÓN
    // ---------------------------------------------------------

    actualizarContador();
    cargarNotificaciones();
    conectar();

})();
