// Prueba del controlador real con DOM simulado. Ejecutable con Node, sin paquetes.
async function probarBiblioteca(source) {
    let assertions = 0;
    function assert(value, message) { if (!value) throw new Error(message); assertions++; }
    class Element {
        constructor(tag = "div") { this.tagName = tag; this.children = []; this.handlers = {}; this.dataset = {}; this.style = {}; this.value = ""; this.hidden = false; this.disabled = false; this.options = []; this.files = []; this.classList = {add() {}}; }
        append(...nodes) { nodes.forEach(n => n.parent = this); this.children.push(...nodes); }
        replaceChildren() { this.children = []; }
        setAttribute(name, value) { this[name] = value; }
        removeAttribute(name) { delete this[name]; }
        addEventListener(name, fn) { this.handlers[name] = fn; }
        dispatchEvent() {}
        scrollIntoView() {}
        add(option) { option.parent = this; this.options.push(option); }
        remove() { this.parent.options = this.parent.options.filter(o => o !== this); }
        reset() {}
        querySelector() { return {value: "csrf-prueba"}; }
        async trigger(name, event = {}) { if (this.handlers[name]) await this.handlers[name].call(this, event); }
    }
    const ids = {};
    const document = {getElementById(id) { return ids[id] ||= new Element(); }, createElement(tag) { return new Element(tag); }, addEventListener(name, fn) { this.ready = fn; }};
    const get = id => document.getElementById(id);
    const field = get("imagen-servicio");
    field.value = "servicio-1.jpg";
    field.options = [{value: "servicio-1.jpg"}];
    get("bibliotecaMultimedia").dataset.listaUrl = "/lista";
    get("subirImagenForm").action = "/subir";
    const staticItem = {valor:"servicio-1.jpg", nombre:"servicio-1.jpg", tipo:"image/jpeg", url:"/static/servicio-1.jpg", tamano:100, fecha:null, eliminar_url:null};
    const dbItem = {id:42, valor:"bd:42", nombre:"portatil.png", tipo:"image/png", url:"/imagenes-servicio/42", tamano:100, fecha:"2026-09-28T12:00:00", eliminar_url:"/eliminar/42", usos:1};
    const newItem = {...dbItem, id:43, valor:"bd:43", nombre:"nueva.png", url:"/imagenes-servicio/43", eliminar_url:"/eliminar/43", usos:0};
    const requests = [];
    const fetch = async (url, options) => {
        requests.push({url, options});
        return {ok:true, redirected:false, json:async()=>url === "/lista" ? {imagenes:[dbItem,staticItem]} : url === "/subir" ? {imagen:newItem, reutilizada:false} : {eliminada:true}};
    };
    const bootstrap = {Modal:{getInstance:()=>({hide(){}})},Tab:{getOrCreateInstance:()=>({show(){}})}};
    class FormData { constructor() { this.data = {}; } append(k,v) { this.data[k]=v; } }
    function Option(text, value) { const option=new Element("option"); option.text=text; option.value=value; return option; }
    const URL = {createObjectURL:()=>"blob:prueba",revokeObjectURL(){}};
    new Function("document","fetch","bootstrap","FormData","Option","Event","URL",source)(document,fetch,bootstrap,FormData,Option,function(){},URL);
    document.ready();
    for (let i=0;i<8;i++) await Promise.resolve();
    const grid=get("cuadriculaImagenes");
    assert(grid.children.length===2,"Carga la biblioteca");
    assert(get("imagen-actual").src===staticItem.url,"Conserva la imagen actual al cargar");
    assert(grid.children[1].children[0].children.length===1,"Las imágenes estáticas no tienen botón eliminar");
    await grid.children[0].children[0].children[1].trigger("click");
    assert(get("bibliotecaMensaje").textContent.includes("1 servicio(s)"),"Advierte imagen en uso");
    assert(!requests.some(r=>r.url.startsWith("/eliminar")),"No solicita eliminación de imagen en uso");
    get("buscarImagen").value="portatil";
    await get("buscarImagen").trigger("input");
    assert(grid.children.length===1,"Filtra por nombre sin recargar");
    await grid.children[0].children[0].children[0].trigger("click");
    assert(field.value===staticItem.valor,"La selección no modifica el servicio antes de confirmar");
    assert(get("previewBiblioteca").src===dbItem.url,"Vista previa seleccionada");
    await get("usarImagen").trigger("click");
    assert(field.value===dbItem.valor,"Usar imagen aplica el id correcto");
    get("archivoImagen").files=[{size:2*1024*1024+1,name:"grande.png"}];
    await get("archivoImagen").trigger("change");
    assert(get("guardarImagen").disabled,"Bloqueo visual de más de 2 MB");
    get("archivoImagen").files=[{size:100,name:"nueva.png"}];
    await get("archivoImagen").trigger("change");
    assert(get("previewSubida").src==="blob:prueba","Vista previa de subida");
    await get("subirImagenForm").trigger("submit",{preventDefault(){}});
    assert(get("previewBiblioteca").src===newItem.url,"La subida queda seleccionada en la biblioteca");
    await get("usarImagen").trigger("click");
    assert(field.value===newItem.valor,"La imagen nueva se asocia al confirmar");
    await grid.children[0].children[0].children[1].trigger("click");
    assert(!get("confirmarBorradoImagen").hidden,"Confirma antes de borrar");
    await get("confirmarBorrado").trigger("click");
    const deletion=requests.find(r=>r.url===newItem.eliminar_url);
    assert(deletion.options.method==="POST" && deletion.options.body.data.csrf_token==="csrf-prueba","Borrado mediante POST y CSRF");
    assert(!field.options.some(o=>o.value===newItem.valor),"Elimina la opción borrada");
    assert(requests.every(r=>r.options.credentials==="same-origin"),"Sesión en todas las peticiones");
    return assertions;
}
if (typeof require !== "undefined" && require.main === module) {
    probarBiblioteca(require("fs").readFileSync(require("path").join(__dirname,"../static/js/biblioteca.js"),"utf8"))
        .then(count=>console.log(count+" comprobaciones frontend aprobadas"))
        .catch(error=>{console.error(error);process.exitCode=1;});
}
