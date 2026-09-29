"""Pagos independientes del flujo técnico, importes del servidor y BYTEA privado."""

from io import BytesIO
from pathlib import Path
from decimal import Decimal
import warnings
from PIL import Image
from pypdf import PdfReader
from flask import abort, request, render_template, redirect, url_for, flash, send_file
from flask_login import current_user, login_required
from psycopg2.extras import RealDictCursor
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
from forms.pagos_form import ComprobanteForm, DecisionPagoForm
from finanzas import importes

MAX_COMPROBANTE = 5 * 1024 * 1024


def validar_comprobante(archivo):
    nombre = secure_filename(archivo.filename or "")
    ext = Path(nombre).suffix.lower()
    nombre = Path(nombre).stem[:140] + ext
    data = archivo.stream.read(MAX_COMPROBANTE + 1)
    if not data or len(data) > MAX_COMPROBANTE:
        raise ValueError("El comprobante debe tener contenido y no superar 5 MB.")
    try:
        if ext == ".pdf":
            if not data.startswith(b"%PDF-"):
                raise ValueError()
            reader = PdfReader(BytesIO(data), strict=True)
            if reader.is_encrypted or not 1 <= len(reader.pages) <= 20:
                raise ValueError()
            root = reader.trailer["/Root"]
            names = root.get("/Names", {})
            if hasattr(names, "get_object"):
                names = names.get_object()
            if any(k in root for k in ("/OpenAction", "/AA")) or any(
                k in names for k in ("/JavaScript", "/EmbeddedFiles")
            ):
                raise ValueError()
            for page in reader.pages:
                if "/AA" in page:
                    raise ValueError()
                for annotation in page.get("/Annots", []):
                    obj = annotation.get_object()
                    if "/A" in obj or "/AA" in obj or "/FS" in obj:
                        raise ValueError()
            mime = "application/pdf"
        elif ext in (".jpg", ".jpeg", ".png"):
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(BytesIO(data)) as img:
                    expected = "PNG" if ext == ".png" else "JPEG"
                    if (
                        img.format != expected
                        or img.width * img.height > 20_000_000
                        or getattr(img, "n_frames", 1) != 1
                    ):
                        raise ValueError()
                    img.verify()
                with Image.open(BytesIO(data)) as img:
                    img.load()
            mime = "image/png" if ext == ".png" else "image/jpeg"
        else:
            raise ValueError()
    except Exception as error:
        raise ValueError(
            "Comprobante inválido: usa JPG, PNG o PDF legible, sin contraseña ni acciones, de hasta 20 páginas."
        ) from error
    return nombre, mime, data


def resumen_pago(cursor, pedido):
    cursor.execute(
        """SELECT id_pago,tipo_pago,monto,estado,nombre_archivo,(contenido IS NOT NULL) AS tiene_comprobante,
                      fecha_subida,fecha_confirmacion,
                      id_usuario_confirma,motivo_rechazo,migracion_historica FROM pagos
                      WHERE id_pedido=%s ORDER BY id_pago DESC""",
        (pedido["id_pedido"],),
    )
    pagos = cursor.fetchall()
    anticipo = sum(
        (
            r["monto"]
            for r in pagos
            if r["estado"] == "Confirmado" and r["tipo_pago"] == "anticipo"
        ),
        Decimal("0"),
    )
    saldo = sum(
        (
            r["monto"]
            for r in pagos
            if r["estado"] == "Confirmado" and r["tipo_pago"] == "saldo"
        ),
        Decimal("0"),
    )
    pago_total = sum(
        (
            r["monto"]
            for r in pagos
            if r["estado"] == "Confirmado" and r["tipo_pago"] == "total"
        ),
        Decimal("0"),
    )
    total = pedido.get("total")
    pagado = anticipo + saldo + pago_total
    anti_ok = total is not None and pagado >= pedido["anticipo_requerido"]
    completo = total is not None and pagado >= total
    estado = (
        "Pago completo"
        if completo
        else (
            "Comprobante enviado"
            if any(r["estado"] == "Pendiente" for r in pagos)
            else (
                "Rechazado"
                if pagos and pagos[0]["estado"] == "Rechazado"
                else (
                    "Saldo pendiente"
                    if anti_ok and pedido["estado"] == "Listo"
                    else "Anticipo confirmado" if anti_ok else "Sin anticipo"
                )
            )
        )
    )
    tipos = []
    if (
        total is not None
        and (pedido.get('porcentaje_descuento') is None or pedido.get('anticipo_solicitado'))
        and not completo
        and pedido["estado"] not in ("Cancelado", "Entregado")
    ):
        pendiente = any(r["estado"] == "Pendiente" for r in pagos)
        if not pendiente:
            if anti_ok:
                if pedido["estado"] == "Listo":
                    tipos = ["saldo"]
            else:
                tipos = ["anticipo", "total"]
    return dict(
        pagos=pagos,
        estado=estado,
        anticipo_confirmado=anti_ok,
        pago_completo=completo,
        anticipo_pagado=anticipo,
        saldo_pagado=saldo + pago_total,
        tipo_disponible=tipos,
        saldo_pendiente=(
            max(total - pagado, Decimal("0")) if total is not None else None
        ),
    )


