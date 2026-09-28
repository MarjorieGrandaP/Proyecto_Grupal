"""Cancelación motivada, anticipo y modales; pruebas PostgreSQL con rollback."""
import unittest
from pathlib import Path
from unittest.mock import patch
import test_facturacion_pedidos as base
from test_correcciones import web


class CancelacionAnticipo(unittest.TestCase):
    query = base.FacturacionPedidos.query
    login = base.FacturacionPedidos.login
    emit = base.FacturacionPedidos.emit
    invoices = base.FacturacionPedidos.invoices
    tearDown = base.FacturacionPedidos.tearDown

    def setUp(self):
        base.FacturacionPedidos.setUp(self)
        self.query("""UPDATE pedidos SET estado='Solicitado',fecha_solicitud=clock_timestamp()::timestamp
                      WHERE id_pedido=%s RETURNING id_pedido""",(self.order,))

    def cancel(self, admin=False, data=None):
        prefix="/pedidos" if admin else "/mis-pedidos"
        return self.client.post(f"{prefix}/{self.order}/cancelar",data=data or {})

    def state(self):
        return self.query("SELECT estado FROM pedidos WHERE id_pedido=%s",(self.order,))[0][0]

    def test_cancelacion_cliente_motivo_observacion_actor_y_auditoria(self):
        self.login(self.customer)
        r=self.cancel(data={"motivo":"Otro","observacion":"Necesito corregir el equipo"})
        self.assertEqual(r.status_code,302)
        row=self.query("""SELECT estado,motivo_cancelacion,observacion,cancelado_por,fecha_cancelacion IS NOT NULL
                          FROM pedidos WHERE id_pedido=%s""",(self.order,))[0]
        self.assertEqual(row,("Cancelado","Otro","Necesito corregir el equipo",self.customer,True))
        history=self.query("""SELECT estado_anterior,estado_nuevo,motivo_cancelacion,observacion,id_usuario_actor
                              FROM historial_estado_pedidos WHERE id_pedido=%s
                              ORDER BY id_historial DESC LIMIT 1""",(self.order,))[0]
        self.assertEqual(history,("Solicitado","Cancelado","Otro","Necesito corregir el equipo",self.customer))
        audit=self.query("""SELECT datos_nuevos->>'motivo_cancelacion' FROM auditoria
                            WHERE tabla='pedidos' AND id_registro=%s AND operacion='UPDATE'
                            ORDER BY id_auditoria DESC LIMIT 1""",(str(self.order),))[0][0]
        self.assertEqual(audit,"Otro")

    def test_motivo_obligatorio_y_otro_vacio_ambos_roles(self):
        for admin,user in ((False,self.customer),(True,self.admin)):
            self.login(user)
            for data in ({},{"motivo":"Otro"},{"motivo":"Otro","observacion":"   "},{"motivo":"Inventado"}):
                with self.subTest(admin=admin,data=data):
                    self.assertEqual(self.cancel(admin,data).status_code,400)
                    self.assertEqual(self.state(),"Solicitado")
        self.login(self.customer)
        self.assertEqual(self.cancel(data={"motivo":"Falta de anticipo"}).status_code,400)

    def test_ventana_cliente_y_limites(self):
        self.login(self.customer)
        for age,allowed in ((301,False),(-60,False),(299,True)):
            self.query("""UPDATE pedidos SET fecha_solicitud=clock_timestamp()::timestamp - (%s * INTERVAL '1 second')
                          WHERE id_pedido=%s RETURNING id_pedido""",(age,self.order))
            r=self.cancel(data={"motivo":"Ya no necesito el servicio"})
            self.assertEqual(r.status_code,302)
            self.assertEqual(self.state(),"Cancelado" if allowed else "Solicitado")

    def test_admin_cancela_fuera_ventana_y_cliente_no_puede(self):
        self.query("""UPDATE pedidos SET estado='En revisión',fecha_solicitud=CURRENT_TIMESTAMP - INTERVAL '2 days'
                      WHERE id_pedido=%s RETURNING id_pedido""",(self.order,))
        self.login(self.customer)
        self.assertEqual(self.cancel(True,{"motivo":"Cliente no respondió"}).status_code,403)
        self.cancel(data={"motivo":"Ya no necesito el servicio"})
        self.assertEqual(self.state(),"En revisión")
        self.login(self.admin)
        self.assertEqual(self.cancel(True,{"motivo":"Cliente no respondió","observacion":"Se intentó contactar al cliente."}).status_code,302)
        self.assertEqual(self.state(),"Cancelado")
        self.assertEqual(self.query("SELECT cancelado_por FROM pedidos WHERE id_pedido=%s",(self.order,))[0][0],self.admin)

    def test_factura_y_terminales_bloquean_cancelacion(self):
        self.query("UPDATE pedidos SET estado='Entregado' WHERE id_pedido=%s RETURNING id_pedido",(self.order,))
        self.emit()
        self.query("UPDATE pedidos SET estado='Solicitado' WHERE id_pedido=%s RETURNING id_pedido",(self.order,))
        for admin,user,motivo in ((True,self.admin,"Solicitud duplicada"),(False,self.customer,"Ya no necesito el servicio")):
            self.login(user)
            self.cancel(admin,{"motivo":motivo})
            self.assertEqual(self.state(),"Solicitado")
        self.login(self.admin)
        for state in ("Entregado","Cancelado"):
            self.query("UPDATE pedidos SET estado=%s WHERE id_pedido=%s RETURNING id_pedido",(state,self.order))
            self.cancel(True,{"motivo":"Falta de anticipo"})
            self.assertEqual(self.state(),state)

    def test_anticipo_obligatorio_y_confirmacion_sin_retroceso(self):
        def change(state):
            return self.client.post(f"/pedidos/{self.order}/estado",data={"estado":state})
        change("En revisión")
        self.assertEqual(self.state(),"Solicitado")
        change("Pendiente de anticipo")
        self.assertEqual(self.state(),"Pendiente de anticipo")
        change("En revisión")
        self.assertEqual(self.state(),"Pendiente de anticipo")
        self.assertEqual(self.query("SELECT anticipo_solicitado,anticipo_pagado FROM pedidos WHERE id_pedido=%s",(self.order,)),[(True,False)])
        self.client.post(f"/pedidos/{self.order}/anticipo",data={"solicitado":"y","pagado":"y"})
        self.assertEqual(self.query("SELECT anticipo_pagado FROM pedidos WHERE id_pedido=%s",(self.order,)),[(True,)])
        self.client.post(f"/pedidos/{self.order}/anticipo",data={"solicitado":"y"})
        self.assertEqual(self.query("SELECT anticipo_pagado FROM pedidos WHERE id_pedido=%s",(self.order,)),[(True,)])
        change("En revisión")
        self.assertEqual(self.state(),"En revisión")
        change("Pendiente de anticipo")
        self.assertEqual(self.state(),"En revisión")

    def test_anticipo_permisos_y_csrf(self):
        self.login(self.customer)
        self.assertEqual(self.client.post(f"/pedidos/{self.order}/anticipo",data={"solicitado":"y","pagado":"y"}).status_code,403)
        self.login(self.admin)
        self.assertEqual(self.client.post(f"/pedidos/{self.order}/anticipo",data={"pagado":"y"}).status_code,400)
        web.app.config["WTF_CSRF_ENABLED"]=True
        self.assertEqual(self.cancel(True,{"motivo":"Falta de anticipo"}).status_code,400)
        self.assertEqual(self.client.post(f"/pedidos/{self.order}/anticipo",data={"solicitado":"y"}).status_code,400)

    def test_modal_historial_actor_motivo_escape_y_propiedad(self):
        self.login(self.customer)
        self.cancel(data={"motivo":"Otro","observacion":"<script>alert(1)</script>"})
        for user in (self.customer,self.admin):
            self.login(user)
            response=self.client.get(f"/pedidos/{self.order}/seguimiento?modal=1")
            self.assertEqual(response.status_code,200)
            html=response.get_data(as_text=True)
            self.assertNotIn("<!DOCTYPE",html)
            if user == self.admin:
                self.assertIn("Realizado por:",html)
                self.assertIn("Otro",html)
                self.assertIn("&lt;script&gt;",html)
            else:
                self.assertNotIn("Realizado por:",html)
                self.assertNotIn("Otro",html)
                self.assertNotIn("&lt;script&gt;",html)
            self.assertNotIn("<script>",html)
        self.login(self.customer)
        self.query("UPDATE pedidos SET id_usuario=%s WHERE id_pedido=%s RETURNING id_pedido",(self.admin,self.order))
        self.assertEqual(self.client.get(f"/pedidos/{self.order}/seguimiento?modal=1").status_code,404)
        for route,user in (("/pedidos",self.admin),("/mis-pedidos",self.customer)):
            self.login(user)
            self.assertIn('id="modalSeguimiento"',self.client.get(route).get_data(as_text=True))

    def test_terminos_obligatorios_y_fecha_aceptacion(self):
        self.login(self.customer)
        data={"servicio":str(self.service),"equipo":"Equipo con términos","descripcion":"Prueba de aceptación"}
        self.assertEqual(self.client.post("/pedido/nuevo",data=data).status_code,200)
        self.assertEqual(self.query("SELECT count(*) FROM pedidos WHERE equipo=%s",(data["equipo"],)),[(0,)])
        data["acepta_terminos"]="y"
        self.assertEqual(self.client.post("/pedido/nuevo",data=data).status_code,302)
        self.assertEqual(self.query("SELECT terminos_aceptados,fecha_aceptacion_terminos IS NOT NULL FROM pedidos WHERE equipo=%s",(data["equipo"],)),[(True,True)])
        for route in ("/terminos","/garantia"):
            self.assertEqual(self.client.get(route).status_code,200)

    def test_reparacion_inconsistencia_registra_y_no_toca_factura(self):
        self.query("UPDATE pedidos SET estado='Entregado' WHERE id_pedido=%s RETURNING id_pedido",(self.order,))
        self.emit()
        factura=self.query("SELECT to_jsonb(f) FROM facturas f WHERE id_pedido=%s",(self.order,))
        self.query("UPDATE pedidos SET estado='Cancelado' WHERE id_pedido=%s RETURNING id_pedido",(self.order,))
        sql=Path("sql/migracion_cancelacion_anticipo.sql").read_text(encoding="utf-8")
        with self.conn.cursor() as cursor: cursor.execute(sql)
        self.assertEqual(self.state(),"Entregado")
        self.assertEqual(self.query("SELECT to_jsonb(f) FROM facturas f WHERE id_pedido=%s",(self.order,)),factura)
        h=self.query("""SELECT estado_anterior,estado_nuevo,observacion FROM historial_estado_pedidos
                        WHERE id_pedido=%s ORDER BY id_historial DESC LIMIT 1""",(self.order,))[0]
        self.assertEqual(h[:2],("Cancelado","Entregado"))
        self.assertIn("Corrección de consistencia",h[2])
        audit=self.query("""SELECT datos_anteriores->>'estado',datos_nuevos->>'estado' FROM auditoria
                            WHERE tabla='pedidos' AND id_registro=%s ORDER BY id_auditoria DESC LIMIT 1""",(str(self.order),))[0]
        self.assertEqual(audit,("Cancelado","Entregado"))
        count=self.query("SELECT count(*) FROM historial_estado_pedidos WHERE id_pedido=%s",(self.order,))
        with self.conn.cursor() as cursor: cursor.execute(sql)
        self.assertEqual(self.query("SELECT count(*) FROM historial_estado_pedidos WHERE id_pedido=%s",(self.order,)),count)

if __name__=="__main__":
    unittest.main()
