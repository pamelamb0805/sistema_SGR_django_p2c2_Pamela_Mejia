
document.addEventListener("DOMContentLoaded", function () {
    const overlay = document.getElementById("sgrDetailOverlay");

    if (!overlay || typeof Chart === "undefined") return;

    const titulo = document.getElementById("sgrDetailTitle");
    const subtitulo = document.getElementById("sgrDetailSubtitle");
    const total = document.getElementById("sgrDetailTotal");
    const filas = document.getElementById("sgrDetailRows");
    const loading = document.getElementById("sgrDetailLoading");
    const empty = document.getElementById("sgrDetailEmpty");
    const errorBox = document.getElementById("sgrDetailError");
    const tableWrap = document.getElementById("sgrDetailTableWrap");

    const urlDetalle = "/dashboard/detalle/";

    function cerrarModal() {
        overlay.classList.remove("is-visible");
        overlay.setAttribute("aria-hidden", "true");
        document.body.classList.remove("sgr-detail-open");
    }

    function abrirModal() {
        overlay.classList.add("is-visible");
        overlay.setAttribute("aria-hidden", "false");
        document.body.classList.add("sgr-detail-open");
    }

    function limpiarEstado() {
        filas.innerHTML = "";
        loading.hidden = false;
        empty.hidden = true;
        errorBox.hidden = true;
        tableWrap.hidden = true;
        total.textContent = "0";
    }

    function crearCelda(valor) {
        const td = document.createElement("td");
        td.textContent = valor || "—";
        return td;
    }

    function mostrarFilas(registros) {
        filas.innerHTML = "";

        registros.forEach(function (registro) {
            const tr = document.createElement("tr");

            tr.appendChild(crearCelda(registro.codigo));
            tr.appendChild(crearCelda(registro.descripcion));
            tr.appendChild(crearCelda(registro.responsable));
            tr.appendChild(crearCelda(registro.delegacion));
            tr.appendChild(crearCelda(registro.fecha));
            tr.appendChild(crearCelda(registro.estado));

            const tdAccion = document.createElement("td");

            const enlace = document.createElement("a");
            enlace.className = "btn btn-sm btn-outline-primary";
            enlace.textContent = "Ver";
            enlace.href = registro.url;

            tdAccion.appendChild(enlace);
            tr.appendChild(tdAccion);
            filas.appendChild(tr);
        });
    }

    async function consultarDetalle(tipo, etiqueta, nombreGrafico) {
        limpiarEstado();
        titulo.textContent = etiqueta;
        subtitulo.textContent = nombreGrafico;
        abrirModal();

        const parametros = new URLSearchParams({
            tipo: tipo,
            etiqueta: etiqueta
        });

        try {
            const respuesta = await fetch(
                urlDetalle + "?" + parametros.toString(),
                {
                    method: "GET",
                    headers: { "X-Requested-With": "XMLHttpRequest" },
                    credentials: "same-origin"
                }
            );

            const datos = await respuesta.json();

            if (!respuesta.ok || !datos.ok) {
                throw new Error(
                    datos.mensaje || "No fue posible consultar los registros."
                );
            }

            loading.hidden = true;
            total.textContent = datos.total;

            if (!datos.filas.length) {
                empty.hidden = false;
                return;
            }

            mostrarFilas(datos.filas);
            tableWrap.hidden = false;

        } catch (e) {
            loading.hidden = true;
            errorBox.textContent = e.message;
            errorBox.hidden = false;
        }
    }

    function conectarGrafico(id, tipo, nombre) {
        const canvas = document.getElementById(id);
        if (!canvas) return;

        const grafico = Chart.getChart(canvas);
        if (!grafico) return;

        grafico.options.onClick = function (evento, elementos) {
            if (!elementos.length) return;

            const indice = elementos[0].index;
            const etiqueta = grafico.data.labels[indice];

            if (etiqueta === undefined || etiqueta === null) return;

            consultarDetalle(tipo, String(etiqueta), nombre);
        };

        grafico.options.onHover = function (evento, elementos) {
            canvas.style.cursor = elementos.length ? "pointer" : "default";
        };

        grafico.update();
    }

    conectarGrafico(
        "graficoPersonal",
        "personal",
        "Cumplimiento por indicador"
    );

    conectarGrafico(
        "graficoSemaforo",
        "semaforo",
        "Semáforo de desempeño"
    );

    conectarGrafico(
        "graficoDelegaciones",
        "delegaciones",
        "Cumplimiento por delegación"
    );

    conectarGrafico(
        "graficoAgenda",
        "agenda",
        "Compromisos por estado"
    );

    conectarGrafico(
        "graficoEvolucion",
        "evolucion",
        "Evolución mensual de actividades"
    );

    conectarGrafico(
        "graficoEvidencias",
        "evidencias",
        "Estado de evidencias"
    );

    document.getElementById("sgrDetailClose")
        .addEventListener("click", cerrarModal);

    document.getElementById("sgrDetailCloseFooter")
        .addEventListener("click", cerrarModal);

    overlay.addEventListener("click", function (evento) {
        if (evento.target === overlay) cerrarModal();
    });

    document.addEventListener("keydown", function (evento) {
        if (evento.key === "Escape" &&
            overlay.classList.contains("is-visible")) {
            cerrarModal();
        }
    });
});
