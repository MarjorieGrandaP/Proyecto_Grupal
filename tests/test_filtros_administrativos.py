"""Filtros administrativos GET con PostgreSQL real y rollback."""
import unittest
from unittest.mock import patch
import test_facturacion_pedidos as fixtures
from test_correcciones import web


class FiltrosAdministrativos(unittest.TestCase):
    setUp = fixtures.FacturacionPedidos.setUp
    tearDown = fixtures.FacturacionPedidos.tearDown
    query = fixtures.FacturacionPedidos.query
    login = fixtures.FacturacionPedidos.login

    def listado(self, ruta, **parametros):
        with patch.object(web, 'render_template', wraps=web.render_template) as render:
            response = self.client.get('/' + ruta, query_string=parametros)
        self.assertEqual(response.status_code, 200)
        contexto = render.call_args.kwargs
        html = response.get_data(as_text=True)
        self.assertIn('method="GET"', html)
        self.assertIn(f'href="/{ruta}" class="btn btn-outline-secondary">Limpiar', html)
        contador = 'Total facturas' if ruta == 'facturacion' else 'Total'
        self.assertIn(f'{contador}: {len(contexto['facturas' if ruta == 'facturacion' else ruta])}', html)
        return contexto, html

    def test_clientes_campos_combinaciones_y_orden(self):
        for nombre, activo, estado in [('Filtro Alfa', True, 'Entregado'), ('Filtro Zeta', False, 'Pendiente')]:
            self.query('''INSERT INTO clientes(nombre,cedula,telefono,correo,equipo,estado,activo)
                          VALUES (%s,'9998877665','0998877665','filtro@ejemplo.test','Equipo Filtro',%s,%s) RETURNING id_cliente''', (nombre, estado, activo))
        for q in ('Filtro Alfa', '9998877665', '0998877665', 'filtro@ejemplo.test', 'Equipo Filtro'):
            contexto, html = self.listado('clientes', q=q, estado='Entregado', registro='activos', orden='antiguos')
            self.assertEqual([c['nombre'] for c in contexto['clientes']], ['Filtro Alfa'])
            self.assertIn('value="Entregado" selected', html)
            self.assertIn('value="activos" selected', html)
            self.assertIn(f'value="{q}"', html)
        contexto, _ = self.listado('clientes', q='Filtro', estado='Entregado', registro='inactivos')
        self.assertEqual(contexto['clientes'], [])
        for orden, inverso in [('antiguos', False), ('recientes', True), ('nombre', False)]:
            contexto, _ = self.listado('clientes', q='Filtro', orden=orden)
            clave = 'nombre' if orden == 'nombre' else 'id_cliente'
            valores = [c[clave] for c in contexto['clientes']]
            self.assertEqual(valores, sorted(valores, reverse=inverso))

    def proveedores_fixture(self):
        for empresa, activo, categoria in [('Filtro Zeta', True, 'Categoría Zeta'), ('Filtro Alfa', False, 'Categoría Alfa')]:
            self.query('''INSERT INTO proveedores(empresa,contacto,telefono,categoria,activo)
                          VALUES (%s,'Contacto exclusivo','0987654321',%s,%s) RETURNING id_proveedor''', (empresa, categoria, activo))

    def test_proveedores_campos_combinaciones_orden_y_controles(self):
        self.proveedores_fixture()
        for q in ('Filtro Zeta', 'Contacto exclusivo', '0987654321', 'Categoría Zeta'):
            contexto, html = self.listado('proveedores', q=q, estado='activos', categoria='Categoría Zeta', orden='empresa_desc')
            self.assertEqual([p['empresa'] for p in contexto['proveedores']], ['Filtro Zeta'])
            self.assertIn('value="Categoría Zeta" selected', html)
            self.assertIn('Categoría Alfa', contexto['categorias'])
            for texto in ('Registrar Proveedor', 'Editar', 'Desactivar', 'bg-success'):
                self.assertIn(texto, html)
        contexto, _ = self.listado('proveedores', estado='inactivos', categoria='Categoría Zeta')
        self.assertEqual(contexto['proveedores'], [])
        for orden, clave, inverso in [('empresa', 'empresa', False), ('empresa_desc', 'empresa', True), ('recientes', 'id_proveedor', True), ('antiguos', 'id_proveedor', False)]:
            contexto, _ = self.listado('proveedores', q='Filtro', orden=orden)
            valores = [p[clave] for p in contexto['proveedores']]
            self.assertEqual(valores, sorted(valores, reverse=inverso))

    def facturas_fixture(self):
        cliente = self.query('''INSERT INTO clientes(nombre,telefono,correo,equipo)
                               VALUES ('Cliente filtro','0999999999','factura@ejemplo.test','Laptop') RETURNING id_cliente''')[0][0]
        for numero, estado, fecha, total in [('FILTRO-A', 'Pagada', '2025-01-01', 30), ('FILTRO-B', 'Pago parcial', '2025-02-01', 10), ('FILTRO-C', 'Pendiente', '2025-03-01', 20)]:
            self.query('''INSERT INTO facturas(numero,id_cliente,id_servicio,servicio_nombre,id_pedido,estado,fecha,total)
                          VALUES (%s,%s,%s,'Servicio congelado',%s,%s,%s,%s) RETURNING id_factura''',
                       (numero, cliente, self.service, self.order if numero == 'FILTRO-A' else None, estado, fecha, total))

    def test_facturas_busqueda_fechas_estado_importes(self):
        self.facturas_fixture()
        before = self.query("SELECT * FROM facturas WHERE numero LIKE 'FILTRO-%%' ORDER BY numero")
        for q in ('FILTRO-A', 'Cliente filtro', 'factura@ejemplo.test', 'Servicio congelado', str(self.order)):
            contexto, html = self.listado('facturacion', q=q, estado='Pagada', desde='2025-01-01', hasta='2025-01-01', orden='mayor_total')
            self.assertEqual([f['numero'] for f in contexto['facturas']], ['FILTRO-A'])
            self.assertIn('value="Pagada" selected', html)
            self.assertIn('value="2025-01-01"', html)
        for estado, numero in [('Pago parcial', 'FILTRO-B'), ('Pendiente', 'FILTRO-C')]:
            contexto, _ = self.listado('facturacion', q='FILTRO-', estado=estado)
            self.assertEqual([f['numero'] for f in contexto['facturas']], [numero])
        for fechas in ({'desde':'2025-04-01'}, {'hasta':'2024-12-31'}, {'desde':'2025-03-01','hasta':'2025-01-01'}):
            contexto, _ = self.listado('facturacion', q='FILTRO-', **fechas)
            self.assertEqual(contexto['facturas'], [])
        self.assertEqual(before, self.query("SELECT * FROM facturas WHERE numero LIKE 'FILTRO-%%' ORDER BY numero"))

    def test_facturas_orden_y_pendiente_condicional(self):
        self.facturas_fixture()
        for orden, clave, inverso in [('recientes','fecha',True), ('antiguos','fecha',False), ('mayor_total','total',True), ('menor_total','total',False)]:
            contexto, _ = self.listado('facturacion', q='FILTRO-', orden=orden)
            valores = [f[clave] for f in contexto['facturas']]
            self.assertEqual(valores, sorted(valores, reverse=inverso))
        for fecha, inverso in [('recientes',True), ('antiguos',False)]:
            contexto, html = self.listado('facturacion', q='FILTRO-', fecha=fecha, orden='mayor_total')
            valores = [f['fecha'] for f in contexto['facturas']]
            self.assertEqual(valores, sorted(valores, reverse=inverso))
            self.assertIn(f'value="{fecha}" selected', html)
        self.query("UPDATE facturas SET estado='Pagada' WHERE estado='Pendiente' RETURNING id_factura")
        contexto, html = self.listado('facturacion')
        self.assertNotIn(('Pendiente','Pendiente'), contexto['estados'])
        self.assertNotIn('value="Pendiente"', html)

    def test_parametros_invalidos_y_sql(self):
        for ruta in ('clientes','proveedores','facturacion'):
            contexto, _ = self.listado(ruta, q="' OR 1=1 --", estado='invalido', orden='DROP TABLE clientes', categoria="' OR 1=1 --", desde='2025-99-99', hasta="' OR 1=1 --", fecha='invalida')
            self.assertEqual(contexto['facturas' if ruta == 'facturacion' else ruta], [])
            self.assertEqual(contexto['estado'], '')
            self.assertNotEqual(contexto['orden'], 'DROP TABLE clientes')
            if ruta == 'facturacion':
                self.assertEqual((contexto['desde'],contexto['hasta'],contexto['fecha']), ('','',''))

    def test_busqueda_factura_usuario_perfil_y_servicio_historico(self):
        self.query("UPDATE usuarios SET correo='usuario-filtro@ejemplo.test' WHERE id_usuario=%s RETURNING id_usuario", (self.customer,))
        self.query('''INSERT INTO facturas(numero,id_usuario,id_servicio,fecha,total,estado)
                      VALUES ('FILTRO-USUARIO',%s,%s,'2024-01-01',12.34,'Pagada') RETURNING id_factura''', (self.customer,self.service))
        for q in ('usuario-filtro@ejemplo.test', 'Servicio original prueba'):
            contexto, _ = self.listado('facturacion', q=q, desde='2024-01-01', hasta='2024-01-01')
            self.assertIn('FILTRO-USUARIO', [f['numero'] for f in contexto['facturas']])