def solicitar_anticipo(cursor, ident, tarifa):
    cursor.execute(
        """SELECT p.*,s.precio FROM pedidos p LEFT JOIN servicios s ON s.id_servicio=p.id_servicio
                      WHERE p.id_pedido=%s FOR UPDATE OF p""",
        (ident,),
    )
    pedido = cursor.fetchone()
    if not pedido:
        abort(404)
    if pedido["estado"] not in ("En revisión", "En reparación", "Listo"):
        raise ValueError("El anticipo se solicita después de iniciar la revisión.")
    if pedido["total"] is not None:
        if not pedido['anticipo_solicitado']:
            cursor.execute('''UPDATE pedidos SET anticipo_solicitado=TRUE, pago_solicitado_por=%s,
                              fecha_solicitud_pago=CURRENT_TIMESTAMP, fecha_actualizacion=CURRENT_TIMESTAMP
                              WHERE id_pedido=%s''', (current_user.id, ident))
        return
    if pedido["precio"] is None:
        raise ValueError("El servicio no tiene un precio disponible.")
    # Pedidos antiguos sin cotización: conservar el flujo previo, sin aplicarles
    # promociones nuevas. Los pedidos nuevos ya traen todos sus importes.
    valores = importes(pedido["precio"], tarifa)
    cursor.execute(
        """UPDATE pedidos SET subtotal=%s,porcentaje_iva=%s,valor_iva=%s,total=%s,
                   anticipo_requerido=%s,saldo_requerido=%s,anticipo_solicitado=TRUE,
                   pago_solicitado_por=%s,fecha_solicitud_pago=CURRENT_TIMESTAMP,
                   fecha_actualizacion=CURRENT_TIMESTAMP WHERE id_pedido=%s""",
        tuple(
            valores[k]
            for k in (
                "subtotal",
                "porcentaje_iva",
                "valor_iva",
                "total",
                "anticipo_requerido",
                "saldo_requerido",
            )
        )
        + (
            current_user.id,
            ident,
        ),
    )


