"""Configuración, cotizaciones y snapshots con PostgreSQL real y rollback."""
from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from pathlib import Path
import unittest
import re
from unittest.mock import patch
from pypdf import PdfReader
import test_facturacion_pedidos as base
from test_correcciones import web


class ConfiguracionComercial(unittest.TestCase):
    query = base.FacturacionPedidos.query
    login = base.FacturacionPedidos.login
    emit = base.FacturacionPedidos.emit
    invoices = base.FacturacionPedidos.invoices
    tearDown = base.FacturacionPedidos.tearDown

    def setUp(self):
        base.FacturacionPedidos.setUp(self)
        self.query('DELETE FROM configuracion_comercial RETURNING id_configuracion')
        self.query('UPDATE servicios SET precio=100 WHERE id_servicio=%s RETURNING id_servicio', (self.service,))
        self.hoy = self.query("SELECT (CURRENT_TIMESTAMP AT TIME ZONE 'America/Guayaquil')::date")[0][0]

    def guardar(self, **cambios):
        self.login(self.admin)
        datos = dict(porcentaje_iva='15', porcentaje_descuento='10', nombre_promocion='Promoción prueba')
        datos.update(cambios)
        return self.client.post('/configuracion', data=datos)

    def crear(self):
        self.login(self.customer)
        response = self.client.post('/pedido/nuevo', data={
            'servicio': self.service, 'equipo': 'Laptop', 'modelo': 'Modelo prueba',
            'descripcion': 'Solicitud comercial de prueba', 'acepta_terminos': 'y', 'solicita_factura': 'y',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith('/mis-pedidos'))
        self.order = self.query('SELECT MAX(id_pedido) FROM pedidos WHERE descripcion=%s', ('Solicitud comercial de prueba',))[0][0]
        return self.query('''SELECT subtotal, porcentaje_iva, valor_iva, total,
                            porcentaje_descuento, valor_descuento, subtotal_con_descuento
                            FROM pedidos WHERE id_pedido=%s''', (self.order,))[0]

    def facturar(self):
        self.login(self.admin)
        self.query("UPDATE pedidos SET estado='Entregado' WHERE id_pedido=%s RETURNING id_pedido", (self.order,))
        self.assertEqual(self.emit().status_code, 302)
        return self.invoices()[0][0]

    def test_iva_respaldo_y_configuracion_prevalece_sin_recalcular(self):
        with patch.dict(web.app.config, IVA_RATE=Decimal('0.15')):
            self.assertEqual(self.crear()[1:4], (Decimal('.15'), Decimal('15'), Decimal('115')))
        invoice = self.facturar()
        anterior = self.query('SELECT * FROM facturas WHERE id_factura=%s', (invoice,))
        pedido = self.query('SELECT * FROM pedidos WHERE id_pedido=%s', (self.order,))
        old_order = self.order
        self.assertEqual(self.guardar(porcentaje_iva='12').status_code, 302)
        with patch.dict(web.app.config, IVA_RATE=Decimal('.99')):
            self.assertEqual(self.crear()[1:4], (Decimal('.12'), Decimal('12'), Decimal('112')))
        self.assertEqual(anterior, self.query('SELECT * FROM facturas WHERE id_factura=%s', (invoice,)))
        self.assertEqual(pedido, self.query('SELECT * FROM pedidos WHERE id_pedido=%s', (old_order,)))

    def test_descuento_snapshot_factura_pdf_catalogo_y_pago_separado(self):
        self.guardar(descuento_activo='y', fecha_inicio_descuento=self.hoy, fecha_fin_descuento=self.hoy)
        self.assertEqual(self.crear(), tuple(map(Decimal, ('100','.15','13.50','103.50','.10','10','90'))))
        html = self.client.get(f'/pedidos/{self.order}/pagos').get_data(as_text=True)
        self.assertIn('Subtotal después del descuento', html)
        self.assertNotIn('Enviar comprobante', html)
        self.guardar(porcentaje_iva='12', porcentaje_descuento='50', descuento_activo='y')
        catalogo = self.client.get('/servicios', query_string={'q':'Servicio original prueba'}).get_data(as_text=True)
        self.assertIn('56.00', catalogo)
        self.assertIn('IVA (12 %)', catalogo)
        self.login(self.admin)
        self.query("UPDATE pedidos SET estado='En revisión' WHERE id_pedido=%s RETURNING id_pedido", (self.order,))
        self.assertEqual(self.client.post(f'/pedidos/{self.order}/anticipo', data={'solicitado':'y'}).status_code, 302)
        self.assertEqual(self.query('SELECT total, anticipo_solicitado FROM pedidos WHERE id_pedido=%s', (self.order,)), [(Decimal('103.50'), True)])
        invoice = self.facturar()
        anterior = self.query('SELECT * FROM facturas WHERE id_factura=%s', (invoice,))
        self.guardar(porcentaje_iva='12', porcentaje_descuento='50', descuento_activo='y')
        self.query("UPDATE servicios SET nombre='Nombre cambiado',descripcion='Descripcion cambiada',precio=500,eliminado=TRUE WHERE id_servicio=%s RETURNING id_servicio", (self.service,))
        self.assertEqual(anterior, self.query('SELECT * FROM facturas WHERE id_factura=%s', (invoice,)))
        response = self.client.get(f'/facturas/{invoice}/pdf')
        self.assertEqual(response.status_code, 200)
        pdf = '\n'.join(page.extract_text() for page in PdfReader(BytesIO(response.data)).pages)
        for texto in ('Servicio original prueba', 'Prueba transaccional', '$100.00', '10', '$90.00', '$13.50', '$103.50', '15'):
            self.assertIn(texto, pdf)
        self.assertNotIn('Nombre cambiado', pdf)
        self.login(self.customer)
        html = self.client.get('/mis-facturas', query_string={'q': anterior[0][1]}).get_data(as_text=True)
        self.assertIn('103.50', html)
        self.assertIn('Subtotal después del descuento', html)

    def test_promocion_inactiva_futura_vencida_abierta_y_limites(self):
        casos = [({}, False),
                 ({'descuento_activo':'y', 'fecha_inicio_descuento':self.hoy+timedelta(days=1)}, False),
                 ({'descuento_activo':'y', 'fecha_fin_descuento':self.hoy-timedelta(days=1)}, False),
                 ({'descuento_activo':'y'}, True),
                 ({'descuento_activo':'y', 'fecha_inicio_descuento':self.hoy}, True),
                 ({'descuento_activo':'y', 'fecha_fin_descuento':self.hoy}, True)]
        for datos, aplica in casos:
            with self.subTest(datos=datos):
                self.assertEqual(self.guardar(**datos).status_code, 302)
                valores = self.crear()
                self.assertEqual(valores[3], Decimal('103.50' if aplica else '115'))
        self.guardar(porcentaje_iva='0', porcentaje_descuento='100', descuento_activo='y')
        self.assertEqual(self.crear()[3], 0)
        self.guardar(porcentaje_iva='100', porcentaje_descuento='0')
        self.assertEqual(self.crear()[3], 200)

    def test_validaciones_backend_csrf_permisos_y_auditoria(self):
        self.login(self.customer)
        for method in (self.client.get, self.client.post):
            self.assertEqual(method('/configuracion').status_code, 403)
        self.login(self.admin)
        with patch.dict(web.app.config, WTF_CSRF_ENABLED=True):
            html = self.client.get('/configuracion').get_data(as_text=True)
            self.assertIn('csrf_token', html)
            self.assertEqual(self.guardar().status_code, 200)
            self.assertEqual(self.query('SELECT count(*) FROM configuracion_comercial'), [(0,)])
            token = re.search(r'name="csrf_token"[^>]*value="([^"]+)"',html).group(1)
            self.assertEqual(self.guardar(csrf_token=token).status_code, 302)
        self.query('DELETE FROM configuracion_comercial RETURNING id_configuracion')
        for campo in ('porcentaje_iva','porcentaje_descuento'):
            for valor in ('-1','100.01','NaN','Infinity','abc','1.234',''):
                with self.subTest(campo=campo, valor=valor):
                    self.assertEqual(self.guardar(**{campo:valor}).status_code, 200)
        self.assertEqual(self.guardar(fecha_inicio_descuento='2026-12-31',fecha_fin_descuento='2026-01-01').status_code, 200)
        self.assertEqual(self.guardar(fecha_inicio_descuento='invalida').status_code, 200)
        nombre = "Promo '); DROP TABLE pedidos; --"
        self.assertEqual(self.guardar(nombre_promocion=nombre).status_code, 302)
        self.assertEqual(self.guardar(porcentaje_iva='12').status_code, 302)
        cambios = self.query("SELECT operacion, datos_nuevos->>'actualizado_por' FROM auditoria WHERE tabla='configuracion_comercial' ORDER BY id_auditoria DESC LIMIT 2")
        self.assertEqual(cambios, [('UPDATE', str(self.admin)), ('INSERT', str(self.admin))])
        self.assertEqual(self.query("SELECT datos_nuevos->>'nombre_promocion' FROM auditoria WHERE tabla='configuracion_comercial' AND operacion='INSERT' ORDER BY id_auditoria DESC LIMIT 1"), [(nombre,)])

    def test_migraciones_repetibles_preservan_snapshots(self):
        self.guardar(descuento_activo='y')
        self.crear()
        self.facturar()
        antes = {t:self.query(f'SELECT to_jsonb(t) FROM {t} t ORDER BY to_jsonb(t)::text') for t in ('pedidos','facturas','configuracion_comercial')}
        with self.conn.cursor() as cursor:
            for _ in range(2):
                for archivo in ('migracion_configuracion_comercial.sql','migracion_indices_paginacion.sql'):
                    cursor.execute(Path('sql',archivo).read_text(encoding='utf-8'))
        for tabla, filas in antes.items():
            self.assertEqual(filas, self.query(f'SELECT to_jsonb(t) FROM {tabla} t ORDER BY to_jsonb(t)::text'))

    def test_servicio_modificado_antes_de_emitir_y_solicitud_editable(self):
        self.guardar(descuento_activo='y')
        self.crear()
        nuevo = self.query("INSERT INTO servicios(nombre,descripcion,precio,duracion,imagen) VALUES ('Servicio alternativo','Descripcion alternativa',200,'2 horas','servicio-1.jpg') RETURNING id_servicio")[0][0]
        self.guardar(porcentaje_iva='12', descuento_activo='y', porcentaje_descuento='50')
        self.login(self.customer)
        self.assertEqual(self.client.post(f'/mis-pedidos/{self.order}/editar',data={
            'servicio':nuevo,'equipo':'Laptop','descripcion':'Cambio explicito de servicio',
        }).status_code,302)
        self.assertEqual(self.query('SELECT subtotal,porcentaje_iva,porcentaje_descuento,total FROM pedidos WHERE id_pedido=%s',(self.order,)),
                         [(Decimal('200'),Decimal('.15'),Decimal('.10'),Decimal('207'))])
        self.query("UPDATE servicios SET nombre='Modificado despues',precio=999,descripcion='Otra descripcion',eliminado=TRUE WHERE id_servicio=%s RETURNING id_servicio",(nuevo,))
        factura=self.facturar()
        self.assertEqual(self.query('SELECT servicio_nombre,servicio_descripcion,servicio_precio,total FROM facturas WHERE id_factura=%s',(factura,)),
                         [('Servicio alternativo','Descripcion alternativa',Decimal('200'),Decimal('207'))])


if __name__ == '__main__':
    unittest.main()
