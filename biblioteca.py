"""Imágenes de servicios en PostgreSQL; las subidas nunca se escriben en disco."""
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import warnings
from PIL import Image, UnidentifiedImageError
from flask import abort, jsonify, request, send_file, url_for
from psycopg2.extras import RealDictCursor
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename
from forms.imagen_servicio_form import ImagenServicioForm
from forms import EliminarForm

MAX_BYTES = 2 * 1024 * 1024
MAX_PIXELS = 20_000_000
FORMATOS = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
EXTENSIONES = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".webp": "WEBP"}


def imagenes_estaticas(root):
    carpeta = Path(root) / "static" / "img"
    return [p for p in sorted(carpeta.glob("servicio-*")) if p.is_file() and p.suffix.lower() in EXTENSIONES]


def validar_imagen(archivo):
    nombre = secure_filename(archivo.filename or "")
    extension = Path(nombre).suffix
    nombre = Path(nombre).stem[:150-len(extension)] + extension
    formato_esperado = EXTENSIONES.get(Path(nombre).suffix.lower())
    if not formato_esperado:
        raise ValueError("Solo se permiten JPG, JPEG, PNG o WEBP.")
    contenido = archivo.stream.read(MAX_BYTES + 1)
    if len(contenido) > MAX_BYTES:
        raise ValueError("La imagen no puede superar 2 MB.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(contenido)) as img:
                formato = img.format
                if formato != formato_esperado or formato not in FORMATOS:
                    raise ValueError("El contenido no coincide con el formato JPG, PNG o WEBP indicado.")
                if img.width * img.height > MAX_PIXELS:
                    raise ValueError("La imagen supera el límite de 20 megapíxeles.")
                if getattr(img, "n_frames", 1) != 1:
                    raise ValueError("Selecciona una imagen sin animación.")
                img.verify()
            with Image.open(BytesIO(contenido)) as img:
                img.load()
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        raise ValueError("El archivo no contiene una imagen válida.") from error
    return nombre, FORMATOS[formato], contenido, sha256(contenido).hexdigest()


def opciones_imagenes(root, obtener_conexion):
    opciones = [(p.name, p.name) for p in imagenes_estaticas(root)]
    conn = obtener_conexion()
    try:
        with conn.cursor() as c:
            c.execute("SELECT id_imagen,nombre FROM imagenes_servicio WHERE activa=TRUE ORDER BY fecha_creacion DESC,id_imagen DESC")
            opciones += [(f"bd:{ident}", nombre) for ident, nombre in c.fetchall()]
    finally:
        conn.close()
    return opciones


def resolver_imagen(cursor, seleccion, anterior="servicio-1.jpg"):
    """Bloquear hasta guardar el servicio impide un borrado concurrente."""
    if seleccion.startswith("bd:"):
        ident = int(seleccion[3:])
        cursor.execute("SELECT id_imagen FROM imagenes_servicio WHERE id_imagen=%s AND activa=TRUE FOR KEY SHARE", (ident,))
        if not cursor.fetchone():
            raise ValueError("La imagen ya no está disponible. Selecciona otra.")
        return anterior, ident
    return seleccion, None


def registrar_biblioteca(app, admin_required, obtener_conexion):
    def item_db(row):
        return dict(id=row["id_imagen"], valor=f"bd:{row['id_imagen']}", nombre=row["nombre"],
                    tipo=row["mime_type"], tamano=row["tamano_bytes"], fecha=row["fecha_creacion"].isoformat(),
                    url=url_for("imagen_servicio", id=row["id_imagen"]), usos=row.get("usos", 0),
                    eliminar_url=url_for("eliminar_imagen_servicio", id=row["id_imagen"]))

    @app.get("/imagenes-servicio/biblioteca")
    @admin_required
    def biblioteca_imagenes():
        conn = obtener_conexion()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as c:
                c.execute("""SELECT i.id_imagen,i.nombre,i.mime_type,i.tamano_bytes,i.fecha_creacion,
                          (SELECT count(*) FROM servicios s WHERE s.id_imagen=i.id_imagen) AS usos
                          FROM imagenes_servicio i WHERE i.activa=TRUE ORDER BY i.fecha_creacion DESC,i.id_imagen DESC""")
                items = [item_db(r) for r in c.fetchall()]
        finally:
            conn.close()
        items += [dict(id=None, valor=p.name, nombre=p.name, tipo=FORMATOS[EXTENSIONES[p.suffix.lower()]],
                       tamano=p.stat().st_size, fecha=None, url=url_for("static", filename="img/"+p.name), usos=None,
                       eliminar_url=None) for p in imagenes_estaticas(app.root_path)]
        response = jsonify(imagenes=items)
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.post("/imagenes-servicio/subir")
    @admin_required
    def subir_imagen_servicio():
        request.max_content_length = MAX_BYTES + 64 * 1024
        try:
            form = ImagenServicioForm()
            if not form.validate_on_submit():
                return jsonify(error=" ".join(str(e) for errors in form.errors.values() for e in errors)), 400
            nombre, mime, contenido, digest = validar_imagen(form.archivo.data)
        except RequestEntityTooLarge:
            return jsonify(error="La imagen no puede superar 2 MB."), 413
        except ValueError as error:
            return jsonify(error=str(error)), 400
        conn = obtener_conexion()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as c:
                c.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (digest,))
                c.execute("SELECT id_imagen FROM imagenes_servicio WHERE hash_sha256=%s", (digest,))
                existente = c.fetchone()
                c.execute("""INSERT INTO imagenes_servicio (nombre,mime_type,contenido,tamano_bytes,hash_sha256)
                             VALUES (%s,%s,%s,%s,%s)
                             ON CONFLICT (hash_sha256) DO UPDATE SET activa=TRUE
                             RETURNING id_imagen,nombre,mime_type,tamano_bytes,fecha_creacion""",
                          (nombre, mime, contenido, len(contenido), digest))
                item = item_db(c.fetchone())
            conn.commit()
        finally:
            conn.close()
        return jsonify(imagen=item, reutilizada=bool(existente)), 200 if existente else 201

    @app.get("/imagenes-servicio/<int:id>")
    def imagen_servicio(id):
        conn = obtener_conexion()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as c:
                c.execute("SELECT contenido,mime_type,hash_sha256,fecha_creacion FROM imagenes_servicio WHERE id_imagen=%s AND activa=TRUE", (id,))
                row = c.fetchone()
        finally:
            conn.close()
        if not row:
            abort(404)
        response = send_file(BytesIO(bytes(row["contenido"])), mimetype=row["mime_type"],
                             etag=row["hash_sha256"] or False, last_modified=row["fecha_creacion"],
                             conditional=True, max_age=3600)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = "default-src 'none'; sandbox"
        return response

    @app.post("/imagenes-servicio/<int:id>/eliminar")
    @admin_required
    def eliminar_imagen_servicio(id):
        form = EliminarForm()
        if not form.validate_on_submit():
            return jsonify(error="La sesión del formulario venció. Recarga la página."), 400
        conn = obtener_conexion()
        try:
            with conn.cursor() as c:
                c.execute("SELECT id_imagen FROM imagenes_servicio WHERE id_imagen=%s FOR UPDATE", (id,))
                if not c.fetchone():
                    abort(404)
                c.execute("SELECT count(*) FROM servicios WHERE id_imagen=%s", (id,))
                usos = c.fetchone()[0]
                if usos:
                    return jsonify(error=f"Esta imagen está siendo utilizada por {usos} servicio(s) y no puede eliminarse."), 409
                c.execute("DELETE FROM imagenes_servicio WHERE id_imagen=%s", (id,))
            conn.commit()
        finally:
            conn.close()
        return jsonify(eliminada=True)