def registrar_rutas_pagos(app, admin_required, cliente_required, conectar):
    def pedido_propio(c, ident, bloquear=False):
        c.execute(
            "SELECT * FROM pedidos WHERE id_pedido=%s AND (%s OR id_usuario=%s)"
            + (" FOR UPDATE" if bloquear else ""),
            (ident, current_user.rol == "admin", current_user.id),
        )
        pedido = c.fetchone()
        if not pedido:
            abort(404)
        return pedido

    @app.get("/pedidos/<int:id>/pagos")
    @login_required
    def ver_pagos(id):
        conn = conectar()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as c:
                pedido = pedido_propio(c, id)
                resumen = resumen_pago(c, pedido)
        finally:
            conn.close()
        banco = {
            k: app.config.get(k, "")
            for k in (
                "PAYMENT_BANK",
                "PAYMENT_ACCOUNT_TYPE",
                "PAYMENT_ACCOUNT_NUMBER",
                "PAYMENT_ACCOUNT_HOLDER",
            )
        }
        return render_template(
            (
                "components/pagos_pedido.html"
                if request.args.get("modal") == "1"
                else "pagos_pedido.html"
            ),
            pedido=pedido,
            resumen=resumen,
            banco=banco,
            comprobante_form=ComprobanteForm(),
            decision_form=DecisionPagoForm(),
        )

    @app.post("/pedidos/<int:id>/comprobantes")
    @cliente_required
    def subir_comprobante(id):
        request.max_content_length = MAX_COMPROBANTE + 65536
        try:
            form = ComprobanteForm()
            if not form.validate_on_submit():
                abort(400)
            nombre, mime, data = validar_comprobante(form.archivo.data)
        except RequestEntityTooLarge:
            abort(413)
        except ValueError as error:
            flash(str(error), "danger")
            return redirect(url_for("ver_pagos", id=id))
        conn = conectar()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as c:
                pedido = pedido_propio(c, id, True)
                resumen = resumen_pago(c, pedido)
                if form.tipo_pago.data not in resumen["tipo_disponible"]:
                    abort(409)
                monto = {
                    "anticipo": pedido["anticipo_requerido"],
                    "saldo": pedido["saldo_requerido"],
                    "total": pedido["total"],
                }[form.tipo_pago.data]
                c.execute(
                    """INSERT INTO pagos(id_pedido,tipo_pago,monto,nombre_archivo,mime_type,contenido)
                             VALUES (%s,%s,%s,%s,%s,%s)""",
                    (id, form.tipo_pago.data, monto, nombre, mime, data),
                )
            conn.commit()
        finally:
            conn.close()
        flash("Comprobante recibido — pendiente de verificación", "success")
        return redirect(url_for("ver_pagos", id=id))

    @app.post("/pagos/<int:id>/decision")
    @admin_required
    def decidir_pago(id):
        form = DecisionPagoForm()
        if not form.validate_on_submit():
            abort(400)
        conn = conectar()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as c:
                c.execute("SELECT id_pedido FROM pagos WHERE id_pago=%s", (id,))
                fila = c.fetchone()
                if not fila:
                    abort(404)
                pedido = pedido_propio(c, fila["id_pedido"], True)
                c.execute("SELECT * FROM pagos WHERE id_pago=%s FOR UPDATE", (id,))
                pago = c.fetchone()
                if pago["estado"] != "Pendiente" or pedido["estado"] in (
                    "Cancelado",
                    "Entregado",
                ):
                    abort(409)
                esperado = {
                    "anticipo": pedido["anticipo_requerido"],
                    "saldo": pedido["saldo_requerido"],
                    "total": pedido["total"],
                }[pago["tipo_pago"]]
                if pago["monto"] != esperado:
                    abort(409)
                c.execute(
                    """UPDATE pagos SET estado=%s,fecha_confirmacion=CURRENT_TIMESTAMP,
                             id_usuario_confirma=%s,motivo_rechazo=%s WHERE id_pago=%s""",
                    (
                        form.decision.data,
                        current_user.id,
                        (
                            form.motivo.data.strip()
                            if form.decision.data == "Rechazado"
                            else None
                        ),
                        id,
                    ),
                )
                if (
                    pago["tipo_pago"] in ("anticipo", "total")
                    and form.decision.data == "Confirmado"
                ):
                    c.execute(
                        "UPDATE pedidos SET anticipo_pagado=TRUE WHERE id_pedido=%s",
                        (pedido["id_pedido"],),
                    )
            conn.commit()
        finally:
            conn.close()
        flash("Decisión de pago registrada en auditoría.", "success")
        return redirect(url_for("pedidos_admin"))

    @app.get("/pagos/<int:id>/comprobante")
    @login_required
    def ver_comprobante(id):
        conn = conectar()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as c:
                c.execute(
                    """SELECT pg.nombre_archivo,pg.mime_type,pg.contenido FROM pagos pg
                             JOIN pedidos p ON p.id_pedido=pg.id_pedido
                             WHERE pg.id_pago=%s AND (%s OR p.id_usuario=%s)""",
                    (id, current_user.rol == "admin", current_user.id),
                )
                row = c.fetchone()
                if not row:
                    abort(404)
        finally:
            conn.close()
        response = send_file(
            BytesIO(bytes(row["contenido"])),
            mimetype=row["mime_type"],
            download_name=row["nombre_archivo"],
            as_attachment=True,
        )
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = "default-src 'none'; sandbox"
        return response

    @app.get("/pagos/<int:id>/recibo-anticipo")
    @login_required
    def recibo_anticipo(id):
        conn = conectar()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as c:
                c.execute(
                    """SELECT pg.id_pago,pg.monto,pg.fecha_confirmacion,p.id_pedido,p.total,
                             p.anticipo_requerido,p.equipo,p.modelo,
                             COALESCE(s.nombre,'Servicio no disponible') AS servicio,
                             COALESCE(NULLIF(BTRIM(CONCAT_WS(' ',pu.nombres,pu.apellidos)),''),u.usuario) AS cliente
                             FROM pagos pg JOIN pedidos p ON p.id_pedido=pg.id_pedido
                             JOIN usuarios u ON u.id_usuario=p.id_usuario
                             LEFT JOIN perfiles_usuario pu ON pu.id_usuario=u.id_usuario
                             LEFT JOIN servicios s ON s.id_servicio=p.id_servicio
                             WHERE pg.id_pago=%s AND pg.tipo_pago='anticipo' AND pg.estado='Confirmado'
                             AND NOT pg.migracion_historica AND (%s OR p.id_usuario=%s)""",
                    (id, current_user.rol == "admin", current_user.id),
                )
                recibo = c.fetchone()
                if not recibo:
                    abort(404)
        finally:
            conn.close()
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table
        from xml.sax.saxutils import escape

        buffer = BytesIO()
        documento = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            leftMargin=inch,
            rightMargin=inch,
            topMargin=inch,
            bottomMargin=inch,
        )
        styles = getSampleStyleSheet()
        contenido = [Paragraph("RECIBO DE ANTICIPO", styles["Title"]), Spacer(1, 18)]
        datos = [
            ("Pedido", str(recibo["id_pedido"])),
            ("Cliente", recibo["cliente"]),
            ("Servicio", recibo["servicio"]),
            ("Equipo", recibo["equipo"]),
            ("Modelo", recibo["modelo"] or "No especificado"),
            ("Total con IVA", f"${recibo['total']:.2f}"),
            ("Monto recibido", f"${recibo['monto']:.2f}"),
            ("Porcentaje pagado", f"{recibo['monto'] / recibo['total'] * 100:.2f} %"),
            (
                "Saldo pendiente",
                f"${max(recibo['total']-recibo['monto'], Decimal('0')):.2f}",
            ),
            ("Fecha", recibo["fecha_confirmacion"].strftime("%d/%m/%Y %H:%M")),
            ("Forma de pago", "Transferencia bancaria"),
        ]
        contenido.append(
            Table(
                [
                    [
                        Paragraph(f"<b>{escape(k)}</b>", styles["Normal"]),
                        Paragraph(escape(v), styles["Normal"]),
                    ]
                    for k, v in datos
                ],
                colWidths=[2 * inch, 4 * inch],
                hAlign="LEFT",
            )
        )
        documento.build(contenido)
        buffer.seek(0)
        response = send_file(
            buffer,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=f"recibo-anticipo-pedido-{recibo['id_pedido']}.pdf",
        )
        response.headers["Cache-Control"] = "private, no-store"
        return response
