
/* SGR · SweetAlert2: mensajes, confirmaciones y protección contra doble envío. */
(function () {
  "use strict";

  if (typeof window.Swal === "undefined") {
    console.error(
      "SGR: SweetAlert2 no está cargado. Revisa templates/base.html."
    );
    return;
  }

  var ICONOS = {
    success: "success",
    info: "info",
    warning: "warning",
    error: "error",
    debug: "info",
    question: "question"
  };

  var TITULOS = {
    success: "Listo",
    info: "Información",
    warning: "Atención",
    error: "No se pudo completar"
  };

  var Toast = Swal.mixin({
    toast: true,
    position: "top-end",
    showConfirmButton: false,
    timer: 4000,
    timerProgressBar: true,
    didOpen: function (toast) {
      toast.addEventListener("mouseenter", Swal.stopTimer);
      toast.addEventListener("mouseleave", Swal.resumeTimer);
    }
  });

  /*
   * API pública:
   * SGR.toast("success", "Guardado correctamente")
   * SGR.alert("error", "Error", "No fue posible guardar")
   */
  window.SGR = {
    toast: function (icono, texto) {
      return Toast.fire({
        icon: ICONOS[icono] || "info",
        title: texto
      });
    },

    alert: function (icono, titulo, texto) {
      return Swal.fire({
        icon: ICONOS[icono] || "info",
        title: titulo,
        text: texto,
        confirmButtonText: "Entendido"
      });
    }
  };

  /* 1. Mensajes generados por Django */
  function mostrarMensajes() {
    var nodos = document.querySelectorAll(
      "#sgr-messages [data-sgr-message]"
    );

    if (!nodos.length) {
      return;
    }

    var mensajes = Array.prototype.map.call(nodos, function (nodo) {
      var etiqueta = (nodo.dataset.tag || "info").split(" ").pop();

      return {
        tag: ICONOS[etiqueta] ? etiqueta : "info",
        texto: nodo.textContent.trim()
      };
    });

    var graves = mensajes.filter(function (mensaje) {
      return mensaje.tag === "error" || mensaje.tag === "warning";
    });

    if (!graves.length) {
      SGR.toast(
        mensajes[0].tag,
        mensajes.map(function (mensaje) {
          return mensaje.texto;
        }).join(" · ")
      );
      return;
    }

    var peor = graves.some(function (mensaje) {
      return mensaje.tag === "error";
    }) ? "error" : "warning";

    var lista = document.createElement("div");
    lista.className = "text-start";

    mensajes.forEach(function (mensaje) {
      var parrafo = document.createElement("p");
      parrafo.className = "mb-2";
      parrafo.textContent = mensaje.texto;
      lista.appendChild(parrafo);
    });

    Swal.fire({
      icon: peor,
      title: TITULOS[peor],
      html: lista,
      confirmButtonText: "Entendido"
    });
  }

  /*
   * 2. Confirmación de formularios POST.
   *
   * Admite ambos formatos:
   * data-confirm="¿Eliminar?"
   * data-confirm-text="¿Eliminar?"
   *
   * También admite:
   * data-confirm-title
   * data-confirm-button
   * data-confirm-icon
   * data-confirm-danger
   */
  document.addEventListener("submit", function (evento) {
    var formulario = evento.target;

    if (!formulario || !formulario.dataset) {
      return;
    }

    if (formulario.dataset.confirmado === "1") {
      return;
    }

    var textoConfirmacion =
      formulario.dataset.confirmText !== undefined
        ? formulario.dataset.confirmText
        : formulario.dataset.confirm;

    if (textoConfirmacion === undefined) {
      return;
    }

    evento.preventDefault();

    var botonEnviar = evento.submitter;

    Swal.fire({
      icon: ICONOS[formulario.dataset.confirmIcon] || "question",
      title: formulario.dataset.confirmTitle || "¿Confirmar acción?",
      text: textoConfirmacion,
      showCancelButton: true,
      confirmButtonText:
        formulario.dataset.confirmButton || "Sí, continuar",
      cancelButtonText: "Cancelar",
      confirmButtonColor: formulario.hasAttribute("data-confirm-danger")
        ? "#dc3545"
        : "#0d6efd",
      focusCancel: true,
      reverseButtons: true
    }).then(function (resultado) {
      if (!resultado.isConfirmed) {
        return;
      }

      formulario.dataset.confirmado = "1";

      /*
       * requestSubmit conserva las validaciones del navegador y
       * vuelve a disparar el evento submit. La marca anterior
       * evita que la confirmación aparezca por segunda vez.
       */
      if (typeof formulario.requestSubmit === "function") {
        if (botonEnviar) {
          formulario.requestSubmit(botonEnviar);
        } else {
          formulario.requestSubmit();
        }
      } else {
        formulario.submit();
      }
    });
  }, true);

  /*
   * 3. Evitar envíos duplicados.
   * Los formularios que esperan una confirmación se deshabilitan
   * después de que el usuario confirma.
   */
  document.addEventListener("submit", function (evento) {
    if (evento.defaultPrevented) {
      return;
    }

    var formulario = evento.target;

    if (!formulario || !formulario.querySelectorAll) {
      return;
    }

    var botones = formulario.querySelectorAll(
      'button[type="submit"], input[type="submit"], button:not([type])'
    );

    botones.forEach(function (boton) {
      if (boton.dataset.sgrProcesando === "1") {
        return;
      }

      boton.dataset.sgrProcesando = "1";

      if (boton.tagName === "BUTTON" && !boton.dataset.original) {
        boton.dataset.original = boton.innerHTML;
        boton.innerHTML =
          '<span class="spinner-border spinner-border-sm me-1" ' +
          'aria-hidden="true"></span>Procesando…';
      }

      boton.disabled = true;
    });
  });

  /* Restaurar botones cuando se vuelve a la página con el navegador */
  window.addEventListener("pageshow", function () {
    document.querySelectorAll("button[data-sgr-procesando]").forEach(
      function (boton) {
        if (boton.dataset.original) {
          boton.innerHTML = boton.dataset.original;
        }

        boton.disabled = false;
        delete boton.dataset.sgrProcesando;
      }
    );

    document.querySelectorAll("form[data-confirmado]").forEach(
      function (formulario) {
        delete formulario.dataset.confirmado;
      }
    );
  });

  /* 4. Inicialización */
  document.addEventListener("DOMContentLoaded", function () {
    mostrarMensajes();

    if (typeof window.bootstrap !== "undefined") {
      document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(
        function (elemento) {
          bootstrap.Tooltip.getOrCreateInstance(elemento);
        }
      );
    }
  });
})();
