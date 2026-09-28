document.addEventListener("DOMContentLoaded", function () {
    const modal = document.getElementById("bibliotecaMultimedia");
    if (!modal) return;
    const field = document.getElementById("imagen-servicio");
    const grid = document.getElementById("cuadriculaImagenes");
    const search = document.getElementById("buscarImagen");
    const use = document.getElementById("usarImagen");
    const upload = document.getElementById("subirImagenForm");
    const file = document.getElementById("archivoImagen");
    const message = document.getElementById("bibliotecaMensaje");
    const confirm = document.getElementById("confirmarBorradoImagen");
    const uploadButton = document.getElementById("guardarImagen");
    let items = [], selected = null, deleting = null, previewURL = null;
    let loading = 0;

    function notify(text, error = false) {
        message.textContent = text;
        message.className = "alert " + (error ? "alert-danger" : "alert-success");
    }
    async function jsonRequest(url, options = {}) {
        const response = await fetch(url, {...options, credentials: "same-origin", headers: {Accept: "application/json"}});
        if (response.redirected) throw new Error("La sesión ha vencido. Recarga la página.");
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "No se pudo completar la operación.");
        return data;
    }
    function metadata(item) {
        return item.tipo + (item.tamano == null ? "" : " · " + (item.tamano / 1024).toFixed(1) + " KB") +
            (item.fecha ? " · " + new Date(item.fecha).toLocaleString() : " · Imagen estática original");
    }
    function preview(id, item) {
        const img = document.getElementById(id);
        img.hidden = !item;
        if (item) img.src = item.url;
        else img.removeAttribute("src");
    }
    function showSelected() {
        preview("previewBiblioteca", selected);
        document.getElementById("detalleImagen").textContent = selected ? selected.nombre + " — " + metadata(selected) : "Selecciona una imagen.";
        use.disabled = !selected;
    }
    function showApplied() {
        const item = items.find(item => item.valor === field.value);
        preview("imagen-actual", item);
        document.getElementById("imagen-actual-nombre").textContent = item ? item.nombre : "Sin imagen seleccionada";
    }
    function render() {
        grid.replaceChildren();
        const query = search.value.trim().toLocaleLowerCase();
        const filtered = items.filter(item => item.nombre.toLocaleLowerCase().includes(query));
        if (!filtered.length) {
            const text = document.createElement("p");
            text.textContent = "No se encontraron imágenes.";
            grid.append(text);
        }
        filtered.forEach(item => {
            const column = document.createElement("div");
            column.className = "col-6 col-md-4 col-lg-3";
            const card = document.createElement("div");
            card.className = "card h-100";
            const button = document.createElement("button");
            button.type = "button";
            button.className = "btn text-start h-100 p-2 " + (selected?.valor === item.valor ? "btn-outline-primary border-3" : "btn-outline-light text-dark border");
            button.setAttribute("aria-pressed", String(selected?.valor === item.valor));
            const img = document.createElement("img");
            img.src = item.url;
            img.alt = item.nombre;
            img.loading = "lazy";
            img.className = "w-100 rounded mb-2";
            img.style.height = "120px";
            img.style.objectFit = "contain";
            const name = document.createElement("span");
            name.className = "d-block fw-semibold text-break";
            name.textContent = item.nombre;
            const info = document.createElement("small");
            info.className = "d-block text-muted text-break";
            info.textContent = metadata(item);
            button.append(img, name, info);
            button.addEventListener("click", () => { selected = item; showSelected(); render(); });
            card.append(button);
            if (item.eliminar_url) {
                const remove = document.createElement("button");
                remove.type = "button";
                remove.className = "btn btn-sm btn-outline-danger m-2";
                remove.textContent = "Eliminar de biblioteca";
                remove.addEventListener("click", () => {
                    if (item.usos > 0) {
                        notify(`Esta imagen está siendo utilizada por ${item.usos} servicio(s) y no puede eliminarse.`, true);
                        return;
                    }
                    deleting = item;
                    confirm.hidden = false;
                    confirm.scrollIntoView({block: "nearest", behavior: "smooth"});
                });
                card.append(remove);
            }
            column.append(card);
            grid.append(column);
        });
    }
    async function load() {
        const version = ++loading;
        try {
            const data = await jsonRequest(modal.dataset.listaUrl);
            if (version !== loading) return;
            items = data.imagenes;
            selected = items.find(item => item.valor === field.value) || null;
            render(); showSelected(); showApplied();
        } catch (error) { notify(error.message, true); }
    }
    modal.addEventListener("show.bs.modal", () => {
        message.classList.add("d-none");
        confirm.hidden = true;
        search.value = "";
        load();
    });
    search.addEventListener("input", render);
    use.addEventListener("click", () => {
        if (!selected) return;
        if (![...field.options].some(option => option.value === selected.valor)) {
            field.add(new Option(selected.nombre, selected.valor));
        }
        field.value = selected.valor;
        field.dispatchEvent(new Event("change", {bubbles: true}));
        showApplied();
        bootstrap.Modal.getInstance(modal).hide();
    });
    function clearPreview() {
        if (previewURL) URL.revokeObjectURL(previewURL);
        previewURL = null;
        document.getElementById("previewSubida").hidden = true;
    }
    file.addEventListener("change", () => {
        clearPreview();
        const chosen = file.files[0];
        uploadButton.disabled = false;
        if (!chosen) return;
        if (chosen.size > 2 * 1024 * 1024 || !/\.(jpe?g|png|webp)$/i.test(chosen.name)) {
            notify("Selecciona JPG, JPEG, PNG o WEBP de hasta 2 MB.", true);
            uploadButton.disabled = true;
            return;
        }
        previewURL = URL.createObjectURL(chosen);
        const img = document.getElementById("previewSubida");
        img.src = previewURL;
        img.hidden = false;
    });
    upload.addEventListener("submit", async event => {
        event.preventDefault();
        if (!file.files.length || uploadButton.disabled) return;
        uploadButton.disabled = true;
        try {
            const data = await jsonRequest(upload.action, {method: "POST", body: new FormData(upload)});
            ++loading; // Una lectura anterior no debe reemplazar la selección recién subida.
            items = [data.imagen, ...items.filter(item => item.valor !== data.imagen.valor)];
            selected = data.imagen;
            search.value = "";
            showSelected(); render();
            bootstrap.Tab.getOrCreateInstance(document.getElementById("bibliotecaTab")).show();
            notify(data.reutilizada ? "La imagen ya existía; se reutilizó sin duplicarla." : "Imagen guardada. Pulsa Usar esta imagen para asociarla al servicio.");
            upload.reset(); clearPreview();
        } catch (error) { notify(error.message, true); }
        finally { uploadButton.disabled = false; }
    });
    document.getElementById("cancelarBorrado").addEventListener("click", () => { deleting = null; confirm.hidden = true; });
    document.getElementById("confirmarBorrado").addEventListener("click", async function () {
        if (!deleting) return;
        this.disabled = true;
        const target = deleting;
        try {
            const body = new FormData();
            const token = upload.querySelector('[name="csrf_token"]');
            if (token) body.append("csrf_token", token.value);
            await jsonRequest(target.eliminar_url, {method: "POST", body});
            items = items.filter(item => item.valor !== target.valor);
            for (const option of [...field.options]) if (option.value === target.valor) option.remove();
            if (selected?.valor === target.valor) selected = null;
            deleting = null; confirm.hidden = true;
            render(); showSelected(); showApplied();
            notify("Imagen eliminada de la biblioteca.");
        } catch (error) { notify(error.message, true); }
        finally { this.disabled = false; }
    });
    modal.addEventListener("hidden.bs.modal", () => { clearPreview(); upload.reset(); uploadButton.disabled = false; });
    load();
});
