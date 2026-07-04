// Nos aseguramos de que el DOM esté completamente cargado antes de ejecutar el código
document.addEventListener("DOMContentLoaded", function () {
    
    // Captura de elementos del DOM
    const formulario = document.getElementById("formulario-equipo");
    const inputNombre = document.getElementById("nombreCliente");
    const inputTipo = document.getElementById("tipoServicio");
    const inputDescripcion = document.getElementById("descripcionProblema");
    const contenedorMensajes = document.getElementById("mensaje-alerta");
    const listaEquipos = document.getElementById("lista-equipos");
    const contadorTotal = document.getElementById("contador-total");

    // Variable para mantener el conteo total de registros
    let totalRegistros = 0;

    // --- 1. FUNCIONES DE VALIDACIÓN DINÁMICA ---

    // Valida la longitud mínima del nombre (mínimo 5 caracteres)
    function validarNombre() {
        const valor = inputNombre.value.trim();
        if (valor.length >= 5) {
            inputNombre.classList.remove("is-invalid");
            inputNombre.classList.add("is-valid");
            return true;
        } else {
            inputNombre.classList.remove("is-valid");
            inputNombre.classList.add("is-invalid");
            return false;
        }
    }

    // Valida que se haya seleccionado una categoría
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

    // Valida que la descripción tenga información suficiente (mínimo 10 caracteres)
    function validarDescripcion() {
        const valor = inputDescripcion.value.trim();
        if (valor.length >= 10) {
            inputDescripcion.classList.remove("is-invalid");
            inputDescripcion.classList.add("is-valid");
            return true;
        } else {
            inputDescripcion.classList.remove("is-valid");
            inputDescripcion.classList.add("is-invalid");
            return false;
        }
    }

    // --- 2. EVENTOS EN TIEMPO REAL (input, change, blur) ---
    // Se activan mientras el usuario escribe o interactúa con los campos

    inputNombre.addEventListener("input", validarNombre);
    inputNombre.addEventListener("blur", validarNombre);

    inputTipo.addEventListener("change", validarTipo); 
    inputTipo.addEventListener("blur", validarTipo);

    inputDescripcion.addEventListener("input", validarDescripcion);
    inputDescripcion.addEventListener("blur", validarDescripcion);


    // --- 3. MANEJO DEL EVENTO SUBMIT ---
    formulario.addEventListener("submit", function (evento) {
        
        // Utilice preventDefault() para evitar que la página se recargue
        evento.preventDefault();

        // Ejecutar todas las validaciones al momento de enviar
        const esNombreValido = validarNombre();
        const esTipoValido = validarTipo();
        const esDescValida = validarDescripcion();

        // Permite registrar información únicamente cuando todas las validaciones sean correctas
        if (esNombreValido && esTipoValido && esDescValida) {
            
            // Extraer valores finales
            const nombre = inputNombre.value.trim();
            const tipo = inputTipo.value;
            const descripcion = inputDescripcion.value.trim();

            // Agregar el registro al DOM
            agregarRegistroDOM(nombre, tipo, descripcion);

            // Muestre mensajes dinámicos de éxito
            mostrarMensaje("¡Equipo registrado con éxito!", "success");

            // Limpiar el formulario para un nuevo ingreso
            formulario.reset();

            // Quitar las clases visuales de validación para resetear el estado visual
            inputNombre.classList.remove("is-valid");
            inputTipo.classList.remove("is-valid");
            inputDescripcion.classList.remove("is-valid");

        } else {
            // Muestre mensajes dinámicos de error
            mostrarMensaje("Por favor, verifica los campos marcados en rojo antes de continuar.", "danger");
        }
    });

    // Función para mostrar alertas dinámicas de Bootstrap
    function mostrarMensaje(texto, tipoBootstrap) {
        contenedorMensajes.innerHTML = `
            <div class="alert alert-${tipoBootstrap} alert-dismissible fade show" role="alert">
                <strong>${tipoBootstrap === 'danger' ? 'Error:' : 'Éxito:'}</strong> ${texto}
            </div>
        `;

        // Quitar la alerta automáticamente después de 3 segundos
        setTimeout(() => {
            contenedorMensajes.innerHTML = "";
        }, 3000);
    }

    // Función principal para crear y mostrar registros en pantalla (Mantenida intacta)
    function agregarRegistroDOM(nombre, tipo, descripcion) {
        
        const columna = document.createElement("div");
        columna.className = "col-md-6 col-lg-4";

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
        botonEliminar.className = "btn btn-danger btn-sm w-100 mt-2";
        botonEliminar.textContent = "Eliminar Registro";

        // Eliminar registro
        botonEliminar.addEventListener("click", function () {
            columna.remove();
            actualizarContador(-1);
        });

        // Ensamblar la tarjeta
        cuerpoTarjeta.appendChild(titulo);
        cuerpoTarjeta.appendChild(subtitulo);
        cuerpoTarjeta.appendChild(textoDescriptivo);
        cuerpoTarjeta.appendChild(botonEliminar);
        
        tarjeta.appendChild(cuerpoTarjeta);
        columna.appendChild(tarjeta);

        listaEquipos.appendChild(columna);

        // Aumentar contador
        actualizarContador(1);
    }

    // Actualizar el contador en pantalla
    function actualizarContador(cambio) {
        totalRegistros += cambio;
        contadorTotal.textContent = totalRegistros;
    }
});
