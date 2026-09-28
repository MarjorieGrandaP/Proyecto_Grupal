"""Validación y persistencia de equipos; las pruebas de BD se revierten."""
import unittest
from pathlib import Path
from unittest.mock import patch
from werkzeug.datastructures import MultiDict
import test_facturacion_pedidos as fixtures
from test_correcciones import web
from test_nombres_personales import Inputs
from forms.cliente_form import ClienteForm
from forms.pedido_form import PedidoForm, EditarPedidoForm
from forms.equipo_form import EquipoPedidoForm, PATRON_EQUIPO


class ValidacionesEquipo(unittest.TestCase):
    def test_backend(self):
        cases = {
            "cedula": (("", "1001234567"), ("5", "123456789", "12345678901", "10012A4567", "１２３４５６７８９０", "1001234567\n")),
            "equipo": (("Laptop", "Laptop HP", "ThinkPad T14", "iPhone 15", "PC Escritorio", "Galaxy S24", "Laptop-HP"), ("455555", "123", "", "   ", "---", "Laptop@", "A"*101)),
            "modelo": (("", "IdeaPad 3 15ALC6", "Pavilion 15", "T14 Gen 3", "15 Pro Max"), ("A"*101,)),
            "correo": (("", "usuario@dominio.com"), ("55554", " ", "usuario@")),
        }
        with web.app.test_request_context():
            for name, (valid, invalid) in cases.items():
                classes = (ClienteForm, PedidoForm, EditarPedidoForm, EquipoPedidoForm) if name in ("equipo", "modelo") else (ClienteForm,)
                for cls in classes:
                    for value in valid + invalid:
                        with self.subTest(form=cls.__name__, field=name, value=value):
                            form = cls(MultiDict({name: value}), meta={"csrf": False})
                            self.assertEqual(getattr(form, name).validate(form), value in valid)


