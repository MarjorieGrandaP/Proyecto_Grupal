"""Regresión del layout PDF y etiquetas visuales; datos de prueba con rollback."""
from io import BytesIO
import unittest
from unittest.mock import patch
from pypdf import PdfReader
import test_facturacion_pedidos as fixtures
from test_correcciones import web


class PresentacionPedidos(unittest.TestCase):
    setUp = fixtures.FacturacionPedidos.setUp
    tearDown = fixtures.FacturacionPedidos.tearDown
    query = fixtures.FacturacionPedidos.query
    login = fixtures.FacturacionPedidos.login
    emit = fixtures.FacturacionPedidos.emit
    invoices = fixtures.FacturacionPedidos.invoices

    def comprobar_pdf(self, invoice):
        tablas = []
        original = web.Table.drawOn

        def registrar(tabla, canvas, x, y, *args, **kwargs):
            tablas.append((canvas.getPageNumber(), y, tabla._height))
            return original(tabla, canvas, x, y, *args, **kwargs)

        with patch.object(web.Table, 'drawOn', registrar):
            response = self.client.get(f'/facturas/{invoice}/pdf')
        self.assertEqual(response.status_code, 200)
        _, detalle, resumen = tablas
        if detalle[0] == resumen[0]:
            self.assertGreaterEqual(detalle[1] - (resumen[1] + resumen[2]), 18)
        else:
            self.assertGreater(resumen[0], detalle[0])
        self.assertGreaterEqual(resumen[1], 90)
        texto = ''.join(p.extract_text() for p in PdfReader(BytesIO(response.data)).pages)
        for etiqueta in ('Subtotal', 'IVA (', 'TOTAL', 'Anticipo aplicado', 'Saldo pagado', 'Saldo pendiente', 'Estado de pago'):
            self.assertIn(etiqueta, texto)
        return detalle[2]

    def test_pdf_multilinea(self):
        self.emit()
        invoice = self.invoices()[0][0]
        altura = self.comprobar_pdf(invoice)
        self.query('UPDATE facturas SET servicio_nombre=%s,equipo_nombre=%s,equipo_modelo=%s WHERE id_factura=%s RETURNING id_factura',
                   ('Mantenimiento preventivo y reparación especializada de equipos informáticos',
                    'Computadora portátil profesional para diseño gráfico y desarrollo',
                    'Modelo profesional de alto rendimiento generación avanzada', invoice))
        self.assertGreater(self.comprobar_pdf(invoice), altura)

    def test_pdf_pedido_4_real(self):
        facturas = self.query('SELECT id_factura FROM facturas WHERE id_pedido=4')
        self.assertTrue(facturas, 'Debe existir la factura del pedido 4 para verificarla')
        for invoice, in facturas:
            self.comprobar_pdf(invoice)

    def test_etiquetas_y_botones(self):
        self.emit()
        invoice = self.invoices()[0][0]
        self.login(self.customer)
        for estado, etiqueta in [('Entregado', 'Finalizado'), ('Cancelado', 'Cancelado'), ('En revisión', 'Pedido en proceso'), ('Listo', 'Pedido en proceso')]:
            with self.subTest(estado=estado):
                self.query('UPDATE pedidos SET estado=%s WHERE id_pedido=%s RETURNING id_pedido', (estado, self.order))
                html = self.client.get(f'/mis-pedidos?q={self.order}').get_data(as_text=True)
                self.assertIn(etiqueta, html)
                if estado in ('Entregado', 'Cancelado'):
                    self.assertNotIn('Pedido en proceso', html)
                for ruta in (f'/facturas/{invoice}/pdf', f'/pedidos/{self.order}/pagos', f'/pedidos/{self.order}/seguimiento'):
                    self.assertIn(ruta, html)

    def test_entregado_sin_factura_no_finalizado(self):
        self.login(self.customer)
        html = self.client.get(f'/mis-pedidos?q={self.order}').get_data(as_text=True)
        self.assertIn('Pedido en proceso', html)
        self.assertNotIn('Finalizado', html)
