"""Regresiones con PostgreSQL y rollback, incluida la migración."""
import unittest
import psycopg2
from pathlib import Path
from unittest.mock import patch
import test_facturacion_pedidos as base
from test_correcciones import web


class EliminacionLogica(unittest.TestCase):
    query = base.FacturacionPedidos.query
    login = base.FacturacionPedidos.login
    emit = base.FacturacionPedidos.emit
    invoices = base.FacturacionPedidos.invoices
    tearDown = base.FacturacionPedidos.tearDown

    def setUp(self):
        base.FacturacionPedidos.setUp(self)
        with self.conn.cursor() as cursor:
            cursor.execute(Path('sql/migracion_eliminacion_logica.sql').read_text(encoding='utf-8'))
            cursor.execute(Path('sql/migracion_nombres_servicios_no_eliminados.sql').read_text(encoding='utf-8'))
        self.service = self.query("INSERT INTO servicios(nombre,descripcion,precio,duracion,imagen) VALUES ('Servicio positivo prueba','Prueba transaccional',25.50,'1 hora','servicio-1.jpg') RETURNING id_servicio")[0][0]
        self.query('UPDATE pedidos SET id_servicio=%s WHERE id_pedido=%s RETURNING id_pedido', (self.service,self.order))

    def eliminar(self):
        self.assertEqual(self.client.post(f'/servicios/eliminar/{self.service}').status_code, 302)

    def crear_mismo_nombre(self, nombre='Servicio positivo prueba'):
        return self.client.post('/servicios/nuevo', data={
            'nombre': nombre, 'descripcion': 'Nueva descripcion independiente',
            'precio': '80', 'duracion': '2 horas',
            'imagen': web.obtener_imagenes_servicios()[0][0], 'id_proveedor': '0',
        })

    def test_reutilizar_nombre_conserva_historial_y_catalogo(self):
        self.emit()
        invoice = self.invoices()[0][0]
        self.eliminar()
        historico = self.query('SELECT * FROM servicios WHERE id_servicio=%s', (self.service,))
        factura = self.query('SELECT * FROM facturas WHERE id_factura=%s', (invoice,))
        pedido = self.query('SELECT * FROM pedidos WHERE id_pedido=%s', (self.order,))
        auditoria = self.query('SELECT * FROM auditoria ORDER BY 1')
        self.assertEqual(self.crear_mismo_nombre().status_code, 302)
        nuevo = self.query('SELECT id_servicio, precio, descripcion FROM servicios WHERE nombre=%s AND eliminado=FALSE', ('Servicio positivo prueba',))[0]
        self.assertNotEqual(nuevo[0], self.service)
        self.assertEqual(nuevo[1], 80)
        self.assertEqual(nuevo[2], 'Nueva descripcion independiente')
        self.assertEqual(historico, self.query('SELECT * FROM servicios WHERE id_servicio=%s', (self.service,)))
        self.assertEqual(factura, self.query('SELECT * FROM facturas WHERE id_factura=%s', (invoice,)))
        self.assertEqual(pedido, self.query('SELECT * FROM pedidos WHERE id_pedido=%s', (self.order,)))
        self.assertEqual(auditoria, self.query('SELECT * FROM auditoria ORDER BY 1')[:len(auditoria)])
        with patch.object(web, 'Paragraph', wraps=web.Paragraph) as paragraph:
            self.assertEqual(self.client.get(f'/facturas/{invoice}/pdf').status_code, 200)
            self.assertIn('Servicio positivo prueba', ' '.join(str(c.args[0]) for c in paragraph.call_args_list))
        self.login(self.customer)
        opciones = dict(web.cargar_opciones_servicios())
        self.assertIn(nuevo[0], opciones)
        self.assertNotIn(self.service, opciones)
        for ruta in ('/servicios', '/mis-pedidos', f'/mis-pedidos/{self.order}/seguimiento'):
            response = self.client.get(ruta)
            self.assertEqual(response.status_code, 200)
            self.assertIn('Servicio positivo prueba', response.get_data(as_text=True))
        response = self.client.post('/pedido/nuevo', data={
            'servicio': nuevo[0], 'equipo': 'Laptop', 'modelo': 'Modelo prueba',
            'descripcion': 'Solicitud para el nuevo servicio',
            'acepta_terminos': 'y',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.query('SELECT count(*) FROM pedidos WHERE id_servicio=%s', (nuevo[0],)), [(1,)])

    def test_duplicados_activos_pausados_archivados_e_indice(self):
        self.eliminar()
        self.assertEqual(self.crear_mismo_nombre().status_code, 302)
        nuevo = self.query('SELECT id_servicio FROM servicios WHERE nombre=%s AND eliminado=FALSE', ('Servicio positivo prueba',))[0][0]
        for activo, archivado in ((True, False), (False, False), (False, True)):
            self.query('UPDATE servicios SET activo=%s, archivado=%s WHERE id_servicio=%s RETURNING id_servicio', (activo, archivado, nuevo))
            response = self.crear_mismo_nombre('  SERVICIO POSITIVO PRUEBA  ')
            self.assertEqual(response.status_code, 200)
            self.assertIn('Puedes restaurarlo' if archivado else 'Ya existe un servicio con ese nombre.', response.get_data(as_text=True))
            with self.conn.cursor() as cursor:
                self.assertIsNone(web.nombre_servicio_duplicado(cursor, 'Servicio positivo prueba', nuevo))
                cursor.execute('SAVEPOINT duplicado')
                try:
                    with self.assertRaises(psycopg2.errors.UniqueViolation):
                        cursor.execute("INSERT INTO servicios(nombre,descripcion,precio,duracion,imagen) VALUES (' SERVICIO POSITIVO PRUEBA ','Duplicado directo',80,'2 horas','servicio-1.jpg')")
                finally:
                    cursor.execute('ROLLBACK TO SAVEPOINT duplicado')
        with self.conn.cursor() as cursor:
            sql = Path('sql/migracion_nombres_servicios_no_eliminados.sql').read_text(encoding='utf-8')
            cursor.execute(sql)
            cursor.execute(sql)
        self.assertEqual(self.query('SELECT count(*) FROM servicios WHERE nombre=%s', ('Servicio positivo prueba',)), [(2,)])

    def test_catalogo_y_restauracion(self):
        self.eliminar()
        for estado in ('todos', 'activos', 'pausados', 'archivados'):
            self.assertNotIn('Servicio positivo prueba', self.client.get('/servicios', query_string={'estado': estado}).get_data(as_text=True))
        for route in (f'/servicios/activar/{self.service}', f'/servicios/{self.service}/restaurar'):
            self.assertEqual(self.client.post(route).status_code, 404)
        self.login(self.customer)
        self.assertNotIn(self.service, dict(web.cargar_opciones_servicios()))
        self.assertNotIn('Servicio positivo prueba', self.client.get('/servicios').get_data(as_text=True))

    def test_nuevo_pedido_rechaza_servicio_eliminado(self):
        self.eliminar()
        self.login(self.customer)
        before = self.query('SELECT count(*) FROM pedidos')
        response = self.client.post('/pedido/nuevo', data={'servicio': self.service, 'equipo': 'Laptop', 'descripcion': 'Pedido nuevo de prueba'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(before, self.query('SELECT count(*) FROM pedidos'))

    def test_factura_snapshot_y_pdf(self):
        self.emit()
        invoice = self.invoices()[0][0]
        original = self.query('SELECT servicio_nombre, servicio_descripcion, servicio_precio FROM facturas WHERE id_factura=%s', (invoice,))
        self.eliminar()
        self.query("UPDATE servicios SET nombre='Otro nombre', descripcion='Otra descripción', precio=999 WHERE id_servicio=%s RETURNING id_servicio", (self.service,))
        self.assertEqual(original, self.query('SELECT servicio_nombre, servicio_descripcion, servicio_precio FROM facturas WHERE id_factura=%s', (invoice,)))
        with patch.object(web, 'Paragraph', wraps=web.Paragraph) as paragraph:
            self.assertEqual(self.client.get(f'/facturas/{invoice}/pdf').status_code, 200)
            texts = ' '.join(str(c.args[0]) for c in paragraph.call_args_list)
            self.assertIn('Servicio positivo prueba', texts)
            self.assertIn('Prueba transaccional', texts)

    def test_pedido_historico(self):
        self.eliminar()
        self.login(self.customer)
        response = self.client.get('/mis-pedidos')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Servicio positivo prueba', response.get_data(as_text=True))

    def test_seguimiento_historico(self):
        self.eliminar()
        self.login(self.customer)
        response = self.client.get(f'/mis-pedidos/{self.order}/seguimiento')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Servicio positivo prueba', response.get_data(as_text=True))

    def test_cliente_eliminado_conserva_factura(self):
        customer = self.query("INSERT INTO clientes(nombre,telefono,equipo) VALUES ('Cliente histórico prueba','0991234567','Laptop') RETURNING id_cliente")[0][0]
        self.emit()
        invoice = self.invoices()[0][0]
        self.query('UPDATE facturas SET id_cliente=%s WHERE id_factura=%s RETURNING id_factura', (customer, invoice))
        self.assertEqual(self.client.post(f'/clientes/eliminar/{customer}').status_code, 302)
        self.assertNotIn('Cliente histórico prueba', self.client.get('/clientes').get_data(as_text=True))
        self.assertEqual(self.client.post(f'/clientes/activar/{customer}').status_code, 404)
        self.assertEqual(self.client.get(f'/clientes/editar/{customer}').status_code, 404)
        self.assertIn('Cliente histórico prueba', self.client.get('/facturacion').get_data(as_text=True))
        self.assertEqual(self.query('SELECT id_cliente FROM facturas WHERE id_factura=%s', (invoice,)), [(customer,)])

    def test_migracion_repetible_sin_cascadas_historicas(self):
        self.emit()
        with self.conn.cursor() as cursor:
            cursor.execute(Path('sql/migracion_eliminacion_logica.sql').read_text(encoding='utf-8'))
        self.assertEqual(self.query("SELECT count(*) FROM pg_constraint WHERE contype='f' AND confdeltype IN ('c','n') AND (conrelid IN ('facturas'::regclass,'pedidos'::regclass) OR confrelid IN ('pedidos'::regclass,'facturas'::regclass))"), [(0,)])


if __name__ == '__main__':
    unittest.main()
