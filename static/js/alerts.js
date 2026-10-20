/* SGR · SweetAlert2: mensajes de Django, confirmaciones y protección contra doble envío. */
(function () {
  "use strict";

  var ICONOS = { success: "success", info: "info", warning: "warning", error: "error", debug: "info" };
  var TITULOS = { success: "Listo", info: "Información", warning: "Atención", error: "No se pudo completar" };

  var Toast = Swal.mixin({
    toast: true, position: "top-end", showConfirmButton: false, timer: 4000, timerProgressBar: true,
    didOpen: function (t) { t.addEventListener("mouseenter", Swal.stopTimer); t.addEventListener("mouseleave", Swal.resumeTimer); }
  });

  /* API pública: SGR.toast("success", "Guardado") · SGR.alert("error", "Título", "Detalle") */
  window.SGR = {
    toast: function (icono, texto) { return Toast.fire({ icon: ICONOS[icono] || "info", title: texto }); },
    alert: function (icono, titulo, texto) {
      return Swal.fire({ icon: ICONOS[icono] || "info", title: titulo, text: texto, confirmButtonText: "Entendido" });
    }
  };

  /* 1) Mensajes de Django ---------------------------------------------------------------- */
  function mostrarMensajes() {
    var nodos = document.querySelectorAll("#sgr-messages [data-sgr-message]");
    if (!nodos.length) { return; }
    var mensajes = Array.prototype.map.call(nodos, function (n) {
      var tag = (n.dataset.tag || "info").split(" ").pop();
      return { tag: ICONOS[tag] ? tag : "info", texto: n.textContent.trim() };
    });
    var graves = mensajes.filter(function (m) { return m.tag === "error" || m.tag === "warning"; });

    if (!graves.length) {                                  // solo éxito / información: aviso breve
      SGR.toast(mensajes[0].tag, mensajes.map(function (m) { return m.texto; }).join(" · "));
      return;
    }
    var peor = graves.some(function (m) { return m.tag === "error"; }) ? "error" : "warning";
    var lista = document.createElement("div");
    lista.className = "text-start";
    mensajes.forEach(function (m) {                        // textContent: sin riesgo de inyección de HTML
      var p = document.createElement("p");
      p.className = "mb-2";
      p.textContent = m.texto;
      lista.appendChild(p);
    });
    Swal.fire({ icon: peor, title: TITULOS[peor], html: lista, confirmButtonText: "Entendido" });
  }

  /* 2) Confirmación en formularios: <form data-confirm="¿Eliminar?" data-confirm-title="..."
        data-confirm-button="Sí, eliminar" data-confirm-icon="warning" data-confirm-danger> ------ */
  document.addEventListener("submit", function (e) {
    var form = e.target;
    if (!form.dataset || form.dataset.confirm === undefined || form.dataset.confirmado === "1") { return; }
    e.preventDefault();
    var submitter = e.submitter;
    Swal.fire({
      icon: form.dataset.confirmIcon || "question",
      title: form.dataset.confirmTitle || "¿Confirmar acción?",
      text: form.dataset.confirm,
      showCancelButton: true,
      confirmButtonText: form.dataset.confirmButton || "Sí, continuar",
      cancelButtonText: "Cancelar",
      confirmButtonColor: form.hasAttribute("data-confirm-danger") ? "#dc3545" : "#0d6efd",
      focusCancel: true, reverseButtons: true
    }).then(function (r) {
      if (r.isConfirmed) {
        form.dataset.confirmado = "1";
        if (form.requestSubmit) { form.requestSubmit(submitter || undefined); } else { form.submit(); }
      }
    });
  }, true);

  /* 3) Evita envíos duplicados (RNF-003) --------------------------------------------------- */
  document.addEventListener("submit", function (e) {
    if (e.defaultPrevented) { return; }
    var botones = e.target.querySelectorAll('button[type="submit"], input[type="submit"]');
    setTimeout(function () {                               // después de que el navegador lea el botón
      botones.forEach(function (b) {
        b.disabled = true;
        if (b.tagName === "BUTTON" && !b.dataset.original) {
          b.dataset.original = b.innerHTML;
          b.innerHTML = '<span class="spinner-border spinner-border-sm me-1" aria-hidden="true"></span>Procesando…';
        }
      });
    }, 0);
  });
  window.addEventListener("pageshow", function (e) {       // al volver con el botón "atrás"
    if (!e.persisted) { return; }
    document.querySelectorAll("button[data-original]").forEach(function (b) { b.innerHTML = b.dataset.original; b.disabled = false; });
    document.querySelectorAll("form[data-confirmado]").forEach(function (f) { delete f.dataset.confirmado; });
  });

  /* 4) Inicio ----------------------------------------------------------------------------- */
  document.addEventListener("DOMContentLoaded", function () {
    mostrarMensajes();
    document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(function (el) { new bootstrap.Tooltip(el); });
  });
})();
