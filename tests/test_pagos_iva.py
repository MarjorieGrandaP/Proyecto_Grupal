"""Flujo real de anticipos/saldo, IVA histórico y comprobantes privados (rollback)."""

from decimal import Decimal
from io import BytesIO
from pathlib import Path
import unittest
from unittest.mock import patch
from PIL import Image
from pypdf import PdfReader
from reportlab.pdfgen.canvas import Canvas
from werkzeug.datastructures import MultiDict
from flask import Flask
import test_facturacion_pedidos as base
from test_correcciones import web
from pagos_utils import confirmar_pago
from finanzas import importes, IVA_PREDETERMINADO, validar_tarifa
from forms.producto_form import ProductoForm


class DuracionIva(unittest.TestCase):
    def test_cantidades_unidades_variable_y_limites(self):
        app = Flask(__name__)
        app.config.update(SECRET_KEY="prueba", WTF_CSRF_ENABLED=False)
        with app.test_request_context():
            for cantidad, unidad, valid in [
                ("30", "Minutos", True),
                ("1.5", "Horas", True),
                ("2", "Días", True),
                ("1", "Semanas", True),
                ("", "Variable", True),
                ("texto", "Variable", True),
                ("", "Horas", False),
                ("0", "Horas", False),
                ("-1", "Días", False),
                ("NaN", "Horas", False),
                ("2", "Inventada", False),
            ]:
                with self.subTest(cantidad=cantidad, unidad=unidad):
                    form = ProductoForm(
                        MultiDict(
                            dict(
                                nombre="Servicio prueba",
                                descripcion="Descripción de servicio",
                                precio="10",
                                duracion_cantidad=cantidad,
                                duracion_unidad=unidad,
                                imagen="servicio-1.jpg",
                                id_proveedor="0",
                                requiere_entrega_equipo="si",
                            )
                        )
                    )
                    form.imagen.choices = [("servicio-1.jpg", "Imagen")]
                    form.id_proveedor.choices = [(0, "Ninguno")]
                    self.assertEqual(form.validate(), valid, form.errors)

    def test_monedas_y_configuracion(self):
        v = importes("100", IVA_PREDETERMINADO)
        self.assertEqual(
            (
                v["subtotal"],
                v["valor_iva"],
                v["total"],
                v["anticipo_requerido"],
                v["saldo_requerido"],
            ),
            tuple(map(Decimal, ("100", "15", "115", "57.50", "57.50"))),
        )
        v = importes("25.50", IVA_PREDETERMINADO)
        self.assertEqual(v["anticipo_requerido"] + v["saldo_requerido"], v["total"])
        self.assertEqual(v["total"], Decimal("29.33"))
        for rate in ("-1", "NaN", "Infinity", "1.1"):
            with self.assertRaises(ValueError):
                validar_tarifa(rate)


