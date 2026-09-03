document.addEventListener("DOMContentLoaded", function () {
    
    const formulario = document.getElementById("formulario-equipo");
    const inputNombre = document.getElementById("nombreCliente");
    const inputTipo = document.getElementById("tipoServicio");
    const inputDescripcion = document.getElementById("descripcionProblema");
    const contenedorMensajes = document.getElementById("mensaje-alerta");
    const listaEquipos = document.getElementById("lista-equipos");
    const contadorTotal = document.getElementById("contador-total");

    let totalRegistros = 0;

    // --- 1. FUNCIONES DE VALIDACIÓN ---
    function validarNombre() {
        if (inputNombre.value.trim().length >= 5) {
            inputNombre.classList.remove("is-invalid");
            inputNombre.classList.add("is-valid");
            return true;
        } else {
            inputNombre.classList.remove("is-valid");
            inputNombre.classList.add("is-invalid");
            return false;
        }
    }

    function validarTipo() {
        if (inputTipo.value !== "") {
            inputTipo.classList.remove("is-invalid");
            inputTipo.classList.add("is-valid");
            return true;
        } else {
            inputTipo.classList.remove("is-valid");
            inputTipo.classList.add("is-invalid");
            return false;
        }
    }

    function validarDescripcion() {
        if (inputDescripcion.value.trim().length >= 10) {
            inputDescripcion.classList.remove("is-invalid");
            inputDescripcion.classList.add("is-valid");
            return true;
        } else {
            inputDescripcion.classList.remove("is-valid");
            inputDescripcion.classList.add("is-invalid");
            return false;
        }
    }

    // Eventos en tiempo real
    inputNombre.addEventListener("input", validarNombre);
    inputTipo.addEventListener("change", validarTipo); 
    inputDescripcion.addEventListener("input", validarDescripcion);

    // --- 2. MANEJO DEL EVENTO SUBMIT (CON SPINNER) ---
    formulario.addEventListener("submit", function (evento) {
        evento.preventDefault();

        const esNombreValido = validarNombre();
        const esTipoValido = validarTipo();
        const esDescValida = validarDescripcion();

        if (esNombreValido && esTipoValido && esDescValida) {
            
            // Elementos del botón y spinner
            const btnEnviar = document.getElementById("btn-enviar");
            const spinner = document.getElementById("spinner-carga");
            const textoBoton = document.getElementById("texto-boton");

            // Estado de "Cargando"
            btnEnviar.disabled = true;
            spinner.classList.remove("d-none");
            textoBoton.textContent = " Procesando Orden...";

            // Simular proceso con setTimeout (Spinner de Bootstrap)
            setTimeout(() => {
                const nombre = inputNombre.value.trim();
                const tipo = inputTipo.value;
                const descripcion = inputDescripcion.value.trim();

                agregarRegistroDOM(nombre, tipo, descripcion);
                mostrarMensaje("¡Orden de servicio generada con éxito!", "success");

                formulario.reset();
                inputNombre.classList.remove("is-valid");
                inputTipo.classList.remove("is-valid");
                inputDescripcion.classList.remove("is-valid");

                // Restaurar Botón
                btnEnviar.disabled = false;
                spinner.classList.add("d-none");
                textoBoton.textContent = "Generar Orden de Servicio";
            }, 1500); // Demora simulada de 1.5 segundos

        } else {
            mostrarMensaje("Por favor, verifica los campos marcados en rojo antes de continuar.", "danger");
        }
    });

    // --- 3. ALERTAS BOOTSTRAP ---
    function mostrarMensaje(texto, tipoBootstrap) {
        contenedorMensajes.innerHTML = `
            <div class="alert alert-${tipoBootstrap} alert-dismissible fade show shadow-sm" role="alert">
                <strong>${tipoBootstrap === 'danger' ? 'Error:' : 'Éxito:'}</strong> ${texto}
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            </div>
        `;
        setTimeout(() => { contenedorMensajes.innerHTML = ""; }, 4000);
    }

    // --- 4. RENDERIZADO DOM Y MODAL BOOTSTRAP ---
    function agregarRegistroDOM(nombre, tipo, descripcion) {
        const columna = document.createElement("div");
        columna.className = "col-md-6 col-lg-4 efecto-flotar";

        const tarjeta = document.createElement("div");
        tarjeta.className = "card h-100 shadow-sm border-info";

        const cuerpoTarjeta = document.createElement("div");
        cuerpoTarjeta.className = "card-body";

        const titulo = document.createElement("h5");
        titulo.className = "card-title text-primary fw-bold";
        titulo.textContent = nombre;

        const subtitulo = document.createElement("h6");
        subtitulo.className = "card-subtitle mb-2 text-muted";
        subtitulo.textContent = `Categoría: ${tipo}`;

        const textoDescriptivo = document.createElement("p");
        textoDescriptivo.className = "card-text mt-3";
        textoDescriptivo.textContent = descripcion;

        const botonEliminar = document.createElement("button");
        botonEliminar.className = "btn btn-outline-danger btn-sm w-100 mt-2";
        botonEliminar.innerHTML = '<i class="fa fa-trash"></i> Eliminar Registro';

        // Lógica de Modal al eliminar
        botonEliminar.addEventListener("click", function () {
            // Instanciar el Modal de Bootstrap
            const modalEliminar = new bootstrap.Modal(document.getElementById('modalEliminar'));
            const btnConfirmar = document.getElementById("btn-confirmar-eliminar");
            
            modalEliminar.show();

            // Reemplazar el botón confirmar para limpiar eventos previos (evita borrar múltiples registros)
            const nuevoBtnConfirmar = btnConfirmar.cloneNode(true);
            btnConfirmar.parentNode.replaceChild(nuevoBtnConfirmar, btnConfirmar);

            nuevoBtnConfirmar.addEventListener("click", function() {
                columna.remove();
                actualizarContador(-1);
                modalEliminar.hide(); // Cerrar modal
                mostrarMensaje("Registro eliminado correctamente.", "warning");
            });
        });

        cuerpoTarjeta.appendChild(titulo);
        cuerpoTarjeta.appendChild(subtitulo);
        cuerpoTarjeta.appendChild(textoDescriptivo);
        cuerpoTarjeta.appendChild(botonEliminar);
        
        tarjeta.appendChild(cuerpoTarjeta);
        columna.appendChild(tarjeta);
        listaEquipos.appendChild(columna);

        actualizarContador(1);
    }

    function actualizarContador(cambio) {
        totalRegistros += cambio;
        contadorTotal.textContent = totalRegistros;
    }
});