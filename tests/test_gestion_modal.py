"""Gestión administrativa y notas persistentes, con rollback de los datos."""

from pagos_utils import confirmar_pago
import unittest
import re
from decimal import Decimal
from pathlib import Path
import test_facturacion_pedidos as base
from test_correcciones import web
from forms.cancelacion_form import MOTIVOS_ADMIN, MOTIVOS_CLIENTE


class GestionModal(unittest.TestCase):
    setUp = base.FacturacionPedidos.setUp
    tearDown = base.FacturacionPedidos.tearDown
    query = base.FacturacionPedidos.query
    login = base.FacturacionPedidos.login
    emit = base.FacturacionPedidos.emit
    invoices = base.FacturacionPedidos.invoices

    def html(self):
        return self.client.get(
            "/pedidos", query_string={"q": str(self.order)}
        ).get_data(as_text=True)

    def test_tabla_limpia_modal_y_terminales(self):
        for estado in ("Entregado", "Cancelado"):
            self.query(
                "UPDATE pedidos SET estado=%s,modelo='T14 Gen 3' WHERE id_pedido=%s RETURNING id_pedido",
                (estado, self.order),
            )
            html = self.html()
            table = html.split("<table", 1)[1].split("</table>", 1)[0]
            self.assertNotIn("<form", table)
            self.assertNotIn("<select", table)
            self.assertEqual(table.count("<button"), 1)
            self.assertIn(f'data-bs-target="#gestionar-{self.order}"', table)
            self.assertIn(f'id="gestionar-{self.order}"', html)
            self.assertIn(f"Gestionar pedido #{self.order}", html)
            self.assertIn("Servicio original prueba", html)
            self.assertIn("T14 Gen 3", html)
            self.assertIn(f"/pedidos/{self.order}/equipo", html)
            self.assertIn("modal-dialog-scrollable", html)
            self.assertNotIn(f'id="estado-{self.order}"', html)
            self.assertNotIn(f"/pedidos/{self.order}/cancelar", html)
            if estado == "Cancelado":
                self.assertNotIn(f'id="form-emision-{self.order}"', html)

    def test_selector_transicion_y_anticipo(self):
        self.query(
            "UPDATE pedidos SET estado='En revisión',anticipo_solicitado=TRUE,anticipo_pagado=FALSE WHERE id_pedido=%s RETURNING id_pedido",
            (self.order,),
        )

        def options():
            html = self.html()
            select = re.search(
                r'<select id="estado-' + str(self.order) + r'".*?</select>', html, re.S
            ).group()
            return re.findall(r'<option\s+value="([^"]+)"', select)

        self.assertEqual(options(), ["En revisión"])
        confirmar_pago(self)
        self.assertEqual(
            self.query(
                "SELECT tipo_pago,monto,estado FROM pagos WHERE id_pedido=%s",
                (self.order,),
            ),
            [("anticipo", Decimal("14.67"), "Confirmado")],
        )
        with self.conn.cursor(cursor_factory=web.RealDictCursor) as cursor:
            cursor.execute("SELECT * FROM pedidos WHERE id_pedido=%s", (self.order,))
            resumen = web.resumen_pago(cursor, cursor.fetchone())
        self.assertTrue(resumen["anticipo_confirmado"], resumen)
        self.assertEqual(
            re.search(r"Pagos · ([^<]+)", self.html()).group(1), "Anticipo confirmado"
        )
        self.assertEqual(options(), ["En revisión", "En reparación"])
        self.client.post(
            f"/pedidos/{self.order}/estado", data={"estado": "En revisión"}
        )
        self.client.post(f"/pedidos/{self.order}/estado", data={"estado": "Solicitado"})
        self.assertEqual(
            self.query("SELECT estado FROM pedidos WHERE id_pedido=%s", (self.order,)),
            [("En revisión",)],
        )

    def test_notas_persisten_con_autor_auditoria_y_seguimiento(self):
        history = self.query(
            "SELECT * FROM historial_estado_pedidos WHERE id_pedido=%s", (self.order,)
        )
        url = f"/pedidos/{self.order}/observaciones"
        for texto in ("Primera nota", "Segunda nota <script>alert(1)</script>"):
            self.assertEqual(
                self.client.post(url, data={"texto": texto}).status_code, 302
            )
        rows = self.query(
            "SELECT texto,id_usuario_actor,fecha_hora IS NOT NULL FROM observaciones_pedidos WHERE id_pedido=%s ORDER BY id_observacion",
            (self.order,),
        )
        self.assertEqual(
            rows,
            [
                ("Primera nota", self.admin, True),
                ("Segunda nota <script>alert(1)</script>", self.admin, True),
            ],
        )
        self.assertEqual(
            self.query(
                "SELECT * FROM historial_estado_pedidos WHERE id_pedido=%s",
                (self.order,),
            ),
            history,
        )
        self.assertEqual(
            self.query(
                "SELECT count(*) FROM auditoria WHERE tabla='observaciones_pedidos' AND datos_nuevos->>'id_pedido'=%s",
                (str(self.order),),
            ),
            [(2,)],
        )
        for user in (self.admin, self.customer):
            self.login(user)
            html = self.client.get(
                f"/pedidos/{self.order}/seguimiento?modal=1"
            ).get_data(as_text=True)
            if user == self.admin:
                self.assertIn("Primera nota", html)
                self.assertIn("&lt;script&gt;", html)
            else:
                self.assertNotIn("Primera nota", html)
                self.assertNotIn("&lt;script&gt;", html)
            self.assertNotIn("<script>alert(1)</script>", html)
        other = self.query(
            "SELECT id_usuario FROM usuarios WHERE rol='cliente' AND id_usuario<>%s LIMIT 1",
            (self.customer,),
        )
        if other:
            self.login(other[0][0])
            self.assertEqual(
                self.client.get(
                    f"/pedidos/{self.order}/seguimiento?modal=1"
                ).status_code,
                404,
            )

    def test_observaciones_permisos_csrf_y_validacion(self):
        url = f"/pedidos/{self.order}/observaciones"
        for value in ("", "   ", "A" * 2001):
            self.client.post(url, data={"texto": value})
        self.login(self.customer)
        self.assertEqual(
            self.client.post(url, data={"texto": "Intento"}).status_code, 403
        )
        self.login(self.admin)
        self.assertEqual(
            self.client.post(
                "/pedidos/987654322/observaciones", data={"texto": "Inexistente"}
            ).status_code,
            404,
        )
        web.app.config["WTF_CSRF_ENABLED"] = True
        self.client.post(url, data={"texto": "Sin CSRF"})
        self.assertEqual(
            self.query(
                "SELECT count(*) FROM observaciones_pedidos WHERE id_pedido=%s",
                (self.order,),
            ),
            [(0,)],
        )

    def test_descripcion_corregida_auditada(self):
        url = f"/pedidos/{self.order}/equipo"
        data = {
            "equipo": "Laptop HP",
            "modelo": "Pavilion 15",
            "descripcion": "Diagnóstico corregido",
        }
        self.assertEqual(self.client.post(url, data=data).status_code, 302)
        self.assertEqual(
            self.query(
                "SELECT equipo,modelo,descripcion,estado FROM pedidos WHERE id_pedido=%s",
                (self.order,),
            ),
            [("Laptop HP", "Pavilion 15", "Diagnóstico corregido", "Entregado")],
        )
        for value in ("   ", "A" * 2001):
            self.assertEqual(
                self.client.post(url, data={**data, "descripcion": value}).status_code,
                200,
            )
        self.assertIn(
            ("Prueba", "Diagnóstico corregido"),
            self.query(
                "SELECT datos_anteriores->>'descripcion',datos_nuevos->>'descripcion' FROM auditoria WHERE tabla='pedidos' AND id_registro=%s AND operacion='UPDATE'",
                (str(self.order),),
            ),
        )

    def test_factura_modal_y_cancelacion_bloqueada(self):
        base.confirmar_total_fixture(self)
        self.assertIn(f'id="form-emision-{self.order}"', self.html())
        self.emit()
        html = self.html()
        self.assertNotIn(f'id="form-emision-{self.order}"', html)
        self.assertIn("Factura: FAC-", html)
        self.assertNotIn(f"/pedidos/{self.order}/cancelar", html)
        self.client.post(
            f"/pedidos/{self.order}/cancelar",
            data={"motivo": "Cliente solicitó cancelación"},
        )
        self.assertEqual(
            self.query("SELECT estado FROM pedidos WHERE id_pedido=%s", (self.order,)),
            [("Entregado",)],
        )

    def test_motivos_actualizados_y_migracion_repetible(self):
        self.assertIn("Cliente solicitó cancelación", MOTIVOS_ADMIN)
        self.assertIn("Ingresé información incorrecta", MOTIVOS_CLIENTE)
        self.assertIn("Deseo realizar otra solicitud", MOTIVOS_CLIENTE)
        self.client.post(
            f"/pedidos/{self.order}/observaciones", data={"texto": "Conservar"}
        )
        with self.conn.cursor() as c:
            sql = Path("sql/migracion_observaciones_pedidos.sql").read_text(
                encoding="utf-8"
            )
            c.execute(sql)
            c.execute(sql)
        self.assertEqual(
            self.query(
                "SELECT texto FROM observaciones_pedidos WHERE id_pedido=%s",
                (self.order,),
            ),
            [("Conservar",)],
        )


if __name__ == "__main__":
    unittest.main()