class PagosIva(unittest.TestCase):
    setUp = base.FacturacionPedidos.setUp
    tearDown = base.FacturacionPedidos.tearDown
    query = base.FacturacionPedidos.query
    login = base.FacturacionPedidos.login
    emit = base.FacturacionPedidos.emit
    invoices = base.FacturacionPedidos.invoices

    def estado(self):
        return self.query(
            "SELECT estado FROM pedidos WHERE id_pedido=%s", (self.order,)
        )[0][0]

    def change(self, estado):
        self.login(self.admin)
        return self.client.post(
            f"/pedidos/{self.order}/estado", data={"estado": estado}
        )

    def preparar(self):
        self.query(
            "UPDATE pedidos SET estado='Solicitado' WHERE id_pedido=%s RETURNING id_pedido",
            (self.order,),
        )
        self.change("En revisión")
        self.assertEqual(self.estado(), "En revisión")
        self.assertEqual(
            self.client.post(
                f"/pedidos/{self.order}/anticipo",
                data={"solicitado": "y", "pagado": "y"},
            ).status_code,
            302,
        )

    def subir(self, tipo="anticipo", data=None, name="recibo.png", **extra):
        self.login(self.customer)
        if data is None:
            out = BytesIO()
            Image.new("RGB", (4, 4), "green").save(out, format="PNG")
            data = out.getvalue()
        response = self.client.post(
            f"/pedidos/{self.order}/comprobantes",
            data={
                "tipo_pago": tipo,
                "monto": "0.01",
                "estado": "Confirmado",
                "archivo": (BytesIO(data), name),
                **extra,
            },
            content_type="multipart/form-data",
        )
        response.request.input_stream.close()
        return response

    def ultimo(self):
        return self.query(
            "SELECT id_pago FROM pagos WHERE id_pedido=%s ORDER BY id_pago DESC",
            (self.order,),
        )[0][0]

    def test_flujo_completo_con_bloqueos_y_auditoria(self):
        self.preparar()
        self.change("En reparación")
        self.assertEqual(self.estado(), "En revisión")
        self.subir()
        ident = self.ultimo()
        pago = self.query("SELECT estado,monto FROM pagos WHERE id_pago=%s", (ident,))[
            0
        ]
        self.assertEqual(pago, ("Pendiente", Decimal("14.67")))
        self.assertEqual(
            self.client.post(
                f"/pagos/{ident}/decision", data={"decision": "Confirmado"}
            ).status_code,
            403,
        )
        self.login(self.admin)
        self.assertEqual(
            self.client.post(
                f"/pagos/{ident}/decision",
                data={"decision": "Confirmado", "monto": "0.01"},
            ).status_code,
            302,
        )
        self.assertEqual(
            self.query(
                "SELECT estado,monto,id_usuario_confirma,fecha_confirmacion IS NOT NULL FROM pagos WHERE id_pago=%s",
                (ident,),
            ),
            [("Confirmado", Decimal("14.67"), self.admin, True)],
        )
        recibo = self.client.get(f"/pagos/{ident}/recibo-anticipo")
        recibo_text = "".join(
            p.extract_text() for p in PdfReader(BytesIO(recibo.data)).pages
        )
        self.assertIn("RECIBO DE ANTICIPO", recibo_text)
        self.assertIn("$14.67", recibo_text)
        self.assertNotIn("FACTURA", recibo_text)
        self.change("En reparación")
        self.assertEqual(self.estado(), "En reparación")
        self.change("Listo")
        self.assertEqual(self.estado(), "Listo")
        self.change("Entregado")
        self.assertEqual(self.estado(), "Listo")
        self.login(self.customer)
        self.assertIn(
            "Saldo pendiente",
            self.client.get(f"/pedidos/{self.order}/pagos").get_data(as_text=True),
        )
        confirmar_pago(self, "saldo")
        self.change("Entregado")
        self.assertEqual(self.estado(), "Entregado")
        self.emit()
        self.assertEqual(
            self.query(
                "SELECT subtotal,porcentaje_iva,valor_iva,total,estado FROM facturas WHERE id_pedido=%s",
                (self.order,),
            ),
            [
                (
                    Decimal("25.50"),
                    Decimal("0.15"),
                    Decimal("3.83"),
                    Decimal("29.33"),
                    "Pagada",
                )
            ],
        )
        rows = self.query(
            "SELECT datos_nuevos FROM auditoria WHERE tabla='pagos' AND operacion='UPDATE'"
        )
        self.assertTrue(
            any(row[0]["id_usuario_confirma"] == self.admin for row in rows)
        )
        self.assertTrue(all("contenido" not in row[0] for row in rows))
        self.assertEqual(
            self.client.post(
                f"/pagos/{ident}/decision",
                data={"decision": "Rechazado", "motivo": "No"},
            ).status_code,
            409,
        )

    def test_rechazo_motivo_reintento_sin_borrar(self):
        self.preparar()
        self.subir()
        ident = self.ultimo()
        self.login(self.admin)
        for motivo in ("", "   "):
            self.assertEqual(
                self.client.post(
                    f"/pagos/{ident}/decision",
                    data={"decision": "Rechazado", "motivo": motivo},
                ).status_code,
                400,
            )
        self.assertEqual(
            self.client.post(
                f"/pagos/{ident}/decision",
                data={
                    "decision": "Rechazado",
                    "motivo": "No se identifica la transferencia",
                },
            ).status_code,
            302,
        )
        self.login(self.customer)
        html = self.client.get(f"/pedidos/{self.order}/pagos").get_data(as_text=True)
        self.assertIn("No se identifica la transferencia", html)
        self.assertIn("Enviar comprobante", html)
        self.subir()
        self.assertNotEqual(self.ultimo(), ident)
        self.assertEqual(
            self.query(
                "SELECT estado FROM pagos WHERE id_pedido=%s ORDER BY id_pago",
                (self.order,),
            ),
            [("Rechazado",), ("Pendiente",)],
        )
        self.assertEqual(self.subir().status_code, 409)

    def test_pdf_jpg_validos_falsos_grandes_y_propiedad(self):
        self.preparar()
        for name, data in [
            ("falso.pdf", b"%PDF-falso"),
            ("falso.jpg", b"texto"),
            ("grande.png", b"x" * (5 * 1024 * 1024 + 1)),
        ]:
            response = self.subir(data=data, name=name)
            self.assertIn(response.status_code, (302, 413))
            self.assertEqual(
                self.query(
                    "SELECT count(*) FROM pagos WHERE id_pedido=%s", (self.order,)
                ),
                [(0,)],
            )
        out = BytesIO()
        canvas = Canvas(out)
        canvas.drawString(50, 700, "Comprobante de prueba")
        canvas.save()
        self.assertEqual(
            self.subir(data=out.getvalue(), name="recibo.pdf").status_code, 302
        )
        ident = self.ultimo()
        response = self.client.get(f"/pagos/{ident}/comprobante")
        self.assertEqual(response.mimetype, "application/pdf")
        self.assertEqual(response.data, out.getvalue())
        self.assertIn("no-store", response.headers["Cache-Control"])
        self.query(
            "UPDATE pedidos SET id_usuario=%s WHERE id_pedido=%s RETURNING id_pedido",
            (self.admin, self.order),
        )
        for url in (f"/pagos/{ident}/comprobante", f"/pedidos/{self.order}/pagos"):
            self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.subir().status_code, 404)

    def test_montos_iva_congelados_aun_si_cambia_tarifa_servicio(self):
        self.preparar()
        before = self.query(
            "SELECT subtotal,porcentaje_iva,valor_iva,total FROM pedidos WHERE id_pedido=%s",
            (self.order,),
        )
        self.query(
            "UPDATE servicios SET precio=100 WHERE id_servicio=%s RETURNING id_servicio",
            (self.service,),
        )
        with patch.dict(web.app.config, IVA_RATE=Decimal("0.20")):
            self.client.post(
                f"/pedidos/{self.order}/anticipo", data={"solicitado": "y"}
            )
            self.assertEqual(
                self.query(
                    "SELECT subtotal,porcentaje_iva,valor_iva,total FROM pedidos WHERE id_pedido=%s",
                    (self.order,),
                ),
                before,
            )
            confirmar_pago(self)
            self.change("En reparación")
            self.change("Listo")
            confirmar_pago(self, "saldo")
            self.change("Entregado")
            self.emit()
        invoice = self.invoices()[0][0]
        with patch.dict(web.app.config, IVA_RATE=Decimal("0.05")):
            pdf = self.client.get(f"/facturas/{invoice}/pdf").data
            text = "".join(p.extract_text() for p in PdfReader(BytesIO(pdf)).pages)
            self.assertIn("IVA (15 %)", text)
            self.assertIn("$29.33", text)
            self.assertNotIn("20 %", text)
        self.assertEqual(
            self.query(
                "SELECT subtotal,porcentaje_iva,valor_iva,total FROM facturas WHERE id_factura=%s",
                (invoice,),
            ),
            before,
        )

    def test_facturas_historicas_iva_pago_y_migracion_idempotente(self):
        self.emit()
        ident = self.invoices()[0][0]
        self.query(
            "DELETE FROM pagos WHERE id_pedido=%s RETURNING id_pago", (self.order,)
        )
        self.query(
            "UPDATE facturas SET subtotal=NULL,porcentaje_iva=NULL,valor_iva=NULL,total=15.00,estado='Pendiente' WHERE id_factura=%s RETURNING id_factura",
            (ident,),
        )
        self.query(
            "INSERT INTO facturas(numero,id_servicio,fecha,total,estado) VALUES ('FAC-HIST-20-PRUEBA',%s,CURRENT_DATE,20.00,'Pendiente') RETURNING id_factura",
            (self.service,),
        )
        migration = Path("sql/migracion_facturas_historicas.sql").read_text(
            encoding="utf-8"
        )
        with self.conn.cursor() as c:
            c.execute(
                "DELETE FROM pcfix_migraciones WHERE nombre='facturas_historicas_iva_15'"
            )
            c.execute(migration)
            c.execute(migration)
        self.assertEqual(
            self.query(
                "SELECT subtotal,porcentaje_iva,valor_iva,total,estado FROM facturas WHERE numero='FAC-HIST-20-PRUEBA' OR id_factura=%s ORDER BY subtotal",
                (ident,),
            ),
            [
                (
                    Decimal("15.00"),
                    Decimal("0.15"),
                    Decimal("2.25"),
                    Decimal("17.25"),
                    "Pagada",
                ),
                (
                    Decimal("20.00"),
                    Decimal("0.15"),
                    Decimal("3.00"),
                    Decimal("23.00"),
                    "Pagada",
                ),
            ],
        )
        self.assertEqual(
            self.query(
                "SELECT tipo_pago,monto,estado,nombre_archivo,mime_type,contenido,migracion_historica FROM pagos WHERE id_pedido=%s",
                (self.order,),
            ),
            [("total", Decimal("17.25"), "Confirmado", None, None, None, True)],
        )
        self.assertEqual(
            self.query(
                "SELECT count(*) FROM pagos WHERE id_pedido=%s AND migracion_historica",
                (self.order,),
            ),
            [(1,)],
        )
        text = "".join(
            p.extract_text()
            for p in PdfReader(
                BytesIO(self.client.get(f"/facturas/{ident}/pdf").data)
            ).pages
        )
        self.assertIn("IVA (15 %)", text)
        self.assertIn("$17.25", text)
        self.assertIn("PAGADO", text)

    def test_pago_total_no_pide_segundo_pago_y_emite_factura_pagada(self):
        self.preparar()
        self.assertEqual(self.subir("total").status_code, 302)
        ident = self.ultimo()
        self.assertEqual(
            self.query("SELECT monto FROM pagos WHERE id_pago=%s", (ident,)),
            [(Decimal("29.33"),)],
        )
        self.login(self.admin)
        self.assertEqual(
            self.client.post(
                f"/pagos/{ident}/decision", data={"decision": "Confirmado"}
            ).status_code,
            302,
        )
        self.change("En reparación")
        self.login(self.customer)
        html = self.client.get(f"/pedidos/{self.order}/pagos").get_data(as_text=True)
        self.assertIn("Pago completo", html)
        self.assertNotIn("Pagar saldo restante", html)
        self.login(self.admin)
        self.emit()
        self.assertEqual(
            self.query(
                "SELECT estado,total FROM facturas WHERE id_pedido=%s", (self.order,)
            ),
            [("Pagada", Decimal("29.33"))],
        )

    def test_csrf_y_solicitud_banco_solo_cuando_corresponde(self):
        self.query(
            "UPDATE pedidos SET estado='Solicitado' WHERE id_pedido=%s RETURNING id_pedido",
            (self.order,),
        )
        with patch.dict(
            web.app.config,
            PAYMENT_BANK="Banco de prueba",
            PAYMENT_ACCOUNT_TYPE="Ahorros",
            PAYMENT_ACCOUNT_NUMBER="999",
            PAYMENT_ACCOUNT_HOLDER="PC Fix",
        ):
            self.login(self.customer)
            self.assertNotIn(
                "Banco de prueba",
                self.client.get(f"/pedidos/{self.order}/pagos").get_data(as_text=True),
            )
            self.assertEqual(self.subir().status_code, 409)
            self.preparar()
            self.login(self.customer)
            html = self.client.get(f"/pedidos/{self.order}/pagos").get_data(
                as_text=True
            )
            self.assertIn("Banco de prueba", html)
            self.subir()
            ident = self.ultimo()
            web.app.config["WTF_CSRF_ENABLED"] = True
            self.assertEqual(self.subir().status_code, 400)
            self.login(self.admin)
            self.assertEqual(
                self.client.post(
                    f"/pagos/{ident}/decision", data={"decision": "Confirmado"}
                ).status_code,
                400,
            )

    def test_jpeg_saldo_anticipado_y_confirmacion_cancelado(self):
        self.preparar()
        out = BytesIO()
        Image.new("RGB", (4, 4), "yellow").save(out, format="JPEG")
        self.assertEqual(
            self.subir(data=out.getvalue(), name="recibo.jpg").status_code, 302
        )
        ident = self.ultimo()
        self.assertEqual(
            self.client.get(f"/pagos/{ident}/comprobante").mimetype, "image/jpeg"
        )
        self.assertEqual(self.subir("saldo").status_code, 409)
        self.login(self.admin)
        self.client.post(
            f"/pedidos/{self.order}/cancelar",
            data={"motivo": "Cliente solicitó cancelación"},
        )
        self.assertEqual(self.estado(), "Cancelado")
        self.assertEqual(
            self.client.post(
                f"/pagos/{ident}/decision", data={"decision": "Confirmado"}
            ).status_code,
            409,
        )
        self.assertEqual(
            self.query("SELECT count(*) FROM pagos WHERE id_pedido=%s", (self.order,)),
            [(1,)],
        )

    def test_centavo_sin_saldo_cero_y_solicitud_auditada(self):
        self.query(
            "UPDATE servicios SET precio=0.01 WHERE id_servicio=%s RETURNING id_servicio",
            (self.service,),
        )
        self.preparar()
        confirmar_pago(self)
        self.change("En reparación")
        self.change("Listo")
        self.login(self.customer)
        html = self.client.get(f"/pedidos/{self.order}/pagos").get_data(as_text=True)
        self.assertIn("Pago completo", html)
        self.assertNotIn("Enviar comprobante", html)
        self.assertEqual(
            self.query(
                "SELECT pago_solicitado_por,fecha_solicitud_pago IS NOT NULL FROM pedidos WHERE id_pedido=%s",
                (self.order,),
            ),
            [(self.admin, True)],
        )

    def test_migracion_estado_antiguo_preserva_historial(self):
        with self.conn.cursor() as c:
            c.execute("ALTER TABLE pedidos DROP CONSTRAINT pedidos_estado_check")
        self.query(
            "UPDATE pedidos SET estado='Pendiente de anticipo',anticipo_solicitado=TRUE WHERE id_pedido=%s RETURNING id_pedido",
            (self.order,),
        )
        before = self.query(
            "SELECT count(*) FROM historial_estado_pedidos WHERE id_pedido=%s",
            (self.order,),
        )[0][0]
        with self.conn.cursor() as c:
            c.execute(
                Path("sql/migracion_pagos_iva_duracion.sql").read_text(encoding="utf-8")
            )
        self.assertEqual(self.estado(), "En revisión")
        self.assertEqual(
            self.query(
                "SELECT count(*) FROM historial_estado_pedidos WHERE id_pedido=%s",
                (self.order,),
            )[0][0],
            before + 1,
        )
        self.assertEqual(
            self.query("SELECT total FROM pedidos WHERE id_pedido=%s", (self.order,)),
            [(None,)],
        )

    def test_servicio_duracion_estructurada_persistente(self):
        data = dict(
            nombre="Servicio estructurado",
            descripcion="Duración con unidades",
            precio="100",
            imagen="servicio-1.jpg",
            id_proveedor="0",
            requiere_entrega_equipo="si",
            duracion_cantidad="1.5",
            duracion_unidad="Horas",
        )
        self.assertEqual(
            self.client.post("/servicios/nuevo", data=data).status_code, 302
        )
        row = self.query(
            "SELECT id_servicio,duracion,duracion_cantidad,duracion_unidad FROM servicios WHERE nombre='Servicio estructurado'"
        )[0]
        self.assertEqual(row[1:], ("1.5 horas", Decimal("1.50"), "Horas"))
        self.assertEqual(
            self.client.post(
                f"/servicios/editar/{row[0]}",
                data={**data, "duracion_cantidad": "", "duracion_unidad": "Variable"},
            ).status_code,
            302,
        )
        self.assertEqual(
            self.query(
                "SELECT duracion,duracion_cantidad,duracion_unidad FROM servicios WHERE id_servicio=%s",
                (row[0],),
            ),
            [("Variable", None, "Variable")],
        )


if __name__ == "__main__":
    unittest.main()
