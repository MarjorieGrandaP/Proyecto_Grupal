"""Edición, cancelación y búsquedas con PostgreSQL real; datos revertidos."""
import unittest
import test_facturacion_pedidos as facturacion_tests
from test_correcciones import web


class PortalCliente(unittest.TestCase):
    setUp = facturacion_tests.FacturacionPedidos.setUp
    tearDown = facturacion_tests.FacturacionPedidos.tearDown
    query = facturacion_tests.FacturacionPedidos.query
    login = facturacion_tests.FacturacionPedidos.login
    emit = facturacion_tests.FacturacionPedidos.emit
    invoices = facturacion_tests.FacturacionPedidos.invoices

    def prepare(self):
        self.query("""UPDATE pedidos SET estado='Solicitado', fecha_solicitud=CURRENT_TIMESTAMP - INTERVAL '1 minute'
                      WHERE id_pedido=%s RETURNING id_pedido""",(self.order,))
        self.login(self.customer)

    def edit(self, **extra):
        data={"servicio":str(self.service),"equipo":"Equipo modificado","descripcion":"Descripción modificada"}
        data.update(extra)
        return self.client.post(f"/mis-pedidos/{self.order}/editar",data=data)

    def cancel(self):
        return self.client.post(f"/mis-pedidos/{self.order}/cancelar",data={"motivo":"Ya no necesito el servicio"})

    def test_editar_solicitado_antiguo_solo_campos_permitidos_y_auditoria(self):
        self.prepare()
        self.query("UPDATE pedidos SET fecha_solicitud=CURRENT_TIMESTAMP - INTERVAL '2 days' WHERE id_pedido=%s RETURNING id_pedido",(self.order,))
        before=self.query("SELECT id_usuario,estado,fecha_solicitud,solicita_factura FROM pedidos WHERE id_pedido=%s",(self.order,))[0]
        response=self.edit(id_usuario=str(self.admin),estado="Entregado",solicita_factura="",fecha_solicitud="2000-01-01")
        self.assertEqual(response.status_code,302)
        self.assertEqual(self.query("SELECT id_usuario,estado,fecha_solicitud,solicita_factura FROM pedidos WHERE id_pedido=%s",(self.order,))[0],before)
        self.assertEqual(self.query("SELECT equipo,descripcion FROM pedidos WHERE id_pedido=%s",(self.order,))[0],("Equipo modificado","Descripción modificada"))
        rows=self.query("""SELECT datos_nuevos->>'equipo',datos_nuevos->>'descripcion' FROM auditoria
                          WHERE tabla='pedidos' AND id_registro=%s AND operacion='UPDATE'""",(str(self.order),))
        self.assertIn(("Equipo modificado","Descripción modificada"),rows)

    def test_cambiar_servicio_activo_auditoria_y_conservar_actual_pausado(self):
        self.prepare()
        self.query("""INSERT INTO servicios (id_servicio,nombre,descripcion,precio,duracion,imagen,activo)
                      VALUES (-876544,'Alternativa','Otro servicio',10,'2 horas','servicio-1.jpg',TRUE)
                      RETURNING id_servicio""")
        self.query("UPDATE servicios SET activo=FALSE WHERE id_servicio=%s RETURNING id_servicio",(self.service,))
        html=self.client.get(f"/mis-pedidos/{self.order}/editar").get_data(as_text=True)
        self.assertIn("En pausa, actual",html)
        self.assertEqual(self.edit().status_code,302)
        self.assertEqual(self.edit(servicio="-876544").status_code,302)
        self.assertEqual(self.query("SELECT id_servicio FROM pedidos WHERE id_pedido=%s",(self.order,))[0][0],-876544)
        # El servicio pausado anterior ya no se puede seleccionar.
        self.assertEqual(self.edit().status_code,200)
        rows=self.query("""SELECT datos_anteriores->>'id_servicio',datos_nuevos->>'id_servicio'
                          FROM auditoria WHERE tabla='pedidos' AND id_registro=%s AND operacion='UPDATE'""",(str(self.order),))
        self.assertIn((str(self.service),"-876544"),rows)

    def test_cancelacion_persiste_historial_auditoria_y_no_solicita_factura(self):
        self.prepare()
        self.query("UPDATE pedidos SET solicita_factura=FALSE WHERE id_pedido=%s RETURNING id_pedido",(self.order,))
        self.assertEqual(self.cancel().status_code,302)
        self.assertEqual(self.query("SELECT estado FROM pedidos WHERE id_pedido=%s",(self.order,)),[("Cancelado",)])
        html=self.client.get("/mis-pedidos",query_string={"q":str(self.order)}).get_data(as_text=True)
        self.assertIn("Cancelado",html)
        self.assertNotIn(f'/mis-pedidos/{self.order}/editar',html)
        self.assertNotIn("Solicitar factura",html)
        self.client.post(f"/mis-pedidos/{self.order}/solicitar-factura")
        self.assertEqual(self.query("SELECT solicita_factura FROM pedidos WHERE id_pedido=%s",(self.order,)),[(False,)])
        rows=self.query("""SELECT datos_anteriores->>'estado',datos_nuevos->>'estado'
                          FROM auditoria WHERE tabla='pedidos' AND id_registro=%s AND operacion='UPDATE'""",(str(self.order),))
        self.assertIn(("Solicitado","Cancelado"),rows)

    def test_todos_los_estados_bloqueados_backend(self):
        self.prepare()
        for state in ("En revisión","En reparación","Listo","Entregado","Cancelado"):
            with self.subTest(state=state):
                self.query("UPDATE pedidos SET estado=%s WHERE id_pedido=%s RETURNING id_pedido",(state,self.order))
                for response in (self.client.get(f"/mis-pedidos/{self.order}/editar"),self.edit(),self.cancel()):
                    self.assertEqual(response.status_code,302)
                self.assertEqual(self.query("SELECT estado,equipo FROM pedidos WHERE id_pedido=%s",(self.order,)),[(state,"Laptop")])
                with self.client.session_transaction() as session:
                    self.assertIn(("warning",web.MENSAJE_PEDIDO_BLOQUEADO),session["_flashes"])

    def test_propiedad_y_csrf(self):
        self.prepare()
        self.query("UPDATE pedidos SET id_usuario=%s WHERE id_pedido=%s RETURNING id_pedido",(self.admin,self.order))
        self.assertEqual(self.edit().status_code,404)
        self.assertEqual(self.cancel().status_code,404)
        self.assertEqual(self.client.get(f"/mis-pedidos/{self.order}/editar").status_code,404)
        self.query("UPDATE pedidos SET id_usuario=%s WHERE id_pedido=%s RETURNING id_pedido",(self.customer,self.order))
        web.app.config["WTF_CSRF_ENABLED"]=True
        self.assertEqual(self.cancel().status_code,400)
        self.assertEqual(self.edit().status_code,200)
        self.assertEqual(self.query("SELECT estado,equipo FROM pedidos WHERE id_pedido=%s",(self.order,)),[("Solicitado","Laptop")])

    def test_facturado_aunque_solicitado_no_modificable(self):
        self.emit()
        self.prepare()
        self.assertEqual(self.edit().status_code,302)
        self.assertEqual(self.cancel().status_code,302)
        self.assertEqual(self.query("SELECT estado,equipo FROM pedidos WHERE id_pedido=%s",(self.order,)),[("Solicitado","Laptop")])

    def test_busqueda_servicios_activos_y_proveedor(self):
        self.login(self.customer)
        self.query("""INSERT INTO proveedores (id_proveedor,empresa,contacto,telefono,categoria)
                      VALUES (-876543,'Proveedor búsqueda única','Ana','0991234567','Prueba') RETURNING id_proveedor""")
        self.query("UPDATE servicios SET id_proveedor=-876543 WHERE id_servicio=%s RETURNING id_servicio",(self.service,))
        for value in ("Servicio original prueba","Prueba transaccional","Proveedor búsqueda única","1 hora"):
            html=self.client.get("/servicios",query_string={"q":value}).get_data(as_text=True)
            self.assertIn("Servicio original prueba",html)
            self.assertIn('name="q"',html)
        self.query("UPDATE servicios SET activo=FALSE WHERE id_servicio=%s RETURNING id_servicio",(self.service,))
        html=self.client.get("/servicios",query_string={"q":"Proveedor búsqueda única"}).get_data(as_text=True)
        self.assertNotIn("Servicio original prueba",html)
        self.assertIn("No se encontraron resultados para esta búsqueda.",html)

    def test_busqueda_pedidos_propiedad_cancelados_e_historicos(self):
        self.prepare()
        self.query("UPDATE servicios SET activo=FALSE WHERE id_servicio=%s RETURNING id_servicio",(self.service,))
        for value in (str(self.order),"Servicio original prueba","Laptop","Prueba","Solicitado"):
            html=self.client.get("/mis-pedidos",query_string={"q":value}).get_data(as_text=True)
            self.assertIn(f"#{self.order}",html)
            self.assertIn("Servicio original prueba",html)
        self.cancel()
        self.assertIn(f"#{self.order}",self.client.get("/mis-pedidos?q=Cancelado").get_data(as_text=True))
        self.query("UPDATE pedidos SET id_usuario=%s WHERE id_pedido=%s RETURNING id_pedido",(self.admin,self.order))
        for value in (str(self.order),"Servicio original prueba","Laptop","Cancelado","%"):
            self.assertNotIn(f"#{self.order}",self.client.get("/mis-pedidos",query_string={"q":value}).get_data(as_text=True))

    def test_busqueda_facturas_historicas_y_propiedad(self):
        self.emit()
        numero=self.query("SELECT numero FROM facturas WHERE id_pedido=%s",(self.order,))[0][0]
        self.query("UPDATE servicios SET activo=FALSE,nombre='Nombre posterior' WHERE id_servicio=%s RETURNING id_servicio",(self.service,))
        self.login(self.customer)
        for value in (numero,"Servicio original prueba","Pendiente","Laptop",str(self.order)):
            html=self.client.get("/mis-facturas",query_string={"q":value}).get_data(as_text=True)
            self.assertIn(numero,html)
            self.assertIn("Servicio original prueba",html)
        self.query("UPDATE facturas SET id_usuario=%s WHERE id_pedido=%s RETURNING id_factura",(self.admin,self.order))
        for value in (numero,"Servicio original prueba","Pendiente",str(self.order),"%"):
            self.assertNotIn(f">{numero}</td>",self.client.get("/mis-facturas",query_string={"q":value}).get_data(as_text=True))

    def test_busquedas_parametrizadas_sin_resultados(self):
        self.login(self.customer)
        for route in ("/servicios","/mis-pedidos","/mis-facturas"):
            response=self.client.get(route,query_string={"q":"' OR 1=1 --"})
            self.assertEqual(response.status_code,200)
            self.assertIn("No se encontraron resultados para esta búsqueda.",response.get_data(as_text=True))

if __name__ == "__main__":
    unittest.main()