class PersistenciaEquipo(unittest.TestCase):
    setUp = fixtures.FacturacionPedidos.setUp
    tearDown = fixtures.FacturacionPedidos.tearDown
    query = fixtures.FacturacionPedidos.query
    login = fixtures.FacturacionPedidos.login
    emit = fixtures.FacturacionPedidos.emit
    invoices = fixtures.FacturacionPedidos.invoices

    def correct(self, equipo="ThinkPad T14", modelo="T14 Gen 3"):
        return self.client.post(f"/pedidos/{self.order}/equipo", data={"equipo": equipo, "modelo": modelo, "estado": "Cancelado"})

    def test_correccion_admin_auditada_no_cambia_estado_ni_historial(self):
        history = self.query("SELECT * FROM historial_estado_pedidos WHERE id_pedido=%s", (self.order,))
        self.assertEqual(self.correct().status_code, 302)
        self.assertEqual(self.query("SELECT equipo,modelo,estado FROM pedidos WHERE id_pedido=%s", (self.order,)), [("ThinkPad T14", "T14 Gen 3", "Entregado")])
        self.assertEqual(self.query("SELECT * FROM historial_estado_pedidos WHERE id_pedido=%s", (self.order,)), history)
        audit = self.query("SELECT datos_anteriores->>'equipo', datos_nuevos->>'modelo' FROM auditoria WHERE tabla='pedidos' AND id_registro=%s AND operacion='UPDATE'", (str(self.order),))
        self.assertIn(("Laptop", "T14 Gen 3"), audit)
        for url in ("/pedidos", f"/pedidos/{self.order}/seguimiento?modal=1"):
            self.assertIn("T14 Gen 3", self.client.get(url).get_data(as_text=True))
        self.login(self.customer)
        self.assertIn("T14 Gen 3", self.client.get("/mis-pedidos").get_data(as_text=True))

    def test_correccion_permisos_validacion_csrf(self):
        self.assertEqual(self.correct(equipo="455555").status_code, 200)
        self.assertEqual(self.query("SELECT equipo FROM pedidos WHERE id_pedido=%s", (self.order,)), [("Laptop",)])
        self.login(self.customer)
        self.assertEqual(self.correct().status_code, 403)
        self.login(self.admin)
        web.app.config["WTF_CSRF_ENABLED"] = True
        self.correct()
        self.assertEqual(self.query("SELECT equipo FROM pedidos WHERE id_pedido=%s", (self.order,)), [("Laptop",)])
        self.assertEqual(self.client.get("/pedidos/987654322/equipo").status_code, 404)

    def test_factura_y_pdf_conservan_snapshot(self):
        self.correct(equipo="Laptop Lenovo", modelo="IdeaPad 3 15ALC6")
        self.emit()
        invoice = self.invoices()[0][0]
        self.correct()
        with patch.object(web, "Paragraph", wraps=web.Paragraph) as paragraph:
            response = self.client.get(f"/facturas/{invoice}/pdf")
            self.assertTrue(response.data.startswith(b"%PDF"))
            texts = [call.args[0] for call in paragraph.call_args_list]
            self.assertIn("Equipo: Laptop Lenovo<br/>Modelo: IdeaPad 3 15ALC6", texts)
            self.assertIn("Servicio original prueba", texts)
            self.assertFalse(any("T14 Gen 3" in t for t in texts))
        self.assertIn("IdeaPad 3 15ALC6", self.client.get("/facturacion").get_data(as_text=True))
        self.login(self.customer)
        html = self.client.get("/mis-facturas?q=Laptop Lenovo").get_data(as_text=True)
        self.assertIn("IdeaPad 3 15ALC6", html)
        self.assertNotIn("T14 Gen 3", html)

    def test_modelo_desconocido_no_se_rellena_despues(self):
        self.emit()
        self.correct()
        migration = Path("sql/migracion_equipo_modelo.sql").read_text(encoding="utf-8")
        with self.conn.cursor() as c:
            c.execute(migration)
            c.execute(migration)
        self.assertEqual(self.query("SELECT equipo_nombre,equipo_modelo FROM facturas WHERE id_pedido=%s", (self.order,)), [("Laptop", "")])
        with patch.object(web, "Paragraph", wraps=web.Paragraph) as paragraph:
            self.client.get(f"/facturas/{self.invoices()[0][0]}/pdf")
            texts = [call.args[0] for call in paragraph.call_args_list]
            self.assertIn("Equipo: Laptop", texts)
            self.assertFalse(any("Modelo:" in t for t in texts))

    def test_migracion_rellena_solo_nulos(self):
        self.correct()
        self.emit()
        self.query("UPDATE facturas SET equipo_nombre=NULL,equipo_modelo=NULL WHERE id_pedido=%s RETURNING id_factura", (self.order,))
        migration = Path("sql/migracion_equipo_modelo.sql").read_text(encoding="utf-8")
        with self.conn.cursor() as c:
            c.execute(migration)
        self.correct("iPhone 15", "15 Pro Max")
        with self.conn.cursor() as c:
            c.execute(migration)
        self.assertEqual(self.query("SELECT equipo_nombre,equipo_modelo,servicio_nombre FROM facturas WHERE id_pedido=%s", (self.order,)), [("ThinkPad T14", "T14 Gen 3", "Servicio original prueba")])

    def test_crear_y_editar_pedido_modelo(self):
        self.login(self.customer)
        response = self.client.post("/pedido/nuevo", data={"servicio": str(self.service), "equipo": "Laptop Lenovo", "modelo": "IdeaPad 3 15ALC6", "descripcion": "Pantalla averiada", "acepta_terminos": "y"})
        self.assertEqual(response.status_code, 302)
        orders = self.query("SELECT id_pedido,modelo FROM pedidos WHERE id_usuario=%s AND id_servicio=%s AND id_pedido<>%s", (self.customer, self.service, self.order))
        self.assertEqual(len(orders), 1)
        ident, modelo = orders[0]
        self.assertEqual(modelo, "IdeaPad 3 15ALC6")
        url = f"/mis-pedidos/{ident}/editar"
        self.assertIn(modelo, self.client.get(url).get_data(as_text=True))
        data = {"servicio": str(self.service), "equipo": "iPhone 15", "modelo": "15 Pro Max", "descripcion": "Pantalla averiada"}
        self.assertEqual(self.client.post(url, data=data).status_code, 302)
        data["equipo"] = "455555"
        self.assertEqual(self.client.post(url, data=data).status_code, 200)
        self.assertEqual(self.query("SELECT equipo,modelo FROM pedidos WHERE id_pedido=%s", (ident,)), [("iPhone 15", "15 Pro Max")])

    def test_clientes_creacion_edicion_y_atributos(self):
        data = {"nombre": "María José", "cedula": "1001234567", "telefono": "0991234567", "correo": "", "equipo": "Laptop", "modelo": "IdeaPad 3 15ALC6", "estado": "Pendiente"}
        self.assertEqual(self.client.post("/clientes/nuevo", data=data).status_code, 302)
        ident = self.query("SELECT id_cliente FROM clientes WHERE nombre=%s AND modelo=%s ORDER BY id_cliente DESC", (data["nombre"], data["modelo"]))[0][0]
        url = f"/clientes/editar/{ident}"
        html = self.client.get(url).get_data(as_text=True)
        parser = Inputs(); parser.feed(html)
        attrs = parser.inputs["cedula"]
        for attr, value in (("inputmode", "numeric"), ("pattern", "[0-9]{10}"), ("maxlength", "10")):
            self.assertEqual(attrs[attr], value)
        self.assertEqual(parser.inputs["equipo"]["pattern"], PATRON_EQUIPO)
        self.assertIn("email", parser.inputs["correo"]["data-validation"])
        self.assertNotIn("required", parser.inputs["modelo"])
        for field, invalid in (("cedula", "5"), ("correo", "55554"), ("equipo", "455555")):
            self.assertEqual(self.client.post(url, data={**data, field: invalid}).status_code, 200)
        data.update(modelo="T14 Gen 3", correo="usuario@dominio.com")
        self.assertEqual(self.client.post(url, data=data).status_code, 302)
        self.assertEqual(self.query("SELECT modelo,correo FROM clientes WHERE id_cliente=%s", (ident,)), [("T14 Gen 3", "usuario@dominio.com")])
        self.assertIn(("T14 Gen 3",), self.query("SELECT datos_nuevos->>'modelo' FROM auditoria WHERE tabla='clientes' AND id_registro=%s AND operacion='UPDATE'", (str(ident),)))

if __name__ == "__main__":
    unittest.main()
