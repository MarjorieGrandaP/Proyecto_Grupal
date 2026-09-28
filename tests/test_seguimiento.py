"""Estados, actor y seguimiento con datos transaccionales revertidos."""
from pagos_utils import confirmar_pago
import unittest
from pathlib import Path
from unittest.mock import patch
import test_facturacion_pedidos as base
from test_correcciones import web


class Seguimiento(unittest.TestCase):
    query = base.FacturacionPedidos.query
    login = base.FacturacionPedidos.login
    emit = base.FacturacionPedidos.emit
    invoices = base.FacturacionPedidos.invoices
    tearDown = base.FacturacionPedidos.tearDown

    def setUp(self):
        base.FacturacionPedidos.setUp(self)

    def change(self, state):
        return self.client.post(f"/pedidos/{self.order}/estado",data={"estado":state})

    def count_history(self):
        return self.query("SELECT count(*) FROM historial_estado_pedidos WHERE id_pedido=%s",(self.order,))[0][0]

    def test_cada_transicion_permitida_historial_auditoria_actor(self):
        for previous,following in (
            ("Solicitado","En revisión"),("En revisión","En reparación"),
            ("En reparación","Listo"),("Listo","Entregado"),
        ):
            with self.subTest(previous=previous,following=following):
                self.query("UPDATE pedidos SET estado=%s WHERE id_pedido=%s RETURNING id_pedido",(previous,self.order))
                if following in ('En reparación','Entregado'):
                    confirmar_pago(self)
                if following == 'Entregado':
                    confirmar_pago(self,'saldo')
                before=self.count_history()
                self.assertEqual(self.change(following).status_code,302)
                self.assertEqual(self.query("SELECT estado FROM pedidos WHERE id_pedido=%s",(self.order,)),[(following,)])
                self.assertEqual(self.count_history(),before+1)
                last=self.query("""SELECT estado_anterior,estado_nuevo,id_usuario_actor
                                   FROM historial_estado_pedidos WHERE id_pedido=%s
                                   ORDER BY id_historial DESC LIMIT 1""",(self.order,))[0]
                self.assertEqual(last,(previous,following,self.admin))
                audit=self.query("""SELECT datos_anteriores->>'estado',datos_nuevos->>'estado'
                                    FROM auditoria WHERE tabla='pedidos' AND id_registro=%s
                                    AND operacion='UPDATE' ORDER BY id_auditoria DESC LIMIT 1""",(str(self.order),))[0]
                self.assertEqual(audit,(previous,following))

    def test_retrocesos_terminales_saltos_sin_update(self):
        pairs=[("En reparación","Solicitado"),("Listo","En revisión"),
               ("Entregado","En reparación"),("Entregado","Solicitado"),
               ("Solicitado","Entregado"),("Solicitado","Cancelado")]
        pairs += [("Cancelado",s) for s in ("Solicitado","En revisión","En reparación","Listo","Entregado")]
        for previous,following in pairs:
            with self.subTest(previous=previous,following=following):
                self.query("UPDATE pedidos SET estado=%s WHERE id_pedido=%s RETURNING id_pedido",(previous,self.order))
                before=self.count_history()
                audit_before=self.query("SELECT count(*) FROM auditoria")
                self.change(following)
                self.assertEqual(self.query("SELECT estado FROM pedidos WHERE id_pedido=%s",(self.order,)),[(previous,)])
                self.assertEqual(self.count_history(),before)
                self.assertEqual(self.query("SELECT count(*) FROM auditoria"),audit_before)
                with self.client.session_transaction() as session:
                    self.assertIn(("warning","No se puede regresar a un estado anterior del pedido."),session["_flashes"])

    def test_mismo_estado_y_cambio_equipo_no_duplican_historial(self):
        before=self.count_history()
        self.change("Entregado")
        self.query("UPDATE pedidos SET equipo='Otro equipo' WHERE id_pedido=%s RETURNING id_pedido",(self.order,))
        self.assertEqual(self.count_history(),before)

    def test_facturado_no_retrocede(self):
        self.emit()
        before=self.count_history()
        self.change("En reparación")
        self.assertEqual(self.count_history(),before)
        self.assertEqual(self.query("SELECT estado FROM pedidos WHERE id_pedido=%s",(self.order,)),[("Entregado",)])

    def test_estado_inicial_por_ruta_cliente(self):
        self.login(self.customer)
        r=self.client.post("/pedido/nuevo",data={"servicio":str(self.service),"equipo":"Equipo nuevo seguimiento","descripcion":"Prueba de creación","acepta_terminos":"y"})
        self.assertEqual(r.status_code,302)
        row=self.query("""SELECT h.estado_anterior,h.estado_nuevo,h.id_usuario_actor
                          FROM historial_estado_pedidos h JOIN pedidos p ON p.id_pedido=h.id_pedido
                          WHERE p.equipo='Equipo nuevo seguimiento'""")
        self.assertEqual(row,[(None,"Solicitado",self.customer)])

    def test_cancelacion_cliente_terminal_y_actor(self):
        self.query("UPDATE pedidos SET estado='Solicitado' WHERE id_pedido=%s RETURNING id_pedido",(self.order,))
        self.login(self.customer)
        r=self.client.post(f"/mis-pedidos/{self.order}/cancelar",data={"motivo":"Ya no necesito el servicio"})
        self.assertEqual(r.status_code,302)
        row=self.query("""SELECT estado_anterior,estado_nuevo,id_usuario_actor FROM historial_estado_pedidos
                          WHERE id_pedido=%s ORDER BY id_historial DESC LIMIT 1""",(self.order,))[0]
        self.assertEqual(row,("Solicitado","Cancelado",self.customer))
        self.assertIn("Cancelado",self.client.get(f"/mis-pedidos/{self.order}/seguimiento").get_data(as_text=True))
        self.login(self.admin)
        self.change("Solicitado")
        self.assertEqual(self.query("SELECT estado FROM pedidos WHERE id_pedido=%s",(self.order,)),[("Cancelado",)])

    def test_seguimiento_propiedad(self):
        self.login(self.customer)
        self.assertEqual(self.client.get(f"/mis-pedidos/{self.order}/seguimiento").status_code,200)
        self.query("UPDATE pedidos SET id_usuario=%s WHERE id_pedido=%s RETURNING id_pedido",(self.admin,self.order))
        self.assertEqual(self.client.get(f"/mis-pedidos/{self.order}/seguimiento").status_code,404)

    def test_mensajes_alerta_fisico_remoto_independientes_busqueda(self):
        self.query("UPDATE pedidos SET estado='Listo' WHERE id_pedido=%s RETURNING id_pedido",(self.order,))
        self.login(self.customer)
        for physical,text in ((True,"Tu equipo está listo para ser retirado."),(False,"El servicio ha sido completado exitosamente.")):
            self.query("UPDATE servicios SET requiere_entrega_equipo=%s WHERE id_servicio=%s RETURNING id_servicio",(physical,self.service))
            html=self.client.get("/mis-pedidos?q=sincoincidencias").get_data(as_text=True)
            self.assertIn(text,html)
        html=self.client.get(f"/mis-pedidos/{self.order}/seguimiento").get_data(as_text=True)
        self.assertIn("El servicio ha sido completado exitosamente.",html)

    def test_selector_y_modalidad(self):
        from html.parser import HTMLParser
        class Options(HTMLParser):
            active=False
            values=None
            def handle_starttag(parser,tag,attrs):
                attrs=dict(attrs)
                if tag=="form":
                    parser.active=attrs.get("action")==f"/pedidos/{self.order}/estado"
                    if parser.active: parser.values=[]
                if tag=="option" and parser.active:
                    parser.values.append(attrs["value"])
            def handle_endtag(parser,tag):
                if tag=="form": parser.active=False
        for state,next_states in web.TRANSICIONES_PEDIDO.items():
            self.query("UPDATE pedidos SET estado=%s WHERE id_pedido=%s RETURNING id_pedido",(state,self.order))
            parser=Options()
            parser.feed(self.client.get("/pedidos").get_data(as_text=True))
            self.assertEqual(parser.values,[state] if state in ("En revisión","Listo") else [state,*next_states] if next_states else None)
        self.assertIn("requiere_entrega_equipo",self.client.get("/servicios/nuevo").get_data(as_text=True))

    def test_migracion_reejecutable_preserva_historial(self):
        before=self.query("SELECT count(*) FROM historial_estado_pedidos")
        with self.conn.cursor() as cursor:
            sql=Path("sql/migracion_seguimiento_pedidos.sql").read_text(encoding="utf-8")
            cursor.execute(sql)
            cursor.execute(sql)
        self.assertEqual(self.query("SELECT count(*) FROM historial_estado_pedidos"),before)

if __name__=="__main__":
    unittest.main()
