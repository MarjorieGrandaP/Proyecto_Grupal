"""Paginación y aislamiento por propietario con PostgreSQL y rollback."""
from html import unescape
import re
import unittest
from unittest.mock import patch, MagicMock
from urllib.parse import urlsplit, parse_qs
import test_facturacion_pedidos as base
from test_correcciones import web
from paginacion import paginar


class Paginacion(unittest.TestCase):
    query = base.FacturacionPedidos.query
    login = base.FacturacionPedidos.login
    tearDown = base.FacturacionPedidos.tearDown

    def setUp(self):
        base.FacturacionPedidos.setUp(self)
        self.query('''INSERT INTO servicios(nombre,descripcion,precio,duracion,imagen)
                      SELECT 'PAGINACION prueba ' || lpad(n::text,2,'0'), 'Descripcion para paginar',100,'1 hora','servicio-1.jpg'
                      FROM generate_series(1,23) n RETURNING id_servicio''')
        self.query('''INSERT INTO clientes(nombre,telefono,equipo)
                      SELECT 'PAGINACION prueba ' || lpad(n::text,2,'0'),'0991234567','Laptop'
                      FROM generate_series(1,23) n RETURNING id_cliente''')
        self.query('''INSERT INTO proveedores(empresa,contacto,telefono,categoria)
                      SELECT 'PAGINACION prueba ' || lpad(n::text,2,'0'),'Contacto','0991234567','Prueba paginada'
                      FROM generate_series(1,23) n RETURNING id_proveedor''')
        self.pedidos = self.query('''INSERT INTO pedidos(id_usuario,id_servicio,equipo,descripcion)
                      SELECT %s,%s,'Laptop','PAGINACION prueba ' || lpad(n::text,2,'0')
                      FROM generate_series(1,23) n RETURNING id_pedido''', (self.customer, self.service))
        self.query('''INSERT INTO facturas(numero,id_usuario,id_servicio,total,estado)
                      SELECT 'PAGINACION prueba ' || lpad(n::text,2,'0'),%s,%s,115,'Pagada'
                      FROM generate_series(1,23) n RETURNING id_factura''', (self.customer,self.service))
        self.query('''INSERT INTO auditoria(tabla,operacion,id_registro,usuario_bd,fecha_hora)
                      SELECT 'proveedores','DELETE',n::text,CURRENT_USER,'2099-01-01'::timestamp
                      FROM generate_series(1,23) n RETURNING id_auditoria''')

    def listado(self, ruta, **args):
        with patch.object(web, 'render_template', wraps=web.render_template) as render:
            response = self.client.get(ruta, query_string=args)
        self.assertEqual(response.status_code, 200)
        return render.call_args.kwargs, response.get_data(as_text=True)

    def test_23_registros_en_todos_los_modulos(self):
        modulos = [('/servicios','servicios'),('/pedidos','pedidos'),('/facturacion','facturas'),
                   ('/clientes','clientes'),('/proveedores','proveedores'),('/auditoria','registros'),
                   ('/mis-pedidos','pedidos'),('/mis-facturas','facturas')]
        for ruta, clave in modulos:
            with self.subTest(ruta=ruta):
                self.login(self.customer if ruta.startswith('/mis-') else self.admin)
                filtros = dict(tabla='proveedores',operacion='DELETE',fecha='2099-01-01') if ruta=='/auditoria' else dict(q='PAGINACION prueba')
                vistos = []
                for pagina, cantidad in ((1,10),(2,10),(3,3)):
                    ctx, html = self.listado(ruta, page=pagina, **filtros)
                    self.assertEqual(len(ctx[clave]),cantidad)
                    self.assertEqual(ctx['paginacion']['total'],23)
                    vistos.extend(ctx[clave])
                    self.assertEqual('rel="prev"' in html, pagina>1)
                    self.assertEqual('rel="next"' in html, pagina<3)
                    self.assertIn(f'de 23 registros',html)
                self.assertEqual(len({str(row) for row in vistos}),23)
        self.login(self.customer)
        ctx, _ = self.listado('/servicios',q='PAGINACION prueba',page=3)
        self.assertEqual(len(ctx['servicios']),3)

    def test_filtros_enlaces_totales_pagina_invalida_y_busqueda_nueva(self):
        filtros = dict(q='PAGINACION prueba',estado='activos',categoria='Prueba paginada',orden='empresa',desde='2026-01-01',hasta='2026-12-31')
        ctx, html = self.listado('/proveedores',page=2,**filtros)
        enlaces = re.findall(r'class="page-link"[^>]*href="([^"]+)"',html)
        self.assertTrue(enlaces)
        for enlace in enlaces:
            args = parse_qs(urlsplit(unescape(enlace)).query)
            for k,v in filtros.items():
                self.assertEqual(args[k],[v])
            self.assertEqual(len(args['page']),1)
        self.assertNotIn('name="page"',html)
        for page, esperado in (('abc',1),('-4',1),('0',1),('999999999999999999999999999999',3)):
            ctx,_ = self.listado('/proveedores',q='PAGINACION prueba',page=page)
            self.assertEqual(ctx['paginacion']['pagina'],esperado)
        ctx, html = self.listado('/proveedores',q='PAGINACION prueba 01',page=3)
        self.assertEqual(ctx['paginacion']['pagina'],1)
        self.assertEqual(ctx['paginacion']['total'],1)
        self.assertIn('Total: 1',html)
        ctx,html = self.listado('/proveedores',q="' OR 1=1 --",page=2)
        self.assertEqual(ctx['paginacion']['total'],0)
        self.assertIn('Mostrando 0–0 de 0 registros',html)

    def test_cliente_solo_registros_propios_y_servicios_disponibles(self):
        self.query("INSERT INTO pedidos(id_usuario,id_servicio,equipo,descripcion) VALUES (%s,%s,'Laptop','PAGINACION ajeno') RETURNING id_pedido", (self.admin,self.service))
        self.query("INSERT INTO facturas(numero,id_usuario,id_servicio,total) VALUES ('PAGINACION ajena',%s,%s,115) RETURNING id_factura", (self.admin,self.service))
        self.query("UPDATE servicios SET archivado=TRUE WHERE nombre='PAGINACION prueba 01' RETURNING id_servicio")
        self.query("UPDATE servicios SET eliminado=TRUE WHERE nombre='PAGINACION prueba 02' RETURNING id_servicio")
        self.query("UPDATE servicios SET activo=FALSE WHERE nombre='PAGINACION prueba 03' RETURNING id_servicio")
        self.login(self.customer)
        for ruta in ('/mis-pedidos','/mis-facturas'):
            ctx,html = self.listado(ruta,q='PAGINACION',page=3)
            self.assertEqual(ctx['paginacion']['total'],23)
            self.assertNotIn('PAGINACION ajen',html)
        ctx,_ = self.listado('/servicios',q='PAGINACION',estado='archivados')
        self.assertEqual(ctx['paginacion']['total'],20)

    def test_sql_parametrizado_y_ventana_acotada(self):
        cursor=MagicMock()
        cursor.fetchone.return_value={'total':10000}
        cursor.fetchall.return_value=[]
        with web.app.test_request_context('/clientes?page=500&q=prueba'):
            resultado=paginar(cursor,'SELECT nombre FROM clientes WHERE nombre ILIKE %s ORDER BY nombre, id_cliente', ('%prueba%',))
        llamadas=cursor.execute.call_args_list
        self.assertIn('COUNT(*)',llamadas[0].args[0])
        self.assertTrue(llamadas[1].args[0].endswith('LIMIT %s OFFSET %s'))
        self.assertEqual(llamadas[1].args[1],('%prueba%',10,4990))
        self.assertLessEqual(len(resultado['numeros']),7)


if __name__=='__main__':
    unittest.main()
