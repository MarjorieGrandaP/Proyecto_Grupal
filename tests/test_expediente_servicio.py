"""Privacidad, expediente, factura comercial y garantía (PostgreSQL con rollback)."""
import unittest
from unittest.mock import patch
from pathlib import Path
import test_facturacion_pedidos as base
from test_correcciones import web


class ExpedienteServicio(unittest.TestCase):
    setUp = base.FacturacionPedidos.setUp
    tearDown = base.FacturacionPedidos.tearDown
    query = base.FacturacionPedidos.query
    login = base.FacturacionPedidos.login
    emit = base.FacturacionPedidos.emit
    invoices = base.FacturacionPedidos.invoices

    def technical(self, **extra):
        data = dict(diagnostico="Diagnóstico privado", trabajo_realizado="Trabajo privado", repuestos="Componente privado", recomendaciones="Recomendación privada")
        data.update(extra)
        return self.client.post(f"/pedidos/{self.order}/detalle-servicio", data=data)

    def test_tecnica_crear_editar_auditada(self):
        self.assertEqual(self.technical().status_code, 302)
        self.assertEqual(self.technical(diagnostico="Diagnóstico corregido").status_code, 302)
        row = self.query("SELECT diagnostico,trabajo_realizado,repuestos,recomendaciones,actualizado_por FROM detalle_servicio WHERE id_pedido=%s", (self.order,))[0]
        self.assertEqual(row, ("Diagnóstico corregido", "Trabajo privado", "Componente privado", "Recomendación privada", self.admin))
        audit = self.query("SELECT operacion,datos_anteriores->>'diagnostico',datos_nuevos->>'diagnostico' FROM auditoria WHERE tabla='detalle_servicio' AND datos_nuevos->>'id_pedido'=%s ORDER BY id_auditoria", (str(self.order),))
        self.assertEqual(audit, [('INSERT', None, 'Diagnóstico privado'), ('UPDATE', 'Diagnóstico privado', 'Diagnóstico corregido')])
        html = self.client.get('/pedidos', query_string={'q': str(self.order)}).get_data(as_text=True)
        for text in ('Información técnica', 'Diagnóstico corregido', 'Trabajo privado', 'Observaciones', 'Garantía'):
            self.assertIn(text, html)

    def test_tecnica_permisos_validacion_csrf(self):
        self.technical(diagnostico='A'*10001)
        self.assertEqual(self.query('SELECT count(*) FROM detalle_servicio WHERE id_pedido=%s', (self.order,)), [(0,)])
        self.login(self.customer)
        self.assertEqual(self.technical().status_code, 403)
        self.assertEqual(self.client.get('/pedidos').status_code, 403)
        self.login(self.admin)
        self.assertEqual(self.client.post('/pedidos/987654322/detalle-servicio', data={}).status_code, 404)
        web.app.config['WTF_CSRF_ENABLED'] = True
        self.technical()
        self.assertEqual(self.query('SELECT count(*) FROM detalle_servicio WHERE id_pedido=%s', (self.order,)), [(0,)])

    def test_cliente_solo_notas_publicas_sin_actor(self):
        self.technical()
        url = f'/pedidos/{self.order}/observaciones'
        self.client.post(url, data={'texto': 'Nota confidencial'})
        self.client.post(url, data={'texto': 'Aviso al cliente', 'visible_cliente': 'y'})
        self.query("UPDATE historial_estado_pedidos SET observacion='Incidencia interna',motivo_cancelacion='Motivo privado',id_usuario_actor=%s WHERE id_pedido=%s RETURNING id_historial", (self.admin, self.order))
        admin_html = self.client.get(f'/pedidos/{self.order}/seguimiento?modal=1').get_data(as_text=True)
        for text in ('Nota confidencial', 'Aviso al cliente', 'Incidencia interna', 'Motivo privado', 'Realizado por:'):
            self.assertIn(text, admin_html)
        self.login(self.customer)
        for suffix in ('', '?modal=1', '?modal=1&seccion=observaciones'):
            html = self.client.get(f'/pedidos/{self.order}/seguimiento{suffix}').get_data(as_text=True)
            self.assertIn('Aviso al cliente', html)
            for text in ('Nota confidencial', 'Incidencia interna', 'Motivo privado', 'Realizado por:', 'Diagnóstico privado'):
                self.assertNotIn(text, html)
        self.query('UPDATE pedidos SET id_usuario=%s WHERE id_pedido=%s RETURNING id_pedido', (self.admin, self.order))
        self.assertEqual(self.client.get(f'/pedidos/{self.order}/seguimiento?modal=1&seccion=observaciones').status_code, 404)

    def test_pdf_comercial_sin_expediente_y_snapshot(self):
        self.query("UPDATE pedidos SET equipo='Laptop Lenovo',modelo='IdeaPad 3' WHERE id_pedido=%s RETURNING id_pedido", (self.order,))
        self.emit()
        self.technical()
        self.client.post(f'/pedidos/{self.order}/observaciones', data={'texto': 'Nota confidencial'})
        self.query("UPDATE servicios SET nombre='Servicio cambiado',precio=999 WHERE id_servicio=%s RETURNING id_servicio", (self.service,))
        self.query("UPDATE pedidos SET equipo='Equipo nuevo',modelo='Modelo nuevo' WHERE id_pedido=%s RETURNING id_pedido", (self.order,))
        self.login(self.customer)
        invoice = self.invoices()[0][0]
        with patch.object(web, 'Paragraph', wraps=web.Paragraph) as paragraphs, patch.object(web, 'Table', wraps=web.Table) as tables:
            response = self.client.get(f'/facturas/{invoice}/pdf')
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.data.startswith(b'%PDF'))
            texts = [c.args[0] for c in paragraphs.call_args_list]
            self.assertIn('Servicio original prueba', texts)
            self.assertIn('Equipo: Laptop Lenovo<br/>Modelo: IdeaPad 3', texts)
            self.assertTrue(any('garantía de 3 meses' in t for t in texts))
            for private in ('Diagnóstico privado', 'Trabajo privado', 'Nota confidencial', 'Equipo nuevo', 'Servicio cambiado'):
                self.assertFalse(any(private in t for t in texts))
            cells = [cell for call in tables.call_args_list for row in call.args[0] for cell in row if isinstance(cell, str)]
            self.assertIn('$25.50', cells)
            self.assertIn('Estado de pago', cells)
            self.assertIn('Pendiente', cells)
        self.query('UPDATE facturas SET id_usuario=%s WHERE id_factura=%s RETURNING id_factura', (self.admin, invoice))
        self.assertEqual(self.client.get(f'/facturas/{invoice}/pdf').status_code, 404)

    def test_garantia_inicio_entrega_y_no_cambia_al_corregir(self):
        self.assertIn('Fecha de entrega no registrada', self.client.get('/pedidos', query_string={'q':str(self.order)}).get_data(as_text=True))
        self.query("UPDATE pedidos SET estado='Listo' WHERE id_pedido=%s RETURNING id_pedido", (self.order,))
        self.client.post(f'/pedidos/{self.order}/estado', data={'estado': 'Entregado'})
        entrega = self.query('SELECT fecha_entrega FROM pedidos WHERE id_pedido=%s', (self.order,))[0][0]
        self.assertIsNotNone(entrega)
        self.technical()
        self.client.post(f'/pedidos/{self.order}/equipo', data={'equipo': 'Equipo corregido', 'modelo': ''})
        self.assertEqual(self.query('SELECT fecha_entrega FROM pedidos WHERE id_pedido=%s', (self.order,))[0][0], entrega)
        html = self.client.get('/pedidos', query_string={'q':str(self.order)}).get_data(as_text=True)
        self.assertIn('Vigente', html)
        self.assertIn(entrega.strftime('%d/%m/%Y'), html)
        self.query("UPDATE pedidos SET fecha_entrega='2024-11-30' WHERE id_pedido=%s RETURNING id_pedido", (self.order,))
        html = self.client.get('/pedidos', query_string={'q':str(self.order)}).get_data(as_text=True)
        self.assertIn('28/02/2025', html)
        self.assertIn('Vencida', html)

    def test_migracion_repetible_no_inventa_entrega_y_preserva_notas(self):
        self.technical()
        self.client.post(f'/pedidos/{self.order}/observaciones', data={'texto':'Pública', 'visible_cliente':'y'})
        sql = Path('sql/migracion_expediente_servicio.sql').read_text(encoding='utf-8')
        with self.conn.cursor() as c:
            c.execute(sql)
            c.execute(sql)
        self.assertEqual(self.query('SELECT fecha_entrega FROM pedidos WHERE id_pedido=%s', (self.order,)), [(None,)])
        self.assertEqual(self.query('SELECT texto,visible_cliente FROM observaciones_pedidos WHERE id_pedido=%s', (self.order,)), [('Pública', True)])
        self.assertEqual(self.query('SELECT diagnostico FROM detalle_servicio WHERE id_pedido=%s', (self.order,)), [('Diagnóstico privado',)])

if __name__ == '__main__':
    unittest.main()
