
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

    if (dropdownNotificaciones && menuNotificaciones) {
        dropdownNotificaciones.addEventListener("click", (evento) => {
            evento.preventDefault();
            evento.stopPropagation();

            const abierto = menuNotificaciones.classList.toggle("show");

            dropdownNotificaciones.setAttribute(
                "aria-expanded",
                String(abierto)
            );
        });

        document.addEventListener("click", (evento) => {
            if (
                !dropdownNotificaciones.closest(".dropdown").contains(evento.target)
            ) {
                menuNotificaciones.classList.remove("show");
                dropdownNotificaciones.setAttribute("aria-expanded", "false");
            }
        });
    }
    
    let socket = null;
    let reintento = 1000;
    let temporizador = null;
    let actualizando = false;

    const MAX_NOTIFICACIONES = 15;

    // ---------------------------------------------------------
    // CONTADOR DE NOTIFICACIONES
    // ---------------------------------------------------------

    function actualizarContador() {
        if (!listaNotificaciones || !contadorNotificaciones) {
            return;
        }

        const pendientes = listaNotificaciones.querySelectorAll(
            ".sgr-notification-unread"
        ).length;

        if (pendientes > 0) {
            contadorNotificaciones.textContent =
                pendientes > 99 ? "99+" : pendientes;

            contadorNotificaciones.classList.remove("d-none");
        } else {
            contadorNotificaciones.textContent = "0";
            contadorNotificaciones.classList.add("d-none");
        }
    }

    // ---------------------------------------------------------
    // MARCAR COMO LEÍDAS
    // ---------------------------------------------------------

    function marcarLeidas() {
        if (!listaNotificaciones) {
            return;
        }

        listaNotificaciones
            .querySelectorAll(".sgr-notification-unread")
            .forEach((elemento) => {
                elemento.classList.remove(
                    "sgr-notification-unread"
                );
            });

        actualizarContador();
    }

    if (botonMarcarLeidas) {
        botonMarcarLeidas.addEventListener(
            "click",
            (evento) => {
                evento.preventDefault();
                evento.stopPropagation();
                marcarLeidas();
            }
        );
    }

    if (dropdownNotificaciones) {
        dropdownNotificaciones
            .closest(".dropdown")
            ?.addEventListener(
                "shown.bs.dropdown",
                marcarLeidas
            );
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
    // CREAR ELEMENTO DE NOTIFICACIÓN
    // ---------------------------------------------------------

    function crearNotificacion(mensaje) {
        if (!listaNotificaciones) {
            return;
        }

        const identificador = String(
            mensaje.object_id || mensaje.object_pk || ""
        );

        const actor = mensaje.actor_name || "Usuario";
        const modulo = mensaje.module_display || mensaje.module;
        const accion = mensaje.action_display || mensaje.action;
        const objeto = mensaje.object_label || (
            `${mensaje.object_type || "Registro"} #${identificador}`
        );

        const delegacion =
            mensaje.delegacion_name ||
            mensaje.organization_name ||
            "General";

        const fecha = formatearFecha(
            mensaje.created_at || mensaje.timestamp
        );

        const elemento = document.createElement("div");

        elemento.className =
            "sgr-notification-item sgr-notification-unread";

        elemento.dataset.notificationId =
            mensaje.notification_id || "";

        const fila = document.createElement("div");
        fila.className = "d-flex gap-2";

        const icono = document.createElement("div");
        icono.className = "sgr-notification-icon";

        const iconoInterno = document.createElement("i");
        iconoInterno.className = "bi bi-activity";

        icono.appendChild(iconoInterno);

        const contenido = document.createElement("div");
        contenido.className = "flex-grow-1 min-width-0";

        const encabezado = document.createElement("div");
        encabezado.className =
            "d-flex justify-content-between gap-2";

        const titulo = document.createElement("strong");
        titulo.className = "small";
        titulo.textContent = modulo;

        const fechaElemento = document.createElement("span");
        fechaElemento.className =
            "small text-body-secondary text-nowrap";
        fechaElemento.textContent = fecha;

        encabezado.append(titulo, fechaElemento);

        const descripcion = document.createElement("p");
        descripcion.className = "small mb-1";
        descripcion.textContent = `${accion} ${objeto}`;

        const responsable = document.createElement("div");
        responsable.className = "small text-body-secondary";
        responsable.textContent = `● ${actor}`;

        const delegacionElemento = document.createElement("div");
        delegacionElemento.className =
            "small text-body-secondary";
        delegacionElemento.textContent = `◆ ${delegacion}`;

        contenido.append(
            encabezado,
            descripcion,
            responsable,
            delegacionElemento
        );

        fila.append(icono, contenido);
        elemento.appendChild(fila);

        const vacio = document.getElementById(
            "sgrNotificationEmpty"
        );

        if (vacio) {
            vacio.remove();
        }

        // Evitar insertar dos veces el mismo evento.
        if (mensaje.notification_id) {
            const duplicado = listaNotificaciones.querySelector(
                `[data-notification-id="${CSS.escape(String(mensaje.notification_id))}"]`
            );

            if (duplicado) {
                return;
            }
        }

        listaNotificaciones.prepend(elemento);

        // Conservar solamente las últimas 15.
        const elementos = listaNotificaciones.querySelectorAll(
            ".sgr-notification-item"
        );

        elementos.forEach((item, indice) => {
            if (indice >= MAX_NOTIFICACIONES) {
                item.remove();
            }
        });

        actualizarContador();
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

        socket.addEventListener(
            "message",
            async (evento) => {
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

                // 1. La notificación se procesa en cualquier módulo.
                if (mensaje.type === "crud_update") {
                    crearNotificacion(mensaje);

                    document.dispatchEvent(
                        new CustomEvent(
                            "sgr:notification",
                            {
                                detail: mensaje
                            }
                        )
                    );
                }

                // 2. La actualización de tabla solo ocurre
                //    si el evento pertenece al módulo actual.
                if (mensaje.module !== moduloActual) {
                    return;
                }

                document.dispatchEvent(
                    new CustomEvent(
                        "sgr:crud-update",
                        {
                            detail: mensaje
                        }
                    )
                );

                await actualizarListado();
            }
        );

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
    // ACTUALIZACIÓN DE TABLAS CRUD
    // ---------------------------------------------------------

    async function actualizarListado() {
        if (actualizando) {
            return;
        }

        const contenidoActual = document.querySelector(
            "#contenido"
        );

        if (
            !contenidoActual ||
            !contenidoActual.querySelector("table")
        ) {
            return;
        }

        actualizando = true;

        try {
            const respuesta = await fetch(
                location.href,
                {
                    method: "GET",
                    credentials: "same-origin",
                    headers: {
                        "X-Requested-With": "XMLHttpRequest"
                    }
                }
            );

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
                tablasActuales.length !==
                tablasNuevas.length
            ) {
                return;
            }

            tablasActuales.forEach(
                (tabla, indice) => {
                    tabla.replaceWith(
                        tablasNuevas[indice].cloneNode(true)
                    );
                }
            );

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
    // RECONEXIÓN AL VOLVER A LA PESTAÑA
    // ---------------------------------------------------------

    document.addEventListener(
        "visibilitychange",
        () => {
            if (
                document.visibilityState === "visible" &&
                (
                    !socket ||
                    socket.readyState === WebSocket.CLOSED
                )
            ) {
                conectar();
            }
        }
    );

    actualizarContador();
    conectar();

})();
