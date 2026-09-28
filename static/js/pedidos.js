document.addEventListener("DOMContentLoaded", function () {
    const modal = document.getElementById("modalSeguimiento");
    let solicitud;
    if (modal) {
        modal.addEventListener("show.bs.modal", async function (event) {
            if (solicitud) solicitud.abort();
            solicitud = new AbortController();
            const signal = solicitud.signal;
            const contenido = document.getElementById("contenidoSeguimiento");
            contenido.textContent = "Cargando historial...";
            try {
                const respuesta = await fetch(event.relatedTarget.dataset.seguimientoUrl, {
                    signal, credentials: "same-origin", headers: {"Accept": "text/html"}
                });
                if (!respuesta.ok || respuesta.redirected) throw new Error("Historial no disponible");
                const html = await respuesta.text();
                if (!signal.aborted) contenido.innerHTML = html;
            } catch (error) {
                if (error.name !== "AbortError" && !signal.aborted) {
                    contenido.textContent = "No fue posible cargar el historial. Cierra el modal e inténtalo nuevamente.";
                }
            }
        });
        modal.addEventListener("hidden.bs.modal", function () {
            if (solicitud) solicitud.abort();
            document.getElementById("contenidoSeguimiento").textContent = "";
        });
    }
    const cancelacion = document.getElementById("cancelarPedido");
    const motivo = document.getElementById("motivoCancelacion");
    const observacion = document.getElementById("observacionCancelacion");
    if (cancelacion && motivo && observacion) {
        function validarOtro() {
            observacion.required = motivo.value === "Otro";
            observacion.setCustomValidity(observacion.required && !observacion.value.trim()
                ? "Describe el motivo de cancelación." : "");
        }
        motivo.addEventListener("change", validarOtro);
        observacion.addEventListener("input", validarOtro);
        cancelacion.addEventListener("show.bs.modal", function (event) {
            const form = document.getElementById("confirmarCancelacion");
            form.reset();
            form.action = event.relatedTarget.dataset.action;
            validarOtro();
        });
    }

});

// Seguimiento expandible: reutiliza la misma ruta y sus permisos.
document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-historial-url]").forEach(function (seccion) {
        let solicitud;
        seccion.addEventListener("show.bs.collapse", async function (event) {
            if (event.target !== seccion) return;
            if (solicitud) solicitud.abort();
            solicitud = new AbortController();
            const signal = solicitud.signal;
            const contenido = seccion.querySelector("[data-historial-contenido]");
            contenido.textContent = "Cargando historial...";
            try {
                const respuesta = await fetch(seccion.dataset.historialUrl, {
                    signal, credentials: "same-origin", headers: {"Accept": "text/html"}
                });
                if (!respuesta.ok || respuesta.redirected) throw new Error("Historial no disponible");
                const html = await respuesta.text();
                if (!signal.aborted) contenido.innerHTML = html;
            } catch (error) {
                if (!signal.aborted) contenido.textContent = "No fue posible cargar el historial. Cierra esta sección y vuelve a abrirla para reintentar.";
            }
        });
        seccion.addEventListener("hide.bs.collapse", function () {
            if (solicitud) solicitud.abort();
        });
    });
});
