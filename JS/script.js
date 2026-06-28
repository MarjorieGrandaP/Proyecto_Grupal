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

    // 1. Capture el evento submit del formulario usando JavaScript
    // 2. Utilice addEventListener() para manejar los eventos
    formulario.addEventListener("submit", function (evento) {
        
        // 3. Utilice preventDefault() para evitar que la página se recargue
        evento.preventDefault();

        // Obtener los valores y quitar espacios en blanco al inicio y final
        const nombre = inputNombre.value.trim();
        const tipo = inputTipo.value;
        const descripcion = inputDescripcion.value.trim();

        // 4. Valide que los campos del formulario no estén vacíos
        if (nombre === "" || tipo === "" || descripcion === "") {
            // 5. Muestre mensajes dinámicos de validación al usuario (Error)
            mostrarMensaje("Por favor, complete todos los campos antes de registrar.", "danger");
            return; // Detiene la ejecución si hay un error
        }

        // Si la validación pasa, agregamos el registro
        agregarRegistroDOM(nombre, tipo, descripcion);

        // Muestre mensajes dinámicos de validación al usuario (Éxito)
        mostrarMensaje("¡Equipo registrado con éxito!", "success");

        // Limpiar el formulario para un nuevo ingreso
        formulario.reset();
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

    // Función principal para crear y mostrar registros en pantalla
    function agregarRegistroDOM(nombre, tipo, descripcion) {
        
        // 6. Utilice createElement() para crear elementos HTML desde JavaScript
        const columna = document.createElement("div");
        // 7. Aplique clases de Bootstrap a los elementos creados dinámicamente
        columna.className = "col-md-6 col-lg-4";

        // Creación de la tarjeta (Card) de Bootstrap
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

        // Botón para eliminar
        const botonEliminar = document.createElement("button");
        botonEliminar.className = "btn btn-danger btn-sm w-100 mt-2";
        botonEliminar.textContent = "Eliminar Registro";

        // 8. Permita eliminar registros mediante un botón y el evento click
        botonEliminar.addEventListener("click", function () {
            // Elimina la columna entera (tarjeta) del DOM
            columna.remove();
            // Actualiza el contador restando 1
            actualizarContador(-1);
        });

        // 9. Utilice appendChild() para agregar los nuevos elementos a la página
        // Armamos la estructura de la tarjeta desde adentro hacia afuera
        cuerpoTarjeta.appendChild(titulo);
        cuerpoTarjeta.appendChild(subtitulo);
        cuerpoTarjeta.appendChild(textoDescriptivo);
        cuerpoTarjeta.appendChild(botonEliminar);
        
        tarjeta.appendChild(cuerpoTarjeta);
        columna.appendChild(tarjeta);

        // Agregamos la tarjeta final al contenedor principal en el HTML
        listaEquipos.appendChild(columna);

        // Aumentamos el contador al agregar uno nuevo
        actualizarContador(1);
    }

    // 10. Muestre en pantalla el total de registros creados
    function actualizarContador(cambio) {
        totalRegistros += cambio;
        contadorTotal.textContent = totalRegistros;
    }
});