/*
 * =========================================================
 * SCRIPT PRINCIPAL DE PC-FIX
 * =========================================================
 *
 * Este archivo contiene la lógica JavaScript utilizada
 * principalmente en el formulario de diagnóstico de la
 * página de inicio.
 *
 * Como script.js se carga también en otras páginas del
 * proyecto, primero se verifica que los elementos del
 * formulario existan antes de ejecutar esta lógica.
 */

document.addEventListener("DOMContentLoaded", function () {

    // =====================================================
    // 1. OBTENER ELEMENTOS DEL FORMULARIO
    // =====================================================

    const formulario = document.getElementById("formulario-equipo");
    const inputNombre = document.getElementById("nombreCliente");
    const inputTipo = document.getElementById("tipoServicio");
    const inputDescripcion = document.getElementById(
        "descripcionProblema"
    );

    const contenedorMensajes = document.getElementById(
        "mensaje-alerta"
    );

    const listaEquipos = document.getElementById(
        "lista-equipos"
    );

    const contadorTotal = document.getElementById(
        "contador-total"
    );


    /*
     * =====================================================
     * VERIFICACIÓN DE SEGURIDAD DEL SCRIPT
     * =====================================================
     *
     * script.js se carga desde base.html y, por lo tanto,
     * también se ejecuta en páginas como:
     *
     * - Login
     * - Registro
     * - Servicios
     * - Clientes
     * - Proveedores
     * - Facturación
     *
     * Sin esta comprobación, JavaScript intentaría utilizar
     * elementos que no existen en esas páginas y produciría
     * errores del tipo:
     *
     * "Cannot read properties of null"
     *
     * Si cualquiera de los elementos del formulario no existe,
     * simplemente se detiene esta parte del script.
     */
    if (
        !formulario ||
        !inputNombre ||
        !inputTipo ||
        !inputDescripcion ||
        !contenedorMensajes ||
        !listaEquipos ||
        !contadorTotal
    ) {
        return;
    }


    // Número de órdenes creadas temporalmente en la página.
    let totalRegistros = 0;


    // =====================================================
    // 2. FUNCIONES DE VALIDACIÓN
    // =====================================================

    /*
     * Comprueba que el campo nombre tenga por lo menos
     * cinco caracteres.
     */
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


    /*
     * Comprueba que el usuario haya seleccionado
     * un tipo de servicio.
     */
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


    /*
     * Comprueba que la descripción del problema contenga
     * al menos diez caracteres.
     */
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


    // =====================================================
    // 3. VALIDACIÓN EN TIEMPO REAL
    // =====================================================

    /*
     * Cada campo se valida mientras el usuario escribe
     * o selecciona una opción.
     */
    inputNombre.addEventListener(
        "input",
        validarNombre
    );

    inputTipo.addEventListener(
        "change",
        validarTipo
    );

    inputDescripcion.addEventListener(
        "input",
        validarDescripcion
    );


    // =====================================================
    // 4. ENVÍO DEL FORMULARIO
    // =====================================================

    formulario.addEventListener(
        "submit",
        function (evento) {

            /*
             * Evita que el navegador recargue inmediatamente
             * la página al enviar el formulario.
             */
            evento.preventDefault();

            const esNombreValido = validarNombre();
            const esTipoValido = validarTipo();
            const esDescValida = validarDescripcion();


            /*
             * El proceso continúa únicamente cuando
             * todas las validaciones son correctas.
             */
            if (
                esNombreValido &&
                esTipoValido &&
                esDescValida
            ) {

                const btnEnviar = document.getElementById(
                    "btn-enviar"
                );

                const spinner = document.getElementById(
                    "spinner-carga"
                );

                const textoBoton = document.getElementById(
                    "texto-boton"
                );


                // Mostrar estado de procesamiento.
                btnEnviar.disabled = true;
                spinner.classList.remove("d-none");

                textoBoton.textContent =
                    " Procesando Orden...";


                /*
                 * Simula un proceso de 1.5 segundos para
                 * representar el procesamiento de la orden.
                 */
                setTimeout(function () {

                    const nombre =
                        inputNombre.value.trim();

                    const tipo =
                        inputTipo.value;

                    const descripcion =
                        inputDescripcion.value.trim();


                    // Crear visualmente la nueva orden.
                    agregarRegistroDOM(
                        nombre,
                        tipo,
                        descripcion
                    );


                    // Mostrar mensaje de éxito.
                    mostrarMensaje(
                        "¡Orden de servicio generada con éxito!",
                        "success"
                    );


                    // Limpiar el formulario.
                    formulario.reset();

                    inputNombre.classList.remove(
                        "is-valid"
                    );

                    inputTipo.classList.remove(
                        "is-valid"
                    );

                    inputDescripcion.classList.remove(
                        "is-valid"
                    );


                    // Restaurar el botón.
                    btnEnviar.disabled = false;

                    spinner.classList.add(
                        "d-none"
                    );

                    textoBoton.textContent =
                        "Generar Orden de Servicio";

                }, 1500);

            } else {

                /*
                 * Si alguna validación falla, se informa
                 * al usuario antes de continuar.
                 */
                mostrarMensaje(
                    "Por favor, verifica los campos marcados en rojo antes de continuar.",
                    "danger"
                );
            }
        }
    );


    // =====================================================
    // 5. MENSAJES BOOTSTRAP
    // =====================================================

    /*
     * Genera dinámicamente una alerta Bootstrap.
     */
    function mostrarMensaje(
        texto,
        tipoBootstrap
    ) {

        contenedorMensajes.innerHTML = `
            <div
                class="alert alert-${tipoBootstrap}
                       alert-dismissible fade show shadow-sm"
                role="alert"
            >
                <strong>
                    ${
                        tipoBootstrap === "danger"
                            ? "Error:"
                            : "Éxito:"
                    }
                </strong>

                ${texto}

                <button
                    type="button"
                    class="btn-close"
                    data-bs-dismiss="alert"
                    aria-label="Cerrar"
                ></button>
            </div>
        `;


        /*
         * El mensaje desaparece automáticamente
         * después de cuatro segundos.
         */
        setTimeout(
            function () {
                contenedorMensajes.innerHTML = "";
            },
            4000
        );
    }


    // =====================================================
    // 6. CREACIÓN DINÁMICA DE ÓRDENES
    // =====================================================

    /*
     * Crea una tarjeta Bootstrap con la información
     * ingresada por el usuario y la agrega al DOM.
     */
    function agregarRegistroDOM(
        nombre,
        tipo,
        descripcion
    ) {

        const columna =
            document.createElement("div");

        columna.className =
            "col-md-6 col-lg-4 efecto-flotar";


        const tarjeta =
            document.createElement("div");

        tarjeta.className =
            "card h-100 shadow-sm border-info";


        const cuerpoTarjeta =
            document.createElement("div");

        cuerpoTarjeta.className =
            "card-body";


        // Nombre y equipo.
        const titulo =
            document.createElement("h5");

        titulo.className =
            "card-title text-primary fw-bold";

        titulo.textContent = nombre;


        // Tipo de servicio.
        const subtitulo =
            document.createElement("h6");

        subtitulo.className =
            "card-subtitle mb-2 text-muted";

        subtitulo.textContent =
            `Categoría: ${tipo}`;


        // Descripción del problema.
        const textoDescriptivo =
            document.createElement("p");

        textoDescriptivo.className =
            "card-text mt-3";

        textoDescriptivo.textContent =
            descripcion;


        // Botón para eliminar la orden.
        const botonEliminar =
            document.createElement("button");

        botonEliminar.className =
            "btn btn-outline-danger btn-sm w-100 mt-2";

        botonEliminar.innerHTML =
            '<i class="fa fa-trash"></i> Eliminar Registro';


        // =================================================
        // 7. MODAL DE CONFIRMACIÓN DE ELIMINACIÓN
        // =================================================

        botonEliminar.addEventListener(
            "click",
            function () {

                const elementoModal =
                    document.getElementById(
                        "modalEliminar"
                    );

                const btnConfirmar =
                    document.getElementById(
                        "btn-confirmar-eliminar"
                    );


                /*
                 * Crear una instancia del modal Bootstrap
                 * utilizado para confirmar la eliminación.
                 */
                const modalEliminar =
                    new bootstrap.Modal(
                        elementoModal
                    );

                modalEliminar.show();


                /*
                 * Se reemplaza el botón anterior por una copia
                 * para evitar acumular varios eventos click.
                 */
                const nuevoBtnConfirmar =
                    btnConfirmar.cloneNode(true);

                btnConfirmar.parentNode.replaceChild(
                    nuevoBtnConfirmar,
                    btnConfirmar
                );


                nuevoBtnConfirmar.addEventListener(
                    "click",
                    function () {

                        // Eliminar la tarjeta visual.
                        columna.remove();

                        // Disminuir el contador.
                        actualizarContador(-1);

                        // Cerrar el modal.
                        modalEliminar.hide();

                        // Informar al usuario.
                        mostrarMensaje(
                            "Registro eliminado correctamente.",
                            "warning"
                        );
                    }
                );
            }
        );


        // Construcción de la tarjeta.
        cuerpoTarjeta.appendChild(titulo);
        cuerpoTarjeta.appendChild(subtitulo);
        cuerpoTarjeta.appendChild(
            textoDescriptivo
        );

        cuerpoTarjeta.appendChild(
            botonEliminar
        );

        tarjeta.appendChild(
            cuerpoTarjeta
        );

        columna.appendChild(
            tarjeta
        );

        listaEquipos.appendChild(
            columna
        );


        // Incrementar contador de órdenes.
        actualizarContador(1);
    }


    // =====================================================
    // 8. ACTUALIZACIÓN DEL CONTADOR
    // =====================================================

    /*
     * Permite aumentar o disminuir el número
     * total de órdenes visibles.
     */
    function actualizarContador(cambio) {

        totalRegistros += cambio;

        contadorTotal.textContent =
            totalRegistros;
    }

});